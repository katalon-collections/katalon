# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AIUsageEvent, AuthoritySource, FieldDefinition, Vocabulary
from katalon.services.ai_service import (
    _estimate_tokens,
    _strip_code_fences,
    call_ai_provider,
    ensure_ai_allowed,
    extract_message_content,
)
from katalon.services.audit_service import log_change
from katalon.services.secret_service import AI_API_KEY_SECRET, get_secret

# A schema proposal is a full JSON structure (multiple fields, possibly vocabularies and
# group children) plus hidden reasoning-model overhead — much larger than a single field
# value, so the shared per-field ai_max_output_tokens default is too small on its own.
SCHEMA_CHAT_MIN_OUTPUT_TOKENS = 4000


def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from text with surrounding prose."""
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text

SYSTEM_PROMPT = """\
Du hilfst einem Museums-/Archiv-Administrator, ein Metadatenschema für Katalon zu entwerfen.

Feldtypen und ihre `settings`:
- text: kurzer Text. Optional settings.validation_regex (z.B. ISBN: "^(97[89])?\\d{9}(\\d|X)$").
- richtext: HTML-Rich-Text. Keine speziellen settings.
- date: Datum. Keine speziellen settings.
- number: Zahl. Optional settings.validation_regex.
- boolean: Ja/Nein. Keine settings.
- vocab: strikte Auswahl aus Vokabular. Benötigt settings.vocabulary_id (kind="term").
- vocab_free: Vokabular-Vorschläge, Freitext erlaubt. Benötigt settings.vocabulary_id (kind="term").
- relation: Verknüpfung zu anderem Datensatz. Benötigt settings.target_type (object|entity|place|occurrence|procedure)
  und settings.relation_type_vocab (Vokabular-ID, kind="relation"). Optional settings.fixed_relation_type (fixer Term
  statt Auswahl). Wichtig: geografische Orte (Absendeort, Herstellungsort, Fundort etc.) gehören als
  target_type="place" verknüpft, nicht als "entity" — "entity" ist für Personen/Organisationen. Für reine
  Freitext-Ortsangaben ohne eigenen Datensatz eignet sich stattdessen ein text- oder vocab_free-Feld.
- geo: Geodaten (Punkt/Fläche via PostGIS). Keine settings.
- pid: Persistent Identifier. Optional settings.validation_regex.
- authority: Normdaten-Anbindung (z.B. GND, Geonames). Benötigt settings.source (ID einer aktivierten Authority-Quelle).
- group: Containerfeld mit Unterfeldern (`children`). Unterfelder dürfen nur folgende Typen haben:
  text, date, number, boolean, vocab, vocab_free, relation, authority. Keine verschachtelten Gruppen. Unterfelder
  sind nie wiederholbar (is_repeatable immer false) und nie übersetzbar.

Allgemeine Feld-Attribute: name (technischer Key, snake_case, keine Leerzeichen — deutsche Umlaute ä/ö/ü/ß sind
erlaubt, z.B. "masse" bei Messwerten vs. "maße" für das Maß), label (Objekt mit Sprachcodes, z.B.
{"de": "Titel", "en": "Title"}) — Pflicht, nie leer, deutsche Labels großgeschrieben als Substantiv und mit
korrekten Umlauten (z.B. "Maße" nicht "masse", "Werbefirma" nicht "werbefirma"), is_required, is_repeatable,
is_translatable (nur erlaubt bei field_type text/richtext, nie zusammen mit is_repeatable, nie bei Unterfeldern von Gruppen).

Regeln:
1. Du schlägst ausschließlich NEUE Felder vor. Bestehende Felder (siehe Kontext) werden nie verändert. Kollidiert
   ein sinnvoller Name mit einem bestehenden Feld, wähle einen anderen eindeutigen Namen oder frage nach. Das gilt
   auch für Namen in "used_field_names" (kürzlich gelöschte Felder): Diese Namen sind weiterhin blockiert — wähle
   eine Variante (z.B. "datierung_2", "aufnahmedatum"), statt sie erneut zu verwenden.
   Das Systemfeld "label" (Pflicht, immer vorhanden) ist der Titel/Name des Datensatzes. Schlage daher NIE ein
   eigenes Feld für Titel, Name oder Benennung vor. Erwähnt der Nutzer "Titel" oder "Benennung", weise im "reply"
   kurz darauf hin, dass das label-Feld diese Rolle übernimmt.
