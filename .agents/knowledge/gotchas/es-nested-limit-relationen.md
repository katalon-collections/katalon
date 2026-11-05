---
type: Gotcha
title: Elasticsearch begrenzt verschachtelte Einträge auf 10.000 je Dokument
description: Eingehende Relationen in den Index zu schreiben sprengt bei Sammel-Zielen (Sammlung, Verlag) das nested-Limit; nur ausgehende Relationen indexieren.
tags: [search, elasticsearch, relations, index]
timestamp: 2026-10-22T00:00:00Z
---

# Symptom

Reindex bricht für einzelne Datensätze ab (`The number of nested documents has exceeded the
allowed limit of [10000]`), typischerweise bei Sammlungen, Verlagen oder Orten, auf die
zehntausende Objekte zeigen.

# Ursache

`index.mapping.nested_objects.limit` (Default 10.000) gilt pro Dokument. Ein Ziel mit allen
eingehenden Relationen als nested-Einträgen überschreitet ihn.

# Regel

Nur ausgehende Relationen indexieren; die Gegenrichtung über die Quellseite auflösen (siehe
[Erweiterte Relationssuche](../decisions/advanced-relational-search.md)). Das Limit nicht hochsetzen.

# Citations

[1] Commit `edd1f512` „fix(search): nur ausgehende Relationen indexieren“ (1.45.0)
