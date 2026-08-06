#!/usr/bin/env python3
"""
ICS Demo-Seeder für Katalon
============================
Legt Felddefinitionen, Vokabulare und Beispieldatensätze nach dem Datenmodell
der Internationalen Computerspielesammlung (ICS) an.

Designed für frische Installationen. Mehrfaches Ausführen erzeugt Duplikate.

Aufruf (aus dem Repo-Root):
    uv run --project backend python scripts/seed_ics_demo.py
    uv run --project backend python scripts/seed_ics_demo.py --base-url http://localhost:8000
    uv run --project backend python scripts/seed_ics_demo.py --help
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import httpx

# ── Standardkonfiguration ──────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_EMAIL = "admin@katalon.dev"
DEFAULT_PASSWORD = "admin"


# ── HTTP-Client ────────────────────────────────────────────────────────────────

class KatalonClient:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self._http = httpx.Client(timeout=30.0)

    def login(self, email: str, password: str) -> None:
        r = self._http.post(
            f"{self.base}/v1/auth/token",
            data={"username": email, "password": password},
        )
        r.raise_for_status()
        self._http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        print(f"Angemeldet als {email}")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._http.post(f"{self.base}{path}", json=payload)
        if not r.is_success:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()  # type: ignore[no-any-return]


def ok(label: str, record_id: str) -> None:
    print(f"  + {label} ({record_id[:8]}…)")


def err(label: str, exc: Exception) -> None:
    print(f"  ! {label}: {exc}", file=sys.stderr)


# ══ Stammdaten ═════════════════════════════════════════════════════════════════

VOCABULARIES: list[dict[str, Any]] = [
    {
        "name": "system",
        "is_hierarchical": False,
        "terms": [
            {"term": "c64",        "label": {"de": "Commodore 64"}},
            {"term": "amiga",      "label": {"de": "Amiga"}},
            {"term": "atari_st",   "label": {"de": "Atari ST"}},
            {"term": "dos",        "label": {"de": "MS-DOS"}},
            {"term": "windows",    "label": {"de": "Windows"}},
            {"term": "mac",        "label": {"de": "Mac OS (Classic)"}},
            {"term": "game_boy",   "label": {"de": "Game Boy"}},
            {"term": "nes",        "label": {"de": "NES / Famicom"}},
            {"term": "snes",       "label": {"de": "Super Nintendo (SNES)"}},
            {"term": "mega_drive", "label": {"de": "Sega Mega Drive / Genesis"}},
        ],
    },
    {
        "name": "genre",
        "is_hierarchical": False,
        "terms": [
            {"term": "puzzle",      "label": {"de": "Puzzle"}},
            {"term": "action",      "label": {"de": "Action"}},
            {"term": "adventure",   "label": {"de": "Adventure"}},
            {"term": "ego_shooter", "label": {"de": "Ego-Shooter", "en": "First-Person Shooter"}},
            {"term": "strategie",   "label": {"de": "Strategiespiel"}},
            {"term": "rpg",         "label": {"de": "Rollenspiel (RPG)"}},
            {"term": "simulation",  "label": {"de": "Simulation"}},
            {"term": "sport",       "label": {"de": "Sport"}},
            {"term": "jump_run",    "label": {"de": "Jump & Run"}},
        ],
    },
    {
        "name": "play_mode",
        "is_hierarchical": False,
        "terms": [
            {"term": "single", "label": {"de": "Einzelspieler", "en": "Single Player"}},
            {"term": "multi",  "label": {"de": "Mehrspieler",   "en": "Multiplayer"}},
            {"term": "coop",   "label": {"de": "Kooperativ",    "en": "Co-op"}},
        ],
    },
    {
        "name": "language_version",
        "is_hierarchical": False,
        "terms": [
            {"term": "de",          "label": {"de": "Deutsch"}},
            {"term": "en",          "label": {"de": "Englisch"}},
            {"term": "fr",          "label": {"de": "Französisch"}},
            {"term": "ja",          "label": {"de": "Japanisch"}},
            {"term": "multilingual","label": {"de": "Mehrsprachig"}},
        ],
    },
    {
        "name": "copy_protection",
        "is_hierarchical": False,
        "terms": [
            {"term": "none",          "label": {"de": "Kein Kopierschutz"}},
            {"term": "dongle",        "label": {"de": "Dongle"}},
            {"term": "manual_lookup", "label": {"de": "Handbuchabfrage"}},
            {"term": "disk_based",    "label": {"de": "Disketten-basiert"}},
            {"term": "cd_check",      "label": {"de": "CD-Prüfung"}},
        ],
    },
    {
        "name": "entity_type",
        "is_hierarchical": False,
        "terms": [
            {"term": "person",       "label": {"de": "Person"}},
            {"term": "organisation", "label": {"de": "Organisation / Unternehmen"}},
            {"term": "verlag",       "label": {"de": "Verlag / Publisher"}},
        ],
    },
    {
        "name": "collection_status",
        "is_hierarchical": False,
        "terms": [
            {"term": "in_collection",  "label": {"de": "In Sammlung"}},
            {"term": "on_loan",        "label": {"de": "Ausgeliehen"}},
            {"term": "missing",        "label": {"de": "Vermisst"}},
            {"term": "deaccessioned",  "label": {"de": "Abgang"}},
        ],
    },
]

FIELD_DEFINITIONS: list[dict[str, Any]] = [
    # ── Objekte ───────────────────────────────────────────────────────────────
    {"target_type": "object", "name": "title",                "label": {"de": "Objekttitel",                  "en": "Title"},             "field_type": "text",    "is_required": True,  "is_repeatable": False, "sort_order": 1},
    {"target_type": "object", "name": "object_identifier",   "label": {"de": "Objektidentifikator"},                                     "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 2},
    {"target_type": "object", "name": "inventory_number",    "label": {"de": "Inventarnummer"},                                          "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 3},
    {"target_type": "object", "name": "old_inventory_number","label": {"de": "Alte Inventarnummer"},                                     "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 4},
    {"target_type": "object", "name": "description",         "label": {"de": "Beschreibung",                  "en": "Description"},       "field_type": "text",    "is_required": False, "is_repeatable": True,  "sort_order": 5},
    {"target_type": "object", "name": "publisher_name",      "label": {"de": "Publisher (Freitext)"},                                    "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 6},
    {"target_type": "object", "name": "system",              "label": {"de": "System / Plattform"},                                      "field_type": "vocab",   "is_required": False, "is_repeatable": True,  "sort_order": 7,  "settings": {"vocabulary": "system"}},
    {"target_type": "object", "name": "language_version",    "label": {"de": "Sprachversion(en)"},                                       "field_type": "vocab",   "is_required": False, "is_repeatable": True,  "sort_order": 8,  "settings": {"vocabulary": "language_version"}},
    {"target_type": "object", "name": "copy_protection",     "label": {"de": "Kopierschutz"},                                            "field_type": "vocab",   "is_required": False, "is_repeatable": False, "sort_order": 9,  "settings": {"vocabulary": "copy_protection"}},
    {"target_type": "object", "name": "copy_protection_detail","label": {"de": "Kopierschutzdetail"},                                    "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 10},
    {"target_type": "object", "name": "is_complete",         "label": {"de": "Objektvollständig?"},                                      "field_type": "boolean", "is_required": False, "is_repeatable": False, "sort_order": 11},
    {"target_type": "object", "name": "ean",                 "label": {"de": "EAN-Nummer"},                                              "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 12},
    {"target_type": "object", "name": "isbn",                "label": {"de": "ISBN-Nummer"},                                             "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 13},
    {"target_type": "object", "name": "collection_status",   "label": {"de": "Sammlungsstatus",               "en": "Collection Status"}, "field_type": "vocab",   "is_required": False, "is_repeatable": False, "sort_order": 14, "settings": {"vocabulary": "collection_status"}},
    {"target_type": "object", "name": "internal_note",       "label": {"de": "Interne Anmerkung"},                                       "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 15},

    # ── Entitäten ─────────────────────────────────────────────────────────────
    {"target_type": "entity", "name": "display_name",        "label": {"de": "Name",                          "en": "Name"},              "field_type": "text",    "is_required": True,  "is_repeatable": False, "sort_order": 1},
    {"target_type": "entity", "name": "entity_subtype",      "label": {"de": "Typ"},                                                      "field_type": "vocab",   "is_required": False, "is_repeatable": False, "sort_order": 2,  "settings": {"vocabulary": "entity_type"}},
    {"target_type": "entity", "name": "bio",                 "label": {"de": "Biographische Angaben"},                                    "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 3},
    {"target_type": "entity", "name": "country",             "label": {"de": "Land"},                                                     "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 4},
    {"target_type": "entity", "name": "founding_year",       "label": {"de": "Gründungsjahr"},                                            "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 5},
    {"target_type": "entity", "name": "dissolved_year",      "label": {"de": "Aufgelöst (Jahr)"},                                         "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 6},
    {"target_type": "entity", "name": "website",             "label": {"de": "Website / URL"},                                            "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 7},
    {"target_type": "entity", "name": "internal_note",       "label": {"de": "Interne Anmerkung"},                                        "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 8},

    # ── Orte ──────────────────────────────────────────────────────────────────
    {"target_type": "place", "name": "place_name",           "label": {"de": "Ortsname",                      "en": "Place Name"},         "field_type": "text",    "is_required": True,  "is_repeatable": False, "sort_order": 1},
    {"target_type": "place", "name": "country",              "label": {"de": "Land"},                                                      "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 2},
    {"target_type": "place", "name": "region",               "label": {"de": "Region / Bundesland"},                                       "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 3},
    {"target_type": "place", "name": "description",          "label": {"de": "Beschreibung"},                                              "field_type": "text",    "is_required": False, "is_repeatable": False, "sort_order": 4},

    # ── Occurrences (Werke + Werkversionen teilen das Schema, bis Issue #2) ──
    {"target_type": "occurrence", "name": "title",                  "label": {"de": "Titel",                   "en": "Title"},             "field_type": "text",  "is_required": True,  "is_repeatable": False, "sort_order": 1},
    {"target_type": "occurrence", "name": "alternative_title",      "label": {"de": "Alternativer Titel"},                                 "field_type": "text",  "is_required": False, "is_repeatable": False, "sort_order": 2},
    {"target_type": "occurrence", "name": "subtitle",               "label": {"de": "Untertitel"},                                         "field_type": "text",  "is_required": False, "is_repeatable": False, "sort_order": 3},
    {"target_type": "occurrence", "name": "description",            "label": {"de": "Beschreibung"},                                       "field_type": "text",  "is_required": False, "is_repeatable": False, "sort_order": 4},
    {"target_type": "occurrence", "name": "first_publication_date", "label": {"de": "Erstveröffentlichung"},                               "field_type": "date",  "is_required": False, "is_repeatable": False, "sort_order": 5},
    {"target_type": "occurrence", "name": "genre",                  "label": {"de": "Genre"},                                              "field_type": "vocab", "is_required": False, "is_repeatable": True,  "sort_order": 6, "settings": {"vocabulary": "genre"}},
    {"target_type": "occurrence", "name": "play_mode",              "label": {"de": "Spielmodus"},                                         "field_type": "vocab", "is_required": False, "is_repeatable": True,  "sort_order": 7, "settings": {"vocabulary": "play_mode"}},
    {"target_type": "occurrence", "name": "system",                 "label": {"de": "System / Plattform"},                                 "field_type": "vocab", "is_required": False, "is_repeatable": True,  "sort_order": 8, "settings": {"vocabulary": "system"}},
    {"target_type": "occurrence", "name": "release_date",           "label": {"de": "Erscheinungsdatum (Version)"},                        "field_type": "date",  "is_required": False, "is_repeatable": False, "sort_order": 9},
    {"target_type": "occurrence", "name": "internal_note",          "label": {"de": "Interne Anmerkung"},                                  "field_type": "text",  "is_required": False, "is_repeatable": False, "sort_order": 10},
]

# ══ Record-Subtypes ════════════════════════════════════════════════════════════
# Primärtypen brauchen registrierte Subtypen (record_subtypes-Tabelle), sonst
# lehnt die API published-Datensätze mit "Subtyp ist erforderlich" ab.
# "person"/"geographikum"/"werk"/"objekt" existieren bereits als System-Default,
# "organisation" und "werkversion" fehlen für dieses Demo-Set.

RECORD_SUBTYPES: list[dict[str, Any]] = [
    {"primary_type": "entity",     "name": "organisation", "label": {"de": "Organisation / Unternehmen"}},
    {"primary_type": "occurrence", "name": "werkversion",  "label": {"de": "Werkversion"}},
]

# ══ Entitäten ══════════════════════════════════════════════════════════════════
# idno wird explizit gesetzt: ohne konfiguriertes idno_schema (AdminConfig) verlangt
# die API bei status="published" zwingend eine idno.
# "label" ist system-weit ein Pflichtfeld (Basisschema), unabhängig vom ICS-Schema.

ENTITIES: list[dict[str, Any]] = [
    {
        "_key": "id Software",
        "idno": "ENT-0001",
        "entity_type": "organisation",
        "status": "public",
        "metadata_": {
            "label": "id Software",
            "display_name": "id Software",
            "entity_subtype": "organisation",
            "bio": "US-amerikanisches Spieleentwicklungsstudio, gegründet 1991 in Mesquite, Texas. Bekannt für Wolfenstein 3D, Doom und Quake.",
            "country": "USA",
            "founding_year": "1991",
            "website": "https://www.idsoftware.com",
        },
    },
    {
        "_key": "LucasArts",
        "idno": "ENT-0002",
        "entity_type": "organisation",
        "status": "public",
        "metadata_": {
            "label": "LucasArts",
            "display_name": "LucasArts",
            "entity_subtype": "organisation",
            "bio": "US-amerikanisches Spieleentwicklungs- und Publishingunternehmen, 1982 als Lucasfilm Games gegründet. Bekannt für Point-and-Click-Adventures wie Monkey Island und Grim Fandango.",
            "country": "USA",
            "founding_year": "1982",
            "dissolved_year": "2013",
        },
    },
    {
        "_key": "Nintendo",
        "idno": "ENT-0003",
        "entity_type": "organisation",
        "status": "public",
        "metadata_": {
            "label": "Nintendo Co., Ltd.",
            "display_name": "Nintendo Co., Ltd.",
            "entity_subtype": "organisation",
            "bio": "Japanisches Videospielunternehmen, gegründet 1889 in Kyoto. Hersteller von Game Boy, NES, SNES und zahlreichen Spielreihen.",
            "country": "Japan",
            "founding_year": "1889",
            "website": "https://www.nintendo.com",
        },
    },
    {
        "_key": "John Carmack",
        "idno": "ENT-0004",
        "entity_type": "person",
        "status": "public",
        "metadata_": {
            "label": "John Carmack",
            "display_name": "John Carmack",
            "entity_subtype": "person",
            "bio": "US-amerikanischer Programmierer und Mitgründer von id Software. Chefentwickler der Doom- und Quake-3D-Engines.",
            "country": "USA",
        },
    },
    {
        "_key": "Ron Gilbert",
        "idno": "ENT-0005",
        "entity_type": "person",
        "status": "public",
        "metadata_": {
            "label": "Ron Gilbert",
            "display_name": "Ron Gilbert",
            "entity_subtype": "person",
            "bio": "US-amerikanischer Spieleentwickler. Schöpfer der Monkey-Island-Reihe und Mitentwickler der SCUMM-Engine bei LucasArts.",
            "country": "USA",
        },
    },
    {
        "_key": "Alexei Paschitnow",
        "idno": "ENT-0006",
        "entity_type": "person",
        "status": "public",
        "metadata_": {
            "label": "Alexei Paschitnow",
            "display_name": "Alexei Paschitnow",
            "entity_subtype": "person",
            "bio": "Russischer Computerwissenschaftler. Entwickelte 1984 Tetris am Dorodnizyn-Computing-Zentrum der Akademie der Wissenschaften der UdSSR in Moskau.",
            "country": "Russland (UdSSR)",
        },
    },
]

# ══ Orte ═══════════════════════════════════════════════════════════════════════

PLACES: list[dict[str, Any]] = [
    {
        "_key": "Mesquite",
        "idno": "PLC-0001",
        "place_type": "geographikum",
        "lat": 32.7668, "lon": -96.9997,
        "status": "public",
        "metadata_": {
            "label": "Mesquite, Texas",
            "place_name": "Mesquite, Texas",
            "country": "USA",
            "region": "Texas",
            "description": "Gründungsort von id Software (1991).",
        },
    },
    {
        "_key": "San Rafael",
        "idno": "PLC-0002",
        "place_type": "geographikum",
        "lat": 37.9735, "lon": -122.5311,
        "status": "public",
        "metadata_": {
            "label": "San Rafael, Kalifornien",
            "place_name": "San Rafael, Kalifornien",
            "country": "USA",
            "region": "Kalifornien",
            "description": "Sitz von LucasArts (Lucasfilm Games).",
        },
    },
    {
        "_key": "Kyoto",
        "idno": "PLC-0003",
        "place_type": "geographikum",
        "lat": 35.0116, "lon": 135.7681,
        "status": "public",
        "metadata_": {
            "label": "Kyoto",
            "place_name": "Kyoto",
            "country": "Japan",
            "description": "Hauptsitz von Nintendo Co., Ltd.",
        },
    },
    {
        "_key": "Moskau",
        "idno": "PLC-0004",
        "place_type": "geographikum",
        "lat": 55.7558, "lon": 37.6173,
        "status": "public",
        "metadata_": {
            "label": "Moskau",
            "place_name": "Moskau",
            "country": "Russland (UdSSR)",
            "description": "Entstehungsort von Tetris (1984), Dorodnizyn-Computing-Zentrum.",
        },
    },
]

# ══ Werke (occurrence_type = "werk") ══════════════════════════════════════════

WERKE: list[dict[str, Any]] = [
    {
        "_key": "Doom",
        "idno": "WRK-0001",
        "occurrence_type": "werk",
        "status": "public",
        "metadata_": {
            "label": "Doom",
            "title": "Doom",
            "description": "Wegweisender Ego-Shooter von id Software (1993). Gilt als eines der einflussreichsten Videospiele der Geschichte und begründete das Genre des modernen Ego-Shooters.",
            "first_publication_date": "1993-12-10",
            "genre": ["ego_shooter", "action"],
            "play_mode": ["single", "multi"],
        },
    },
    {
        "_key": "Monkey Island",
        "idno": "WRK-0002",
        "occurrence_type": "werk",
        "status": "public",
        "metadata_": {
            "label": "The Secret of Monkey Island",
            "title": "The Secret of Monkey Island",
            "description": "Point-and-Click-Adventure von LucasArts (1990). Spielt in der Karibik des 17. Jahrhunderts und folgt dem Piraten-Anwärter Guybrush Threepwood. Gilt als Klassiker des Genres.",
            "first_publication_date": "1990-10-01",
            "genre": ["adventure"],
            "play_mode": ["single"],
        },
    },
    {
        "_key": "Tetris",
        "idno": "WRK-0003",
        "occurrence_type": "werk",
        "status": "public",
        "metadata_": {
            "label": "Tetris",
            "title": "Tetris",
            "description": "Klassisches Puzzlespiel, 1984 von Alexei Paschitnow in Moskau entwickelt. Eines der meistverkauften und meistgespielten Videospiele aller Zeiten.",
            "first_publication_date": "1984-06-06",
            "genre": ["puzzle"],
            "play_mode": ["single"],
        },
    },
]

# ══ Werkversionen (occurrence_type = "werkversion") ════════════════════════════

WERKVERSIONEN: list[dict[str, Any]] = [
    {
        "_key": "Doom DOS 1.0",
        "_werk": "Doom",
        "idno": "WV-0001",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "Doom – MS-DOS Shareware v1.0",
            "title": "Doom – MS-DOS Shareware v1.0",
            "system": ["dos"],
            "release_date": "1993-12-10",
            "description": "Erste veröffentlichte Version als Shareware (Episode 1 kostenlos, Episoden 2 & 3 käuflich).",
        },
    },
    {
        "_key": "Doom DOS 1.9",
        "_werk": "Doom",
        "idno": "WV-0002",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "Doom – MS-DOS v1.9 (Ultimate Doom, 4 Episoden)",
            "title": "Doom – MS-DOS v1.9 (Ultimate Doom, 4 Episoden)",
            "system": ["dos"],
            "release_date": "1994-10-01",
            "description": "Letzte DOS-Version mit vierter Episode 'Thy Flesh Consumed'. Über GT Interactive als Retail-Version vertrieben.",
        },
    },
    {
        "_key": "Monkey Island DOS Disk",
        "_werk": "Monkey Island",
        "idno": "WV-0003",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "The Secret of Monkey Island – DOS Disketten-Edition",
            "title": "The Secret of Monkey Island – DOS Disketten-Edition",
            "system": ["dos"],
            "release_date": "1990-10-01",
            "description": "Originalversion für MS-DOS auf fünf 3,5\"-Disketten.",
        },
    },
    {
        "_key": "Monkey Island CD-ROM",
        "_werk": "Monkey Island",
        "idno": "WV-0004",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "The Secret of Monkey Island – CD-ROM Edition",
            "title": "The Secret of Monkey Island – CD-ROM Edition",
            "system": ["dos"],
            "release_date": "1992-01-01",
            "description": "CD-ROM-Version mit vollständiger Sprachausgabe (iMUSE-Audiosystem). Erstmals Text vollständig vertont.",
        },
    },
    {
        "_key": "Tetris DOS",
        "_werk": "Tetris",
        "idno": "WV-0005",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "Tetris – DOS-Version (Spectrum HoloByte)",
            "title": "Tetris – DOS-Version (Spectrum HoloByte)",
            "system": ["dos"],
            "release_date": "1987-01-01",
            "description": "Erste kommerzielle PC-Version für IBM-PC/DOS, veröffentlicht von Spectrum HoloByte.",
        },
    },
    {
        "_key": "Tetris Game Boy",
        "_werk": "Tetris",
        "idno": "WV-0006",
        "occurrence_type": "werkversion",
        "status": "public",
        "metadata_": {
            "label": "Tetris – Game Boy (Nintendo)",
            "title": "Tetris – Game Boy (Nintendo)",
            "system": ["game_boy"],
            "release_date": "1989-06-14",
            "description": "Legendäre Game Boy-Version, von Nintendo publiziert. Im Starterpaket mit dem Game Boy enthalten. Entscheidend für den Erfolg des Handhelds.",
        },
    },
]

# ══ Softwareobjekte ════════════════════════════════════════════════════════════

OBJECTS: list[dict[str, Any]] = [
    {
        "_key": "ICS-0001",
        "_werkversion": "Doom DOS 1.0",
        "_publisher_entity": "id Software",
        "idno": "ICS-0001",
        "object_type": "objekt",
        "status": "public",
        "metadata_": {
            "label": "Doom – Shareware-Diskette v1.0 (DOS)",
            "title": "Doom – Shareware-Diskette v1.0 (DOS)",
            "object_identifier": "ICS-0001",
            "inventory_number": "1",
            "description": ["Originale 3,5\"-Shareware-Diskette von Doom v1.0 für MS-DOS."],
            "system": ["dos"],
            "language_version": ["en"],
            "copy_protection": "none",
            "is_complete": True,
            "collection_status": "in_collection",
        },
    },
    {
        "_key": "ICS-0002",
        "_werkversion": "Doom DOS 1.9",
        "_publisher_entity": "id Software",
        "idno": "ICS-0002",
        "object_type": "objekt",
        "status": "public",
        "metadata_": {
            "label": "Doom – Retail Box (DOS, GT Interactive)",
            "title": "Doom – Retail Box (DOS, GT Interactive)",
            "object_identifier": "ICS-0002",
            "inventory_number": "2",
            "description": ["Retail-Box-Version von Doom (Ultimate Doom, v1.9) für MS-DOS, vertrieben von GT Interactive."],
            "publisher_name": "GT Interactive",
            "system": ["dos"],
            "language_version": ["en"],
            "copy_protection": "disk_based",
            "is_complete": True,
            "collection_status": "in_collection",
        },
    },
    {
        "_key": "ICS-0003",
        "_werkversion": "Monkey Island DOS Disk",
        "_publisher_entity": "LucasArts",
        "idno": "ICS-0003",
        "object_type": "objekt",
        "status": "public",
        "metadata_": {
            "label": "The Secret of Monkey Island – Disketten-Edition (DOS)",
            "title": "The Secret of Monkey Island – Disketten-Edition (DOS)",
            "object_identifier": "ICS-0003",
            "inventory_number": "3",
            "description": ["Box-Edition mit 5 Disketten (3,5\") für MS-DOS."],
            "publisher_name": "LucasFilm Games",
            "system": ["dos"],
            "language_version": ["en"],
            "copy_protection": "manual_lookup",
            "copy_protection_detail": "Monkey Wrench-Kopierschutz: Codeabfrage anhand Insel-Treff-Tabelle im Handbuch.",
            "is_complete": False,
            "internal_note": "Handbuch fehlt.",
            "collection_status": "in_collection",
        },
    },
    {
        "_key": "ICS-0004",
        "_werkversion": "Monkey Island CD-ROM",
        "_publisher_entity": "LucasArts",
        "idno": "ICS-0004",
        "object_type": "objekt",
        "status": "public",
        "metadata_": {
            "label": "The Secret of Monkey Island – CD-ROM Edition",
            "title": "The Secret of Monkey Island – CD-ROM Edition",
            "object_identifier": "ICS-0004",
            "inventory_number": "4",
            "description": ["CD-ROM Edition mit vollständiger Sprachausgabe und iMUSE-Soundtrack."],
            "publisher_name": "LucasArts",
            "system": ["dos"],
            "language_version": ["en"],
            "copy_protection": "cd_check",
            "is_complete": True,
            "collection_status": "in_collection",
        },
    },
    {
        "_key": "ICS-0005",
        "_werkversion": "Tetris Game Boy",
        "_publisher_entity": "Nintendo",
        "idno": "ICS-0005",
        "object_type": "objekt",
        "status": "public",
        "metadata_": {
            "label": "Tetris – Game Boy Modul (Nintendo, Bundle-Version)",
            "title": "Tetris – Game Boy Modul (Nintendo, Bundle-Version)",
            "object_identifier": "ICS-0005",
            "inventory_number": "5",
            "description": ["Game-Boy-Modul aus dem europäischen Game-Boy-Starterpaket (1990). Ohne Verpackung, Modul und Anleitung vorhanden."],
            "publisher_name": "Nintendo",
            "system": ["game_boy"],
            "language_version": ["multilingual"],
            "copy_protection": "none",
            "is_complete": False,
            "internal_note": "Originalverpackung fehlt.",
            "collection_status": "in_collection",
        },
    },
]

# ══ Werk-Relationen (Entitäten + Orte) ════════════════════════════════════════

# (from_key, from_type, to_key, to_type, relation_type)
WERK_RELATIONS: list[tuple[str, str, str, str, str]] = [
    # Entwickler
    ("Doom",          "occurrence", "id Software",       "entity", "entwickelt_von"),
    ("Monkey Island", "occurrence", "LucasArts",         "entity", "entwickelt_von"),
    ("Tetris",        "occurrence", "Alexei Paschitnow", "entity", "entwickelt_von"),
    # Entstehungsorte
    ("Doom",          "occurrence", "Mesquite",    "place", "entstanden_in"),
    ("Monkey Island", "occurrence", "San Rafael",  "place", "entstanden_in"),
    ("Tetris",        "occurrence", "Moskau",      "place", "entstanden_in"),
    # Personen → Organisationen
    ("John Carmack",  "entity", "id Software", "entity", "mitgegruendet"),
    ("Ron Gilbert",   "entity", "LucasArts",   "entity", "angestellt_bei"),
    # Nintendo (Heimatort)
    ("Nintendo",      "entity", "Kyoto",       "place",  "ansaessig_in"),
]


# ══ Seeding ════════════════════════════════════════════════════════════════════

def seed(client: KatalonClient) -> None:
    # ID-Register für Relationen
    ids: dict[str, str] = {}

    # ── 1. Vokabulare ─────────────────────────────────────────────────────────
    print("\n── Vokabulare ───────────────────────────────────────────────────────")
    # Bestehende Vokabulare laden um Duplikate zu überspringen
    existing_vocabs: dict[str, str] = {}
    try:
        ev = client._http.get(f"{client.base}/v1/vocabularies")
        if ev.is_success:
            raw = ev.json()
            items = raw if isinstance(raw, list) else raw.get("items", raw.get("results", []))
            existing_vocabs = {v["name"]: v["id"] for v in items}
    except Exception:
        pass

    for vocab in VOCABULARIES:
        terms = vocab["terms"]
        payload = {"name": vocab["name"], "is_hierarchical": vocab["is_hierarchical"]}
        if vocab["name"] in existing_vocabs:
            vid = existing_vocabs[vocab["name"]]
            print(f"  ~ {vocab['name']} existiert bereits ({vid[:8]}…) – überspringe")
            continue
        try:
            result = client.post("/v1/vocabularies", payload)
            vid = result["id"]
            # Kurz warten bis die DB-Row committed ist (verhindert FK-Fehler beim ersten Term)
            time.sleep(0.15)
            print(f"  + {vocab['name']} ({vid[:8]}…) – {len(terms)} Terms")
        except RuntimeError as e:
            err(vocab["name"], e)
            continue
        for term in terms:
            try:
                client.post(f"/v1/vocabularies/{vid}/terms", {
                    "vocabulary_id": vid,
                    "term": term["term"],
                    "label": term.get("label", {}),
                })
            except RuntimeError as e:
                err(f"  term {term['term']}", e)

    # ── 1b. Record-Subtypes ───────────────────────────────────────────────────
    print("\n── Record-Subtypes ──────────────────────────────────────────────────")
    existing_subtypes: set[tuple[str, str]] = set()
    try:
        es = client._http.get(f"{client.base}/v1/record-subtypes")
        if es.is_success:
            existing_subtypes = {(s["primary_type"], s["name"]) for s in es.json()}
    except Exception:
        pass

    for subtype in RECORD_SUBTYPES:
        key = (subtype["primary_type"], subtype["name"])
        if key in existing_subtypes:
            print(f"  ~ {subtype['primary_type']}.{subtype['name']} existiert bereits – überspringe")
            continue
        try:
            client.post("/v1/record-subtypes", subtype)
            print(f"  + {subtype['primary_type']}.{subtype['name']}")
        except RuntimeError as e:
            err(f"{subtype['primary_type']}.{subtype['name']}", e)

    # ── 2. Felddefinitionen ───────────────────────────────────────────────────
    print("\n── Felddefinitionen ─────────────────────────────────────────────────")
    for fdef in FIELD_DEFINITIONS:
        try:
            client.post("/v1/schema", fdef)
            print(f"  + {fdef['target_type']}.{fdef['name']}")
        except RuntimeError as e:
            err(f"{fdef['target_type']}.{fdef['name']}", e)

    # ── 3. Entitäten ──────────────────────────────────────────────────────────
    print("\n── Entitäten ────────────────────────────────────────────────────────")
    for entity in ENTITIES:
        key = entity["_key"]
        payload = {k: v for k, v in entity.items() if not k.startswith("_")}
        try:
            result = client.post("/v1/entities", payload)
            ids[key] = result["id"]
            ok(key, result["id"])
        except RuntimeError as e:
            err(key, e)

    # ── 4. Orte ───────────────────────────────────────────────────────────────
    print("\n── Orte ─────────────────────────────────────────────────────────────")
    for place in PLACES:
        key = place["_key"]
        payload = {k: v for k, v in place.items() if not k.startswith("_")}
        try:
            result = client.post("/v1/places", payload)
            ids[key] = result["id"]
            ok(key, result["id"])
        except RuntimeError as e:
            err(key, e)

    # ── 5. Werke ──────────────────────────────────────────────────────────────
    print("\n── Werke ────────────────────────────────────────────────────────────")
    for werk in WERKE:
        key = werk["_key"]
        payload = {k: v for k, v in werk.items() if not k.startswith("_")}
        try:
            result = client.post("/v1/occurrences", payload)
            ids[key] = result["id"]
            ok(key, result["id"])
        except RuntimeError as e:
            err(key, e)

    # ── 6. Werkversionen + Relation werkversion_von ───────────────────────────
    print("\n── Werkversionen ────────────────────────────────────────────────────")
    for wv in WERKVERSIONEN:
        key = wv["_key"]
        werk_key = wv["_werk"]
        payload = {k: v for k, v in wv.items() if not k.startswith("_")}
        try:
            result = client.post("/v1/occurrences", payload)
            ids[key] = result["id"]
            ok(key, result["id"])
        except RuntimeError as e:
            err(key, e)
            continue

        if werk_key in ids:
            try:
                client.post("/v1/relations", {
                    "from_type": "occurrence",
                    "from_id": ids[key],
                    "to_type": "occurrence",
                    "to_id": ids[werk_key],
                    "relation_type": "werkversion_von",
                })
                print(f"    → werkversion_von: {werk_key}")
            except RuntimeError as e:
                err(f"Relation {key} → {werk_key}", e)

    # ── 7. Objekte + Relationen enthaelt_werkversion + published_by ──────────
    print("\n── Objekte ──────────────────────────────────────────────────────────")
    for obj in OBJECTS:
        key = obj["_key"]
        wv_key = obj.get("_werkversion")
        pub_key = obj.get("_publisher_entity")
        payload = {k: v for k, v in obj.items() if not k.startswith("_")}
        try:
            result = client.post("/v1/objects", payload)
            obj_id = result["id"]
            ids[key] = obj_id
            ok(key, obj_id)
        except RuntimeError as e:
            err(key, e)
            continue

        if wv_key and wv_key in ids:
            try:
                client.post("/v1/relations", {
                    "from_type": "object",
                    "from_id": obj_id,
                    "to_type": "occurrence",
                    "to_id": ids[wv_key],
                    "relation_type": "enthaelt_werkversion",
                })
                print(f"    → enthaelt_werkversion: {wv_key}")
            except RuntimeError as e:
                err(f"Relation {key} → {wv_key}", e)

        if pub_key and pub_key in ids:
            try:
                client.post("/v1/relations", {
                    "from_type": "object",
                    "from_id": obj_id,
                    "to_type": "entity",
                    "to_id": ids[pub_key],
                    "relation_type": "published_by",
                })
                print(f"    → published_by: {pub_key}")
            except RuntimeError as e:
                err(f"Relation {key} → {pub_key}", e)

    # ── 8. Werk-Relationen (Entitäten + Orte) ─────────────────────────────────
    print("\n── Werk-Relationen ──────────────────────────────────────────────────")
    for from_key, from_type, to_key, to_type, rel_type in WERK_RELATIONS:
        if from_key not in ids:
            err(f"{from_key}", RuntimeError("ID nicht bekannt, überspringe"))
            continue
        if to_key not in ids:
            err(f"{to_key}", RuntimeError("ID nicht bekannt, überspringe"))
            continue
        try:
            client.post("/v1/relations", {
                "from_type": from_type,
                "from_id": ids[from_key],
                "to_type": to_type,
                "to_id": ids[to_key],
                "relation_type": rel_type,
            })
            print(f"  + {from_key} –[{rel_type}]→ {to_key}")
        except RuntimeError as e:
            err(f"{from_key} → {to_key}", e)

    print(f"\nSeeding abgeschlossen. {len(ids)} Datensätze angelegt.")


# ══ Einstiegspunkt ════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICS Demo-Seeder für Katalon – legt Vokabulare, Felder und Beispieldaten an."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API-Basis-URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--email",    default=DEFAULT_EMAIL,    help="Admin-E-Mail")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Admin-Passwort")
    args = parser.parse_args()

    client = KatalonClient(args.base_url)
    client.login(args.email, args.password)
    seed(client)


if __name__ == "__main__":
    main()