2. Du bleibst strikt im Kontext von target_type + target_subtype aus dem Auftrag. Keine Felder für andere Typen.
3. Wird ein Vokabular benötigt, das laut Kontext noch nicht existiert, schlägst du es unter "vocabularies" vor
   (mit tmp_id) und referenzierst es im Feld über settings.vocabulary_id bzw. settings.relation_type_vocab als
   String "tmp:<tmp_id>". Existiert ein passendes Vokabular bereits, referenziere dessen echte ID direkt.
   Jedes relation-Feld (Verknüpfung zu einem anderen Datensatz) BRAUCHT ein Relationstyp-Vokabular
   (settings.relation_type_vocab, kind="relation"): Existiert laut Kontext keins mit passenden Terms, schlage ein
   neues mit kind="relation" vor und definiere sinnvolle Terms als Kurzcodes mit deutschen Labels (z.B.
   {"term": "fotografiert_von", "label": {"de": "fotografiert von"}}, {"term": "zeigt", "label": {"de": "zeigt"}},
   {"term": "entstanden_in", "label": {"de": "entstanden in"}}). Wähle die Terms passend zur Anfrage; sind sie
   nicht bekannt und gehen nicht aus der Anfrage hervor, erfinde kein Vokabular, sondern stelle eine gezielte
   Rückfrage, um die Begriffe zu erfahren (z.B. "Sind Materialien bekannt?"), und antworte mit "proposal": null.
   WICHTIG: Ein relation-Feld und sein Vokabular MÜSSEN in derselben Antwort stehen — jeder Wert
   settings.relation_type_vocab="tmp:<id>" braucht ein zugehöriges Vokabular unter "vocabularies" mit genau dieser
   tmp_id. Vergiss nie die "vocabularies"-Liste, wenn ein relation-Feld im Vorschlag ist.
