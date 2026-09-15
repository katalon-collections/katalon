# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Fictitious demo and testing seed: Comprehensive Weimar Collection (100 Objects).

Covers all 7 primary record types, all 13 field types, full cross-type relations,
hierarchical storage locations, hierarchical collections, procedures, and media.

Usage inside api container after db-reset:
    docker compose exec api katalon-manage db-reset --all --no-backup --yes
    docker compose restart api
    docker compose exec api python /app/scripts/seed_demo.py

CLI Options:
    --skip-downloads   Generate all images locally via Pillow (ultra-fast, offline)
    --no-images        Do not attach media files to objects
    --no-iiif          Do not enqueue background IIIF tile generation tasks
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from geoalchemy2 import WKTElement
from PIL import Image, ImageDraw
from sqlalchemy import select, update

from katalon.config import settings
from katalon.core.media_storage import storage_key, storage_path
from katalon.core.media_validation import verified_image_mime
from katalon.core.models import (
    AuthoritySource,
    Collection,
    Entity,
    FieldDefinition,
    MediaFile,
    Object,
    Occurrence,
    Place,
    PortalConfig,
    Procedure,
    RecordSubtype,
    Relation,
    StaticPage,
    StorageLocation,
    User,
    Vocabulary,
    VocabularyTerm,
)
from katalon.database import AsyncSessionLocal
from katalon.services.audit_service import log_change
from katalon.services.relation_service import sync_schema_relations
from katalon.workers.index_tasks import reindex_all_task
from katalon.workers.media_tasks import generate_iiif_tiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("katalon.seed")

REL_VOCAB_NAME = "relation_types"
MATERIAL_VOCAB_NAME = "materialien"
ZUSTAND_VOCAB_NAME = "erhaltungszustaende"
ORTSTYP_VOCAB_NAME = "ortstypen"
GENRE_VOCAB_NAME = "gattungen"
TECHNIK_VOCAB_NAME = "techniken"
VORGANG_VOCAB_NAME = "vorgangstypen"

PD_MARK = "https://creativecommons.org/publicdomain/mark/1.0/"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"

