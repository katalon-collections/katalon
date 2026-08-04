---
title: "Fuzzy Vocabulary Clustering"
summary: "Katalon's importer suggests near-duplicate vocabulary values during dry-run using rapidfuzz Levenshtein clustering, then applies confirmed merges as vocab_map transforms."
topics: [decisions, importer, vocabularies, reconciliation]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/importer-fuzzy-vocab-clustering.md
  - id: importer-service
    type: file
    path: backend/src/katalon/services/importer_service.py
  - id: importer-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
  - id: vocab-models
    type: file
    path: backend/src/katalon/core/models.py
  - id: importer-state
    type: file
    path: frontend/admin/src/components/screens/importer/useImporterState.ts
  - id: dry-run-step
    type: file
    path: frontend/admin/src/components/screens/importer/StepDryRun.tsx
---

Katalon's importer uses fuzzy vocabulary clustering to catch spelling and casing variants before they become separate vocabulary terms. During dry-run, it collects values mapped to `vocab` fields, groups near-duplicates with normalized Levenshtein similarity from `rapidfuzz`, and returns only non-singleton clusters as suggestions [@importer-service]. The Admin UI shows those suggestions to the user and, when confirmed, adds a `vocab_map` transform to the relevant mapping instead of silently changing import data [@dry-run-step] [@importer-state]. This decision connects importer reconciliation with [Vocabularies](../../concepts/metadata/vocabularies) without adding a new persistence model.

## Context

Vocabulary imports can turn minor variants into new controlled-list terms. The recorded decision names examples such as `Berlin`, `berlin`, and `Brlin`, where treating every string as distinct would pollute vocabulary data during import [@decision-note]. Katalon's model stores vocabularies and vocabulary terms as first-class tables, while field definitions mark metadata fields as `vocab` and can point at configured vocabularies through settings [@vocab-models]. That makes cleanup before creation cheaper than correcting many new terms afterward.

The decision rejects k-means-style clustering for this problem because raw strings do not have a useful vector space without extra embedding infrastructure [@decision-note]. Edit distance is a smaller fit for typo and spelling-variant detection.

## Decision

Fuzzy clustering runs only for mapped fields whose field definition has `field_type == "vocab"` [@importer-service]. `_collect_vocab_values()` applies any existing transforms first, counts resulting raw values per mapped vocabulary field, and skips non-vocabulary targets [@importer-service].

`_cluster_values()` sorts values by descending frequency, uses the most frequent unassigned value as a pivot, normalizes candidates by trimming and lowercasing, and joins candidates whose Levenshtein normalized similarity is at least `0.82` [@importer-service]. Clusters are capped at ten values and singleton clusters are dropped, so dry-run returns suggestions only when there is something to reconcile [@importer-service].

The dry-run API reshapes backend cluster output into a list with field names, display labels, and clusters for the frontend [@importer-api]. `StepDryRun` renders "Mögliche Schreibweisen-Varianten" with counts and a merge button, while `applyVocabCluster()` writes every non-canonical variant into a `vocab_map` transform for the mapped field and reruns dry-run [@dry-run-step] [@importer-state].

## Consequences

The importer can suggest common vocabulary cleanup without taking authority away from the cataloger. Nothing is merged until the user clicks "Zusammenführen", and the accepted merge is represented by the existing transform chain rather than by hidden importer state [@dry-run-step] [@importer-state].

The algorithm is intentionally simple and bounded. It is O(n²) over distinct incoming values, capped by cluster size, and runs in dry-run rather than in a request path that serves public search or record display [@importer-service]. Future work should consider richer clustering only if real imports show that Levenshtein suggestions miss important variants or produce too many false positives.