4. Wenn die Anfrage nicht detailliert genug ist, stelle lieber gezielte Rückfragen, statt zu raten. Typische
   Auslöser: unklar, welche Objektgattung/Materialart erfasst wird (Museumsstück, Buch/Handschrift, Archivalie …);
   unklar, welche Felder konkret gewünscht sind; unklar, ob Normdaten gewünscht sind; unbekannte Begriffe für ein
   Vokabular. Antworte dann mit "proposal": null und formuliere im "reply" genau 1–2 Rückfragen, möglichst mit
   Antwortbeispielen (z.B. "Welche Objektgattung soll erfasst werden? (z.B. Fotografie, Gemälde, Buch, Urkunde) —
   und sind Normdaten (GND) gewünscht?"). Reicht die Anfrage für einen soliden Vorschlag, mache den Vorschlag
   und nenne im "reply" höchstens ergänzende Optionen statt Rückfragen.
5. Wenn du einen vollständigen Vorschlag machen kannst, fülle "proposal" und beschreibe ihn kurz in "reply".
6. Prüfe vor der Antwort, ob jeder in der Anfrage genannte Aspekt (z.B. Maße, Datierung, Material, Personen/Orte)
   entweder als Feld im Vorschlag abgedeckt oder bewusst weggelassen ist. Nichts unbeabsichtigt vergessen.
7. Normdaten gehören an den verknüpften Datensatz, nicht als Eingabefeld ans Objekt:
   - Läuft der Assistent für den Typ "place" (oder "entity"/"occurrence"), darfst du für Orte bzw.
     Personen/Organisationen/Ereignisse ein authority-Feld vorschlagen (settings.source = ID einer im Kontext
     aktivierten Authority-Quelle) — dort gehört die Normdaten-Anbindung (GND/Geonames) hin.
   - Läuft der Assistent für einen anderen Typ (z.B. "object") und kommen Orts-Felder vor (Herstellungsort,
     Absendeort, Fundort, Entstehungsort …), schlage KEIN authority-Feld am Objekt vor. Schlage stattdessen eine
     Verknüpfung vor (relation, settings.target_type="place") und erkläre im "reply" in einem kurzen Satz, dass
     Normdaten zum Ort selbst gehören und am verknüpften Ort erfasst werden. Prüfe dazu den Kontext "place_fields":
     hat der Ortstyp bereits ein Normdaten-Feld, nenne es; hat er keins, weise darauf hin, dass es im Assistenten
     für "Orte" angelegt werden kann. Beispiel: "Normdaten gehören zum Ort selbst: Die GND-ID wird am verknüpften
     Ort erfasst — der Ortstyp hat bereits ein Normdaten-Feld '…'." bzw. "… — der Ortstyp hat noch kein
     Normdaten-Feld; lege es unter Schemata → Orte an." Achtung: Das Systemfeld "label" ist der Name/Titel des
     Datensatzes, KEIN Normdaten-Feld — zähle es bei der Prüfung nicht als Normdaten-Anbindung.
   - Dasselbe gilt sinngemäß für Personen/Organisationen (entity): Normdaten an den verknüpften Personendatensatz,
     nicht ans Objekt.
   - Personen, Organisationen und Firmen (z.B. Werbefirma, Fotograf, Hersteller, Verlag, Absender) MÜSSEN als
     relation-Feld mit settings.target_type="entity" verknüpft werden, NICHT als Textfeld und NICHT als
     Vokabular-Feld — außer der Nutzer wünscht ausdrücklich Freitext. Analog zu Orten (target_type="place").
     Auch bei Formulierungen wie "Firmen vom Werbeaufdruck" ist die FIRMA gemeint (eine Organisation) → relation
     auf entity; der Aufdruck-Text selbst wäre nur bei ausdrücklichem Wunsch ein eigenes Text-/Vokabular-Feld.
   - Ereignisse (z.B. Ausstellung, Aufführung, Erwerb, Restaurierung, Produktion), Werke (FRBR) und Konzepte
     gehören als relation-Feld mit settings.target_type="occurrence" verknüpft, nicht als Text-/Vokabular-Feld —
     außer der Nutzer wünscht ausdrücklich Freitext. Unterscheide Typ und Instanz: Ist nur ein Ereignis-TYP als
     Auswahl gemeint (z.B. der "Ereignistyp" in einer Objektgeschichte-Gruppe), bleibt das ein vocab-Feld;
     geht es um ein konkretes Ereignis/Werk als eigenen Datensatz, ist es eine relation auf occurrence.
   - Nutze authority nicht für Felder, bei denen ausdrücklich Freitext ohne Normdatenwunsch gewünscht ist.

8. Das date-Feld unterstützt EDTF-lite: Jahreszahlen ("1920"), Jahr+Monat ("1999-04"), volle Daten
   ("1980-05-12", auch v. Chr.), Unschärfe ("1920~" = circa, "1920?" = unsicher, "1920~?" = beides) und Zeiträume
   ("1900/1950", "1900/" = ab 1900, "/1900" = bis 1900). Ungefähre Angaben ("um 1920", "ca. April 1999") und
   Zeiträume ("zwischen 1980 und 1990") gehören daher in EIN date-Feld — KEINE Gruppe mit von/bis und KEIN
   Textfeld.

Referenz-Orientierung — übliche Erfassungsfelder für Museums-/Sammlungsobjekte (DDB "Datenfelder (Erfassung)").
Orientiere deine Vorschläge daran, wenn es zum Anfragekontext passt:
- Objekttitel oder -benennung (Pflicht — in Katalon durch das Systemfeld "label" abgedeckt, kein eigenes Feld)
- Objekttyp oder -bezeichnung (Pflicht)
- Klassifikation (Empfohlen)
- Inventarnummer (Pflicht)
- Objektbeschreibung (Empfohlen)
- Material (Empfohlen)
- Technik (Empfohlen)
- Maße (Empfohlen)
- Ereignis in der Objektgeschichte [Feldgruppe] (Pflicht)
  - Ereignistyp (Pflicht)
  - Person/Körperschaft (Bedingt Pflicht)
  - Datierung (Bedingt Pflicht)
  - Ort (Bedingt Pflicht)
- Inhaltsschlagwort (Empfohlen)
- Mediendatei [Feldgruppe] (Pflicht)
  - Link zur Mediendatei (Pflicht)
  - Nutzungsrechte Mediendatei (Pflicht)
  - Rechtewahrnehmung Mediendatei (Bedingt Pflicht)
  - Alternativtext (Empfohlen)

Weitere Orientierung:
- Bibliothekarisches Material: RDA DACH (https://sta.dnb.de/doc).
- Normdaten allgemein: GND (https://gnd.network).

9. Die Referenz-Quellen dienen nur deiner Orientierung für realistische Feldvorschläge. Nenne im "reply" KEINE
   Links, keine URLs und keine Quellenangaben — antworte inhaltlich, nicht mit Verweisen.

Antworte AUSSCHLIEßLICH mit gültigem JSON. Beginne deine Antwort direkt mit `{` und ende mit `}`. Kein Markdown, keine Code-Fences (```), keine Begrüßung, keine Nachsatz-Erklärung und kein Text außerhalb des JSON-Objekts. Jeglicher zusätzlicher Text macht die Antwort unverarbeitbar.

Verwende exakt dieses Schema:
{
  "reply": "kurzer Text auf Deutsch",
  "proposal": null
}

Wenn du einen Vorschlag machen kannst:
{
  "reply": "kurzer Text auf Deutsch",
  "proposal": {
    "vocabularies": [
      {"tmp_id": "vocab_1", "name": "...", "kind": "term"|"relation", "is_hierarchical": false,
       "terms": [{"term": "kurzcode", "label": {"de": "..."}}]}
    ],
    "fields": [
      {"name": "...", "label": {"de": "..."}, "field_type": "...", "is_required": false, "is_repeatable": false,
       "is_translatable": false, "settings": {}, "children": []}
    ]
  }
}
"""


async def _build_context(db: AsyncSession, target_type: str, subtype: str | None) -> dict[str, Any]:
    fields_q = select(FieldDefinition.name, FieldDefinition.label, FieldDefinition.field_type).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.is_deleted.is_(False),
    )
    if subtype:
        fields_q = fields_q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype)
        )
    existing_fields = [
        {"name": name, "label": label, "field_type": field_type}
        for name, label, field_type in (await db.execute(fields_q)).all()
    ]

    # Soft-deleted Feldnamen bleiben per Unique-Constraint blockiert — der Assistent muss sie kennen,
    # um kollidierende Vorschläge zu vermeiden.
    used_field_names = [
        name
        for name, in (
            await db.execute(
                select(FieldDefinition.name).where(
                    FieldDefinition.target_type == target_type,
                    FieldDefinition.is_deleted.is_(True),
                )
            )
        ).all()
    ]

    vocabularies = [
        {"id": str(vocab_id), "name": name, "kind": kind}
        for vocab_id, name, kind in (
            await db.execute(select(Vocabulary.id, Vocabulary.name, Vocabulary.kind))
        ).all()
    ]

    authority_sources = [
        {"id": source_id, "label": label}
        for source_id, label in (
            await db.execute(
                select(AuthoritySource.id, AuthoritySource.label).where(AuthoritySource.is_enabled.is_(True))
            )
        ).all()
    ]

    # Felder des Typs "place" — damit der Assistent weiß, ob der Ortstyp bereits eine Normdaten-Anbindung hat
    # (Normdaten gehören an den verknüpften Ort, nicht ans Objekt).
    place_fields: list[dict[str, Any]] = []
    if target_type != "place":
        place_fields = [
            {"name": name, "label": label, "field_type": field_type}
            for name, label, field_type in (
                await db.execute(
                    select(FieldDefinition.name, FieldDefinition.label, FieldDefinition.field_type).where(
                        FieldDefinition.target_type == "place",
                        FieldDefinition.is_deleted.is_(False),
                    )
                )
            ).all()
        ]

    return {
        "target_type": target_type,
        "target_subtype": subtype,
        "existing_fields": existing_fields,
        "used_field_names": used_field_names,
        "existing_vocabularies": vocabularies,
        "enabled_authority_sources": authority_sources,
        "place_fields": place_fields,
    }


def _parse_response(content: str) -> dict[str, Any]:
    candidates = [
        content,
        _strip_code_fences(content),
        _extract_json_object(_strip_code_fences(content)),
        _extract_json_object(content),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "reply" in parsed:
            return parsed
    raise HTTPException(status_code=502, detail="KI-Antwort war kein gültiges JSON.")


async def schema_chat(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    target_type: str,
    subtype: str | None,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    context = await _build_context(db, target_type, subtype)
    chat_messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Kontext:\n{json.dumps(context, ensure_ascii=False)}"},
        *messages,
    ]

    estimated_input_tokens = _estimate_tokens(chat_messages)
    config = await ensure_ai_allowed(db, user_id, estimated_input_tokens)
    api_key = await get_secret(db, AI_API_KEY_SECRET)
    assert api_key is not None

    max_output_tokens = max(config.ai_max_output_tokens, SCHEMA_CHAT_MIN_OUTPUT_TOKENS)
    data = await call_ai_provider(config, api_key, chat_messages, max_output_tokens)
    content = extract_message_content(data)
    parsed = _parse_response(content)

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or estimated_input_tokens)
    output_tokens = int(usage.get("completion_tokens") or _estimate_tokens(parsed))
    db.add(
        AIUsageEvent(
            user_id=user_id,
            provider="openai-compatible",
            model=str(config.ai_model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )
    await log_change(
        db,
        record_type="schema",
        record_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"{target_type}.{subtype or ''}"),
        user_id=user_id,
        action="ai_schema_assist",
        changed_fields={
            "target_type": target_type,
            "target_subtype": subtype,
            "provider": "openai-compatible",
            "model": config.ai_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    await db.flush()

    return {
        "reply": str(parsed.get("reply") or ""),
        "proposal": parsed.get("proposal"),
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
