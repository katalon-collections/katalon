from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from lxml import etree

from .base import Selector, SourceFormat, SourceRecord

# Matches a single Clark-notation tag {ns}local or a bare name (no { or /)
_CLARK_TAG_RE = re.compile(r"\{[^}]+\}[^{/]+|[^{/]+")


def _clark_to_label(tag: str, nsmap: dict[str, Any]) -> str:
    """Convert Clark-notation {ns}local to prefix:local using doc nsmap."""
    if not tag.startswith("{"):
        return tag
    ns, local = tag[1:].split("}", 1)
    for prefix, uri in nsmap.items():
        if uri == ns:
            return f"{prefix}:{local}" if prefix else local
    # Fallback: last meaningful segment of the namespace URI
    short = ns.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return f"{short}:{local}"


def _rel_tag_path(child: etree._Element, elem: etree._Element) -> str:
    """Build Clark-notation tag path from child to elem (no position predicates)."""
    parts: list[str] = []
    current: etree._Element | None = elem
    while current is not None and current is not child:
        parts.append(current.tag)
        current = current.getparent()
    parts.reverse()
    return "/".join(parts)


def _tag_path_to_label(path: str, nsmap: dict[str, Any]) -> str:
    """Convert a /‑joined Clark-notation path to a human-readable label.

    Splits by Clark tags rather than raw '/' so namespace URIs are not broken.
    """
    parts = _CLARK_TAG_RE.findall(path)
    return "/".join(_clark_to_label(p, nsmap) for p in parts)


class XmlFormat(SourceFormat):
    """Generic XML import handler using lxml."""

    max_depth = 64

    def _parse_root(self, content: bytes) -> etree._Element:
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            huge_tree=False,
            recover=False,
        )
        root = etree.fromstring(content, parser=parser)
        for elem in root.iter():
            if sum(1 for _ in elem.iterancestors()) > self.max_depth:
                raise ValueError(f"XML ist zu tief verschachtelt (max {self.max_depth} Ebenen)")
        return root

    def sniff(self, content: bytes, filename: str) -> bool:
        if filename.lower().endswith(".xml"):
            return True
        stripped = content.lstrip()
        return stripped.startswith(b"<?xml") or (stripped.startswith(b"<") and not stripped.startswith(b"<!"))

    # ------------------------------------------------------------------
    # XML-specific: not part of SourceFormat ABC
    # ------------------------------------------------------------------

    def list_element_levels(self, content: bytes, max_depth: int = 5) -> list[dict[str, Any]]:
        """Return distinct element tags at each depth level.

        Used by the frontend to let the user choose which element = one record.
        Returns list of {depth, tags: [{label, clark_tag}]}.
        """
        root = self._parse_root(content)
        levels: dict[int, dict[str, str]] = {}  # depth -> {clark_tag: label}
        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue  # skip PIs / comments
            depth = sum(1 for _ in elem.iterancestors())
            if depth > max_depth:
                continue
            clark = elem.tag
            # Use the element's own (inherited) nsmap, not the document root's:
            # in a multi-file XML batch, each original file's root re-declares
            # its own namespace prefixes that the synthetic wrapper root doesn't see.
            label = _clark_to_label(clark, elem.nsmap)
            levels.setdefault(depth, {})[clark] = label
        return [
            {
                "depth": d,
                "tags": [{"clark_tag": ct, "label": lbl} for ct, lbl in sorted(tags.items(), key=lambda x: x[1])],
            }
            for d, tags in sorted(levels.items())
        ]

    def parse_flat(self, content: bytes, record_xpath: str = "*") -> Iterator[SourceRecord]:
        """Like parse() but strips __tree__ — safe for JSON serialisation."""
        for record in self.parse(content, record_xpath):
            yield {k: v for k, v in record.items() if k != "__tree__"}

    # ------------------------------------------------------------------
    # SourceFormat ABC
    # ------------------------------------------------------------------

    def parse(self, content: bytes, record_xpath: str = "*") -> Iterator[SourceRecord]:
        """Parse XML and yield one SourceRecord per matched element.

        record_xpath: Clark-notation tag like "{http://...}mods", or "*" for
        direct root children.

        Element attributes are exposed as separate selectors under
        "<tag-path>@<attr-label>". A tag path or attribute that occurs more
        than once within a record is collected as a list (order preserved);
        single occurrences stay plain strings for backward compatibility.
        """
        root = self._parse_root(content)
        if record_xpath == "*":
            elements = list(root)
        else:
            elements = [e for e in root.iter(record_xpath) if isinstance(e.tag, str)]

        for child in elements:
            values: dict[str, list[str]] = {}
            for elem in child.iter():
                if not isinstance(elem.tag, str):
                    continue
                path = _rel_tag_path(child, elem)
                if elem.text and elem.text.strip() and path:
                    values.setdefault(path, []).append(elem.text.strip())
                for attr_name, attr_val in elem.attrib.items():
                    if not attr_val or not attr_val.strip():
                        continue
                    # elem.nsmap (not root.nsmap): see list_element_levels for why.
                    alabel = _clark_to_label(attr_name, elem.nsmap)
                    apath = f"{path}@{alabel}" if path else f"@{alabel}"
                    values.setdefault(apath, []).append(attr_val.strip())

            record: SourceRecord = {"__tree__": child}
            for path, vals in values.items():
                record[path] = vals[0] if len(vals) == 1 else vals
            yield record

    def list_selectors(self, content: bytes, record_xpath: str = "*", sample_size: int = 50) -> list[Selector]:
        """List all distinct tag paths (and attribute paths) across the first sample_size records.

        kind is "list" for a path that repeats within at least one sampled record,
        "scalar" otherwise.
        """
        root = self._parse_root(content)

        if record_xpath == "*":
            elements = list(root)[:sample_size]
        else:
            elements = [e for e in root.iter(record_xpath) if isinstance(e.tag, str)][:sample_size]

        path_samples: dict[str, list[str]] = {}
        path_labels: dict[str, str] = {}
        path_repeats: set[str] = set()
        for child in elements:
            occurrences: dict[str, int] = {}
            for elem in child.iter():
                if not isinstance(elem.tag, str):
                    continue
                path = _rel_tag_path(child, elem)
                if not path:
                    continue
                # elem.nsmap (not root.nsmap): see list_element_levels for why.
                nsmap = elem.nsmap
                entries: list[tuple[str, str, str]] = []
                if elem.text and elem.text.strip():
                    entries.append((path, _tag_path_to_label(path, nsmap), elem.text.strip()))
                for attr_name, attr_val in elem.attrib.items():
                    if not attr_val or not attr_val.strip():
                        continue
                    alabel = _clark_to_label(attr_name, nsmap)
                    entries.append((f"{path}@{alabel}", f"{_tag_path_to_label(path, nsmap)}@{alabel}", attr_val.strip()))
                for p, label, sample in entries:
                    occurrences[p] = occurrences.get(p, 0) + 1
                    if occurrences[p] > 1:
                        path_repeats.add(p)
                    path_labels.setdefault(p, label)
                    path_samples.setdefault(p, [])
                    if len(path_samples[p]) < 3:
                        path_samples[p].append(sample)

        return [
            Selector(
                path=p,
                label=path_labels.get(p, p),
                sample=", ".join(samples),
                kind="list" if p in path_repeats else "scalar",
            )
            for p, samples in sorted(path_samples.items())
        ]
