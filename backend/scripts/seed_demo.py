"""One-off demo data seed: Weimarer-Klassik-Sammlung.

Not committed. Run inside the api container after a full db-reset --all:

    docker compose exec api katalon-manage db-reset --all --no-backup --yes
    docker compose restart api   # recreates authority sources, admin, config
    docker compose exec api python /app/scripts/seed_demo.py

Populates schema (field_definitions + vocabularies) for all four primary
types plus 20 objects / 5 entities / 5 places / 5 occurrences with every
field_type in use, and cross-type relations.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import select, update

from katalon.core.models import (
    AuthoritySource,
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    RecordSubtype,
    Vocabulary,
    VocabularyTerm,
)
from katalon.database import AsyncSessionLocal
from katalon.services.relation_service import sync_schema_relations

# Relation-type terms MUST live in the system "relation_types" vocabulary — the portal's
# generic incoming-relations panel (useRelationTypeLabels.ts, portal_public.py) only ever
# resolves labels/inverse_labels from that one vocab, never from a field's own
# relation_type_vocab. A separate vocab here silently produces unlabeled placeholder terms.
REL_VOCAB_NAME = "relation_types"
MATERIAL_VOCAB_NAME = "materialien"
ORTSTYP_VOCAB_NAME = "ortstypen"
GENRE_VOCAB_NAME = "gattungen"

MATERIAL_LABELS = {"papier": "Papier", "buetten": "Büttenpapier", "karton": "Karton", "leinwand": "Leinwand", "glasnegativ": "Glasnegativ"}
ORTSTYP_LABELS = {"residenzstadt": "Residenzstadt", "stadt": "Stadt", "dorf": "Dorf"}
GENRE_LABELS = {"drama": "Drama", "roman": "Roman", "gedichtzyklus": "Gedichtzyklus", "oper": "Oper", "epos": "Epos"}


async def make_vocab(db, name: str, kind: str, terms: list[dict[str, Any]], hierarchical: bool = False) -> dict[str, str]:
    """Create or reuse a vocabulary, add terms, return {term_code: term_id}."""
    vocab = (await db.execute(select(Vocabulary).where(Vocabulary.name == name))).scalar_one_or_none()
    ids: dict[str, str] = {}
    if vocab is None:
        vocab = Vocabulary(name=name, kind=kind, is_hierarchical=hierarchical)
        db.add(vocab)
        await db.flush()
    else:
        existing = await db.execute(select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab.id))
        ids = {t.term: str(t.id) for t in existing.scalars().all()}
    for t in terms:
        if t["term"] in ids:
            continue
        parent_code = t.pop("parent", None)
        vt = VocabularyTerm(
            vocabulary_id=vocab.id,
            term=t["term"],
            label=t["label"],
            inverse_label=t.get("inverse_label", {}),
            applies_from=t.get("applies_from", []),
            applies_to=t.get("applies_to", []),
            parent_id=uuid.UUID(ids[parent_code]) if parent_code else None,
        )
        db.add(vt)
        await db.flush()
        ids[t["term"]] = str(vt.id)
    return ids


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
    is_translatable: bool = False,
    settings: dict[str, Any] | None = None,
    parent_id: uuid.UUID | None = None,
    detail_role: str = "none",
    detail_slot: str = "sidebar",
) -> FieldDefinition:
    fd = FieldDefinition(
        target_type=target_type,
        name=name,
        label=label,
        field_type=field_type,
        is_required=is_required,
        is_repeatable=is_repeatable,
        is_translatable=is_translatable,
        sort_order=sort_order,
        settings=settings or {},
        parent_id=parent_id,
        detail_role=detail_role,
        detail_slot=detail_slot,
    )
    db.add(fd)
    await db.flush()
    return fd


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # -------------------------------------------------------------- record subtypes
        # object_type/entity_type/place_type/occurrence_type values used below must have a
        # matching RecordSubtype row, or the admin UI refuses to show any schema fields
        # ("Ungültiger Subtyp ... für ...").
        existing_subtypes = {
            (r.primary_type, r.name)
            for r in (await db.execute(select(RecordSubtype))).scalars().all()
        }
        for primary_type, name, label, is_default in [
            ("object", "sammlungsobjekt", {"de": "Sammlungsobjekt"}, True),
            ("entity", "person", {"de": "Person"}, True),
            ("entity", "organisation", {"de": "Organisation"}, False),
            ("place", "ort", {"de": "Ort"}, True),
            ("occurrence", "werk", {"de": "Werk"}, True),
        ]:
            if (primary_type, name) not in existing_subtypes:
                db.add(RecordSubtype(primary_type=primary_type, name=name, label=label, is_default=is_default))
        await db.flush()

        # authority sources used by gnd_id/geonames_id/viaf_pid fields below are disabled
        # by default (except gnd) — enable them so the fields resolve to real links.
        await db.execute(
            update(AuthoritySource).where(AuthoritySource.id.in_(("geonames", "viaf"))).values(is_enabled=True)
        )

        # -------------------------------------------------------------- vocabularies
        rel_ids = await make_vocab(
            db, REL_VOCAB_NAME, "relation",
            [
                {"term": "fotografiert_von", "label": {"de": "fotografiert von"}, "inverse_label": {"de": "fotografierte"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "abgebildete_person", "label": {"de": "abgebildete Person"}, "inverse_label": {"de": "abgebildet in"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "zeigt", "label": {"de": "zeigt"}, "inverse_label": {"de": "gezeigt in"}, "applies_from": ["object"], "applies_to": ["entity", "place", "occurrence"]},
                {"term": "bezieht_sich_auf", "label": {"de": "bezieht sich auf"}, "inverse_label": {"de": "thematisiert in"}, "applies_from": ["object"], "applies_to": ["occurrence"]},
                {"term": "vorbesitzer", "label": {"de": "Vorbesitzer"}, "inverse_label": {"de": "vormals besessen"}, "applies_from": ["object"], "applies_to": ["entity"]},
                {"term": "verfasst_von", "label": {"de": "verfasst von"}, "inverse_label": {"de": "Autor von"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "komponiert_von", "label": {"de": "komponiert von"}, "inverse_label": {"de": "Komponist von"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "spielt_in", "label": {"de": "spielt in"}, "inverse_label": {"de": "Schauplatz von"}, "applies_from": ["occurrence"], "applies_to": ["place"]},
                {"term": "geboren_in", "label": {"de": "geboren in"}, "inverse_label": {"de": "Geburtsort von"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "gestorben_in", "label": {"de": "gestorben in"}, "inverse_label": {"de": "Sterbeort von"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "verwaltet_von", "label": {"de": "verwaltet von"}, "inverse_label": {"de": "verwaltet"}, "applies_from": ["place"], "applies_to": ["entity"]},
                {"term": "nachbarort", "label": {"de": "Nachbarort"}, "inverse_label": {"de": "Nachbarort"}, "applies_from": ["place"], "applies_to": ["place"]},
                {"term": "wirkte_in", "label": {"de": "wirkte in"}, "inverse_label": {"de": "Wirkungsort von"}, "applies_from": ["entity"], "applies_to": ["place"]},
                {"term": "auffuehrung_in", "label": {"de": "aufgeführt in"}, "inverse_label": {"de": "Aufführungsort von"}, "applies_from": ["occurrence"], "applies_to": ["place"]},
                {"term": "mitwirkende", "label": {"de": "mitwirkende Person"}, "inverse_label": {"de": "wirkte mit an"}, "applies_from": ["occurrence"], "applies_to": ["entity"]},
                {"term": "aufgenommen_in", "label": {"de": "aufgenommen in"}, "inverse_label": {"de": "Aufnahmeort von"}, "applies_from": ["object"], "applies_to": ["place"]},
                {"term": "illustriert", "label": {"de": "illustriert"}, "inverse_label": {"de": "illustriert durch"}, "applies_from": ["object"], "applies_to": ["occurrence"]},
            ],
        )
        material_ids = await make_vocab(
            db, MATERIAL_VOCAB_NAME, "term",
            [
                {"term": "papier", "label": {"de": "Papier"}},
                {"term": "buetten", "label": {"de": "Büttenpapier"}, "parent": "papier"},
                {"term": "karton", "label": {"de": "Karton"}, "parent": "papier"},
                {"term": "leinwand", "label": {"de": "Leinwand"}},
                {"term": "glasnegativ", "label": {"de": "Glasnegativ"}},
            ],
            hierarchical=True,
        )
        ortstyp_ids = await make_vocab(
            db, ORTSTYP_VOCAB_NAME, "term",
            [
                {"term": "residenzstadt", "label": {"de": "Residenzstadt"}},
                {"term": "stadt", "label": {"de": "Stadt"}},
                {"term": "dorf", "label": {"de": "Dorf"}},
            ],
        )
        genre_ids = await make_vocab(
            db, GENRE_VOCAB_NAME, "term",
            [
                {"term": "drama", "label": {"de": "Drama"}},
                {"term": "roman", "label": {"de": "Roman"}},
                {"term": "gedichtzyklus", "label": {"de": "Gedichtzyklus"}},
                {"term": "oper", "label": {"de": "Oper"}},
                {"term": "epos", "label": {"de": "Epos"}},
            ],
        )

        # -------------------------------------------------------------- field definitions: object
        obj_material_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == MATERIAL_VOCAB_NAME))).scalar_one()
        obj_ortstyp_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == ORTSTYP_VOCAB_NAME))).scalar_one()
        obj_genre_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == GENRE_VOCAB_NAME))).scalar_one()
        obj_rel_vocab_id = (await db.execute(select(Vocabulary.id).where(Vocabulary.name == REL_VOCAB_NAME))).scalar_one()

        await add_field(db, "object", "beschreibung", {"de": "Beschreibung"}, "richtext", sort_order=1,
                         detail_role="description", detail_slot="main")
        await add_field(db, "object", "material", {"de": "Material"}, "vocab", sort_order=2,
                         settings={"vocabulary_id": str(obj_material_vocab_id)})
        await add_field(db, "object", "technik", {"de": "Technik"}, "vocab_free", sort_order=3,
                         settings={"vocabulary_id": str(obj_material_vocab_id)}, is_repeatable=True)
        await add_field(db, "object", "masse", {"de": "Maße"}, "text", sort_order=4)
        await add_field(db, "object", "anzahl", {"de": "Anzahl Stücke"}, "number", sort_order=5)
        await add_field(db, "object", "ist_ausgestellt", {"de": "Aktuell ausgestellt"}, "boolean", sort_order=6)
        await add_field(db, "object", "inventardatum", {"de": "Inventardatum"}, "date", sort_order=7)
        await add_field(db, "object", "objekt_pid", {"de": "Persistenter Identifier"}, "pid", sort_order=8,
                         settings={"pattern": r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$"})
        await add_field(db, "object", "aufnahmeort_koordinate", {"de": "Aufnahmeort (Koordinate)"}, "geo", sort_order=9)
        await add_field(db, "object", "fotograf", {"de": "Fotograf/in"}, "relation", sort_order=10,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "fotografiert_von"})
        await add_field(db, "object", "abgebildete_person", {"de": "Abgebildete Person"}, "relation", sort_order=11,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "abgebildete_person"})
        await add_field(db, "object", "zeigt_ort", {"de": "Zeigt Ort"}, "relation", sort_order=12,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "zeigt"})
        # Second, distinct place-relation type: a photograph was taken AT a place, which is
        # a different fact from an engraving/painting DEPICTING a place (zeigt_ort above).
        await add_field(db, "object", "aufnahmeort", {"de": "Aufnahmeort"}, "relation", sort_order=13,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "aufgenommen_in"})
        await add_field(db, "object", "bezug_werk", {"de": "Bezug zu Werk/Ereignis"}, "relation", sort_order=14,
                         settings={"target_type": "occurrence", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "bezieht_sich_auf"})
        # Second, distinct occurrence-relation type: a playbill directly illustrates/documents
        # a performance, which is a stronger tie than the generic "bezieht sich auf".
        await add_field(db, "object", "illustriert", {"de": "Illustriert Werk/Ereignis"}, "relation", sort_order=15,
                         settings={"target_type": "occurrence", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "illustriert"})
        objektgeschichte = await add_field(db, "object", "objektgeschichte", {"de": "Objektgeschichte"}, "group", sort_order=13, is_repeatable=True)
        await add_field(db, "object", "ereignistyp", {"de": "Ereignistyp"}, "vocab", sort_order=1,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)}, parent_id=objektgeschichte.id)
        await add_field(db, "object", "person", {"de": "Person"}, "relation", sort_order=2,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "vorbesitzer"}, parent_id=objektgeschichte.id)
        await add_field(db, "object", "datierung", {"de": "Datierung"}, "date", sort_order=3, parent_id=objektgeschichte.id)
        await add_field(db, "object", "ort", {"de": "Ort"}, "relation", sort_order=4,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "zeigt"}, parent_id=objektgeschichte.id)

        # -------------------------------------------------------------- field definitions: entity
        await add_field(db, "entity", "beschreibung", {"de": "Beschreibung"}, "richtext", sort_order=1,
                         detail_role="description", detail_slot="main")
        await add_field(db, "entity", "geburtsdatum", {"de": "Geburtsdatum"}, "date", sort_order=2)
        await add_field(db, "entity", "sterbedatum", {"de": "Sterbedatum"}, "date", sort_order=3)
        await add_field(db, "entity", "gnd_id", {"de": "GND-Normdatum"}, "authority", sort_order=4,
                         settings={"source": "gnd"})
        await add_field(db, "entity", "beruf", {"de": "Beruf/Tätigkeit"}, "vocab_free", sort_order=5,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)}, is_repeatable=True)
        await add_field(db, "entity", "ist_person", {"de": "Ist Einzelperson (kein Kollektiv)"}, "boolean", sort_order=6)
        await add_field(db, "entity", "anzahl_werke", {"de": "Anzahl bekannter Werke"}, "number", sort_order=7)
        # authority, not pid: pidUrl() only resolves urn:nbn: values via nbn-resolving.org,
        # VIAF isn't a URN. AUTHORITY_BASE already maps "viaf" to https://viaf.org/viaf/.
        await add_field(db, "entity", "viaf_pid", {"de": "VIAF-Normdatum"}, "authority", sort_order=8,
                         settings={"source": "viaf"})
        await add_field(db, "entity", "geburtsort", {"de": "Geburtsort"}, "relation", sort_order=9,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "geboren_in"})
        await add_field(db, "entity", "sterbeort", {"de": "Sterbeort"}, "relation", sort_order=10,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "gestorben_in"})
        wirkungsstationen = await add_field(db, "entity", "wirkungsstationen", {"de": "Wirkungsstationen"}, "group", sort_order=11, is_repeatable=True)
        await add_field(db, "entity", "ort", {"de": "Ort"}, "relation", sort_order=1,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id)}, parent_id=wirkungsstationen.id)
        await add_field(db, "entity", "von", {"de": "Von"}, "date", sort_order=2, parent_id=wirkungsstationen.id)
        await add_field(db, "entity", "bis", {"de": "Bis"}, "date", sort_order=3, parent_id=wirkungsstationen.id)
        await add_field(db, "entity", "funktion", {"de": "Funktion"}, "vocab_free", sort_order=4,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)}, parent_id=wirkungsstationen.id)

        # -------------------------------------------------------------- field definitions: place
        await add_field(db, "place", "beschreibung", {"de": "Beschreibung"}, "richtext", sort_order=1,
                         detail_role="description", detail_slot="main")
        await add_field(db, "place", "geonames_id", {"de": "Geonames-Normdatum"}, "authority", sort_order=2,
                         settings={"source": "geonames"})
        await add_field(db, "place", "plz", {"de": "Postleitzahl"}, "text", sort_order=3)
        await add_field(db, "place", "ist_hauptort", {"de": "Hauptort der Region"}, "boolean", sort_order=4)
        await add_field(db, "place", "ersterwaehnung", {"de": "Ersterwähnung"}, "date", sort_order=5)
        await add_field(db, "place", "einwohnerzahl", {"de": "Einwohnerzahl (historisch)"}, "number", sort_order=6)
        await add_field(db, "place", "ortstyp", {"de": "Ortstyp"}, "vocab", sort_order=7,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)})
        await add_field(db, "place", "grenzpunkt", {"de": "Referenzpunkt"}, "geo", sort_order=8)
        await add_field(db, "place", "verwaltet_von", {"de": "Verwaltet von"}, "relation", sort_order=9,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "verwaltet_von"})
        nachbarorte = await add_field(db, "place", "nachbarorte", {"de": "Nachbarorte"}, "group", sort_order=10, is_repeatable=True)
        await add_field(db, "place", "ort", {"de": "Ort"}, "relation", sort_order=1,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "nachbarort"}, parent_id=nachbarorte.id)
        await add_field(db, "place", "beziehungsart", {"de": "Beziehungsart"}, "vocab_free", sort_order=2,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)}, parent_id=nachbarorte.id)

        # -------------------------------------------------------------- field definitions: occurrence
        await add_field(db, "occurrence", "beschreibung", {"de": "Beschreibung"}, "richtext", sort_order=1,
                         detail_role="description", detail_slot="main")
        await add_field(db, "occurrence", "entstehungsdatum", {"de": "Entstehungsdatum"}, "date", sort_order=2)
        await add_field(db, "occurrence", "gattung", {"de": "Gattung"}, "vocab", sort_order=3,
                         settings={"vocabulary_id": str(obj_genre_vocab_id)})
        await add_field(db, "occurrence", "form", {"de": "Form"}, "vocab_free", sort_order=4,
                         settings={"vocabulary_id": str(obj_genre_vocab_id)}, is_repeatable=True)
        await add_field(db, "occurrence", "verfasser", {"de": "Verfasser/in"}, "relation", sort_order=5,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "verfasst_von"})
        await add_field(db, "occurrence", "komponist", {"de": "Komponist/in"}, "relation", sort_order=6,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "komponiert_von"})
        await add_field(db, "occurrence", "spielort", {"de": "Spielort"}, "relation", sort_order=7,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id), "fixed_relation_type": "spielt_in"})
        await add_field(db, "occurrence", "werk_pid", {"de": "Persistenter Identifier"}, "pid", sort_order=8)
        await add_field(db, "occurrence", "ist_vollendet", {"de": "Vollendet"}, "boolean", sort_order=9)
        await add_field(db, "occurrence", "umfang", {"de": "Umfang (Akte/Seiten)"}, "number", sort_order=10)
        auffuehrungen = await add_field(db, "occurrence", "auffuehrungen", {"de": "Aufführungen/Ausgaben"}, "group", sort_order=11, is_repeatable=True)
        await add_field(db, "occurrence", "datum", {"de": "Datum"}, "date", sort_order=1, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "ort", {"de": "Ort"}, "relation", sort_order=2,
                         settings={"target_type": "place", "relation_type_vocab": str(obj_rel_vocab_id)}, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "person", {"de": "Person"}, "relation", sort_order=3,
                         settings={"target_type": "entity", "relation_type_vocab": str(obj_rel_vocab_id)}, parent_id=auffuehrungen.id)
        await add_field(db, "occurrence", "rolle", {"de": "Rolle"}, "vocab_free", sort_order=4,
                         settings={"vocabulary_id": str(obj_ortstyp_vocab_id)}, parent_id=auffuehrungen.id)

        await db.commit()

        # ============================================================== records: places
        places_data = [
            ("weimar", "Weimar", "residenzstadt", "99423", True, "-0975", 6000, (50.9795, 11.3235)),
            ("jena", "Jena", "stadt", "07743", False, "0852", 4500, (50.9271, 11.5892)),
            ("frankfurt-am-main", "Frankfurt am Main", "stadt", "60311", False, "0794", 30000, (50.1109, 8.6821)),
            ("rom", "Rom", "stadt", "00184", False, "-0753", 160000, (41.9028, 12.4964)),
            ("strassburg", "Straßburg", "stadt", "67000", False, "0012", 25000, (48.5734, 7.7521)),
        ]
        places: dict[str, Place] = {}
        for idno, label_de, ortstyp, plz, hauptort, ersterw, einwohner, (lat, lon) in places_data:
            p = Place(
                idno=f"PLACE-{idno.upper()}",
                place_type="ort",
                status="public",
                # Portal map (StaticMap in PlaceDetailPage.tsx) reads lat/lon from this
                # PostGIS column via the API's PlaceRead schema — NOT from the "grenzpunkt"
                # metadata field or the geonames authority link. Must be set explicitly.
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                metadata_={
                    "label": label_de,
                    "beschreibung": f"{label_de} ist ein zentraler Schauplatz der Weimarer Klassik.",
                    "plz": plz,
                    "ist_hauptort": hauptort,
                    "ersterwaehnung": ersterw,
                    "einwohnerzahl": einwohner,
                    "ortstyp": {"id": ortstyp_ids[ortstyp], "label": ORTSTYP_LABELS[ortstyp]},
                    "grenzpunkt": f"{lat},{lon}",
                    "geonames_id": {"source": "geonames", "external_id": f"28524{len(places)}", "label": label_de},
                },
            )
            db.add(p)
            places[idno] = p
        await db.flush()

        # ============================================================== records: entities
        entities_data = [
            ("goethe", "Johann Wolfgang von Goethe", "1749-08-28", "1832-03-22", "Dichter, Naturforscher, Staatsmann", "frankfurt-am-main", "weimar"),
            ("schiller", "Friedrich Schiller", "1759-11-10", "1805-05-09", "Dichter, Dramatiker, Historiker", None, "weimar"),
            ("herder", "Johann Gottfried Herder", "1744-08-25", "1803-12-18", "Theologe, Philosoph, Dichter", None, "weimar"),
            ("schroeter-atelier", "Atelier Schröter", "1860", "1920", "Hoffotograf-Atelier", None, None),
            ("gnd-verein", "Klassik-Gesellschaft Weimar e.V.", None, None, "Trägerverein, kein Individuum", None, None),
        ]
        entities: dict[str, Entity] = {}
        for idno, name, geb, gest, beruf, geb_ort, gest_ort in entities_data:
            md: dict[str, Any] = {
                "label": name,
                "beschreibung": f"{name} — Teil der Sammlung Weimarer Klassik.",
                "beruf": [beruf],
                "ist_person": idno not in ("gnd-verein",),
                "anzahl_werke": 42 if idno in ("goethe", "schiller") else 3,
                "viaf_pid": {"source": "viaf", "external_id": str(1000 + len(entities)), "label": name},
                "gnd_id": {"source": "gnd", "external_id": f"11850053{len(entities)}", "label": name},
                "wirkungsstationen": [
                    {"ort": rel(str(places["weimar"].id), "Weimar", "wirkte_in") if geb_ort or gest_ort else None, "von": geb or "", "bis": gest or "", "funktion": "Wirkungsort"}
                ] if idno in ("goethe", "schiller", "herder") else [],
            }
            if geb:
                md["geburtsdatum"] = geb
            if gest:
                md["sterbedatum"] = gest
            if geb_ort:
                md["geburtsort"] = rel(str(places[geb_ort].id), places[geb_ort].metadata_["label"], "geboren_in")
            if gest_ort:
                md["sterbeort"] = rel(str(places[gest_ort].id), places[gest_ort].metadata_["label"], "gestorben_in")
            e = Entity(idno=f"ENT-{idno.upper()}", entity_type="person" if idno not in ("gnd-verein",) else "organisation",
                       status="public", metadata_=md)
            db.add(e)
            entities[idno] = e
        await db.flush()

        # ============================================================== records: occurrences
        occ_data = [
            ("faust", "Faust. Eine Tragödie", "1808", "drama", "goethe", None, "weimar"),
            ("raeuber", "Die Räuber", "1781", "drama", "schiller", None, "jena"),
            ("werther", "Die Leiden des jungen Werthers", "1774", "roman", "goethe", None, "frankfurt-am-main"),
            ("roemische-elegien", "Römische Elegien", "1790", "gedichtzyklus", "goethe", None, "rom"),
            ("ideen-geschichte", "Ideen zur Philosophie der Geschichte der Menschheit", "1791", "epos", "herder", None, "weimar"),
        ]
        occurrences: dict[str, Occurrence] = {}
        for idno, title, jahr, gattung, verfasser, komponist, spielort in occ_data:
            md = {
                "label": title,
                "beschreibung": f"{title} entstand im Umfeld der Weimarer Klassik.",
                "entstehungsdatum": jahr,
                "gattung": {"id": genre_ids[gattung], "label": GENRE_LABELS[gattung]},
                "form": [gattung],
                "verfasser": rel(str(entities[verfasser].id), entities[verfasser].metadata_["label"], "verfasst_von") if verfasser else None,
                "spielort": rel(str(places[spielort].id), places[spielort].metadata_["label"], "spielt_in") if spielort else None,
                "werk_pid": {"value": f"urn:nbn:de:demo-{idno}", "label": "URN"},
                "ist_vollendet": True,
                "umfang": 5 if gattung == "drama" else 1,
                "auffuehrungen": [
                    {"datum": jahr, "ort": rel(str(places[spielort].id), places[spielort].metadata_["label"], "auffuehrung_in") if spielort else None,
                     "person": rel(str(entities[verfasser].id), entities[verfasser].metadata_["label"], "mitwirkende") if verfasser else None,
                     "rolle": "Uraufführung"},
                ],
            }
            o = Occurrence(idno=f"OCC-{idno.upper()}", occurrence_type="werk", status="public", metadata_=md)
            db.add(o)
            occurrences[idno] = o
        await db.flush()

        # ============================================================== records: objects (20)
        photographer = entities["schroeter-atelier"]
        obj_templates = [
            ("Bildnis Goethe im Alter", "goethe", "weimar", "faust", "leinwand", "Ölmalerei"),
            ("Bildnis Schiller", "schiller", "weimar", "raeuber", "leinwand", "Ölmalerei"),
            ("Porträtfoto Herder", "herder", "weimar", "ideen-geschichte", "glasnegativ", "Albumin-Abzug"),
            ("Erstausgabe Faust", None, "weimar", "faust", "papier", "Buchdruck"),
            ("Erstausgabe Die Räuber", None, "jena", "raeuber", "papier", "Buchdruck"),
            ("Manuskriptseite Werther", "goethe", "frankfurt-am-main", "werther", "buetten", "Handschrift"),
            ("Ansicht Weimar um 1800", None, "weimar", None, "karton", "Kupferstich"),
            ("Ansicht Rom, Forum Romanum", None, "rom", "roemische-elegien", "papier", "Radierung"),
            ("Reisepass Goethe (Italienreise)", "goethe", "rom", "roemische-elegien", "papier", "Handschrift"),
            ("Brief Goethe an Schiller", "goethe", "weimar", None, "papier", "Handschrift"),
            ("Brief Schiller an Herder", "schiller", "weimar", None, "papier", "Handschrift"),
            ("Totenmaske Goethe", "goethe", "weimar", None, "karton", "Gipsabguss"),
            ("Silhouette Herder", "herder", "weimar", None, "papier", "Scherenschnitt"),
            ("Fotografie Schillerhaus", None, "weimar", None, "glasnegativ", "Albumin-Abzug"),
            ("Fotografie Goethehaus", None, "weimar", None, "glasnegativ", "Albumin-Abzug"),
            ("Notenmanuskript Vertonung Erlkönig", "goethe", "jena", None, "buetten", "Handschrift"),
            ("Theaterzettel Uraufführung Räuber", None, "jena", "raeuber", "papier", "Buchdruck"),
            ("Kupferstich Straßburger Münster", None, "strassburg", None, "karton", "Kupferstich"),
            ("Studienheft Herder Straßburg", "herder", "strassburg", None, "papier", "Handschrift"),
            ("Fotografie Atelier Schröter, Gruppenbild", "goethe", "weimar", "faust", "glasnegativ", "Albumin-Abzug"),
        ]
        for i, (title, ent_key, place_key, occ_key, material, technik) in enumerate(obj_templates, start=1):
            md: dict[str, Any] = {
                "label": title,
                "beschreibung": f"{title} — Bestandteil der Sammlung Weimarer Klassik.",
                "material": {"id": material_ids[material], "label": MATERIAL_LABELS[material]},
                "technik": [technik],
                "masse": f"{20 + i} x {15 + i} cm",
                "anzahl": 1,
                "ist_ausgestellt": i % 3 == 0,
                "inventardatum": f"20{10 + (i % 10):02d}-0{1 + (i % 9)}",
                "objekt_pid": {"value": f"10.5072/demo.obj.{i:04d}", "label": "DOI"},
                "aufnahmeort_koordinate": "50.9795,11.3235",
                "fotograf": rel(str(photographer.id), photographer.metadata_["label"], "fotografiert_von") if "Fotografie" in title else None,
                "abgebildete_person": rel(str(entities[ent_key].id), entities[ent_key].metadata_["label"], "abgebildete_person") if ent_key and any(word in title for word in ("Bildnis", "Porträt", "Silhouette")) else None,
                # A photograph was taken AT a place (aufnahmeort); a painting/engraving instead
                # DEPICTS a place (zeigt_ort) — two distinct relation types, not one blurred field.
                "zeigt_ort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "zeigt") if place_key and "Fotografie" not in title else None,
                "aufnahmeort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "aufgenommen_in") if place_key and "Fotografie" in title else None,
                # A playbill directly illustrates a performance (illustriert); other objects
                # merely relate to a work in a looser sense (bezug_werk).
                "bezug_werk": rel(str(occurrences[occ_key].id), occurrences[occ_key].metadata_["label"], "bezieht_sich_auf") if occ_key and "Theaterzettel" not in title else None,
                "illustriert": rel(str(occurrences[occ_key].id), occurrences[occ_key].metadata_["label"], "illustriert") if occ_key and "Theaterzettel" in title else None,
                "objektgeschichte": [
                    {
                        "ereignistyp": {"id": ortstyp_ids["stadt"], "label": ORTSTYP_LABELS["stadt"]},
                        "person": rel(str(entities[ent_key].id), entities[ent_key].metadata_["label"], "vorbesitzer") if ent_key else None,
                        "datierung": f"19{10 + i}",
                        "ort": rel(str(places[place_key].id), places[place_key].metadata_["label"], "zeigt") if place_key else None,
                    }
                ] if ent_key else [],
            }
            o = Object(idno=f"OBJ-{i:03d}", object_type="sammlungsobjekt", status="public", metadata_=md)
            db.add(o)
        await db.flush()
        await db.commit()

        # -------------------------------------------------------------- mirror relation fields into `relations`
        result = await db.execute(select(Object))
        for obj in result.scalars().all():
            await sync_schema_relations(db, "object", obj.id, obj.metadata_)
        result = await db.execute(select(Entity))
        for ent in result.scalars().all():
            await sync_schema_relations(db, "entity", ent.id, ent.metadata_)
        result = await db.execute(select(Place))
        for pl in result.scalars().all():
            await sync_schema_relations(db, "place", pl.id, pl.metadata_)
        result = await db.execute(select(Occurrence))
        for occ in result.scalars().all():
            await sync_schema_relations(db, "occurrence", occ.id, occ.metadata_)
        await db.commit()

    print("Seed done: 5 places, 5 entities, 5 occurrences, 20 objects, 4 vocabularies, schema fields.")


if __name__ == "__main__":
    asyncio.run(main())
