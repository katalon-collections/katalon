# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Portal facet catalog: which facets exist per record type, of which kind,
and which index fields they filter and aggregate on.

Facet names (as listed in the portal config's ``facet_fields``):

``<field>``               a top-level field (kind from its field type/settings)
``<group>__<child>``      a sub-field of a group field
``inherited_<t>_<f>``     an inherited relation field (stored in portal config)
``related_*``             all relations to a target type (stored in portal config)
``relfacet_<key>``        a configured relation facet (PortalConfig.relation_facets)

All derived index fields live under ``facet_*`` and are therefore keyword-mapped
by the existing dynamic template — no mapping change needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.integrations.elasticsearch import RELATED_FACET_NAMES

GROUP_SEPARATOR = "__"
RELATION_FACET_PREFIX = "relfacet_"
DATE_GRANULARITIES = ("decade", "century", "year")
SORTABLE_FACET_KINDS = ("terms", "inherited", "related", "relation")
RELATION_TARGET_TYPES = ("entity", "place", "occurrence", "collection", "object")
RELATION_DIRECTIONS = ("outgoing", "incoming", "both")
_KEY_RE = re.compile(r"^[a-z0-9_]{1,48}$")


@dataclass
class FacetSpec:
    name: str
    kind: str  # terms | numeric | boolean | date | tree | inherited | related | relation
    filter_field: str
    agg_field: str
    label: dict[str, str] | None = None
    granularity: str | None = None
    vocabulary_id: str | None = None
    sort: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """Shape exposed in the portal config (``facet_kinds``)."""
        out: dict[str, Any] = {"kind": self.kind}
        if self.label:
            out["label"] = self.label
        if self.granularity:
            out["granularity"] = self.granularity
        if self.sort:
            out["sort"] = self.sort
        return out


def valid_relation_facet_key(key: str) -> bool:
    return bool(_KEY_RE.match(key))


def _field_spec(name: str, field_type: str, settings: dict[str, Any], hierarchical: set[str]) -> FacetSpec:
    if field_type == "number":
        return FacetSpec(name, "numeric", f"facet_all_{name}", f"facet_all_{name}")
    if field_type == "boolean":
        return FacetSpec(name, "boolean", f"facet_all_{name}", f"facet_all_{name}")
    granularity = settings.get("facet_granularity")
    if field_type == "date" and granularity in DATE_GRANULARITIES:
        return FacetSpec(
            name, "date", f"facet_date_{name}", f"facet_date_{name}", granularity=granularity
        )
    vocabulary_id = str(settings.get("vocabulary_id") or "")
    if field_type == "vocab" and vocabulary_id in hierarchical:
        return FacetSpec(
            name, "tree", f"facet_path_{name}", f"facet_path_{name}", vocabulary_id=vocabulary_id
        )
    return FacetSpec(name, "terms", f"facet_all_{name}", f"facet_all_{name}")


async def hierarchical_vocabulary_ids(db: AsyncSession) -> set[str]:
    from katalon.core.models import Vocabulary

    rows = await db.execute(select(Vocabulary.id).where(Vocabulary.is_hierarchical.is_(True)))
    return {str(row[0]) for row in rows.all()}


async def field_facet_specs(
    db: AsyncSession, target_types: tuple[str, ...] | list[str], *, facets_only: bool = True
) -> dict[str, dict[str, FacetSpec]]:
    """Field-based facets per type (top-level and group sub-fields), in schema
    order. With ``facets_only=False`` every public field is described (used by
    the index builder, which derives facet fields for all public fields)."""
    from katalon.core.models import FieldDefinition

    query = (
        select(FieldDefinition)
        .where(
            FieldDefinition.target_type.in_(list(target_types)),
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.is_public.is_(True),
        )
        .order_by(FieldDefinition.sort_order, FieldDefinition.name)
    )
    fields = list((await db.execute(query)).scalars().all())
    by_id = {f.id: f for f in fields}
    hierarchical = await hierarchical_vocabulary_ids(db)
    out: dict[str, dict[str, FacetSpec]] = {t: {} for t in target_types}
    # Parents first so group sub-facets follow the group's schema position.
    ordered = sorted(
        fields,
        key=lambda f: (
            (by_id[f.parent_id].sort_order, by_id[f.parent_id].name, 1, f.sort_order, f.name)
            if f.parent_id in by_id
            else (f.sort_order, f.name, 0, 0, "")
        ),
    )
    for f in ordered:
        if facets_only and not f.is_facet:
            continue
        if f.field_type == "group":
            continue
        if f.parent_id is not None:
            parent = by_id.get(f.parent_id)
            if parent is None:
                continue
            name = f"{parent.name}{GROUP_SEPARATOR}{f.name}"
        else:
            name = f.name
        spec = _field_spec(name, f.field_type, f.settings or {}, hierarchical)
        spec.extra["field_type"] = f.field_type
        if f.parent_id is not None:
            spec.extra["group"] = by_id[f.parent_id].name
            spec.extra["child"] = f.name
            # The portal knows field labels by name only; give sub-field facets
            # their own label.
            spec.label = f.label or {}
        out.setdefault(f.target_type, {})[name] = spec
    return out


def relation_facet_specs(relation_facets: dict[str, Any] | None) -> dict[str, dict[str, FacetSpec]]:
    out: dict[str, dict[str, FacetSpec]] = {}
    for record_type, entries in (relation_facets or {}).items():
        for entry in entries or []:
            key = entry.get("key", "")
            if not valid_relation_facet_key(key):
                continue
            name = f"{RELATION_FACET_PREFIX}{key}"
            out.setdefault(record_type, {})[name] = FacetSpec(
                name,
                "relation",
                f"facet_relid_{key}",
                f"facet_rel_{key}",
                label=entry.get("label") or {},
                extra=dict(entry),
            )
    return out


def special_spec(name: str) -> FacetSpec | None:
    if name in RELATED_FACET_NAMES:
        return FacetSpec(name, "related", name, name)
    if name.startswith("inherited_"):
        return FacetSpec(name, "inherited", f"facet_{name}", f"facet_{name}")
    return None


def apply_order(names: list[str], order: list[str] | None) -> list[str]:
    """Configured order first, remaining names in their default order."""
    if not order:
        return names
    present = set(names)
    head = [n for n in order if n in present]
    return head + [n for n in names if n not in set(head)]


async def portal_facets(
    db: AsyncSession, config: Any, target_types: tuple[str, ...] | list[str]
) -> dict[str, dict[str, FacetSpec]]:
    """All active facets per type, ordered (dict order) as the portal shows them."""
    saved = (getattr(config, "facet_fields", None) or {}) if config is not None else {}
    order = (getattr(config, "facet_order", None) or {}) if config is not None else {}
    sort_overrides = (
        (getattr(config, "facet_sort_overrides", None) or {}) if config is not None else {}
    )
    default_sort = (getattr(config, "facet_sort", None) or "count") if config is not None else "count"
    relation = relation_facet_specs(getattr(config, "relation_facets", None) if config else None)
    fields = await field_facet_specs(db, target_types)
    out: dict[str, dict[str, FacetSpec]] = {}
    for target_type in target_types:
        specs: dict[str, FacetSpec] = dict(fields.get(target_type, {}))
        for name in saved.get(target_type, []) or []:
            special = special_spec(name)
            if special is not None:
                specs[name] = special
        specs.update(relation.get(target_type, {}))
        type_sorts = sort_overrides.get(target_type) or {}
        for name, spec in specs.items():
            if spec.kind in SORTABLE_FACET_KINDS:
                override = type_sorts.get(name)
                spec.sort = override if override in ("count", "alpha") else default_sort
        ordered = apply_order(list(specs), order.get(target_type))
        out[target_type] = {name: specs[name] for name in ordered}
    return out


# ---------------------------------------------------------------------------
# Date buckets (EDTF-lite values as stored by date fields)
# ---------------------------------------------------------------------------

# Spans of more than this many decades contribute only their start and end
# bucket, so a vague "1850/1950" does not count in every decade in between.
DATE_SPAN_MAX_DECADES = 5
_YEAR_RE = re.compile(r"^(-?\d{1,4})")


def _year(part: str) -> int | None:
    part = part.strip().rstrip("~?%")
    match = _YEAR_RE.match(part)
    if not match or not part:
        return None
    return int(match.group(1))


def _plausible(year: int | None) -> bool:
    return year is not None and 1000 <= year <= datetime.now(UTC).year + 1


def _bucket(year: int, granularity: str) -> str:
    if granularity == "century":
        return str(year // 100 * 100)
    if granularity == "decade":
        return str(year // 10 * 10)
    return str(year)


def date_buckets(values: list[str], granularity: str) -> tuple[list[str], list[str]]:
    """Buckets for EDTF-lite values; returns (buckets, rejected values).

    Single dates (incl. ``~`` approximate) give their year's bucket; open
    intervals (``YYYY/`` and ``/YYYY``) only the bucket of the given end;
    closed intervals every covered bucket, or just start and end bucket when
    longer than DATE_SPAN_MAX_DECADES decades. Implausible years (< 1000 or
    in the future) are rejected.
    """
    buckets: set[str] = set()
    rejected: list[str] = []
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        if "/" in value:
            start_raw, end_raw = value.split("/", 1)
            start, end = _year(start_raw), _year(end_raw)
            known = [y for y in (start, end) if y is not None]
            if not known or not all(_plausible(y) for y in known):
                rejected.append(value)
                continue
            if start is not None and end is not None:
                lo, hi = sorted((start, end))
                if (hi - lo) / 10 > DATE_SPAN_MAX_DECADES:
                    buckets.update({_bucket(lo, granularity), _bucket(hi, granularity)})
                else:
                    step = {"century": 100, "decade": 10}.get(granularity, 1)
                    first = int(_bucket(lo, granularity))
                    buckets.update(_bucket(y, granularity) for y in range(first, hi + 1, step))
            else:
                buckets.add(_bucket(known[0], granularity))
            continue
        year = _year(value)
        if not _plausible(year):
            rejected.append(value)
            continue
        assert year is not None
        buckets.add(_bucket(year, granularity))
    return sorted(buckets, key=int), rejected
