# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from collections import deque
from typing import Any
from urllib.parse import urlparse

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import DC, DCTERMS, RDF, RDFS, SKOS

from katalon.services.vocabulary_import_service import (
    DEFAULT_LABEL_LANGUAGE,
    ImportTerm,
    _slugify,
    _term_from_label,
)

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".ttl": "turtle",
    ".turtle": "turtle",
    ".rdf": "xml",
    ".xml": "xml",
    ".owl": "xml",
    ".jsonld": "json-ld",
    ".json-ld": "json-ld",
    ".json": "json-ld",
    ".nt": "nt",
    ".ntriples": "nt",
    ".n3": "n3",
    ".trig": "trig",
}


def detect_rdf_format(filename: str | None = None, content: bytes | None = None) -> str:
    """Guess RDF format from filename or content sample."""
    if filename:
        ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext in SUPPORTED_EXTENSIONS:
            if ext == ".json" and content:
                # Check if it's JSON-LD
                sample = content[:4096].decode("utf-8", errors="replace")
                if "@context" in sample or "@graph" in sample:
                    return "json-ld"
            else:
                return SUPPORTED_EXTENSIONS[ext]

    if content:
        raw_sample = content[:4096].strip()
        sample_str = raw_sample.decode("utf-8", errors="replace").lower()
        if sample_str.startswith("<?xml") or "<rdf:rdf" in sample_str:
            return "xml"
        if sample_str.startswith("{") and ("@context" in sample_str or "@graph" in sample_str):
            return "json-ld"
        if "@prefix" in sample_str or "prefix " in sample_str:
            return "turtle"

    return "turtle"


def parse_skos_graph(content: bytes, format_hint: str | None = None) -> rdflib.Graph:
    """Parse RDF content into an rdflib Graph, trying format_hint and common fallbacks."""
    graph = rdflib.Graph()
    formats_to_try: list[str] = []
    if format_hint:
        formats_to_try.append(format_hint)
    for fmt in ("turtle", "xml", "json-ld", "nt"):
        if fmt not in formats_to_try:
            formats_to_try.append(fmt)

    last_error: Exception | None = None
    for fmt in formats_to_try:
        try:
            graph.parse(data=content, format=fmt)
            return graph
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    raise ValueError(f"SKOS/RDF-Datei konnte nicht geparst werden: {last_error}")


def _clean_uri(uri: Any) -> str:
    return str(uri).strip()


def _get_literal_text(literal: Any) -> str:
    return str(literal).strip()


def _extract_label(node: Any, graph: rdflib.Graph) -> str:
    """Extract a human-friendly display label for a Concept or ConceptScheme."""
    for pred in (SKOS.prefLabel, RDFS.label, DCTERMS.title, DC.title):
        for val in graph.objects(node, pred):
            if (
                isinstance(val, Literal)
                and val.language
                and val.language.lower() in (DEFAULT_LABEL_LANGUAGE, "en")
            ):
                return str(val).strip()
    for pred in (SKOS.prefLabel, RDFS.label, DCTERMS.title, DC.title):
        for val in graph.objects(node, pred):
            text = str(val).strip()
            if text:
                return text
    # Fallback to URI fragment or last segment
    uri_str = str(node)
    parsed = urlparse(uri_str)
    if parsed.fragment:
        return parsed.fragment
    segment = parsed.path.rstrip("/").split("/")[-1]
    return segment or uri_str


