---
type: Decision
title: Erweiterte Relationssuche wird von innen nach außen aufgelöst
status: accepted
date: 2026-08-29
---

# Kontext

Die Portalsuche soll Bedingungen über verknüpfte Datensätze kombinieren, etwa Objekte von Fotografen mit Geburtsdatum vor 1950 und Geburtsort Bremen.

# Entscheidung

Elasticsearch-Dokumente enthalten typisierte Werte der eigenen öffentlichen Suchfelder sowie Ziel-IDs eigener Relationsfelder. Verschachtelte Bedingungen werden zur Laufzeit vom innersten Ziel nach außen aufgelöst. Maximal zwei Relationsschritte und 10.000 IDs je Zwischenergebnis sind erlaubt.

# Begründung

Rekursive Denormalisierung würde Indexgröße und Reindex-Kaskaden unnötig vervielfachen. Die zusätzliche Suchanfrage je Relationsschritt ist für den interaktiven Builder begrenzt und nachvollziehbar.

# Citations

- `backend/src/katalon/services/advanced_search_service.py`
- `backend/src/katalon/services/search_service.py`
- `almanac/decisions/search/inherited-fields-in-elasticsearch.md`
