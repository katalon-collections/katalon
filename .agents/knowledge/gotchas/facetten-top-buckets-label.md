---
type: Gotcha
title: Ausgewählter Facettenwert außerhalb der Top-Buckets hat kein Label
description: Relationsfacetten liefern nur die häufigsten Werte; ein per URL gewählter seltener Wert kam ohne Titel zurück und der Filter-Chip zeigte die UUID.
tags: [search, facets, portal, elasticsearch]
timestamp: 2026-10-24T00:00:00Z
---

# Symptom

`/search?meta_relfacet_maler=<uuid>` zeigt den Chip mit UUID statt Namen.

# Ursache

Bucket-Werte haben die Form `<id>|<titel>`; der Titel kommt nur aus den Buckets, und die
Aggregation liefert nur die Top 100.

# Regel

Ausgewählte Werte immer zusätzlich anfordern (Sub-Aggregation `selected` mit `include`-Pattern
auf die gewählten IDs) und in die Bucket-Liste mischen. Gilt für jede neue Facettenart, deren
Anzeige-Label aus dem Bucket stammt.

# Citations

[1] Commit `1d0b8edf` (1.46.0), `backend/src/katalon/integrations/elasticsearch.py`