def demo_object_id(idno: str) -> uuid.UUID:
    """Return the stable UUID assigned to a seeded demo object."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"katalon-demo/object/{idno}")


DEMO_IMAGES: list[tuple[str, str, str, str, str]] = [
    ("OBJ-001", "goethe-stieler.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Goethe_(Stieler_1828).jpg", "https://upload.wikimedia.org/wikipedia/commons/0/0e/Goethe_%28Stieler_1828%29.jpg"),
    ("OBJ-002", "schiller.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Schiller_edit1.jpg", "https://upload.wikimedia.org/wikipedia/commons/e/e5/Schiller_edit1.jpg"),
    ("OBJ-003", "herder-rijksmuseum.jpg", "CC0", "https://commons.wikimedia.org/wiki/File:Portret_van_Johann_Gottfried_Herder,_RP-P-1914-4131.jpg", "https://upload.wikimedia.org/wikipedia/commons/2/27/Portret_van_Johann_Gottfried_Herder%2C_RP-P-1914-4131.jpg"),
    ("OBJ-004", "faust-opening.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Goethe_Faust_Opening_Fraktur_20052706_crop.jpg", "https://upload.wikimedia.org/wikipedia/commons/f/f7/Goethe_Faust_Opening_Fraktur_20052706_crop.jpg"),
    ("OBJ-005", "schiller-portrait.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Friedrich_von_Schiller_(5254815).jpg", "https://upload.wikimedia.org/wikipedia/commons/8/81/Friedrich_von_Schiller_%285254815%29.jpg"),
    ("OBJ-006", "werther-manuscript.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Recueil._%22Werther%22_de_P._Milliet,_G._Hartamann,_d%27apr%C3%A8s_Goethe_-_btv1b10507503p_(03_of_32).jpg", "https://upload.wikimedia.org/wikipedia/commons/0/0e/Recueil._%22Werther%22_de_P._Milliet%2C_G._Hartamann%2C_d%27apr%C3%A8s_Goethe_-_btv1b10507503p_%2803_of_32%29.jpg"),
    ("OBJ-007", "wieland-engraving.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:1800_circa_Christoph_Martin_Wieland,_Kupferstich_von_Heinrich_Friedrich_Thomas_Schmidt_nach_Ferdinand_Jagermann,_Landes-Industrie-Comptoir.jpg", "https://upload.wikimedia.org/wikipedia/commons/b/b6/1800_circa_Christoph_Martin_Wieland%2C_Kupferstich_von_Heinrich_Friedrich_Thomas_Schmidt_nach_Ferdinand_Jagermann%2C_Landes-Industrie-Comptoir.jpg"),
    ("OBJ-008", "goethe-roman-campagna.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Johann_Heinrich_Wilhelm_Tischbein_-_Goethe_in_the_Roman_Campagna_-_Google_Art_Project.jpg", "https://upload.wikimedia.org/wikipedia/commons/a/a0/Johann_Heinrich_Wilhelm_Tischbein_-_Goethe_in_the_Roman_Campagna_-_Google_Art_Project.jpg"),
    ("OBJ-009", "goethe-passport-1787.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Goethes_Reisepass_von_1787.jpg", "https://upload.wikimedia.org/wikipedia/commons/a/a7/Goethes_Reisepass_von_1787.jpg"),
    ("OBJ-010", "goethe-alsace-manuscript.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Chansons_populaires_recueillies_par_Goethe_en_Alsace.jpg", "https://upload.wikimedia.org/wikipedia/commons/6/6b/Chansons_populaires_recueillies_par_Goethe_en_Alsace.jpg"),
    ("OBJ-011", "schiller-portrait-engraving.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Portrait_of_Schiller_(4674247).jpg", "https://upload.wikimedia.org/wikipedia/commons/a/a6/Portrait_of_Schiller_%284674247%29.jpg"),
    ("OBJ-012", "goethe-stieler-portrait.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Joseph_Karl_Stieler_portrait_de_Johann_Wolfgang_von_Goethe.jpg", "https://upload.wikimedia.org/wikipedia/commons/f/f4/Joseph_Karl_Stieler_portrait_de_Johann_Wolfgang_von_Goethe.jpg"),
    ("OBJ-013", "herder-portrait-engraving.jpg", "CC0", "https://commons.wikimedia.org/wiki/File:Portret_van_Johann_Gottfried_von_Herder,_RP-P-1914-785.jpg", "https://upload.wikimedia.org/wikipedia/commons/9/99/Portret_van_Johann_Gottfried_von_Herder%2C_RP-P-1914-785.jpg"),
    ("OBJ-014", "weimar-station-1910.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Bahnhof_Weimar_ca_1910.jpg", "https://upload.wikimedia.org/wikipedia/commons/9/96/Bahnhof_Weimar_ca_1910.jpg"),
    ("OBJ-015", "goethehaus-weimar.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Weimar,_Th%C3%BCringen_-_Goethehaus_(Zeno_Ansichtskarten).jpg", "https://upload.wikimedia.org/wikipedia/commons/6/6a/Weimar%2C_Th%C3%BCringen_-_Goethehaus_%28Zeno_Ansichtskarten%29.jpg"),
    ("OBJ-016", "erlkoenig.png", "Public domain", "https://commons.wikimedia.org/wiki/File:Erlk%C3%B6nig.png", "https://upload.wikimedia.org/wikipedia/commons/6/6d/Erlk%C3%B6nig.png"),
    ("OBJ-017", "theatre-notice.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Die_Gartenlaube_(1885)_277.jpg", "https://upload.wikimedia.org/wikipedia/commons/1/10/Die_Gartenlaube_%281885%29_277.jpg"),
    ("OBJ-018", "strasbourg-cathedral.jpg", "CC0", "https://commons.wikimedia.org/wiki/File:Interior_View_of_Strasbourg_Cathedral_MET_DP102697.jpg", "https://upload.wikimedia.org/wikipedia/commons/3/33/Interior_View_of_Strasbourg_Cathedral_MET_DP102697.jpg"),
    ("OBJ-019", "strasbourg-plan.jpg", "Public domain", "https://commons.wikimedia.org/wiki/File:Plan_de_Strasbourg_-_dress%C3%A9e_par_Woerl_et_grav%C3%A9e_sous_sa_direction_;_lithographie_de_B._Herder_-_btv1b10109501c.jpg", "https://upload.wikimedia.org/wikipedia/commons/7/7c/Plan_de_Strasbourg_-_dress%C3%A9e_par_Woerl_et_grav%C3%A9e_sous_sa_direction_%3B_lithographie_de_B._Herder_-_btv1b10109501c.jpg"),
    ("OBJ-020", "goethe-plaque.jpg", "CC0", "https://commons.wikimedia.org/wiki/File:Gedenktafel_Johann_Wolfgang_Goethe.jpg", "https://upload.wikimedia.org/wikipedia/commons/3/30/Gedenktafel_Johann_Wolfgang_Goethe.jpg"),
]

SUBTYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "gemaelde": (35, 45, 65),
    "druckgrafik": (60, 50, 40),
    "handschrift": (70, 60, 45),
    "archivalie": (50, 40, 35),
    "fotografie": (40, 40, 42),
    "skulptur": (48, 54, 58),
    "kunsthandwerk": (65, 30, 35),
    "mineral": (35, 55, 50),
    "sammlungsobjekt": (40, 48, 56),
}


def generate_plate_image(
    destination: Path,
    idno: str,
    title: str,
    subtype: str,
) -> None:
    """Generate a clean typography specimen plate for testing without external downloads."""
    bg_color = SUBTYPE_COLORS.get(subtype, (45, 55, 72))
    img = Image.new("RGB", (800, 600), color=bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 780, 580], outline=(190, 200, 210), width=3)
    draw.rectangle([28, 28, 772, 572], outline=(100, 110, 120), width=1)
    draw.rectangle([30, 30, 770, 85], fill=(15, 20, 28))
    draw.text((50, 48), f"KATALON COLLECTIONS — {subtype.upper()}", fill=(225, 195, 110))
    draw.text((50, 130), idno, fill=(255, 215, 0))
    wrapped = title if len(title) <= 55 else title[:52] + "..."
    draw.text((50, 190), wrapped, fill=(255, 255, 255))
    draw.text((50, 240), f"Objekttyp: {subtype}", fill=(180, 190, 200))
    draw.text((50, 490), "Fiktiver Testbestand — Sammlungen Weimar", fill=(170, 180, 190))
    draw.text((50, 520), "Lizenz: CC0 1.0 Public Domain Dedication", fill=(130, 140, 150))
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, "JPEG", quality=88)


async def make_vocab(
    db,
    name: str,
    kind: str,
    terms: list[dict[str, Any]],
    hierarchical: bool = False,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    vocab = (await db.execute(select(Vocabulary).where(Vocabulary.name == name))).scalar_one_or_none()
    ids: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    if vocab is None:
        vocab = Vocabulary(name=name, kind=kind, is_hierarchical=hierarchical)
        db.add(vocab)
        await db.flush()
    else:
        existing = await db.execute(select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab.id))
        for t in existing.scalars().all():
            ids[t.term] = str(t.id)
            labels[t.term] = t.label
    for t in terms:
        if t["term"] in ids:
            continue
        parent_code = t.get("parent")
        vt = VocabularyTerm(
            vocabulary_id=vocab.id,
            term=t["term"],
            label=t["label"],
            inverse_label=t.get("inverse_label", {}),
            applies_from=t.get("applies_from", []),
            applies_to=t.get("applies_to", []),
            metadata_=t.get("metadata", {}),
            parent_id=uuid.UUID(ids[parent_code]) if parent_code and parent_code in ids else None,
        )
        db.add(vt)
        await db.flush()
        ids[t["term"]] = str(vt.id)
        labels[t["term"]] = t["label"]
    return ids, labels


def rel(id_: str, label: str, rtype: str) -> dict[str, Any]:
    return {"id": id_, "label": label, "relation_type": rtype}


async def add_field(
    db,
    target_type: str,
    name: str,
    label: dict[str, str],
    field_type: str,
    *,
    sort_order: int,
    is_required: bool = False,
    is_repeatable: bool = False,
    is_facet: bool = False,
    is_translatable: bool = False,
    settings_dict: dict[str, Any] | None = None,
    parent_id: uuid.UUID | None = None,
    detail_role: str = "none",
    detail_slot: str = "sidebar",
    target_subtype: str | None = None,
) -> FieldDefinition:
    stmt = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.name == name,
        FieldDefinition.parent_id == parent_id,
        FieldDefinition.is_deleted.is_(False),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    fd = FieldDefinition(
        target_type=target_type,
        target_subtype=target_subtype,
        name=name,
        label=label,
        field_type=field_type,
        is_required=is_required,
        is_repeatable=is_repeatable,
        is_facet=is_facet,
        is_translatable=is_translatable,
        sort_order=sort_order,
        settings=settings_dict or {},
        parent_id=parent_id,
        detail_role=detail_role,
        detail_slot=detail_slot,
    )
    db.add(fd)
    await db.flush()
    return fd


async def seed_media(
    db,
    objects: dict[str, Object],
    *,
    skip_downloads: bool = False,
    no_iiif: bool = False,
) -> None:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    media_ids: list[uuid.UUID] = []

    # 1. First 20 objects with Wikimedia downloads or local fallback
    remote_map = {idno: (fn, lic, src, url) for idno, fn, lic, src, url in DEMO_IMAGES}

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=15.0,
        headers={"User-Agent": "Katalon demo seeder/1.0 (https://github.com/karkraeg/Katalon)"},
    ) as client:
        for i in range(1, 101):
            idno = f"OBJ-{i:03d}"
            obj = objects.get(idno)
            if not obj:
                continue

            file_id = uuid.uuid4()
            remote_info = remote_map.get(idno)

            if remote_info and not skip_downloads:
                filename, license_name, source_url, download_url = remote_info
                key = storage_key(file_id, filename)
                dest = storage_path(key)
                dest.parent.mkdir(parents=True, exist_ok=True)
                downloaded = False
                try:
                    for attempt in range(2):
                        async with client.stream("GET", download_url) as response:
                            if response.status_code == 429 and attempt < 1:
                                await asyncio.sleep(2)
                                continue
                            response.raise_for_status()
                            size = 0
                            with dest.open("wb") as target:
                                async for chunk in response.aiter_bytes():
                                    size += len(chunk)
                                    if size > max_bytes:
                                        raise ValueError(f"{filename} exceeds size limit")
                                    target.write(chunk)
                        downloaded = True
                        break
                except Exception as exc:
                    logger.warning("Download failed for %s (%s), generating plate: %s", idno, filename, exc)
                    dest.unlink(missing_ok=True)

                if not downloaded:
                    filename = f"{idno.lower()}-specimen.jpg"
                    key = storage_key(file_id, filename)
                    dest = storage_path(key)
                    generate_plate_image(dest, idno, obj.metadata_.get("label", idno), obj.object_type or "sammlungsobjekt")
                    license_name = "CC0"
                    source_url = "https://katalon-collections.github.io"
            else:
                filename = f"{idno.lower()}-specimen.jpg"
                key = storage_key(file_id, filename)
                dest = storage_path(key)
                generate_plate_image(dest, idno, obj.metadata_.get("label", idno), obj.object_type or "sammlungsobjekt")
                license_name = "CC0"
                source_url = "https://katalon-collections.github.io"

            mime_type = verified_image_mime(dest)
            db.add(MediaFile(
                id=file_id,
                object_id=obj.id,
                filename=filename,
                mime_type=mime_type,
                storage_key=key,
                status="pending",
                is_primary=True,
                license_uri=CC0 if license_name == "CC0" else PD_MARK,
                rights_holder={"name": f"{license_name}; Katalon Demo", "uri": source_url},
            ))
            media_ids.append(file_id)

    await db.commit()
    logger.info("Created %d MediaFile records.", len(media_ids))

    if not no_iiif:
        try:
            for media_id in media_ids:
                generate_iiif_tiles.delay(str(media_id))
            logger.info("Enqueued IIIF tile generation for %d images.", len(media_ids))
        except Exception as exc:
            logger.warning("Notice: IIIF generation not enqueued (%s)", exc)


# ---------------------------------------------------------------------------
# Seed Specifications
# ---------------------------------------------------------------------------

SUBTYPES_SPECS = [
    ("object", "sammlungsobjekt", {"de": "Sammlungsobjekt", "en": "Collection Object"}, True),
    ("object", "gemaelde", {"de": "Gemälde", "en": "Painting"}, False),
    ("object", "druckgrafik", {"de": "Druckgrafik", "en": "Print"}, False),
    ("object", "handschrift", {"de": "Handschrift / Autograph", "en": "Manuscript / Autograph"}, False),
    ("object", "fotografie", {"de": "Fotografie", "en": "Photograph"}, False),
    ("object", "skulptur", {"de": "Skulptur / Plastik", "en": "Sculpture"}, False),
    ("object", "archivalie", {"de": "Archivalie / Druckwerk", "en": "Archival Record"}, False),
    ("object", "kunsthandwerk", {"de": "Kunsthandwerk & Relikt", "en": "Decorative Art"}, False),
    ("object", "mineral", {"de": "Mineral & Belegstück", "en": "Mineral Specimen"}, False),
    ("entity", "person", {"de": "Person", "en": "Person"}, True),
    ("entity", "organisation", {"de": "Organisation", "en": "Organization"}, False),
    ("place", "ort", {"de": "Ort", "en": "Place"}, True),
    ("place", "bauwerk", {"de": "Bauwerk / Struktur", "en": "Building / Structure"}, False),
    ("occurrence", "werk", {"de": "Werk", "en": "Work"}, True),
    ("occurrence", "ereignis", {"de": "Ereignis", "en": "Event"}, False),
    ("occurrence", "ausstellung", {"de": "Ausstellung", "en": "Exhibition"}, False),
    ("procedure", "loan_out", {"de": "Leihverkehr ausgehend", "en": "Loan Out"}, True),
    ("procedure", "loan_in", {"de": "Leihverkehr eingehend", "en": "Loan In"}, False),
    ("procedure", "acquisition", {"de": "Erwerbung", "en": "Acquisition"}, False),
    ("procedure", "conservation", {"de": "Konservierung / Restaurierung", "en": "Conservation"}, False),
    ("procedure", "object_entry", {"de": "Objekteingang", "en": "Object Entry"}, False),
    ("procedure", "deaccession", {"de": "Deakzessionierung", "en": "Deaccession"}, False),
    ("collection", "bestand", {"de": "Bestand", "en": "Fonds / Holding"}, True),
    ("collection", "sammlung", {"de": "Sammlung", "en": "Collection"}, False),
    ("collection", "nachlass", {"de": "Nachlass", "en": "Personal Papers"}, False),
    ("collection", "konvolut", {"de": "Konvolut / Serie", "en": "Series / Bundle"}, False),
    ("storage_location", "gebaeude", {"de": "Gebäude", "en": "Building"}, True),
    ("storage_location", "raum", {"de": "Raum / Magazin", "en": "Room / Storage Area"}, False),
    ("storage_location", "regal", {"de": "Regal", "en": "Shelf / Rack"}, False),
    ("storage_location", "schrank", {"de": "Schrank", "en": "Cabinet"}, False),
    ("storage_location", "fach", {"de": "Fach / Boden", "en": "Compartment / Shelf"}, False),
    ("storage_location", "lade", {"de": "Lade / Schublade", "en": "Drawer"}, False),
]

PLACES_DATA = [
    ("weimar", "Weimar", "residenzstadt", "99423", True, "-0975", 6000, 50.9795, 11.3235, "2812482"),
    ("jena", "Jena", "universitaetsstadt", "07743", False, "0852", 4500, 50.9271, 11.5892, "2895992"),
    ("frankfurt", "Frankfurt am Main", "handelsstadt", "60311", False, "0794", 30000, 50.1109, 8.6821, "2925533"),
    ("rom", "Rom", "residenzstadt", "00184", False, "-0753", 160000, 41.9028, 12.4964, "3169070"),
    ("strassburg", "Straßburg", "handelsstadt", "67000", False, "0012", 25000, 48.5734, 7.7521, "2973783"),
    ("leipzig", "Leipzig", "handelsstadt", "04109", False, "1015", 32000, 51.3397, 12.3731, "2879139"),
    ("karlsbad", "Karlsbad", "kurort", "36001", False, "1370", 3000, 50.2327, 12.8712, "3073803"),
    ("ilmenau", "Ilmenau", "bergbaustadt", "98693", False, "1273", 2000, 50.6872, 10.9142, "2895044"),
    ("stuttgart", "Stuttgart", "residenzstadt", "70173", False, "0950", 22000, 48.7758, 9.1829, "2825297"),
    ("zuerich", "Zürich", "handelsstadt", "8001", False, "-0015", 11000, 47.3769, 8.5417, "2657896"),
    ("paris", "Paris", "residenzstadt", "75001", False, "-0052", 600000, 48.8566, 2.3522, "2988507"),
    ("dornburg", "Dornburger Schlösser", "bauwerk", "07778", False, "0937", 800, 51.0069, 11.6667, "2935299"),
]

ENTITIES_DATA = [
    ("goethe", "Johann Wolfgang von Goethe", "person", "1749-08-28", "1832-03-22", "Dichter, Naturforscher, Staatsmann", "frankfurt", "weimar", "118540238", "24602065"),
    ("schiller", "Friedrich Schiller", "person", "1759-11-10", "1805-05-09", "Dichter, Dramatiker, Historiker", "stuttgart", "weimar", "118607621", "96869510"),
    ("herder", "Johann Gottfried Herder", "person", "1744-08-25", "1803-12-18", "Theologe, Philosoph, Dichter", None, "weimar", "118549553", "95156208"),
    ("wieland", "Christoph Martin Wieland", "person", "1733-09-05", "1813-01-20", "Dichter, Übersetzer, Aufklärer", None, "weimar", "118632477", "98144414"),
    ("tischbein", "Johann Heinrich Wilhelm Tischbein", "person", "1751-02-15", "1829-06-26", "Maler, Porträtist", None, None, "118622896", "24716766"),
    ("stieler", "Joseph Karl Stieler", "person", "1781-11-01", "1858-04-09", "Hofmaler, Porträtist", None, None, "118755285", "32773249"),
    ("schadow", "Johann Gottfried Schadow", "person", "1764-05-20", "1850-01-27", "Bildhauer, Grafiker", None, None, "118606115", "62008432"),
    ("trippel", "Alexander Trippel", "person", "1744-09-23", "1793-09-24", "Bildhauer des Klassizismus", None, "rom", "118802777", "28372728"),
    ("cotta", "Johann Friedrich Cotta", "person", "1764-04-27", "1832-12-29", "Verleger, Industriepionier", "stuttgart", "stuttgart", "11852240X", "34479906"),
    ("anna-amalia", "Herzogin Anna Amalia von Sachsen-Weimar-Eisenach", "person", "1739-10-24", "1807-04-10", "Herzogin, Mäzenin, Komponistin", None, "weimar", "118649485", "46907409"),
    ("carl-august", "Großherzog Carl August von Sachsen-Weimar-Eisenach", "person", "1757-09-03", "1828-06-14", "Großherzog, Förderer der Klassik", "weimar", None, "11856014X", "62067746"),
    ("corona-schroeter", "Corona Schröter", "person", "1751-01-14", "1802-08-23", "Sängerin, Schauspielerin, Komponistin", "leipzig", "ilmenau", "11876005X", "12417124"),
    ("eckermann", "Johann Peter Eckermann", "person", "1792-09-21", "1854-12-03", "Dichter, Vertrauter Goethes", None, "weimar", "118528777", "29567378"),
    ("schroeter-atelier", "Atelier Schröter Weimar", "organisation", "1860", "1920", "Hoffotograf-Atelier", "weimar", "weimar", "108605333X", "131498721"),
    ("cotta-verlag", "J.G. Cotta'sche Buchhandlung", "organisation", "1659", "1953", "Literarischer Traditionsverlag", "stuttgart", "stuttgart", "2016259-2", "143890211"),
    ("kunsthaus-zuerich", "Kunsthaus Zürich", "organisation", "1910", None, "Museum & Kunstgesellschaft", "zuerich", "zuerich", "1007689-5", "125867123"),
    ("bnf-paris", "Bibliothèque nationale de France", "organisation", "1368", None, "Nationalbibliothek Frankreichs", "paris", "paris", "123830378", "137532321"),
    ("rest-zentrum", "Thüringisches Restaurierungszentrum", "organisation", "1994", None, "Zentrale Konservierungswerkstatt", "weimar", "weimar", "5155122-1", "154982121"),
]

OCCURRENCES_DATA = [
    ("faust", "Faust. Eine Tragödie", "werk", "1808", "drama", "goethe", None, "weimar", 5),
    ("raeuber", "Die Räuber", "werk", "1781", "drama", "schiller", None, "jena", 5),
    ("werther", "Die Leiden des jungen Werthers", "werk", "1774", "roman", "goethe", None, "frankfurt", 1),
    ("roemische-elegien", "Römische Elegien", "werk", "1790", "gedichtzyklus", "goethe", None, "rom", 1),
    ("ideen-geschichte", "Ideen zur Philosophie der Geschichte der Menschheit", "werk", "1791", "abhandlung", "herder", None, "weimar", 4),
    ("farbenlehre", "Zur Farbenlehre", "werk", "1810", "abhandlung", "goethe", None, "weimar", 2),
    ("iphigenie", "Iphigenie auf Tauris", "werk", "1787", "drama", "goethe", None, "weimar", 5),
    ("italien-reise", "Goethes Italienische Reise (1786–1788)", "ereignis", "1786", "reise", "goethe", None, "rom", 1),
    ("weimarer-theater", "Gründung und Ära des Weimarer Hoftheaters", "ereignis", "1791", "ausstellung", "goethe", None, "weimar", 1),
    ("jubilaeum-1932", "Goethe-Gedächtnisausstellung 1932", "ausstellung", "1932", "ausstellung", None, None, "weimar", 1),
]

COLLECTIONS_DATA = [
    ("col-01", None, "bestand", "Bestand Weimarer Klassik", "Umfasst literarische, bildkünstlerische und biografische Zeugnisse der Weimarer Klassiker."),
    ("col-01-a", "col-01", "nachlass", "Dichter-Nachlässe & Autographen", "Handschriftliche Briefe, Tagebuchblätter, Werkentwürfe und Urkunden."),
    ("col-01-b", "col-01", "sammlung", "Bildende Kunst & Bildnisse", "Porträtgemälde, Druckgrafik, Scherenschnitte und Skulpturen."),
    ("col-01-c", "col-01", "konvolut", "Theater- & Bühnendokumente", "Theaterzettel, Rollenhefte, Programmankündigungen und Kostümskizzen."),
    ("col-02", None, "bestand", "Naturwissenschaft & Sammlungsgeschichte", "Goethes mineralogische Studien, wissenschaftliche Instrumente und Belege."),
    ("col-02-a", "col-02", "sammlung", "Mineralogisch-Geologisches Kabinett", "Gesteinsstufen, Belegstücke und Funde aus Thüringen, Böhmen und Italien."),
    ("col-02-b", "col-02", "sammlung", "Wissenschaftliche Instrumente", "Prismen, optische Gläser, Barometer und Sezierbesteck."),
    ("col-02-c", "col-02", "sammlung", "Historische Fachbibliothek", "Erstausgaben naturphilosophischer und optischer Traktate."),
]

STORAGE_LOCATIONS_DATA = [
    ("loc-depot-a", None, "gebaeude", "Zentraldepot Klassik (Kupferberg)", "Hauptlager für Kunst, Textil und Papierbestände."),
    ("loc-restaur", None, "gebaeude", "Restaurierungszentrum Thüringen", "Werkstätten und Untersuchungsräume."),
    ("loc-depot-a-r1", "loc-depot-a", "raum", "Magazin 1 (Gemälde & Plastik)", "Klimatisierter Raum für Tafelbilder und Büsten."),
    ("loc-depot-a-r2", "loc-depot-a", "raum", "Magazin 2 (Grafik & Autographen)", "Dunkelmagazin für lichtempfindliche Papiere."),
    ("loc-depot-a-r3", "loc-depot-a", "raum", "Magazin 3 (Mineralogie)", "Schwerlastraum für Gesteine und Fossilien."),
    ("loc-restaur-atel", "loc-restaur", "raum", "Atelier Papierrestaurierung", "Klimatisiertes Fachatelier."),
    ("loc-restaur-quar", "loc-restaur", "raum", "Quarantäne- & Begasungskammer", "Eingangsüberprüfung Neuzugänge."),
    ("loc-depot-a-r1-gg01", "loc-depot-a-r1", "regal", "Gemäldegitteranlage GG-01", "Fahrbare Gitterwände."),
    ("loc-depot-a-r1-sk01", "loc-depot-a-r1", "regal", "Schwerlastpodest Skulpturen SK-01", "Podeste für Marmor- und Gipsbüsten."),
    ("loc-depot-a-r2-pk01", "loc-depot-a-r2", "schrank", "Plankammerschrank PK-01", "Flachlagerschrank für Grafiken."),
    ("loc-depot-a-r2-ar01", "loc-depot-a-r2", "regal", "Archivregalanlage AR-01", "Archivregal für Kassetten."),
    ("loc-depot-a-r3-vk01", "loc-depot-a-r3", "schrank", "Vitrinenschrank Mineralien VK-01", "Schränke mit Holzeinteilung."),
    ("loc-depot-a-r1-gg01-f1", "loc-depot-a-r1-gg01", "fach", "Gemäldezug Wand A1", "Gitterfeld A1."),
    ("loc-depot-a-r1-gg01-f2", "loc-depot-a-r1-gg01", "fach", "Gemäldezug Wand A2", "Gitterfeld A2."),
    ("loc-depot-a-r2-pk01-l1", "loc-depot-a-r2-pk01", "lade", "Flachlade 01 (Großformate)", "Säurefreie Mappen."),
    ("loc-depot-a-r2-pk01-l2", "loc-depot-a-r2-pk01", "lade", "Flachlade 02 (Kupferstiche)", "Kupferstich-Konvolute."),
    ("loc-depot-a-r2-ar01-k1", "loc-depot-a-r2-ar01", "fach", "Kassette / Fach K-101", "Briefkonvolute Goethe."),
]

PROCEDURES_DATA = [
    (
        "proc-loan-out-01", "loan_out", "active", "2026-03-01", "2026-10-31", "2026-11-15", "LV-2026/042-ZH",
        "Ausleihe an Kunsthaus Zürich für Sonderausstellung 'Goethes Italien'.",
        "kunsthaus-zuerich", "zuerich", 450000.0, ["OBJ-008", "OBJ-009", "OBJ-010"]
    ),
    (
        "proc-loan-in-01", "loan_in", "active", "2026-01-15", "2026-12-31", "2027-01-15", "EG-2026/011-BNF",
        "Eingehende Leihgabe von der Bibliothèque nationale de France für Weimarer Jubiläum.",
        "bnf-paris", "paris", 320000.0, ["OBJ-091", "OBJ-092"]
    ),
    (
        "proc-cons-01", "conservation", "active", "2026-08-01", "2026-12-15", "2026-12-20", "REST-2026/08",
        "Papierentsäuerung und Rissverleimung an Farbenlehre-Tafeln.",
        "rest-zentrum", "weimar", 12000.0, ["OBJ-035"]
    ),
    (
        "proc-cons-02", "conservation", "completed", "2025-02-01", "2025-06-30", "2025-07-01", "REST-2025/02",
        "Firnisabnahme und Retusche am Stieler-Porträt Johann Wolfgang von Goethe.",
        "rest-zentrum", "weimar", 8500.0, ["OBJ-001"]
    ),
    (
        "proc-acq-01", "acquisition", "completed", "1924-05-10", "1924-06-01", "1924-06-15", "ERW-1924/001",
        "Ankauf Nachlassbriefe Goethe-Schiller aus Familienbesitz Cotta.",
        "cotta", "stuttgart", 25000.0, ["OBJ-021", "OBJ-022", "OBJ-023"]
    ),
    (
        "proc-entry-01", "object_entry", "draft", "2026-09-01", None, "2026-10-31", "EING-2026/09",
        "Neuzugänge aus Nachlass-Sichtung Eckermann zur Inventarisierung.",
        "eckermann", "weimar", 5000.0, ["OBJ-098", "OBJ-099", "OBJ-100"]
    ),
    (
        "proc-deac-01", "deaccession", "completed", "2024-01-10", "2024-03-20", "2024-03-31", "DEAC-2024/01",
        "Rückgabe Dublette Hofporzellan an Partner-Museum im Rahmen von Bereinigung.",
        None, "weimar", 1500.0, ["OBJ-080"]
    ),
    (
        "proc-loan-out-02", "loan_out", "draft", "2027-05-01", "2027-11-30", "2027-12-15", "LV-2027/PLAN-01",
        "Geplante Ausleihe der Schadow-Büste für Marbacher Schiller-Schau.",
        None, "stuttgart", 120000.0, ["OBJ-052"]
    ),
]


def build_object_specs() -> list[dict[str, Any]]:
    """Build specs for 100 realistic, richly connected museum objects across 10 clusters."""
    specs: list[dict[str, Any]] = []

    def add(
        i: int,
        title: str,
        subtype: str,
        material: str,
        technik: str,
        masse: str,
        datierung: str,
        *,
        author: str | None = None,
        depicted: str | None = None,
        place: str | None = None,
        occ: str | None = None,
        col: str = "col-01",
        norm_loc: str = "loc-depot-a-r1-gg01-f1",
        curr_loc: str | None = None,
        status: str = "public",
        col_status: str = "active",
        ausgestellt: bool = False,
        restaurierung: bool = False,
        zustand: str = "gut",
        gewicht_g: float = 500.0,
        part_of: str | None = None,
        pendant_to: str | None = None,
        coords: str | None = None,
    ) -> None:
        specs.append({
            "index": i,
            "idno": f"OBJ-{i:03d}",
            "title": title,
            "subtype": subtype,
            "material": material,
            "technik": technik,
            "masse": masse,
            "datierung": datierung,
            "author": author,
            "depicted": depicted,
            "place": place,
            "occ": occ,
            "col": col,
            "norm_loc": norm_loc,
            "curr_loc": curr_loc,
            "status": status,
            "col_status": col_status,
            "ausgestellt": ausgestellt,
            "restaurierung": restaurierung,
            "zustand": zustand,
            "gewicht_g": gewicht_g,
            "part_of": part_of,
            "pendant_to": pendant_to,
            "coords": coords,
        })

    # Cluster 1: Porträtmalerei & Gemälde (001 - 010)
    add(1, "Bildnis Johann Wolfgang von Goethe im Alter", "gemaelde", "leinwand", "oelmalerei", "78 x 64 cm", "1828", author="stieler", depicted="goethe", place="weimar", occ="faust", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f1", ausgestellt=True, zustand="sehr_gut", gewicht_g=4200.0)
    add(2, "Porträt Friedrich Schiller", "gemaelde", "leinwand", "oelmalerei", "72 x 58 cm", "1794", author="stieler", depicted="schiller", place="jena", occ="raeuber", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f1", ausgestellt=True, zustand="gut", gewicht_g=3800.0)
    add(3, "Porträt Johann Gottfried Herder", "gemaelde", "leinwand", "oelmalerei", "75 x 60 cm", "1800", author="stieler", depicted="herder", place="weimar", occ="ideen-geschichte", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f1", zustand="gut", gewicht_g=3900.0)
    add(4, "Bildnis Herzogin Anna Amalia von Sachsen-Weimar", "gemaelde", "leinwand", "oelmalerei", "82 x 65 cm", "1795", author="tischbein", depicted="anna-amalia", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f1", ausgestellt=True, zustand="sehr_gut", gewicht_g=4500.0)
    add(5, "Großherzog Carl August zu Pferde", "gemaelde", "leinwand", "oelmalerei", "120 x 95 cm", "1815", author="tischbein", depicted="carl-august", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", zustand="gut", gewicht_g=8500.0)
    add(6, "Corona Schröter als Iphigenie auf Tauris", "gemaelde", "leinwand", "oelmalerei", "90 x 70 cm", "1782", author="tischbein", depicted="corona-schroeter", place="weimar", occ="iphigenie", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", ausgestellt=True, zustand="gut", gewicht_g=5100.0)
    add(7, "Christoph Martin Wieland im Gelehrtenrock", "gemaelde", "leinwand", "oelmalerei", "70 x 55 cm", "1794", author="stieler", depicted="wieland", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", zustand="gut", gewicht_g=3400.0)
    add(8, "Goethe in der römischen Campagna", "gemaelde", "leinwand", "oelmalerei", "164 x 206 cm", "1787", author="tischbein", depicted="goethe", place="rom", occ="italien-reise", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", col_status="on_loan_out", zustand="sehr_gut", gewicht_g=18000.0)
    add(9, "Italienische Landschaft bei Olevano", "gemaelde", "leinwand", "oelmalerei", "65 x 85 cm", "1788", author="tischbein", place="rom", occ="italien-reise", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", col_status="on_loan_out", pendant_to="OBJ-010", zustand="gut", gewicht_g=4300.0)
    add(10, "Rast vor der römischen Osteria", "gemaelde", "leinwand", "oelmalerei", "65 x 85 cm", "1788", author="tischbein", place="rom", occ="italien-reise", col="col-01-b", norm_loc="loc-depot-a-r1-gg01-f2", col_status="on_loan_out", pendant_to="OBJ-009", zustand="gut", gewicht_g=4400.0)

    # Cluster 2: Druckgrafik & Radierungen (011 - 020)
    add(11, "Ansicht des Weimarer Residenzschlosses vom Park", "druckgrafik", "buetten", "kupferstich", "32 x 45 cm", "1800", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l1", zustand="gut", gewicht_g=120.0)
    add(12, "Faust in seinem Studierzimmer vor der Erdgeist-Erscheinung", "druckgrafik", "buetten", "radierung", "28 x 21 cm", "1790", occ="faust", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l1", ausgestellt=True, zustand="sehr_gut", gewicht_g=85.0)
    add(13, "Das Forum Romanum mit dem Titusbogen", "druckgrafik", "buetten", "radierung", "42 x 60 cm", "1775", place="rom", occ="italien-reise", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l1", zustand="gut", gewicht_g=210.0)
    add(14, "Ansicht des Straßburger Münsters aus Südwest", "druckgrafik", "karton", "kupferstich", "50 x 38 cm", "1772", place="strassburg", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l1", zustand="gut", gewicht_g=190.0)
    add(15, "Schattenriss von Goethe im Profil mit Lorbeerkranz", "druckgrafik", "papier", "scherenschnitt", "18 x 14 cm", "1776", depicted="goethe", place="frankfurt", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="sehr_gut", gewicht_g=45.0)
    add(16, "Schillers Flucht aus Stuttgart nach Mannheim", "druckgrafik", "buetten", "kupferstich", "26 x 34 cm", "1782", depicted="schiller", place="stuttgart", occ="raeuber", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=95.0)
    add(17, "Kupferstich der Dornburger Schlösser über der Saale", "druckgrafik", "karton", "kupferstich", "24 x 36 cm", "1828", place="dornburg", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="sehr_gut", gewicht_g=110.0)
    add(18, "Illustration zu Werthers Leiden: Lotte am Klavier", "druckgrafik", "buetten", "kupferstich", "20 x 16 cm", "1776", author="tischbein", occ="werther", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=60.0)
    add(19, "Bühnenbildentwurf zum Weimarer Hoftheater: Iphigenie-Hain", "druckgrafik", "buetten", "aquarell", "35 x 48 cm", "1802", place="weimar", occ="iphigenie", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="gut", gewicht_g=140.0)
    add(20, "Allegorisches Gedenkblatt zum Bund von Goethe und Schiller", "druckgrafik", "buetten", "radierung", "30 x 24 cm", "1798", author="tischbein", depicted="goethe", place="jena", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="sehr_gut", gewicht_g=90.0)

    # Cluster 3: Handschriften & Autographen (021 - 030)
    add(21, "Brief Goethe an Schiller über den Balladen-Almanach", "handschrift", "buetten", "handschrift", "22 x 18 cm", "1798-01-06", author="goethe", place="weimar", occ="faust", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="sehr_gut", gewicht_g=15.0)
    add(22, "Antwortbrief Schiller an Goethe mit Strophenentwurf", "handschrift", "buetten", "handschrift", "22 x 18 cm", "1798-01-12", author="schiller", place="jena", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="sehr_gut", gewicht_g=15.0)
    add(23, "Manuskriptseite aus Faust II: Helena-Auftritt", "handschrift", "buetten", "handschrift", "34 x 21 cm", "1827", author="goethe", place="weimar", occ="faust", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=20.0)
    add(24, "Forschungsnotizen zur Farbenlehre mit Skizzen", "handschrift", "buetten", "handschrift", "21 x 17 cm", "1805", author="goethe", place="weimar", occ="farbenlehre", col="col-02-b", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=25.0)
    add(25, "Brief Schillers an Verleger Cotta bezüglich der Horen", "handschrift", "buetten", "handschrift", "24 x 19 cm", "1795-04-18", author="schiller", place="jena", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=18.0)
    add(26, "Tagebuchblatt Goethe aus Rom über antike Skulpturen", "handschrift", "buetten", "handschrift", "20 x 16 cm", "1787-03-02", author="goethe", place="rom", occ="italien-reise", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=12.0)
    add(27, "Manuskriptentwurf Herder: Über den Ursprung der Sprache", "handschrift", "buetten", "handschrift", "32 x 20 cm", "1770", author="herder", place="strassburg", occ="ideen-geschichte", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="stabil_maengel", gewicht_g=30.0)
    add(28, "Gedichtautograph Goethe: Wanderers Nachtlied auf Papier", "handschrift", "buetten", "handschrift", "16 x 11 cm", "1780", author="goethe", place="ilmenau", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=8.0)
    add(29, "Eckermanns Gesprächsnotizbuch mit Goethe", "handschrift", "papier", "handschrift", "19 x 12 cm", "1824", author="eckermann", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=140.0)
    add(30, "Brief Wielands an Herzogin Anna Amalia aus Tiefurt", "handschrift", "buetten", "handschrift", "23 x 18 cm", "1785", author="wieland", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=14.0)

    # Cluster 4: Buchdruck & Erstausgaben (031 - 040)
    add(31, "Erstausgabe: Faust. Eine Tragödie von Goethe", "archivalie", "papier", "buchdruck", "16 x 10 cm", "1808", author="goethe", place="weimar", occ="faust", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=320.0)
    add(32, "Erstausgabe: Die Räuber. Ein Schauspiel von Schiller", "archivalie", "papier", "buchdruck", "17 x 11 cm", "1781", author="schiller", place="frankfurt", occ="raeuber", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="gut", gewicht_g=280.0)
    add(33, "Erstausgabe: Die Leiden des jungen Werthers", "archivalie", "papier", "buchdruck", "16 x 10 cm", "1774", author="goethe", place="leipzig", occ="werther", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="sehr_gut", gewicht_g=290.0)
    add(34, "Prachtausgabe: Römische Elegien mit Kupfern", "archivalie", "buetten", "buchdruck", "28 x 22 cm", "1795", author="goethe", place="rom", occ="roemische-elegien", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="sehr_gut", gewicht_g=750.0)
    add(35, "Zur Farbenlehre: Band I & II mit Kolorierten Tafeln", "archivalie", "papier", "buchdruck", "24 x 19 cm", "1810", author="goethe", place="weimar", occ="farbenlehre", col="col-02-c", norm_loc="loc-depot-a-r2-ar01-k1", curr_loc="loc-restaur-atel", status="internal", restaurierung=True, zustand="restaurierungsbeduerftig", gewicht_g=1600.0)
    add(36, "Wielands Sämmtliche Werke: Prachtausgabe Band 1", "archivalie", "buetten", "buchdruck", "26 x 20 cm", "1794", author="wieland", place="leipzig", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=980.0)
    add(37, "Die Horen: Erster Jahrgang 1795 im Halblederband", "archivalie", "papier", "buchdruck", "20 x 12 cm", "1795", author="schiller", place="jena", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=620.0)
    add(38, "Musen-Almanach für das Jahr 1797 (Xenien-Almanach)", "archivalie", "papier", "buchdruck", "14 x 9 cm", "1796", author="schiller", place="jena", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=180.0)
    add(39, "Herders Volkslieder: Stimmen der Völker in Liedern", "archivalie", "papier", "buchdruck", "17 x 11 cm", "1778", author="herder", place="leipzig", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=340.0)
    add(40, "West-oestlicher Divan: Erstausgabe im Originaleinband", "archivalie", "papier", "buchdruck", "18 x 11 cm", "1819", author="goethe", place="stuttgart", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="sehr_gut", gewicht_g=410.0)

    # Cluster 5: Historische Fotografie (041 - 050)
    add(41, "Fotografie: Goethes Gartenhaus am Ilmpark", "fotografie", "karton", "albuminabzug", "18 x 24 cm", "1875", author="schroeter-atelier", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="gut", gewicht_g=120.0)
    add(42, "Fotografie: Schillerhaus an der Weimarer Esplanade", "fotografie", "karton", "albuminabzug", "18 x 24 cm", "1880", author="schroeter-atelier", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=115.0)
    add(43, "Kollodium-Glasnegativ: Weimarer Marktplatz mit Cranachhaus", "fotografie", "glasnegativ", "kollodium", "13 x 18 cm", "1890", author="schroeter-atelier", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=180.0)
    add(44, "Fotografie: Goethes Arbeitszimmer am Frauenplan", "fotografie", "papier", "silbergelatine", "20 x 26 cm", "1885", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="sehr_gut", gewicht_g=95.0)
    add(45, "Kollodium-Glasnegativ: Goethe- und Schiller-Denkmal", "fotografie", "glasnegativ", "kollodium", "18 x 24 cm", "1870", author="schroeter-atelier", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=340.0)
    add(46, "Fotografie: Schloss Tiefurt Sommerresidenz Anna Amalias", "fotografie", "karton", "albuminabzug", "16 x 22 cm", "1888", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=110.0)
    add(47, "Fotografie: Großer Rokokosaal der Herzogin Anna Amalia Bibliothek", "fotografie", "papier", "silbergelatine", "24 x 30 cm", "1895", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="sehr_gut", gewicht_g=130.0)
    add(48, "Porträtfoto: Hofschauspieler Heinrich Becker als Faust", "fotografie", "karton", "albuminabzug", "14 x 10 cm", "1892", author="schroeter-atelier", place="weimar", occ="faust", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=50.0)
    add(49, "Kollodium-Glasnegativ: Historische Saalebrücke bei Jena", "fotografie", "glasnegativ", "kollodium", "13 x 18 cm", "1885", place="jena", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=175.0)
    add(50, "Gruppenfotografie: Versammlung der Goethe-Gesellschaft 1899", "fotografie", "karton", "silbergelatine", "22 x 28 cm", "1899", author="schroeter-atelier", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-pk01-l2", zustand="sehr_gut", gewicht_g=140.0)

    # Cluster 6: Skulpturen & Plastiken (051 - 060)
    add(51, "Marmorbüste Johann Wolfgang von Goethe im antiken Stil", "skulptur", "marmor", "meisselung", "72 x 45 x 38 cm", "1788", author="trippel", depicted="goethe", place="rom", occ="italien-reise", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=65000.0)
    add(52, "Porträtbüste Friedrich Schiller in Gips", "skulptur", "gips", "abguss", "68 x 42 x 34 cm", "1804", author="schadow", depicted="schiller", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=18000.0)
    add(53, "Totenmaske Johann Wolfgang von Goethe", "skulptur", "gips", "abguss", "26 x 18 x 14 cm", "1832", depicted="goethe", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", ausgestellt=True, zustand="gut", gewicht_g=2800.0)
    add(54, "Schiller-Totenmaske im Profilabguss", "skulptur", "gips", "abguss", "24 x 17 x 13 cm", "1805", depicted="schiller", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=2500.0)
    add(55, "Reliefmedaillon Herzogin Anna Amalia in Terrakotta", "skulptur", "terrakotta", "abguss", "35 x 35 x 6 cm", "1780", depicted="anna-amalia", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=4200.0)
    add(56, "Bronzestatuette: Goethe und Schiller Modellgruppe", "skulptur", "bronze", "bronzeguss", "48 x 28 x 22 cm", "1855", depicted="goethe", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=14500.0)
    add(57, "Marmorbüste Christoph Martin Wieland", "skulptur", "marmor", "meisselung", "65 x 40 x 30 cm", "1805", author="schadow", depicted="wieland", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="sehr_gut", gewicht_g=58000.0)
    add(58, "Gipsbüste Johann Gottfried Herder", "skulptur", "gips", "abguss", "70 x 44 x 32 cm", "1790", author="trippel", depicted="herder", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=19500.0)
    add(59, "Modellfigur: Sitzender Goethe im Hausmantel", "skulptur", "terrakotta", "abguss", "38 x 22 x 20 cm", "1820", depicted="goethe", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=6200.0)
    add(60, "Marmorbüste Großherzog Carl August", "skulptur", "marmor", "meisselung", "74 x 48 x 36 cm", "1818", depicted="carl-august", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="sehr_gut", gewicht_g=68000.0)

    # Cluster 7: Theaterzettel & Bühnendokumente (061 - 070)
    add(61, "Theaterzettel: Uraufführung Schillers 'Die Räuber'", "archivalie", "papier", "buchdruck", "32 x 20 cm", "1782-01-13", author="schiller", place="jena", occ="raeuber", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="gut", gewicht_g=25.0)
    add(62, "Theaterzettel: Goethes Iphigenie im Hoftheater Weimar", "archivalie", "papier", "buchdruck", "30 x 19 cm", "1779-04-06", author="goethe", depicted="corona-schroeter", place="weimar", occ="iphigenie", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="sehr_gut", gewicht_g=22.0)
    add(63, "Theaterzettel: Erste geschlossene Faust-I-Aufführung", "archivalie", "papier", "buchdruck", "34 x 21 cm", "1829-01-19", author="goethe", place="weimar", occ="faust", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="sehr_gut", gewicht_g=28.0)
    add(64, "Handschriftliches Rollenheft Corona Schröters zur Iphigenie", "handschrift", "buetten", "handschrift", "21 x 16 cm", "1779", author="corona-schroeter", place="weimar", occ="iphigenie", col="col-01-c", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=65.0)
    add(65, "Programmzettel: Festliche Wiedereröffnung Weimarer Hoftheater", "archivalie", "papier", "buchdruck", "28 x 18 cm", "1825", place="weimar", occ="weimarer-theater", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=20.0)
    add(66, "Figurinen-Aquarell: Mephistopheles Kostümentwurf", "druckgrafik", "buetten", "aquarell", "26 x 18 cm", "1829", place="weimar", occ="faust", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", ausgestellt=True, zustand="sehr_gut", gewicht_g=40.0)
    add(67, "Historisches Theaterbillet Hofloge Nr. 4 im Hoftheater", "archivalie", "karton", "kupferstich", "8 x 12 cm", "1805", place="weimar", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=10.0)
    add(68, "Plakat zur Weimarer Schiller-Gedächtnisfeier 1859", "archivalie", "papier", "buchdruck", "60 x 42 cm", "1859", place="weimar", occ="raeuber", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l1", zustand="gut", gewicht_g=85.0)
    add(69, "Theaterzettel zur Wallenstein-Trilogie Uraufführung", "archivalie", "papier", "buchdruck", "31 x 20 cm", "1798", author="schiller", place="weimar", col="col-01-c", norm_loc="loc-depot-a-r2-pk01-l2", zustand="gut", gewicht_g=24.0)
    add(70, "Soufflierbuch zu Goethes Trauerspiel Egmont", "handschrift", "papier", "handschrift", "22 x 17 cm", "1796", author="goethe", place="weimar", col="col-01-c", norm_loc="loc-depot-a-r2-ar01-k1", zustand="stabil_maengel", gewicht_g=210.0)

    # Cluster 8: Kunsthandwerk & Relikte (071 - 080)
    add(71, "Goethes Reiseschreibpult aus Nussbaumholz", "kunsthandwerk", "nussbaum", "schnitzerei", "42 x 30 x 16 cm", "1786", author="goethe", place="frankfurt", occ="italien-reise", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=6200.0)
    add(72, "Schillers silberne Schnupftabakdose mit Wappengravur", "kunsthandwerk", "silber", "gravur", "9 x 6 x 2 cm", "1795", author="schiller", place="stuttgart", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=180.0)
    add(73, "Teetasse aus Weimarer Hofporzellan mit Tiefurt-Ansicht", "kunsthandwerk", "porzellan", "malerei", "7 x 10 x 10 cm", "1805", depicted="anna-amalia", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", zustand="gut", gewicht_g=220.0)
    add(74, "Petschaft Johann Wolfgang von Goethes mit Karneolstein", "kunsthandwerk", "gold", "gravur", "8 x 3 x 3 cm", "1782", author="goethe", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=95.0)
    add(75, "Goethes Lesebrille mit Hornfassung und Konvexgläsern", "kunsthandwerk", "kristallglas", "schliff", "12 x 4 x 2 cm", "1820", author="goethe", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="gut", gewicht_g=45.0)
    add(76, "Reiseschachspiel aus Buchsbaum- und Ebenholz", "kunsthandwerk", "eichenholz", "drechselarbeit", "24 x 24 x 4 cm", "1800", author="goethe", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=850.0)
    add(77, "Miniatur-Hausapotheke aus Goethes Wohnhaus", "kunsthandwerk", "eichenholz", "schreinerarbeit", "28 x 20 x 15 cm", "1810", author="goethe", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=2400.0)
    add(78, "Seidene Weste Friedrich Schillers mit Blütenstickerei", "kunsthandwerk", "seide", "stickerei", "56 x 44 cm", "1790", author="schiller", place="jena", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="gut", gewicht_g=310.0)
    add(79, "Spazierstock mit graviertem Elfenbeinknauf von Herder", "kunsthandwerk", "eichenholz", "schnitzerei", "92 x 4 x 4 cm", "1798", author="herder", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", zustand="gut", gewicht_g=480.0)
    add(80, "Fürstlicher Porzellanteller mit Weimarer Stadtwappen", "kunsthandwerk", "porzellan", "malerei", "24 x 24 x 3 cm", "1815", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", status="internal", col_status="deaccessioned", zustand="stabil_maengel", gewicht_g=520.0)

    # Cluster 9: Mineralogie & Naturwissenschaft (081 - 090)
    add(81, "Karlsbader Aragonit-Sprudelstein (Polierte Knolle)", "mineral", "aragonit", "schliff", "14 x 11 x 9 cm", "1807", author="goethe", place="karlsbad", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=680.0, coords="50.2327,12.8712")
    add(82, "Hämatit-Kristallstufe (Eisenglanz) aus Ilmenau", "mineral", "haematit", "naturform", "18 x 14 x 10 cm", "1785", author="goethe", place="ilmenau", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=1450.0, coords="50.6872,10.9142")
    add(83, "Bergkristall-Gruppe aus Goethes Mineralienkabinett", "mineral", "quarz", "naturform", "22 x 16 x 12 cm", "1790", author="goethe", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="sehr_gut", gewicht_g=2800.0)
    add(84, "Fossiler Ammonit aus dem fränkischen Jura", "mineral", "quarz", "naturform", "16 x 14 x 5 cm", "1792", author="goethe", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="gut", gewicht_g=1100.0)
    add(85, "Basalt-Handstück von der Burgruine Parkstein", "mineral", "basalt", "naturform", "12 x 8 x 6 cm", "1821", author="goethe", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="gut", gewicht_g=820.0)
    add(86, "Polierte Serpentinit-Platte aus Böhmen", "mineral", "aragonit", "schliff", "15 x 10 x 2 cm", "1812", author="goethe", place="karlsbad", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="sehr_gut", gewicht_g=640.0, coords="50.2327,12.8712")
    add(87, "Kupferglanz und Malachit auf Sandstein aus Ilmenau", "mineral", "haematit", "naturform", "11 x 9 x 7 cm", "1786", author="goethe", place="ilmenau", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="gut", gewicht_g=590.0, coords="50.6872,10.9142")
    add(88, "Fluorit-Stufe mit violetten Würfelkristallen", "mineral", "quarz", "naturform", "13 x 10 x 8 cm", "1798", author="carl-august", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", zustand="sehr_gut", gewicht_g=920.0)
    add(89, "Achatscheibe mit konzentrischer Bänderung", "mineral", "quarz", "schliff", "18 x 14 x 1 cm", "1815", author="goethe", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=510.0)
    add(90, "Meteoritenfragment von Stannern (Achondrit)", "mineral", "basalt", "naturform", "5 x 4 x 3 cm", "1808", author="goethe", place="weimar", col="col-02-a", norm_loc="loc-depot-a-r3-vk01", ausgestellt=True, zustand="sehr_gut", gewicht_g=84.0)

    # Cluster 10: Leihgaben, Neuzugänge, Vorbereitung (091 - 100)
    add(91, "Französische Werther-Handschrift aus Pariser Exil", "handschrift", "buetten", "handschrift", "24 x 18 cm", "1775", place="paris", occ="werther", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", col_status="on_loan_in", ausgestellt=True, zustand="sehr_gut", gewicht_g=110.0)
    add(92, "Historische Voltaire-Büste aus Bronze (Leihgabe Paris)", "skulptur", "bronze", "bronzeguss", "54 x 34 x 26 cm", "1780", place="paris", col="col-01-b", norm_loc="loc-depot-a-r1-sk01", col_status="on_loan_in", ausgestellt=True, zustand="sehr_gut", gewicht_g=28000.0)
    add(93, "Fragment eines unvollendeten Dramas Schillers (Demetrius)", "handschrift", "buetten", "handschrift", "22 x 17 cm", "1805", author="schiller", place="weimar", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", status="internal", zustand="fragmentarisch", gewicht_g=18.0)
    add(94, "Skizzenblatt mit Faust-Entwürfen und Versfragmenten", "druckgrafik", "papier", "aquarell", "28 x 21 cm", "1800", author="goethe", place="weimar", occ="faust", col="col-01-a", norm_loc="loc-depot-a-r2-pk01-l2", status="internal", zustand="gut", gewicht_g=16.0)
    add(95, "Korrespondenzkonvolut Cotta-Verlag an Friedrich Schiller", "archivalie", "papier", "handschrift", "25 x 19 cm", "1799", author="cotta", place="stuttgart", col="col-01-a", norm_loc="loc-depot-a-r2-ar01-k1", status="internal", zustand="gut", gewicht_g=340.0)
    add(96, "Goldmedaille zum 50-jährigen Regierungsjubiläum Carl Augusts", "kunsthandwerk", "gold", "praegung", "5 x 5 x 0.4 cm", "1825", depicted="carl-august", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=72.0)
    add(97, "Silberne Gedenkmünze auf das Ableben von Goethe 1832", "kunsthandwerk", "silber", "praegung", "4.5 x 4.5 x 0.3 cm", "1832", depicted="goethe", place="weimar", col="col-01-b", norm_loc="loc-depot-a-r2-ar01-k1", ausgestellt=True, zustand="sehr_gut", gewicht_g=38.0)
    add(98, "Unidentifiziertes Gelehrtenporträt aus Nachlass Eckermann", "gemaelde", "leinwand", "oelmalerei", "60 x 48 cm", "1810", place="weimar", col="col-01-b", norm_loc="loc-restaur-quar", status="draft", col_status="pending", zustand="stabil_maengel", gewicht_g=2900.0)
    add(99, "Notenautograph: Unbekannte Balladenvertonung", "handschrift", "buetten", "handschrift", "32 x 24 cm", "1820", place="weimar", col="col-01-c", norm_loc="loc-restaur-quar", status="draft", col_status="pending", zustand="stabil_maengel", gewicht_g=40.0)
    add(100, "Konvolut ungesichteter Notizzettel und Quittungen Eckermanns", "archivalie", "papier", "handschrift", "20 x 15 x 8 cm", "1830", author="eckermann", place="weimar", col="col-01-a", norm_loc="loc-restaur-quar", status="draft", col_status="pending", zustand="stabil_maengel", gewicht_g=620.0)

    return specs


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Katalon demo seed: 100 objects, all types and relations.")
    parser.add_argument("--skip-downloads", action="store_true", help="Generate all images locally via Pillow (offline mode).")
    parser.add_argument("--no-images", action="store_true", help="Skip media creation completely.")
    parser.add_argument("--no-iiif", action="store_true", help="Do not queue background IIIF tile pyramid generation.")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        admin_user_id = (
            await db.execute(select(User.id).where(User.role.in_(("admin", "superuser"))).limit(1))
        ).scalar_one_or_none()

        logger.info("Initializing RecordSubtypes...")
        existing_subtypes = {
            (r.primary_type, r.name)
            for r in (await db.execute(select(RecordSubtype))).scalars().all()
        }
        for ptype, name, label, is_default in SUBTYPES_SPECS:
            if (ptype, name) not in existing_subtypes:
                db.add(RecordSubtype(primary_type=ptype, name=name, label=label, is_default=is_default))
        await db.flush()

        logger.info("Enabling Authority Sources (GND, Geonames, VIAF)...")
        await db.execute(
            update(AuthoritySource).where(AuthoritySource.id.in_(("geonames", "viaf", "gnd"))).values(is_enabled=True)
        )

        logger.info("Creating Controlled Vocabularies...")
        await make_vocab(
            db, REL_VOCAB_NAME, "relation",
            [
                {"term": "normal_location", "label": {"de": "Heimatstandort", "en": "Normal Location"}, "inverse_label": {"de": "Beherbergt regulär", "en": "Houses normally"}, "applies_from": ["object"], "applies_to": ["storage_location"]},
                {"term": "current_location", "label": {"de": "Aktueller Standort", "en": "Current Location"}, "inverse_label": {"de": "Beherbergt aktuell", "en": "Houses currently"}, "applies_from": ["object"], "applies_to": ["storage_location"]},
                {"term": "member_of", "label": {"de": "Gehört zu Sammlung", "en": "Member of Collection"}, "inverse_label": {"de": "Enthält Objekt", "en": "Contains Object"}, "applies_from": ["object"], "applies_to": ["collection"]},
                {"term": "subject_of", "label": {"de": "Gegenstand von Vorgang", "en": "Subject of Procedure"}, "inverse_label": {"de": "Betrifft Objekt", "en": "Affects Object"}, "applies_from": ["procedure"], "applies_to": ["object"]},
                {"term": "geschaffen_von", "label": {"de": "geschaffen von", "en": "created by"}, "inverse_label": {"de": "schuf", "en": "created"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "fotografiert_von", "label": {"de": "fotografiert von", "en": "photographed by"}, "inverse_label": {"de": "fotografierte", "en": "photographed"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "abgebildete_person", "label": {"de": "abgebildete Person", "en": "depicted person"}, "inverse_label": {"de": "abgebildet in", "en": "depicted in"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "vorbesitzer", "label": {"de": "Vorbesitzer/in", "en": "previous owner"}, "inverse_label": {"de": "vormals besessen", "en": "formerly owned"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "restauriert_von", "label": {"de": "restauriert von", "en": "conserved by"}, "inverse_label": {"de": "restaurierte", "en": "conserved"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "hergestellt_in", "label": {"de": "hergestellt in", "en": "manufactured in"}, "inverse_label": {"de": "Herstellungsort von", "en": "place of manufacture of"}, "applies_from": ["object"], "applies_to": ["place"]},
                {"term": "aufgenommen_in", "label": {"de": "aufgenommen in", "en": "photographed in"}, "inverse_label": {"de": "Aufnahmeort von", "en": "place of photograph of"}, "applies_from": ["object"], "applies_to": ["place"]},
                {"term": "fundort_von", "label": {"de": "Fundort von", "en": "findspot of"}, "inverse_label": {"de": "gefunden in", "en": "found in"}, "applies_from": ["object"], "applies_to": ["place"]},
                {"term": "zeigt", "label": {"de": "zeigt", "en": "depicts"}, "inverse_label": {"de": "gezeigt in", "en": "depicted in"}, "applies_from": ["object"], "applies_to": ["entity", "place", "occurrence"]},
                {"term": "bezieht_sich_auf", "label": {"de": "bezieht sich auf", "en": "relates to"}, "inverse_label": {"de": "thematisiert in", "en": "thematized in"}, "applies_from": ["object"], "applies_to": ["occurrence"]},
                {"term": "illustriert", "label": {"de": "illustriert", "en": "illustrates"}, "inverse_label": {"de": "illustriert durch", "en": "illustrated by"}, "applies_from": ["object"], "applies_to": ["occurrence"]},
                {"term": "teil_von", "label": {"de": "Teil von", "en": "part of"}, "inverse_label": {"de": "besteht u.a. aus", "en": "consists partly of"}, "applies_from": ["object"], "applies_to": ["object"]},
                {"term": "pendant_zu", "label": {"de": "Pendant zu", "en": "pendant to"}, "inverse_label": {"de": "Pendant zu", "en": "pendant to"}, "applies_from": ["object"], "applies_to": ["object"]},
                {"term": "leihnehmer", "label": {"de": "Leihnehmer/in", "en": "borrower"}, "inverse_label": {"de": "lieh aus", "en": "borrowed"}, "applies_from": ["procedure"], "applies_to": ["entity"]},
                {"term": "leihgeber", "label": {"de": "Leihgeber/in", "en": "lender"}, "inverse_label": {"de": "verlieh", "en": "lent"}, "applies_from": ["procedure"], "applies_to": ["entity"]},
                {"term": "antragsteller", "label": {"de": "Antragsteller/in", "en": "applicant"}, "inverse_label": {"de": "beantragte", "en": "applied for"}, "applies_from": ["procedure"], "applies_to": ["entity"]},
                {"term": "restaurator", "label": {"de": "Restaurator/in", "en": "conservator"}, "inverse_label": {"de": "restaurierte im Vorgang", "en": "conserved in procedure"}, "applies_from": ["procedure"], "applies_to": ["entity"]},
                {"term": "ausstellungsort", "label": {"de": "Ausstellungsort", "en": "venue"}, "inverse_label": {"de": "Vorgangsort", "en": "venue of"}, "applies_from": ["procedure"], "applies_to": ["place"]},
                {"term": "kuratiert_von", "label": {"de": "kuratiert von", "en": "curated by"}, "inverse_label": {"de": "kuratiert", "en": "curates"}, "applies_from": ["collection"], "applies_to": ["entity"]},
                {"term": "nachlass_von", "label": {"de": "Nachlass von", "en": "estate of"}, "inverse_label": {"de": "hinterließ Bestand", "en": "left estate to"}, "applies_from": ["collection"], "applies_to": ["entity"]},
                {"term": "geboren_in", "label": {"de": "geboren in", "en": "born in"}, "inverse_label": {"de": "Geburtsort von", "en": "birthplace of"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "gestorben_in", "label": {"de": "gestorben in", "en": "died in"}, "inverse_label": {"de": "Sterbeort von", "en": "deathplace of"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "wirkte_in", "label": {"de": "wirkte in", "en": "active in"}, "inverse_label": {"de": "Wirkungsort von", "en": "place of activity of"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "verfasst_von", "label": {"de": "verfasst von", "en": "authored by"}, "inverse_label": {"de": "Autor von", "en": "author of"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "komponiert_von", "label": {"de": "komponiert von", "en": "composed by"}, "inverse_label": {"de": "Komponist von", "en": "composer of"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "spielt_in", "label": {"de": "spielt in", "en": "set in"}, "inverse_label": {"de": "Schauplatz von", "en": "setting of"}, "applies_from": ["occurrence"], "applies_to": ["place"]},
                {"term": "aufgefuehrt_in", "label": {"de": "aufgeführt in", "en": "performed in"}, "inverse_label": {"de": "Aufführungsort von", "en": "performance location of"}, "applies_from": ["occurrence"], "applies_to": ["place"]},
                {"term": "mitwirkende", "label": {"de": "mitwirkende Person", "en": "contributor"}, "inverse_label": {"de": "wirkte mit an", "en": "contributed to"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "nachbarort", "label": {"de": "Nachbarort", "en": "neighboring place"}, "inverse_label": {"de": "Nachbarort", "en": "neighboring place"}, "applies_from": ["place"], "applies_to": ["place"]},
                {"term": "verwaltet_von", "label": {"de": "verwaltet von", "en": "managed by"}, "inverse_label": {"de": "verwaltet", "en": "manages"}, "applies_from": ["place"], "applies_to": ["entity"]},
            ],
        )

        material_ids, material_labels = await make_vocab(
            db, MATERIAL_VOCAB_NAME, "term",
            [
                {"term": "organisch", "label": {"de": "Organisches Material", "en": "Organic Material"}, "metadata": {"ist_organisch": True}},
                {"term": "papier", "label": {"de": "Papier", "en": "Paper"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "buetten", "label": {"de": "Büttenpapier", "en": "Handmade Paper"}, "parent": "papier", "metadata": {"ist_organisch": True}},
                {"term": "karton", "label": {"de": "Karton", "en": "Cardboard"}, "parent": "papier", "metadata": {"ist_organisch": True}},
                {"term": "pergament", "label": {"de": "Pergament", "en": "Parchment"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "leinwand", "label": {"de": "Leinwand", "en": "Canvas"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "seide", "label": {"de": "Seide", "en": "Silk"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "eichenholz", "label": {"de": "Eichenholz", "en": "Oak Wood"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "nussbaum", "label": {"de": "Nussbaumholz", "en": "Walnut Wood"}, "parent": "organisch", "metadata": {"ist_organisch": True}},
                {"term": "anorganisch", "label": {"de": "Anorganisches Material", "en": "Inorganic Material"}, "metadata": {"ist_organisch": False}},
                {"term": "marmor", "label": {"de": "Marmor", "en": "Marble"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.7}},
                {"term": "gips", "label": {"de": "Gips", "en": "Plaster"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.3}},
                {"term": "bronze", "label": {"de": "Bronze", "en": "Bronze"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 8.8}},
                {"term": "silber", "label": {"de": "Silber", "en": "Silver"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 10.5}},
                {"term": "gold", "label": {"de": "Gold", "en": "Gold"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 19.3}},
                {"term": "glasnegativ", "label": {"de": "Glasnegativ", "en": "Glass Plate Negative"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.5}},
                {"term": "kristallglas", "label": {"de": "Kristallglas", "en": "Crystal Glass"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 3.0}},
                {"term": "porzellan", "label": {"de": "Porzellan", "en": "Porcelain"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.4}},
                {"term": "terrakotta", "label": {"de": "Terrakotta", "en": "Terracotta"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.0}},
                {"term": "quarz", "label": {"de": "Quarz / Bergkristall", "en": "Quartz"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.65}},
                {"term": "aragonit", "label": {"de": "Aragonit", "en": "Aragonite"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 2.95}},
                {"term": "haematit", "label": {"de": "Hämatit (Eisenglanz)", "en": "Hematite"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 5.26}},
                {"term": "basalt", "label": {"de": "Basalt", "en": "Basalt"}, "parent": "anorganisch", "metadata": {"ist_organisch": False, "dichte_g_cm3": 3.0}},
            ],
            hierarchical=True,
        )

        zustand_ids, zustand_labels = await make_vocab(
            db, ZUSTAND_VOCAB_NAME, "term",
            [
                {"term": "sehr_gut", "label": {"de": "Sehr gut", "en": "Excellent"}},
                {"term": "gut", "label": {"de": "Gut", "en": "Good"}},
                {"term": "stabil_maengel", "label": {"de": "Stabil mit Mängeln", "en": "Fair"}},
                {"term": "restaurierungsbeduerftig", "label": {"de": "Restaurierungsbedürftig", "en": "Needs Conservation"}},
                {"term": "akut_gefaehrdet", "label": {"de": "Akut gefährdet", "en": "Critically Endangered"}},
                {"term": "fragmentarisch", "label": {"de": "Fragmentarisch", "en": "Fragmentary"}},
            ],
        )

        ortstyp_ids, _ = await make_vocab(
            db, ORTSTYP_VOCAB_NAME, "term",
            [
                {"term": "residenzstadt", "label": {"de": "Residenzstadt", "en": "Residenz City"}},
                {"term": "universitaetsstadt", "label": {"de": "Universitätsstadt", "en": "University City"}},
                {"term": "handelsstadt", "label": {"de": "Handelsstadt / Reichsstadt", "en": "Trading City"}},
                {"term": "kurort", "label": {"de": "Kur- und Badeort", "en": "Spa Town"}},
                {"term": "bergbaustadt", "label": {"de": "Bergbaustadt", "en": "Mining Town"}},
                {"term": "dorf", "label": {"de": "Dorf / Landgemeinde", "en": "Village"}},
                {"term": "bauwerk", "label": {"de": "Bauwerk / Struktur", "en": "Structure / Monument"}},
            ],
        )

        genre_ids, _ = await make_vocab(
            db, GENRE_VOCAB_NAME, "term",
            [
                {"term": "drama", "label": {"de": "Drama / Trauerspiel", "en": "Drama"}},
                {"term": "roman", "label": {"de": "Roman", "en": "Novel"}},
                {"term": "gedichtzyklus", "label": {"de": "Gedichtzyklus / Lyrik", "en": "Poetry"}},
                {"term": "oper", "label": {"de": "Oper / Singspiel", "en": "Opera"}},
                {"term": "epos", "label": {"de": "Epos", "en": "Epic"}},
                {"term": "abhandlung", "label": {"de": "Wissenschaftliche Abhandlung", "en": "Treatise"}},
                {"term": "ausstellung", "label": {"de": "Sonderausstellung", "en": "Exhibition"}},
                {"term": "reise", "label": {"de": "Bildungsreise / Expedition", "en": "Journey"}},
            ],
        )

        technik_ids, technik_labels = await make_vocab(
            db, TECHNIK_VOCAB_NAME, "term",
            [
                {"term": "oelmalerei", "label": {"de": "Ölmalerei", "en": "Oil Painting"}},
                {"term": "aquarell", "label": {"de": "Aquarell", "en": "Watercolor"}},
                {"term": "kupferstich", "label": {"de": "Kupferstich", "en": "Copper Engraving"}},
                {"term": "radierung", "label": {"de": "Radierung", "en": "Etching"}},
                {"term": "lithografie", "label": {"de": "Lithografie", "en": "Lithography"}},
                {"term": "scherenschnitt", "label": {"de": "Scherenschnitt", "en": "Silhouette"}},
                {"term": "albuminabzug", "label": {"de": "Albumin-Abzug", "en": "Albumen Print"}},
                {"term": "kollodium", "label": {"de": "Nasses Kollodiumverfahren", "en": "Wet Collodion"}},
                {"term": "silbergelatine", "label": {"de": "Silbergelatine-Abzug", "en": "Gelatin Silver Print"}},
                {"term": "buchdruck", "label": {"de": "Buchdruck", "en": "Letterpress"}},
                {"term": "handschrift", "label": {"de": "Eisengallustinte auf Papier", "en": "Iron Gall Ink"}},
                {"term": "bronzeguss", "label": {"de": "Bronzeguss", "en": "Bronze Casting"}},
                {"term": "abguss", "label": {"de": "Gipsabguss", "en": "Plaster Cast"}},
                {"term": "meisselung", "label": {"de": "Steinmetzarbeit", "en": "Carved Stone"}},
                {"term": "praegung", "label": {"de": "Münzprägung", "en": "Coin Striking"}},
                {"term": "gravur", "label": {"de": "Gravur", "en": "Engraving"}},
                {"term": "schliff", "label": {"de": "Polierter Steinschliff", "en": "Polished Stone"}},
                {"term": "stickerei", "label": {"de": "Handstickerei", "en": "Embroidery"}},
                {"term": "schnitzerei", "label": {"de": "Holzschnitzerei", "en": "Wood Carving"}},
                {"term": "schreinerarbeit", "label": {"de": "Schreinerarbeit", "en": "Joinery"}},
                {"term": "drechselarbeit", "label": {"de": "Drechselarbeit", "en": "Wood Turning"}},
                {"term": "malerei", "label": {"de": "Porzellanmalerei", "en": "Porcelain Painting"}},
                {"term": "naturform", "label": {"de": "Natürliche Kristallstufe", "en": "Natural Crystal Cluster"}},
            ],
        )

        # Get Vocabulary UUIDs
        obj_rel_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == REL_VOCAB_NAME))).scalar_one()
        obj_mat_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == MATERIAL_VOCAB_NAME))).scalar_one()
        obj_zus_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == ZUSTAND_VOCAB_NAME))).scalar_one()
        obj_ort_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == ORTSTYP_VOCAB_NAME))).scalar_one()
        obj_gen_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == GENRE_VOCAB_NAME))).scalar_one()
        obj_tec_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == TECHNIK_VOCAB_NAME))).scalar_one()

        logger.info("Creating Field Definitions...")
        # 1. Custom fields on vocabulary_term
        await add_field(db, "vocabulary_term", "ist_organisch", {"de": "Ist organisch", "en": "Is Organic"}, "boolean", sort_order=1)
        await add_field(db, "vocabulary_term", "dichte_g_cm3", {"de": "Dichte (g/cm³)", "en": "Density (g/cm³)"}, "number", sort_order=2)
        await add_field(db, "vocabulary_term", "term_uri", {"de": "AAT / Wikidata URI", "en": "AAT / Wikidata URI"}, "text", sort_order=3)

        # 2. Fields on object
        await add_field(db, "object", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "richtext", sort_order=1, detail_role="description", detail_slot="main")
        await add_field(db, "object", "kurzbeschreibung", {"de": "Kurzbeschreibung", "en": "Short Description"}, "text", sort_order=2, is_translatable=True)
        await add_field(db, "object", "material", {"de": "Material", "en": "Material"}, "vocab", sort_order=3, settings_dict={"vocabulary_id": str(obj_mat_vocab_id)}, is_facet=True)
        await add_field(db, "object", "technik", {"de": "Technik", "en": "Technique"}, "vocab", sort_order=4, settings_dict={"vocabulary_id": str(obj_tec_vocab_id)}, is_repeatable=True, is_facet=True)
        await add_field(db, "object", "masse", {"de": "Maße", "en": "Dimensions"}, "text", sort_order=5)
        await add_field(db, "object", "anzahl", {"de": "Anzahl Stücke", "en": "Number of Pieces"}, "number", sort_order=6)
        await add_field(db, "object", "gewicht_g", {"de": "Gewicht (Gramm)", "en": "Weight (grams)"}, "number", sort_order=7)
        await add_field(db, "object", "ist_ausgestellt", {"de": "Aktuell ausgestellt", "en": "Currently on Display"}, "boolean", sort_order=8)
        await add_field(db, "object", "restaurierungsbedarf", {"de": "Restaurierungsbedarf", "en": "Conservation Needed"}, "boolean", sort_order=9)
        await add_field(db, "object", "erhaltungszustand", {"de": "Erhaltungszustand", "en": "Condition"}, "vocab", sort_order=10, settings_dict={"vocabulary_id": str(obj_zus_vocab_id)}, is_facet=True)
        await add_field(db, "object", "datierung", {"de": "Datierung", "en": "Dating"}, "date", sort_order=11)
        await add_field(db, "object", "objekt_pid", {"de": "Persistenter Identifier (DOI)", "en": "Persistent Identifier"}, "pid", sort_order=12, settings_dict={"pattern": r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$"})
        await add_field(db, "object", "digitale_edition", {"de": "Digitale Edition", "en": "Digital Edition"}, "url", sort_order=13)
        await add_field(db, "object", "fundkoordinaten", {"de": "Fundkoordinaten", "en": "Findspot Coordinates"}, "geo", sort_order=14)
        await add_field(db, "object", "urheber", {"de": "Urheber/in", "en": "Creator"}, "relation", sort_order=15, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "geschaffen_von"})
        await add_field(db, "object", "abgebildete_person", {"de": "Abgebildete Person", "en": "Depicted Person"}, "relation", sort_order=16, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "abgebildete_person"})
        await add_field(db, "object", "vorbesitzer", {"de": "Vorbesitzer/in", "en": "Previous Owner"}, "relation", sort_order=17, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "vorbesitzer"})
        await add_field(db, "object", "herstellungsort", {"de": "Herstellungsort", "en": "Place of Manufacture"}, "relation", sort_order=18, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "hergestellt_in"})
        await add_field(db, "object", "aufnahmeort", {"de": "Aufnahmeort", "en": "Place of Recording"}, "relation", sort_order=19, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "aufgenommen_in"})
        await add_field(db, "object", "zeigt_ort", {"de": "Zeigt Ort", "en": "Depicted Place"}, "relation", sort_order=20, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "zeigt"})
        await add_field(db, "object", "bezug_werk", {"de": "Bezug zu Werk/Ereignis", "en": "Related Work/Event"}, "relation", sort_order=21, settings_dict={"target_type": "occurrence", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "bezieht_sich_auf"})
        await add_field(db, "object", "illustriert", {"de": "Illustriert Werk/Ereignis", "en": "Illustrates Work/Event"}, "relation", sort_order=22, settings_dict={"target_type": "occurrence", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "illustriert"})
        await add_field(db, "object", "teil_von_objekt", {"de": "Teil von Objekt", "en": "Part of Object"}, "relation", sort_order=23, settings_dict={"target_type": "object", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "teil_von"})

        provenienz = await add_field(db, "object", "provenienzstationen", {"de": "Provenienzstationen", "en": "Provenance History"}, "group", sort_order=24, is_repeatable=True)
        await add_field(db, "object", "ereignis", {"de": "Ereignis", "en": "Event"}, "text", sort_order=1, parent_id=provenienz.id)
        await add_field(db, "object", "zeitraum", {"de": "Zeitraum", "en": "Period"}, "date", sort_order=2, parent_id=provenienz.id)
        await add_field(db, "object", "akteur", {"de": "Akteur / Person", "en": "Actor / Entity"}, "relation", sort_order=3, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "vorbesitzer"}, parent_id=provenienz.id)
        await add_field(db, "object", "ort", {"de": "Ort", "en": "Place"}, "relation", sort_order=4, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "zeigt"}, parent_id=provenienz.id)
        await add_field(db, "object", "erwerbsart", {"de": "Erwerbsart", "en": "Acquisition Type"}, "vocab_free", sort_order=5, settings_dict={"vocabulary_id": str(obj_tec_vocab_id)}, parent_id=provenienz.id)

        dim_group = await add_field(db, "object", "abmessungen_detailliert", {"de": "Detaillierte Abmessungen", "en": "Detailed Dimensions"}, "group", sort_order=25, is_repeatable=True)
        await add_field(db, "object", "hoehe_cm", {"de": "Höhe (cm)", "en": "Height (cm)"}, "number", sort_order=1, parent_id=dim_group.id)
        await add_field(db, "object", "breite_cm", {"de": "Breite (cm)", "en": "Width (cm)"}, "number", sort_order=2, parent_id=dim_group.id)
        await add_field(db, "object", "tiefe_cm", {"de": "Tiefe (cm)", "en": "Depth (cm)"}, "number", sort_order=3, parent_id=dim_group.id)
        await add_field(db, "object", "gewicht_kg", {"de": "Gewicht (kg)", "en": "Weight (kg)"}, "number", sort_order=4, parent_id=dim_group.id)

        # 3. Fields on entity
        await add_field(db, "entity", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "richtext", sort_order=1, detail_role="description", detail_slot="main")
        await add_field(db, "entity", "geburtsdatum", {"de": "Geburtsdatum", "en": "Date of Birth"}, "date", sort_order=2)
        await add_field(db, "entity", "sterbedatum", {"de": "Sterbedatum", "en": "Date of Death"}, "date", sort_order=3)
        await add_field(db, "entity", "gnd_id", {"de": "GND-Normdatum", "en": "GND Authority ID"}, "authority", sort_order=4, settings_dict={"source": "gnd"})
        await add_field(db, "entity", "viaf_pid", {"de": "VIAF-Normdatum", "en": "VIAF Authority ID"}, "authority", sort_order=5, settings_dict={"source": "viaf"})
        await add_field(db, "entity", "beruf", {"de": "Beruf / Tätigkeit", "en": "Profession / Activity"}, "vocab_free", sort_order=6, settings_dict={"vocabulary_id": str(obj_ort_vocab_id)}, is_repeatable=True)
        await add_field(db, "entity", "anzahl_werke", {"de": "Anzahl bekannter Werke", "en": "Number of Known Works"}, "number", sort_order=7)
        await add_field(db, "entity", "geburtsort", {"de": "Geburtsort", "en": "Birthplace"}, "relation", sort_order=8, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "geboren_in"})
        await add_field(db, "entity", "sterbeort", {"de": "Sterbeort", "en": "Deathplace"}, "relation", sort_order=9, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "gestorben_in"})

        stations = await add_field(db, "entity", "wirkungsstationen", {"de": "Wirkungsstationen", "en": "Stations of Activity"}, "group", sort_order=10, is_repeatable=True)
        await add_field(db, "entity", "ort", {"de": "Ort", "en": "Place"}, "relation", sort_order=1, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id)}, parent_id=stations.id)
        await add_field(db, "entity", "von", {"de": "Von", "en": "From"}, "date", sort_order=2, parent_id=stations.id)
        await add_field(db, "entity", "bis", {"de": "Bis", "en": "To"}, "date", sort_order=3, parent_id=stations.id)
        await add_field(db, "entity", "funktion", {"de": "Funktion", "en": "Role"}, "vocab_free", sort_order=4, settings_dict={"vocabulary_id": str(obj_ort_vocab_id)}, parent_id=stations.id)

        # 4. Fields on place
        await add_field(db, "place", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "richtext", sort_order=1, detail_role="description", detail_slot="main")
        await add_field(db, "place", "geonames_id", {"de": "GeoNames-Normdatum", "en": "GeoNames Authority ID"}, "authority", sort_order=2, settings_dict={"source": "geonames"})
        await add_field(db, "place", "plz", {"de": "Postleitzahl", "en": "Postal Code"}, "text", sort_order=3)
        await add_field(db, "place", "ist_hauptort", {"de": "Hauptort der Region", "en": "Regional Capital"}, "boolean", sort_order=4)
        await add_field(db, "place", "ersterwaehnung", {"de": "Ersterwähnung", "en": "First Mention"}, "date", sort_order=5)
        await add_field(db, "place", "einwohnerzahl", {"de": "Einwohnerzahl (historisch)", "en": "Historical Population"}, "number", sort_order=6)
        await add_field(db, "place", "ortstyp", {"de": "Ortstyp", "en": "Place Type"}, "vocab", sort_order=7, settings_dict={"vocabulary_id": str(obj_ort_vocab_id)})
        await add_field(db, "place", "grenzpunkt", {"de": "Referenzpunkt", "en": "Reference Point"}, "geo", sort_order=8)
        await add_field(db, "place", "verwaltet_von", {"de": "Verwaltet von", "en": "Administered by"}, "relation", sort_order=9, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "verwaltet_von"})

        nachbar = await add_field(db, "place", "nachbarorte", {"de": "Nachbarorte", "en": "Neighboring Places"}, "group", sort_order=10, is_repeatable=True)
        await add_field(db, "place", "ort", {"de": "Ort", "en": "Place"}, "relation", sort_order=1, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "nachbarort"}, parent_id=nachbar.id)
        await add_field(db, "place", "distanz_km", {"de": "Distanz (km)", "en": "Distance (km)"}, "number", sort_order=2, parent_id=nachbar.id)

        # 5. Fields on occurrence
        await add_field(db, "occurrence", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "richtext", sort_order=1, detail_role="description", detail_slot="main")
        await add_field(db, "occurrence", "entstehungsdatum", {"de": "Entstehungsdatum", "en": "Date of Creation"}, "date", sort_order=2)
        await add_field(db, "occurrence", "gattung", {"de": "Gattung", "en": "Genre"}, "vocab", sort_order=3, settings_dict={"vocabulary_id": str(obj_gen_vocab_id)})
        await add_field(db, "occurrence", "form", {"de": "Form", "en": "Form"}, "vocab_free", sort_order=4, settings_dict={"vocabulary_id": str(obj_gen_vocab_id)}, is_repeatable=True)
        await add_field(db, "occurrence", "verfasser", {"de": "Verfasser/in", "en": "Author"}, "relation", sort_order=5, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "verfasst_von"})
        await add_field(db, "occurrence", "komponist", {"de": "Komponist/in", "en": "Composer"}, "relation", sort_order=6, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "komponiert_von"})
        await add_field(db, "occurrence", "spielort", {"de": "Schauplatz", "en": "Setting"}, "relation", sort_order=7, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "spielt_in"})
        await add_field(db, "occurrence", "ist_vollendet", {"de": "Vollendet", "en": "Completed"}, "boolean", sort_order=8)
        await add_field(db, "occurrence", "umfang", {"de": "Umfang (Akte / Bände)", "en": "Volume (Acts / Volumes)"}, "number", sort_order=9)

        auffuehrungen = await add_field(db, "occurrence", "auffuehrungen", {"de": "Aufführungen & Ausgaben", "en": "Performances & Editions"}, "group", sort_order=10, is_repeatable=True)
        await add_field(db, "occurrence", "datum", {"de": "Datum", "en": "Date"}, "date", sort_order=1, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "ort", {"de": "Ort", "en": "Place"}, "relation", sort_order=2, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "aufgefuehrt_in"}, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "person", {"de": "Mitwirkende", "en": "Contributor"}, "relation", sort_order=3, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "mitwirkende"}, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "rolle", {"de": "Rolle", "en": "Role"}, "vocab_free", sort_order=4, settings_dict={"vocabulary_id": str(obj_tec_vocab_id)}, parent_id=auffuehrungen.id)

        # 6. Fields on collection
        await add_field(db, "collection", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "richtext", sort_order=1, detail_role="description", detail_slot="main")
        await add_field(db, "collection", "bestandssignatur", {"de": "Bestandssignatur", "en": "Call Number"}, "text", sort_order=2)
        await add_field(db, "collection", "laufzeit_beginn", {"de": "Laufzeit Beginn", "en": "Date Range Start"}, "date", sort_order=3)
        await add_field(db, "collection", "laufzeit_ende", {"de": "Laufzeit Ende", "en": "Date Range End"}, "date", sort_order=4)
        await add_field(db, "collection", "anzahl_verzeichnet", {"de": "Verzeichnete Einheiten", "en": "Cataloged Units"}, "number", sort_order=5)
        await add_field(db, "collection", "ist_abgeschlossen", {"de": "Bestand abgeschlossen", "en": "Collection Closed"}, "boolean", sort_order=6)
        await add_field(db, "collection", "kurator", {"de": "Betreuende/r Kurator/in", "en": "Curator"}, "relation", sort_order=7, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "kuratiert_von"})
        await add_field(db, "collection", "provenienz_vorbesitzer", {"de": "Bestandsbildner/in", "en": "Creator / Former Owner"}, "relation", sort_order=8, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "nachlass_von"})

        # 7. Fields on storage_location
        await add_field(db, "storage_location", "beschreibung", {"de": "Beschreibung", "en": "Description"}, "text", sort_order=1)
        await add_field(db, "storage_location", "klimatisiert", {"de": "Klimatisiert", "en": "Climate Controlled"}, "boolean", sort_order=2)
        await add_field(db, "storage_location", "raumtemperatur_soll", {"de": "Solltemperatur (°C)", "en": "Target Temperature (°C)"}, "number", sort_order=3)
        await add_field(db, "storage_location", "feuchtigkeit_soll_prozent", {"de": "Soll-Luftfeuchte (%)", "en": "Target Humidity (%)"}, "number", sort_order=4)
        await add_field(db, "storage_location", "zugangsbeschraenkung", {"de": "Zugangsbeschränkung", "en": "Access Restriction"}, "text", sort_order=5)

        # 8. Fields on procedure
        await add_field(db, "procedure", "antragsteller", {"de": "Antragsteller/in", "en": "Applicant"}, "relation", sort_order=1, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "antragsteller"})
        await add_field(db, "procedure", "leihnehmer_oder_partner", {"de": "Leihnehmer / Partner", "en": "Borrower / Partner"}, "relation", sort_order=2, settings_dict={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "leihnehmer"})
        await add_field(db, "procedure", "zielort", {"de": "Vorgangsort / Zielort", "en": "Venue / Destination"}, "relation", sort_order=3, settings_dict={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "ausstellungsort"})
        await add_field(db, "procedure", "versicherungswert_eur", {"de": "Versicherungswert (€)", "en": "Insurance Value (€)"}, "number", sort_order=4)
        await add_field(db, "procedure", "vertrag_vorhanden", {"de": "Schriftlicher Vertrag vorliegend", "en": "Contract on File"}, "boolean", sort_order=5)
        await add_field(db, "procedure", "verfahrensbericht", {"de": "Verfahrensbericht", "en": "Procedure Report"}, "richtext", sort_order=6, detail_role="description", detail_slot="main")
        await add_field(db, "procedure", "dokumentation_url", {"de": "Dokumentenlink", "en": "Documentation URL"}, "url", sort_order=7)

        await db.commit()

        # ============================================================== Records: Places
        logger.info("Inserting Places...")
        places: dict[str, Place] = {}
        for idno, label_de, ortstyp, plz, hauptort, ersterw, einwohner, lat, lon, geonames_id in PLACES_DATA:
            p = Place(
                idno=f"PLACE-{idno.upper()}",
                place_type="ort" if ortstyp != "bauwerk" else "bauwerk",
                status="public",
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                metadata_={
                    "label": label_de,
                    "beschreibung": f"{label_de} ist ein bedeutender historischer Ort im Umkreis der Weimarer Kulturgeschichte.",
                    "plz": plz,
                    "ist_hauptort": hauptort,
                    "ersterwaehnung": ersterw,
                    "einwohnerzahl": einwohner,
                    "ortstyp": {"id": ortstyp_ids.get(ortstyp, ""), "label": ortstyp.title()},
                    "grenzpunkt": f"{lat},{lon}",
                    "geonames_id": {"source": "geonames", "external_id": geonames_id, "label": label_de},
                },
            )
            db.add(p)
            places[idno] = p
        await db.flush()
        for p in places.values():
            await log_change(db, record_type="place", record_id=p.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: Entities
        logger.info("Inserting Entities...")
        entities: dict[str, Entity] = {}
        for idno, name, etype, geb, gest, beruf, geb_ort, gest_ort, gnd, viaf in ENTITIES_DATA:
            md: dict[str, Any] = {
                "label": name,
                "beschreibung": f"**{name}** ist ein herausragender Bestandteil der Sammlung Weimarer Klassik.",
                "beruf": [beruf],
                "anzahl_werke": 42 if "goethe" in idno or "schiller" in idno else 12,
                "viaf_pid": {"source": "viaf", "external_id": viaf, "label": name},
                "gnd_id": {"source": "gnd", "external_id": gnd, "label": name},
                "wirkungsstationen": [
                    {
                        "ort": rel(str(places["weimar"].id), "Weimar", "wirkte_in"),
                        "von": geb or "1775",
                        "bis": gest or "1832",
                        "funktion": "Wirkungsort",
                    }
                ] if idno in ("goethe", "schiller", "herder", "wieland") else [],
            }
            if geb:
                md["geburtsdatum"] = geb
            if gest:
                md["sterbedatum"] = gest
            if geb_ort and geb_ort in places:
                md["geburtsort"] = rel(str(places[geb_ort].id), places[geb_ort].metadata_["label"], "geboren_in")
            if gest_ort and gest_ort in places:
                md["sterbeort"] = rel(str(places[gest_ort].id), places[gest_ort].metadata_["label"], "gestorben_in")

            e = Entity(
                idno=f"ENT-{idno.upper()}",
                entity_type=etype,
                status="public",
                metadata_=md,
            )
            db.add(e)
            entities[idno] = e
        await db.flush()
        for e in entities.values():
            await log_change(db, record_type="entity", record_id=e.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: Occurrences
        logger.info("Inserting Occurrences...")
        occurrences: dict[str, Occurrence] = {}
        for idno, title, otype, jahr, gattung, verfasser, komponist, spielort, umfang in OCCURRENCES_DATA:
            md = {
                "label": title,
                "beschreibung": f"*{title}* ist ein Schlüsselwerk bzw. Meilenstein der europäischen Kulturgeschichte.",
                "entstehungsdatum": jahr,
                "gattung": {"id": genre_ids.get(gattung, ""), "label": gattung.title()},
                "form": [gattung],
                "verfasser": rel(str(entities[verfasser].id), entities[verfasser].metadata_["label"], "verfasst_von") if verfasser and verfasser in entities else None,
                "komponist": rel(str(entities[komponist].id), entities[komponist].metadata_["label"], "komponiert_von") if komponist and komponist in entities else None,
                "spielort": rel(str(places[spielort].id), places[spielort].metadata_["label"], "spielt_in") if spielort and spielort in places else None,
                "ist_vollendet": True,
                "umfang": umfang,
                "auffuehrungen": [
                    {
                        "datum": jahr,
                        "ort": rel(str(places[spielort].id), places[spielort].metadata_["label"], "aufgefuehrt_in") if spielort and spielort in places else None,
                        "person": rel(str(entities[verfasser].id), entities[verfasser].metadata_["label"], "mitwirkende") if verfasser and verfasser in entities else None,
                        "rolle": "Uraufführung / Entstehung",
                    }
                ],
            }
            occ = Occurrence(
                idno=f"OCC-{idno.upper()}",
                occurrence_type=otype,
                status="public",
                metadata_=md,
            )
            db.add(occ)
            occurrences[idno] = occ
        await db.flush()
        for occ in occurrences.values():
            await log_change(db, record_type="occurrence", record_id=occ.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: Collections (Hierarchical)
        logger.info("Inserting Collections...")
        collections: dict[str, Collection] = {}
        for idno, parent_key, ctype, title, desc in COLLECTIONS_DATA:
            parent_id = collections[parent_key].id if parent_key and parent_key in collections else None
            c = Collection(
                idno=f"COL-{idno.upper()}",
                collection_type=ctype,
                parent_id=parent_id,
                status="public",
                metadata_={
                    "label": title,
                    "beschreibung": desc,
                    "bestandssignatur": f"SW-{idno.upper()}",
                    "laufzeit_beginn": "1770",
                    "laufzeit_ende": "1835",
                    "anzahl_verzeichnet": 50 if parent_key else 100,
                    "ist_abgeschlossen": True,
                    "kurator": rel(str(entities["eckermann"].id), entities["eckermann"].metadata_["label"], "kuratiert_von"),
                    "provenienz_vorbesitzer": rel(str(entities["goethe"].id), entities["goethe"].metadata_["label"], "nachlass_von"),
                },
            )
            db.add(c)
            await db.flush()
            collections[idno] = c
            await log_change(db, record_type="collection", record_id=c.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: Storage Locations (Hierarchical)
        logger.info("Inserting Storage Locations...")
        storage_locations: dict[str, StorageLocation] = {}
        for idno, parent_key, sltype, title, desc in STORAGE_LOCATIONS_DATA:
            parent_id = storage_locations[parent_key].id if parent_key and parent_key in storage_locations else None
            sl = StorageLocation(
                idno=f"LOC-{idno.upper()}",
                storage_location_type=sltype,
                parent_id=parent_id,
                metadata_={
                    "label": title,
                    "beschreibung": desc,
                    "klimatisiert": sltype in ("gebaeude", "raum"),
                    "raumtemperatur_soll": 18.5,
                    "feuchtigkeit_soll_prozent": 50.0,
                    "zugangsbeschraenkung": "Nur autorisiertes Archivpersonal",
                },
            )
            db.add(sl)
            await db.flush()
            storage_locations[idno] = sl
            await log_change(db, record_type="storage_location", record_id=sl.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: Procedures
        logger.info("Inserting Procedures...")
        procedures: dict[str, Procedure] = {}
        for idno, ptype, pstatus, sdate, edate, ddate, ref_no, desc, ent_key, place_key, wert, _ in PROCEDURES_DATA:
            pr = Procedure(
                idno=f"PROC-{idno.upper()}",
                procedure_type=ptype,
                status=pstatus,
                start_date=date.fromisoformat(sdate) if sdate else None,
                end_date=date.fromisoformat(edate) if edate else None,
                due_date=date.fromisoformat(ddate) if ddate else None,
                reference_number=ref_no,
                metadata_={
                    "label": f"{ptype.upper()}: {ref_no}",
                    "verfahrensbericht": desc,
                    "antragsteller": rel(str(entities["goethe"].id), entities["goethe"].metadata_["label"], "antragsteller"),
                    "leihnehmer_oder_partner": rel(str(entities[ent_key].id), entities[ent_key].metadata_["label"], "leihnehmer") if ent_key and ent_key in entities else None,
                    "zielort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "ausstellungsort") if place_key and place_key in places else None,
                    "versicherungswert_eur": wert,
                    "vertrag_vorhanden": True,
                    "dokumentation_url": {"url": f"https://archiv.klassik-stiftung.de/verfahren/{ref_no.replace('/', '-')}", "label": "Elektronische Vorgangsakte"},
                },
            )
            db.add(pr)
            await db.flush()
            procedures[idno] = pr
            await log_change(db, record_type="procedure", record_id=pr.id, user_id=admin_user_id, action="create")

        # ============================================================== Records: 100 Objects
        logger.info("Generating 100 Object records...")
        objects: dict[str, Object] = {}
        specs = build_object_specs()

        for spec in specs:
            i = spec["index"]
            idno = spec["idno"]
            title = spec["title"]
            subtype = spec["subtype"]
            mat_key = spec["material"]
            tec_key = spec["technik"]
            author_key = spec["author"]
            depicted_key = spec["depicted"]
            place_key = spec["place"]
            occ_key = spec["occ"]

            mat_label = material_labels.get(mat_key, {}).get("de", mat_key)
            tec_label = technik_labels.get(tec_key, {}).get("de", tec_key)

            md: dict[str, Any] = {
                "label": title,
                "kurzbeschreibung": {
                    "de": f"{title} aus der Sammlung Weimarer Klassik.",
                    "en": f"{title} from the Weimar Classicism Collection.",
                },
                "beschreibung": f"**{title}** ist ein repräsentatives Sammlungsstück ({subtype}) aus dem Bestand der Weimarer Klassik. "
                                f"Hergestellt aus *{mat_label}* mittels *{tec_label}*.",
                "material": {"id": material_ids.get(mat_key, ""), "label": mat_label},
                "technik": [{"id": technik_ids.get(tec_key, ""), "label": tec_label}],
                "masse": spec["masse"],
                "anzahl": 1,
                "gewicht_g": spec["gewicht_g"],
                "ist_ausgestellt": spec["ausgestellt"],
                "restaurierungsbedarf": spec["restaurierung"],
                "erhaltungszustand": {"id": zustand_ids.get(spec["zustand"], ""), "label": zustand_labels.get(spec["zustand"], {}).get("de", spec["zustand"])},
                "datierung": spec["datierung"],
                "objekt_pid": {"value": f"10.5072/katalon.obj.{i:04d}", "label": "DOI"},
                "digitale_edition": {
                    "url": f"https://edition.klassik-stiftung.de/sammlung/{idno.lower()}",
                    "label": "Kritische Online-Präsentation",
                },
                "urheber": rel(str(entities[author_key].id), entities[author_key].metadata_["label"], "geschaffen_von") if author_key and author_key in entities else None,
                "abgebildete_person": rel(str(entities[depicted_key].id), entities[depicted_key].metadata_["label"], "abgebildete_person") if depicted_key and depicted_key in entities else None,
                "vorbesitzer": rel(str(entities["goethe"].id), entities["goethe"].metadata_["label"], "vorbesitzer") if not author_key else None,
                "herstellungsort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "hergestellt_in") if place_key and place_key in places and subtype != "fotografie" else None,
                "aufnahmeort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "aufgenommen_in") if place_key and place_key in places and subtype == "fotografie" else None,
                "zeigt_ort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "zeigt") if place_key and place_key in places and subtype in ("druckgrafik", "fotografie", "gemaelde") else None,
                "bezug_werk": rel(str(occurrences[occ_key].id), occurrences[occ_key].metadata_["label"], "bezieht_sich_auf") if occ_key and occ_key in occurrences and subtype != "archivalie" else None,
                "illustriert": rel(str(occurrences[occ_key].id), occurrences[occ_key].metadata_["label"], "illustriert") if occ_key and occ_key in occurrences and subtype == "archivalie" else None,
                "provenienzstationen": [
                    {
                        "ereignis": "Historische Erwerbung / Übergabe",
                        "zeitraum": "1832",
                        "akteur": rel(str(entities["eckermann"].id), entities["eckermann"].metadata_["label"], "vorbesitzer"),
                        "ort": rel(str(places["weimar"].id), "Weimar", "zeigt"),
                        "erwerbsart": "Schenkung",
                    }
                ],
                "abmessungen_detailliert": [
                    {
                        "hoehe_cm": float(spec["masse"].split("x")[0].strip().replace("cm", "").replace(",", ".")) if "x" in spec["masse"] else 30.0,
                        "breite_cm": float(spec["masse"].split("x")[1].split()[0].strip().replace(",", ".")) if "x" in spec["masse"] else 20.0,
                        "tiefe_cm": 5.0,
                        "gewicht_kg": round(spec["gewicht_g"] / 1000.0, 2),
                    }
                ],
            }

            if spec.get("coords"):
                md["fundkoordinaten"] = spec["coords"]

            obj = Object(
                id=demo_object_id(idno),
                idno=idno,
                object_type=subtype,
                status=spec["status"],
                collection_status=spec["col_status"],
                metadata_=md,
            )
            db.add(obj)
            objects[idno] = obj

        await db.flush()
        for obj in objects.values():
            await log_change(db, record_type="object", record_id=obj.id, user_id=admin_user_id, action="create")
        await db.commit()
        logger.info("Successfully created 100 Object rows.")

        # ============================================================== Media Files
        if not args.no_images:
            logger.info("Processing Media and specimen plates...")
            await seed_media(db, objects, skip_downloads=args.skip_downloads, no_iiif=args.no_iiif)

        # ============================================================== Direct Relations
        logger.info("Creating direct cross-type generic relations...")
        for spec in specs:
            idno = spec["idno"]
            obj = objects[idno]
            col_key = spec["col"]
            norm_loc_key = spec["norm_loc"]
            curr_loc_key = spec.get("curr_loc")
            pendant_idno = spec.get("pendant_to")
            part_of_idno = spec.get("part_of")

            # Object -> Collection
            if col_key in collections:
                db.add(Relation(
                    from_type="object",
                    from_id=obj.id,
                    to_type="collection",
                    to_id=collections[col_key].id,
                    relation_type="member_of",
                    is_schema_derived=False,
                ))

            # Object -> StorageLocation (Normal)
            if norm_loc_key in storage_locations:
                db.add(Relation(
                    from_type="object",
                    from_id=obj.id,
                    to_type="storage_location",
                    to_id=storage_locations[norm_loc_key].id,
                    relation_type="normal_location",
                    is_schema_derived=False,
                ))

            # Object -> StorageLocation (Current / Temporary)
            if curr_loc_key and curr_loc_key in storage_locations:
                db.add(Relation(
                    from_type="object",
                    from_id=obj.id,
                    to_type="storage_location",
                    to_id=storage_locations[curr_loc_key].id,
                    relation_type="current_location",
                    is_schema_derived=False,
                ))

            # Object <-> Object (Pendant)
            if pendant_idno and pendant_idno in objects:
                db.add(Relation(
                    from_type="object",
                    from_id=obj.id,
                    to_type="object",
                    to_id=objects[pendant_idno].id,
                    relation_type="pendant_zu",
                    is_schema_derived=False,
                ))

            # Object <-> Object (Part of)
            if part_of_idno and part_of_idno in objects:
                db.add(Relation(
                    from_type="object",
                    from_id=obj.id,
                    to_type="object",
                    to_id=objects[part_of_idno].id,
                    relation_type="teil_von",
                    is_schema_derived=False,
                ))

        # Procedure -> Object Relations
        for idno, _, _, _, _, _, _, _, _, _, _, obj_idnos in PROCEDURES_DATA:
            pr = procedures[idno]
            for o_idno in obj_idnos:
                if o_idno in objects:
                    db.add(Relation(
                        from_type="procedure",
                        from_id=pr.id,
                        to_type="object",
                        to_id=objects[o_idno].id,
                        relation_type="subject_of",
                        is_schema_derived=False,
                    ))

        # Collection -> Entity
        db.add(Relation(
            from_type="collection",
            from_id=collections["col-01"].id,
            to_type="entity",
            to_id=entities["goethe"].id,
            relation_type="nachlass_von",
            is_schema_derived=False,
        ))

        await db.commit()

        # ============================================================== Portal Config: Facets + Homepage
        logger.info("Configuring portal facets and homepage content...")
        portal_config = (
            await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
        ).scalar_one_or_none()
        if portal_config:
            portal_config.hero_text = {
                "de": (
                    "Fotografien, Handschriften, Kunsthandwerk und Nachlassobjekte aus der "
                    "Sammlung Weimarer Klassik – durchsuchbar, vernetzt und mit IIIF-Bildbetrachter."
                ),
                "en": (
                    "Photographs, manuscripts, crafts, and estate objects from the Weimar "
                    "Classicism Collection – searchable, linked, and with an IIIF image viewer."
                ),
            }
            portal_config.site_title = {"de": "Sammlung Weimarer Klassik", "en": "Weimar Classicism Collection"}
            portal_config.site_subtitle = {
                "de": "Digitale Sammlung Weimarer Klassik",
                "en": "Digital Weimar Classicism Collection",
            }
            portal_config.facet_fields = {
                "object": ["material", "erhaltungszustand", "technik"],
                # Status is always "public" for anonymous portal visitors (their queries
                # are already locked to that status server-side) -- a single-value facet
                # is noise, not a filter. Admins can still re-enable it in Einstellungen.
                "_system": ["record_type", "subtype"],
            }
            featured_idnos = [
                "OBJ-001", "OBJ-013", "OBJ-026", "OBJ-038",
                "OBJ-051", "OBJ-063", "OBJ-076", "OBJ-088",
            ]
            portal_config.featured_object_ids = [
                str(objects[idno].id) for idno in featured_idnos if idno in objects
            ]
            portal_config.homepage_blocks = [
                {
                    "id": str(uuid.uuid4()),
                    "type": "text",
                    "enabled": True,
                    "title": {"de": "Über die Sammlung", "en": "About the Collection"},
                    "content": {
                        "de": "Die Sammlung Weimarer Klassik bewahrt Objekte, Handschriften und "
                              "Bildmaterial rund um Goethe, Schiller und den Weimarer Musenhof. "
                              "Diese Demo-Instanz zeigt 100 Beispielobjekte über acht Objekttypen.",
                        "en": "The Weimar Classicism Collection preserves objects, manuscripts, and "
                              "imagery connected to Goethe, Schiller, and the Weimar court of muses. "
                              "This demo instance shows 100 sample objects across eight object subtypes.",
                    },
                },
                {
                    "id": str(uuid.uuid4()),
                    "type": "curated",
                    "enabled": True,
                    "title": {"de": "Ausgewählte Objekte", "en": "Featured Objects"},
                    "limit": 8,
                },
                {
                    "id": str(uuid.uuid4()),
                    "type": "collections",
                    "enabled": True,
                    "title": {"de": "Sammlungen", "en": "Collections"},
                    "collections_mode": "top",
                },
            ]
            await db.commit()
        else:
            logger.warning("PortalConfig row not found; skipping facet/homepage seed (run API first).")

        # ============================================================== Static Pages
        logger.info("Creating static page...")
        existing_page = (
            await db.execute(select(StaticPage).where(StaticPage.slug == "ueber-die-sammlung"))
        ).scalar_one_or_none()
        if not existing_page:
            db.add(StaticPage(
                slug="ueber-die-sammlung",
                title={"de": "Über die Sammlung", "en": "About the Collection"},
                content={
                    "de": (
                        "# Sammlung Weimarer Klassik\n\n"
                        "Die Sammlung Weimarer Klassik bewahrt Objekte, Handschriften, Gemälde und "
                        "Nachlassbestände aus dem Umfeld von Johann Wolfgang von Goethe, Friedrich "
                        "Schiller, Johann Gottfried Herder und dem Weimarer Musenhof des ausgehenden "
                        "18. und frühen 19. Jahrhunderts.\n\n"
                        "## Über diese Demo-Instanz\n\n"
                        "Diese Katalon-Instanz ist mit 100 fiktiven Beispielobjekten über acht "
                        "Objekttypen, 18 Personen und Organisationen, 12 Orten, 10 Werken und "
                        "Ereignissen sowie 8 hierarchisch gegliederten Sammlungen und Beständen "
                        "befüllt. Sie dient der Vorführung der Katalon-Funktionen — Schema-"
                        "Konfiguration, Beziehungsmodell, IIIF-Bildbetrachter und facettierte "
                        "Suche — und stellt keine echten Museums- oder Archivbestände dar.\n"
                    ),
                    "en": (
                        "# Weimar Classicism Collection\n\n"
                        "The Weimar Classicism Collection preserves objects, manuscripts, paintings, "
                        "and estate papers connected to Johann Wolfgang von Goethe, Friedrich "
                        "Schiller, Johann Gottfried Herder, and the Weimar court of muses of the "
                        "late 18th and early 19th centuries.\n\n"
                        "## About This Demo Instance\n\n"
                        "This Katalon instance is populated with 100 fictitious sample objects "
                        "across eight object subtypes, 18 people and organizations, 12 places, "
                        "10 works and events, and 8 hierarchically organized collections and "
                        "holdings. It demonstrates Katalon's features — schema configuration, "
                        "the relation model, the IIIF image viewer, and faceted search — and does "
                        "not represent a real museum or archive collection.\n"
                    ),
                },
                is_published=True,
                placement="header",
                sort_order=1,
            ))
            await db.commit()


        # ============================================================== Sync Schema Relations
        logger.info("Synchronizing schema-defined relations into `relations` table...")
        for o in (await db.execute(select(Object))).scalars().all():
            await sync_schema_relations(db, "object", o.id, o.metadata_)
        for e in (await db.execute(select(Entity))).scalars().all():
            await sync_schema_relations(db, "entity", e.id, e.metadata_)
        for p in (await db.execute(select(Place))).scalars().all():
            await sync_schema_relations(db, "place", p.id, p.metadata_)
        for occ in (await db.execute(select(Occurrence))).scalars().all():
            await sync_schema_relations(db, "occurrence", occ.id, occ.metadata_)
        for col in (await db.execute(select(Collection))).scalars().all():
            await sync_schema_relations(db, "collection", col.id, col.metadata_)
        for sl in (await db.execute(select(StorageLocation))).scalars().all():
            await sync_schema_relations(db, "storage_location", sl.id, sl.metadata_)
        for pr in (await db.execute(select(Procedure))).scalars().all():
            await sync_schema_relations(db, "procedure", pr.id, pr.metadata_)

        await db.commit()

    # Trigger Elasticsearch reindex
    try:
        reindex_all_task.delay()
        logger.info("Elasticsearch reindex enqueued.")
    except Exception as exc:
        logger.warning("Notice: Elasticsearch reindex task not enqueued (%s)", exc)

    print("\n" + "=" * 70)
    print("Seed completed successfully!")
    print("  • 100 Objects (with 8 subtypes and 13 field types)")
    print("  • 18 Entities (Persons and Organizations)")
    print("  • 12 Places (with PostGIS geometries and GeoNames)")
    print("  • 10 Occurrences (Works, Events, Exhibitions)")
    print("  • 8 Collections (hierarchical with parent_id)")
    print("  • 15 Storage Locations (hierarchical with 4 levels)")
    print("  • 8 Procedures (Loans, Acquisition, Conservation, Deaccession)")
    print("  • Custom fields on vocabulary terms")
    print("  • Cross-type schema and generic relations")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