def extract_schemes_and_top_concepts(
    graph: rdflib.Graph,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Inspect graph to discover ConceptSchemes and TopConcepts."""
    schemes: list[dict[str, str]] = []
    seen_schemes: set[str] = set()

    for scheme in graph.subjects(RDF.type, SKOS.ConceptScheme):
        if isinstance(scheme, BNode):
            continue
        scheme_uri = _clean_uri(scheme)
        if scheme_uri not in seen_schemes:
            seen_schemes.add(scheme_uri)
            schemes.append({
                "uri": scheme_uri,
                "label": _extract_label(scheme, graph),
            })

    top_concepts: list[dict[str, str]] = []
    seen_top: set[str] = set()

    # Via skos:hasTopConcept
    for _, _, concept in graph.triples((None, SKOS.hasTopConcept, None)):
        if isinstance(concept, BNode):
            continue
        c_uri = _clean_uri(concept)
        if c_uri not in seen_top:
            seen_top.add(c_uri)
            top_concepts.append({
                "uri": c_uri,
                "label": _extract_label(concept, graph),
            })

    # Via skos:topConceptOf
    for concept, _, _ in graph.triples((None, SKOS.topConceptOf, None)):
        if isinstance(concept, BNode):
            continue
        c_uri = _clean_uri(concept)
        if c_uri not in seen_top:
            seen_top.add(c_uri)
            top_concepts.append({
                "uri": c_uri,
                "label": _extract_label(concept, graph),
            })

    return schemes, top_concepts


def _find_all_concepts(graph: rdflib.Graph) -> set[URIRef]:
    """Find all Concept nodes in the graph, excluding ConceptSchemes."""
    schemes = set(graph.subjects(RDF.type, SKOS.ConceptScheme))

    concepts: set[URIRef] = set()
    for s in graph.subjects(RDF.type, SKOS.Concept):
        if isinstance(s, URIRef) and s not in schemes:
            concepts.add(s)

    # Include nodes with skos:prefLabel or inScheme or broader if they are not schemes
    for s in graph.subjects(SKOS.prefLabel, None):
        if isinstance(s, URIRef) and s not in schemes:
            concepts.add(s)
    for s in graph.subjects(SKOS.inScheme, None):
        if isinstance(s, URIRef) and s not in schemes:
            concepts.add(s)
    for s in graph.subjects(SKOS.broader, None):
        if isinstance(s, URIRef) and s not in schemes:
            concepts.add(s)

    return concepts


def _matches_scheme(c: URIRef, scheme_uris: set[str], graph: rdflib.Graph) -> bool:
    """Check if concept belongs to any of the normalized scheme URIs."""
    for s in graph.objects(c, SKOS.inScheme):
        if _clean_uri(s).rstrip("/") in scheme_uris:
            return True
    for s in graph.objects(c, SKOS.topConceptOf):
        if _clean_uri(s).rstrip("/") in scheme_uris:
            return True
    for scheme_uri in scheme_uris:
        if (URIRef(scheme_uri), SKOS.hasTopConcept, c) in graph or (
            URIRef(scheme_uri + "/"),
            SKOS.hasTopConcept,
            c,
        ) in graph:
            return True
    return False


def _generate_candidate_term_id(
    c: URIRef,
    graph: rdflib.Graph,
    labels: dict[str, str],
) -> str:
    """Derive a clean, short slug or identifier for a concept."""
    # 1. Check skos:notation
    for notat in graph.objects(c, SKOS.notation):
        raw = str(notat).strip()
        slugged = _slugify(raw)
        if slugged:
            return slugged

    # 2. Check URI fragment or last path component
    uri_str = str(c)
    parsed = urlparse(uri_str)
    if parsed.fragment:
        slugged = _slugify(parsed.fragment)
        if slugged:
            return slugged

    last_segment = parsed.path.rstrip("/").split("/")[-1]
    if last_segment:
        slugged = _slugify(last_segment)
        if slugged and slugged not in ("concept", "term", "item"):
            return slugged

    # 3. Fallback to label
    if labels:
        slugged = _term_from_label(labels)
        if slugged:
            return slugged

    # 4. Ultimate fallback
    return _slugify(uri_str)[-32:] or "concept"


def parse_skos_terms(
    content: bytes,
    filename: str | None = None,
    format_hint: str | None = None,
    concept_scheme: str | None = None,
    top_concept: str | None = None,
    max_depth: int | None = None,
    max_terms: int | None = None,
    is_hierarchical: bool = True,
) -> tuple[list[ImportTerm], list[dict[str, Any]], dict[str, Any]]:
    """Parse SKOS data with optional selective filtering (scheme, top concept, depth, term cap).

    Returns:
        (terms, errors, metadata_summary)
    """
    effective_format = format_hint or detect_rdf_format(filename, content)
    graph = parse_skos_graph(content, effective_format)

    detected_schemes, detected_top = extract_schemes_and_top_concepts(graph)
    all_concepts = _find_all_concepts(graph)

    # Build hierarchy graph (broader and narrower)
    # parent -> set of children
    children_map: dict[str, set[str]] = {}
    # child -> set of parents
    parents_map: dict[str, list[str]] = {}

    for c in all_concepts:
        c_uri = _clean_uri(c)
        if c_uri not in parents_map:
            parents_map[c_uri] = []

        # c skos:broader p
        for p in graph.objects(c, SKOS.broader):
            if isinstance(p, URIRef):
                p_uri = _clean_uri(p)
                children_map.setdefault(p_uri, set()).add(c_uri)
                if p_uri not in parents_map[c_uri]:
                    parents_map[c_uri].append(p_uri)

        # p skos:narrower c  (so c has parent p)
        for child in graph.objects(c, SKOS.narrower):
            if isinstance(child, URIRef):
                child_uri = _clean_uri(child)
                children_map.setdefault(c_uri, set()).add(child_uri)
                parents_map.setdefault(child_uri, [])
                if c_uri not in parents_map[child_uri]:
                    parents_map[child_uri].append(c_uri)

    # Determine candidate concepts to import
    selected_uris: set[str] = set()
    depth_map: dict[str, int] = {}
    errors: list[dict[str, Any]] = []

    # Filter 1: Top Concept subtree traversal
    if top_concept and top_concept.strip():
        root_uri = top_concept.strip()
        matched_roots = [
            c_uri for c_uri in all_concepts if _clean_uri(c_uri).rstrip("/") == root_uri.rstrip("/")
        ]
        if not matched_roots:
            errors.append({
                "row": None,
                "message": f"Top-Concept '{top_concept}' wurde in den SKOS-Daten nicht gefunden.",
            })
            return [], errors, {
                "detected_schemes": detected_schemes,
                "detected_top_concepts": detected_top,
                "total_concepts_found": len(all_concepts),
                "total_concepts_selected": 0,
            }

        queue: deque[tuple[str, int]] = deque((_clean_uri(r), 1) for r in matched_roots)
        while queue:
            curr_uri, curr_depth = queue.popleft()
            if curr_uri in selected_uris:
                continue
            if max_depth is not None and max_depth > 0 and curr_depth > max_depth:
                continue

            selected_uris.add(curr_uri)
            depth_map[curr_uri] = curr_depth

            for child_uri in children_map.get(curr_uri, ()):
                if child_uri not in selected_uris:
                    queue.append((child_uri, curr_depth + 1))

    # Filter 2: Concept Scheme filter
    elif concept_scheme and concept_scheme.strip():
        scheme_norm = concept_scheme.strip().rstrip("/")
        scheme_set = {scheme_norm}
        scheme_concepts = {
            _clean_uri(c) for c in all_concepts if _matches_scheme(c, scheme_set, graph)
        }

        # If scheme has top concepts, traverse downwards to ensure descendants are included
        queue_schemes: deque[tuple[str, int]] = deque()
        for tc in detected_top:
            if tc["uri"] in scheme_concepts or (
                URIRef(tc["uri"]),
                SKOS.inScheme,
                URIRef(scheme_norm),
            ) in graph:
                queue_schemes.append((tc["uri"], 1))

        # Also add root concepts in scheme (those without broader in scheme)
        for c_uri in scheme_concepts:
            parents = parents_map.get(c_uri, [])
            if not any(p in scheme_concepts for p in parents):
                queue_schemes.append((c_uri, 1))

        visited_scheme: set[str] = set()
        while queue_schemes:
            curr_uri, curr_depth = queue_schemes.popleft()
            if curr_uri in visited_scheme:
                continue
            if max_depth is not None and max_depth > 0 and curr_depth > max_depth:
                continue
            visited_scheme.add(curr_uri)
            selected_uris.add(curr_uri)
            depth_map[curr_uri] = curr_depth

            for child_uri in children_map.get(curr_uri, ()):
                if child_uri in scheme_concepts or child_uri in all_concepts:
                    queue_schemes.append((child_uri, curr_depth + 1))

        # Also add any standalone concepts in scheme that might not be connected hierarchically
        for c_uri in scheme_concepts:
            if max_depth is None or c_uri in depth_map:
                selected_uris.add(c_uri)
    else:
        # Full file import (with optional max_depth from roots)
        if max_depth is not None and max_depth > 0:
            roots = [c_uri for c_uri, parents in parents_map.items() if not parents]
            if not roots:
                roots = [_clean_uri(c) for c in all_concepts]
            queue_all: deque[tuple[str, int]] = deque((r, 1) for r in roots)
            while queue_all:
                curr_uri, curr_depth = queue_all.popleft()
                if curr_uri in selected_uris:
                    continue
                if curr_depth > max_depth:
                    continue
                selected_uris.add(curr_uri)
                depth_map[curr_uri] = curr_depth

                for child_uri in children_map.get(curr_uri, ()):
                    if child_uri not in selected_uris:
                        queue_all.append((child_uri, curr_depth + 1))
        else:
            selected_uris = {_clean_uri(c) for c in all_concepts}

    total_selected_before_cap = len(selected_uris)

    # Protection against memory overflow: enforce max_terms limit
    effective_max_terms = max_terms if (max_terms is not None and max_terms > 0) else 50000
    sorted_selected_uris = sorted(selected_uris)
    if len(sorted_selected_uris) > effective_max_terms:
        sorted_selected_uris = sorted_selected_uris[:effective_max_terms]
        selected_uris = set(sorted_selected_uris)
        errors.append({
            "row": None,
            "message": f"Mengenbegrenzung erreicht: {len(sorted_selected_uris)} von {total_selected_before_cap} Konzepten ausgewählt.",
        })

    # Convert selected concepts to ImportTerms
    uri_to_node = {_clean_uri(c): c for c in all_concepts}
    uri_to_term_id: dict[str, str] = {}
    used_term_ids: set[str] = set()

    concept_data: list[dict[str, Any]] = []

    # First pass: collect labels, altLabels, exactMatch, notations and allocate unique term IDs
    for idx, c_uri in enumerate(sorted_selected_uris, start=1):
        c_node = uri_to_node.get(c_uri)
        if not c_node:
            continue

        # Extract prefLabels
        labels: dict[str, str] = {}
        for lit in graph.objects(c_node, SKOS.prefLabel):
            if isinstance(lit, Literal):
                lang = lit.language.lower() if lit.language else DEFAULT_LABEL_LANGUAGE
                if lang not in labels:
                    labels[lang] = _get_literal_text(lit)

        # Extract altLabels
        alt_labels: dict[str, list[str]] = {}
        for lit in graph.objects(c_node, SKOS.altLabel):
            if isinstance(lit, Literal):
                lang = lit.language.lower() if lit.language else DEFAULT_LABEL_LANGUAGE
                text = _get_literal_text(lit)
                if text:
                    alt_labels.setdefault(lang, []).append(text)

        # Extract exactMatch
        exact_matches: list[str] = []
        for match in graph.objects(c_node, SKOS.exactMatch):
            match_uri = _clean_uri(match)
            if match_uri and match_uri not in exact_matches:
                exact_matches.append(match_uri)

        # Generate unique term ID
        base_term = _generate_candidate_term_id(c_node, graph, labels)
        candidate = base_term
        counter = 2
        while candidate in used_term_ids:
            candidate = f"{base_term}-{counter}"
            counter += 1
        used_term_ids.add(candidate)
        uri_to_term_id[c_uri] = candidate

        concept_data.append({
            "row": idx,
            "uri": c_uri,
            "node": c_node,
            "term": candidate,
            "labels": labels,
            "alt_labels": alt_labels,
            "exact_matches": exact_matches,
        })

    # Second pass: resolve parent_term using uri_to_term_id
    terms: list[ImportTerm] = []
    for item in concept_data:
        c_uri = item["uri"]
        parent_term: str | None = None

        if is_hierarchical:
            # Parents of c_uri
            parents = parents_map.get(c_uri, [])
            for p_uri in parents:
                if p_uri in uri_to_term_id:
                    parent_term = uri_to_term_id[p_uri]
                    break

        metadata: dict[str, Any] = {}
        if item["alt_labels"]:
            metadata["alt_labels"] = item["alt_labels"]

        terms.append(
            ImportTerm(
                term=item["term"],
                label=item["labels"],
                inverse_label={},
                parent_term=parent_term,
                row=item["row"],
                uri=item["uri"],
                exact_match_uris=item["exact_matches"],
                metadata=metadata,
            )
        )

    meta_summary = {
        "detected_schemes": detected_schemes,
        "detected_top_concepts": detected_top,
        "total_concepts_found": len(all_concepts),
        "total_concepts_selected": len(terms),
    }

    return terms, errors, meta_summary
