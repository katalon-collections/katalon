---
type: Decision
title: Relationsfeld-Werte nur mit geprüften öffentlichen Zielen ausgeben
status: accepted
date: 2026-10-23
---

# Kontext

Werte von Relationsfeldern speichern `{id, label, relation_type}` in den Metadaten, also den
Namen des Ziels. Die öffentliche Projektion ließ sie ungefiltert durch: Namen von Entwürfen,
internen Datensätzen und Vorgängen standen im Portal, Suchindex, OAI/LIDO, IIIF-Manifest und
RDF-Export.

# Entscheidung

`filter_public_metadata(..., hidden_targets=...)` lässt Einträge mit nicht öffentlichem Ziel weg
(auch in Gruppen); ohne `hidden_targets` gibt sie **gar keine** Relationsfeld-Werte heraus
(fail closed). Aufrufer laden die Ziele mit `load_hidden_relation_targets` bzw. nutzen
`filter_public_metadata_checked`/`project_public_record`. `visible_record_ids` ist die gemeinsame
Sichtbarkeitsprüfung. RDF ohne Leserecht und der Oxigraph-Sync nutzen dieselbe öffentliche
Sicht (`public=True`). Relationen aus Relationsfeldern sind `is_schema_derived` mit
`metadata.source_field`; das Portal zeigt sie beim Feld und nicht noch einmal unter
„Verknüpfte Datensätze“. Namen in Relationsfeldern verlinken auf die vorgefilterte Suche.

# Begründung

Ein Label in Metadaten ist eine Kopie fremder Daten und erbt deren Sichtbarkeit. Fail closed,
damit ein neuer Ausgabepfad ohne Prüfung nichts preisgibt.

# Citations

- `backend/src/katalon/services/public_metadata_service.py`
- `backend/src/katalon/services/rdf_service.py`
- `backend/tests/test_public_relation_fields.py`
- `almanac/concepts/relations/generic-relations.md`
- [Relationen — strukturierte Felder und freie Zusatzbeziehungen](relationen-strukturierte-und-freie-beziehungen.md)
