# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""AI-assisted Natural Language to SPARQL (NL2SPARQL) service.

Translates human queries in natural language (German/English) into syntactically
valid, read-only SPARQL 1.1 queries aligned with Katalon's CIDOC-CRM/LRMoo/SKOS RDF projection.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AIUsageEvent
from katalon.integrations.oxigraph import validate_read_only_sparql
from katalon.services.ai_service import (
    _estimate_tokens,
    _strip_code_fences,
    call_ai_provider,
    ensure_ai_allowed,
    extract_message_content,
)
from katalon.services.audit_service import log_change
from katalon.services.secret_service import AI_API_KEY_SECRET, get_secret

logger = logging.getLogger(__name__)

NL2SPARQL_MIN_OUTPUT_TOKENS = 2000

SYSTEM_PROMPT = """You are an expert SPARQL query generator for the Katalon GLAM Metadata Management System.
Your task is to translate a user's natural language request into a valid, read-only SPARQL 1.1 SELECT or ASK query.

KATALON RDF PROJECTION & ONTOLOGY CONVENTIONS:
Prefixes:
  PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
  PREFIX lrmoo: <http://iflastandards.info/ns/lrm/lrmoo/>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
  PREFIX dcterms: <http://purl.org/dc/terms/>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
  PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
  PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

Core Classes:
  - Object (Artefakte, Fotos, Gemälde, Digitalisate): crm:E22_Human_Made_Object, lrmoo:F5_Item
  - Entity (Personen, Körperschaften / Organisationen): crm:E21_Person, crm:E74_Group
  - Place (Orte, Standorte): crm:E53_Place
  - Occurrence (Werke, Ereignisse, Ausstellungen): lrmoo:F1_Work, lrmoo:F2_Expression, crm:E5_Event
  - Collection (Sammlungen, Bestände): crm:E78_Curated_Holding
  - Vocabulary Terms (Konzepte): skos:Concept

Common Properties:
  - Title: crm:P102_has_title (can point to title node with rdfs:label or directly rdfs:label)
  - Identifier / Inventarnummer: crm:P1_is_identified_by -> [ a crm:E42_Identifier ; crm:P190_has_symbolic_content ?idno ]
  - Creator / Author / Artist: crm:P14_carried_out_by (e.g. ?object crm:P14_carried_out_by ?person)
  - Depicts / Represents: crm:P138_represents (e.g. ?object crm:P138_represents ?entity)
  - Place / Location: crm:P7_took_place_at (e.g. ?event crm:P7_took_place_at ?place)
  - Storage Location: crm:P53_has_former_or_current_location
  - Owner: crm:P52_has_current_owner
  - Part of / Composed of: crm:P46_is_composed_of
  - Realised in: lrmoo:R3_is_realised_in
  - Embodied in: lrmoo:R4_is_embodied_in
  - Exemplifies: lrmoo:R7_exemplifies
  - Label / Name: rdfs:label, skos:prefLabel

CRITICAL RULES:
1. ONLY produce read-only SPARQL queries (SELECT, ASK, CONSTRUCT, or DESCRIBE). NEVER generate INSERT, DELETE, DROP, CLEAR, LOAD, or any UPDATE query.
2. Always declare necessary PREFIX statements at the top.
3. Always include a sensible LIMIT (e.g. LIMIT 50 or 100) unless explicitly asked for a count.
4. Always use `SELECT DISTINCT` unless aggregating/counting, to prevent duplicates across linked named graphs.
5. Use descriptive variable names (e.g. ?object, ?title, ?creator, ?place).
6. Output format must be a JSON object with two fields:
   - "sparql": The exact, runnable SPARQL query string.
   - "explanation": A concise 1-2 sentence explanation of how the query works (in the user's language: German if prompt is German, else English).
Respond ONLY with valid JSON in this schema:
{
  "sparql": "PREFIX crm: <...> ... SELECT ... WHERE { ... } LIMIT 50",
  "explanation": "..."
}
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse JSON object from text, handling potential Markdown fences."""
    cleaned = _strip_code_fences(text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        logger.debug("Failed to parse JSON directly from LLM response: %s (text: %s)", exc, text)

    # Fallback: if text contains a raw SPARQL query starting with PREFIX or SELECT
    if "SELECT" in text.upper() or "ASK" in text.upper() or "CONSTRUCT" in text.upper():
        sparql_text = _strip_code_fences(text).strip()
        return {"sparql": sparql_text, "explanation": "Automatisch generierte SPARQL-Abfrage."}

    raise HTTPException(status_code=502, detail="KI-Antwort konnte nicht als SPARQL-Abfrage geparst werden.")


async def generate_sparql_from_prompt(
    db: AsyncSession,
    user_id: uuid.UUID,
    prompt: str,
) -> dict[str, str]:
    """Translate natural language prompt to a validated read-only SPARQL query."""
    user_prompt = prompt.strip()
    if not user_prompt:
        raise HTTPException(status_code=422, detail="Prompt darf nicht leer sein.")

    if len(user_prompt) > 2000:
        raise HTTPException(status_code=422, detail="Prompt ist zu lang (maximal 2000 Zeichen).")

    chat_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    estimated_input_tokens = _estimate_tokens(chat_messages)
    config = await ensure_ai_allowed(db, user_id, estimated_input_tokens)
    api_key = await get_secret(db, AI_API_KEY_SECRET)
    if not api_key:
        raise HTTPException(status_code=409, detail="Kein KI-API-Key konfiguriert.")

    max_output_tokens = max(config.ai_max_output_tokens, NL2SPARQL_MIN_OUTPUT_TOKENS)
    data = await call_ai_provider(config, api_key, chat_messages, max_output_tokens, temperature=0.1)
    content = extract_message_content(data)
    parsed = _extract_json(content)

    sparql_query = parsed.get("sparql", "").strip()
    if not sparql_query:
        raise HTTPException(status_code=502, detail="Keine SPARQL-Abfrage in der KI-Antwort enthalten.")

    explanation = parsed.get("explanation", "").strip()

    # Validate read-only SPARQL AST syntax
    try:
        validate_read_only_sparql(sparql_query)
    except HTTPException as exc:
        logger.warning("NL2SPARQL generated invalid SPARQL: %s (query: %s)", exc.detail, sparql_query)
        raise HTTPException(
            status_code=502,
            detail=f"Die generierte SPARQL-Abfrage ist syntaktisch fehlerhaft: {exc.detail}",
        ) from exc

    # Log usage event and audit log
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or estimated_input_tokens)
    output_tokens = int(usage.get("completion_tokens") or _estimate_tokens([{"role": "assistant", "content": content}]))

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
        record_type="sparql",
        record_id=user_id,
        user_id=user_id,
        action="nl2sparql_generated",
        changed_fields={
            "prompt": user_prompt,
            "provider": "openai-compatible",
            "model": config.ai_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    await db.commit()

    return {
        "sparql": sparql_query,
        "explanation": explanation,
    }
