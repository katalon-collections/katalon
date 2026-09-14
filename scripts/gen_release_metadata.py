#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin
"""Generiert katalon-release.json für ein Release-Tag (katalon-cli Issue #286).

Version + migration_required/breaking werden automatisch ermittelt,
compose_revision/minimum_installer_version/requires kommen aus release-meta.toml
(manuell gepflegt, s. Kommentar dort).

Zusätzlich werden Metadaten zu Umgebungsvariablen (env_vars und deprecated_env_vars)
unterstützt. Mögliche Quellen (in absteigender Priorität):
1. Explizite Definitionsdatei (--definitions oder Env KATALON_RELEASE_DEFINITIONS)
2. Versionsspezifischer Block in release-meta.toml ([releases."1.31.0"])
3. Konventionsdatei unter releases/<version>.toml bzw. releases/<version>.json
4. Metadaten im CHANGELOG.md (HTML-Kommentar <!-- release-metadata: ... --> oder
   Abschnitt ### Environment Variables / ### Umgebungsvariablen)
5. Top-Level env_vars / deprecated_env_vars in release-meta.toml
6. Default: leere Listen []

Usage: scripts/gen_release_metadata.py [--tag vX.Y.Z] [--out katalon-release.json]
                                       [--meta-file release-meta.toml]
                                       [--definitions path/or/json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, check: bool = True) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=check).stdout.strip()


def current_version(tag: str | None, root: Path = REPO_ROOT) -> str:
    if tag:
        return tag.lstrip("v")
    pyproject = root / "backend/pyproject.toml"
    if not pyproject.exists():
        raise SystemExit(f"backend/pyproject.toml nicht gefunden unter {pyproject}.")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
    if not match:
        raise SystemExit("Version nicht in backend/pyproject.toml gefunden.")
    return match.group(1)


def previous_tag(current_tag: str) -> str | None:
    tags = run("git", "tag", "--sort=-v:refname", check=False).splitlines()
    tags = [t for t in tags if t != current_tag and t.strip()]
    return tags[0] if tags else None


def migration_required(current_tag: str, prev_tag: str | None) -> bool:
    if prev_tag is None:
        return True  # erstes Release: Migrationen sind neu ggü. "nichts"
    diff = run(
        "git", "diff", "--name-only", f"{prev_tag}..{current_tag}",
        "--", "backend/migrations/versions/",
        check=False,
    )
    return bool(diff.strip())


def is_breaking(version: str, changelog_path: Path | None = None) -> bool:
    target = changelog_path or (REPO_ROOT / "CHANGELOG.md")
    if not target.exists():
        return False
    changelog = target.read_text(encoding="utf-8")
    section = re.search(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL
    )
    if not section:
        return False
    return "### Breaking" in section.group(0)


def normalize_env_var(item: Any) -> dict[str, Any]:
    """Validiert und normalisiert einen env_vars-Eintrag."""
    if not isinstance(item, dict):
        raise TypeError(f"Ungültiger env_vars-Eintrag (Dict erwartet): {item!r}")
    key = str(item.get("key", "")).strip()
    if not key:
        raise ValueError(f"env_vars-Eintrag ohne 'key': {item!r}")

    raw_default = item.get("default")
    default_val = None if raw_default is None else str(raw_default)

    return {
        "key": key,
        "description": str(item.get("description", "")).strip(),
        "required": bool(item.get("required", False)),
        "secret": bool(item.get("secret", False)),
        "default": default_val,
    }


def normalize_deprecated_env_var(item: Any) -> dict[str, str]:
    """Validiert und normalisiert einen deprecated_env_vars-Eintrag."""
    if not isinstance(item, dict):
        raise TypeError(f"Ungültiger deprecated_env_vars-Eintrag (Dict erwartet): {item!r}")
    key = str(item.get("key", "")).strip()
    if not key:
        raise ValueError(f"deprecated_env_vars-Eintrag ohne 'key': {item!r}")

    return {
        "key": key,
        "note": str(item.get("note", "")).strip(),
    }


def normalize_env_vars(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise TypeError(f"'env_vars' muss eine Liste sein, nicht {type(raw).__name__}")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        norm = normalize_env_var(entry)
        if norm["key"] not in seen:
            seen.add(norm["key"])
            result.append(norm)
    return result


def normalize_deprecated_env_vars(raw: Any) -> list[dict[str, str]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise TypeError(f"'deprecated_env_vars' muss eine Liste sein, nicht {type(raw).__name__}")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        norm = normalize_deprecated_env_var(entry)
        if norm["key"] not in seen:
            seen.add(norm["key"])
            result.append(norm)
    return result


def parse_changelog_env_metadata(
    version: str, changelog_text: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Extrahiert Umgebungsvariablen-Metadaten aus dem CHANGELOG für eine Version."""
    section_match = re.search(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)", changelog_text, re.MULTILINE | re.DOTALL
    )
    if not section_match:
        return [], []
    section = section_match.group(0)

    # 1. Prüfe auf strukturierte HTML-Kommentare: <!-- release-metadata: { ... } -->
    comment_match = re.search(
        r"<!--\s*release-meta(?:data)?:\s*(\{.*?\})\s*-->", section, re.DOTALL
    )
    if comment_match:
        try:
            parsed = json.loads(comment_match.group(1))
            return (
                normalize_env_vars(parsed.get("env_vars")),
                normalize_deprecated_env_vars(parsed.get("deprecated_env_vars")),
            )
        except json.JSONDecodeError:
            pass

    # 2. Prüfe auf Markdown-Listen in dedizierten Abschnitten
    env_vars: list[dict[str, Any]] = []
    deprecated_env_vars: list[dict[str, str]] = []

    # ### Environment Variables / ### Umgebungsvariablen
    env_block = re.search(
        r"^###\s+(?:Environment Variables|Umgebungsvariablen)\s*\n(.*?)(?=^###|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if env_block:
        for line in env_block.group(1).splitlines():
            line = line.strip()
            item_match = re.match(r"^[-*]\s+`?([A-Z0-9_]+)`?\s*(?::\s*|-+\s*)?(.*)$", line)
            if not item_match:
                continue
            key, rest = item_match.group(1), item_match.group(2).strip()
            is_dep = "(deprecated)" in rest.lower() or "veraltet" in rest.lower()
            if is_dep:
                clean_note = re.sub(r"\((?:deprecated|veraltet)\)", "", rest, flags=re.IGNORECASE).strip(" :-,")
                deprecated_env_vars.append({"key": key, "note": clean_note})
            else:
                req = bool(re.search(r"\b(?:required|pflicht)\b", rest, re.IGNORECASE))
                sec = bool(re.search(r"\bsecret\b", rest, re.IGNORECASE))
                def_match = re.search(r"\bdefault:\s*([^\),]+)", rest, re.IGNORECASE)
                default_val = def_match.group(1).strip().strip('"\'') if def_match else None
                if default_val == "null":
                    default_val = None
                # Beschreibung bereinigen (Metadaten-Klammern entfernen)
                clean_desc = re.sub(r"\([^\)]*\)", "", rest).strip(" :-,")
                env_vars.append({
                    "key": key,
                    "description": clean_desc,
                    "required": req,
                    "secret": sec,
                    "default": default_val,
                })

    # ### Deprecated Environment Variables / ### Veraltete Umgebungsvariablen
    dep_block = re.search(
        r"^###\s+(?:Deprecated Environment Variables|Veraltete Umgebungsvariablen)\s*\n(.*?)(?=^###|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if dep_block:
        for line in dep_block.group(1).splitlines():
            line = line.strip()
            item_match = re.match(r"^[-*]\s+`?([A-Z0-9_]+)`?\s*(?::\s*|-+\s*)?(.*)$", line)
            if item_match:
                key, rest = item_match.group(1), item_match.group(2).strip()
                clean_note = re.sub(r"\((?:deprecated|veraltet)\)", "", rest, flags=re.IGNORECASE).strip(" :-,")
                deprecated_env_vars.append({"key": key, "note": clean_note})

    return normalize_env_vars(env_vars), normalize_deprecated_env_vars(deprecated_env_vars)


def load_definitions_data(source: str | Path) -> dict[str, Any]:
    """Lädt Definitionsdaten aus Pfad (JSON/TOML), Verzeichnis oder inline JSON."""
    path_candidate = Path(source)
    if path_candidate.is_file():
        content = path_candidate.read_text(encoding="utf-8")
        if path_candidate.suffix in (".toml", ".tml"):
            return tomllib.loads(content)
        return json.loads(content)
    if path_candidate.is_dir():
        # Verzeichnis wird später versionsspezifisch durchsucht
        return {}
    # Prüfe auf inline JSON
    trimmed = str(source).strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        return json.loads(trimmed)
    raise FileNotFoundError(f"Definitionsdatei nicht gefunden: {source}")


def resolve_release_env_vars(
    version: str,
    meta: dict[str, Any],
    definitions_source: str | Path | None = None,
    changelog_path: Path | None = None,
    root: Path = REPO_ROOT,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Ermittelt env_vars und deprecated_env_vars anhand der Prioritätskaskade."""
    # Quelle 1: Explizite Definition via CLI/Env
    def_arg = definitions_source or os.environ.get("KATALON_RELEASE_DEFINITIONS")
    if def_arg:
        candidate = Path(def_arg)
        if candidate.is_dir():
            for filename in (f"{version}.toml", f"v{version}.toml", f"{version}.json", f"v{version}.json"):
                fp = candidate / filename
                if fp.is_file():
                    data = load_definitions_data(fp)
                    return (
                        normalize_env_vars(data.get("env_vars")),
                        normalize_deprecated_env_vars(data.get("deprecated_env_vars")),
                    )
        else:
            data = load_definitions_data(def_arg)
            # Falls versionsspezifisch verschachtelt
            vdata = data.get("releases", {}).get(version) or data.get("releases", {}).get(f"v{version}") or data
            return (
                normalize_env_vars(vdata.get("env_vars")),
                normalize_deprecated_env_vars(vdata.get("deprecated_env_vars")),
            )

    # Quelle 2: Versionsspezifischer Block in release-meta.toml
    releases_meta = meta.get("releases", {})
    v_meta = releases_meta.get(version) or releases_meta.get(f"v{version}")
    if isinstance(v_meta, dict) and ("env_vars" in v_meta or "deprecated_env_vars" in v_meta):
        return (
            normalize_env_vars(v_meta.get("env_vars")),
            normalize_deprecated_env_vars(v_meta.get("deprecated_env_vars")),
        )

    # Quelle 3: Konventionsdatei unter releases/<version>.toml bzw. .json
    releases_dir = root / "releases"
    if releases_dir.is_dir():
        for filename in (f"{version}.toml", f"v{version}.toml", f"{version}.json", f"v{version}.json"):
            fp = releases_dir / filename
            if fp.is_file():
                data = load_definitions_data(fp)
                return (
                    normalize_env_vars(data.get("env_vars")),
                    normalize_deprecated_env_vars(data.get("deprecated_env_vars")),
                )

    # Quelle 4: CHANGELOG.md-Metadaten
    cl_path = changelog_path or (root / "CHANGELOG.md")
    if cl_path.exists():
        cl_env, cl_dep = parse_changelog_env_metadata(version, cl_path.read_text(encoding="utf-8"))
        if cl_env or cl_dep:
            return cl_env, cl_dep

    # Quelle 5: Top-Level env_vars / deprecated_env_vars in release-meta.toml
    if "env_vars" in meta or "deprecated_env_vars" in meta:
        return (
            normalize_env_vars(meta.get("env_vars")),
            normalize_deprecated_env_vars(meta.get("deprecated_env_vars")),
        )

    # Quelle 6: Default (leere Listen für vollständige Abwärtskompatibilität)
    return [], []


def build_release_payload(
    tag: str,
    version: str,
    meta: dict[str, Any],
    definitions_source: str | Path | None = None,
    changelog_path: Path | None = None,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Erstellt das vollständige Dictionary für katalon-release.json."""
    prev = previous_tag(tag)
    env_vars, deprecated_env_vars = resolve_release_env_vars(
        version=version,
        meta=meta,
        definitions_source=definitions_source,
        changelog_path=changelog_path,
        root=root,
    )

    return {
        "version": version,
        "minimum_installer_version": meta["minimum_installer_version"],
        "migration_required": migration_required(tag, prev),
        "breaking": is_breaking(version, changelog_path=changelog_path),
        "compose_revision": meta["compose_revision"],
        "requires": meta.get("requires", {}),
        "env_vars": env_vars,
        "deprecated_env_vars": deprecated_env_vars,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generiert katalon-release.json für Release-Tags und katalon-cli."
    )
    parser.add_argument("--tag", help="Release-Tag, z.B. v0.11.0. Default: aktueller git-Tag von HEAD.")
    parser.add_argument("--out", default="katalon-release.json", help="Pfad der Ausgabedatei.")
    parser.add_argument(
        "--meta-file",
        default=str(REPO_ROOT / "release-meta.toml"),
        help="Pfad zu release-meta.toml (Standard: Repository-Root).",
    )
    parser.add_argument(
        "--definitions",
        help="Pfad zu einer JSON-/TOML-Definitionsdatei oder Verzeichnis für env_vars.",
    )
    parser.add_argument(
        "--changelog",
        default=str(REPO_ROOT / "CHANGELOG.md"),
        help="Pfad zu CHANGELOG.md (Standard: Repository-Root).",
    )
    args = parser.parse_args()

    tag = args.tag or run("git", "describe", "--tags", "--exact-match")
    version = current_version(tag)

    meta_path = Path(args.meta_file)
    if not meta_path.exists():
        raise SystemExit(f"Release-Metadatendatei nicht gefunden: {meta_path}")
    meta = tomllib.loads(meta_path.read_text(encoding="utf-8"))

    payload = build_release_payload(
        tag=tag,
        version=version,
        meta=meta,
        definitions_source=args.definitions,
        changelog_path=Path(args.changelog),
        root=REPO_ROOT,
    )

    Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
