---
type: Decision
title: Facetten-Katalog mit Relations-, Datums- und Baumfacetten, Sortierung pro Facette
status: accepted
date: 2026-10-13
---

# Kontext

Portalfacetten waren an `is_facet` einfacher Felder gebunden und hingen mit `show_in_detail`
zusammen. Migrierte Bestände (BPK) brauchen Facetten über Beziehungen (z. B. Künstler/in,
Verlag), über Unterfelder, Jahrzehnte und Hierarchien.

# Entscheidung

`services/facet_service.py` ist der Katalog: je Typ, welche Facetten es gibt, welcher Art
(`terms`, `inherited`, `related`, `relation`, Datum mit `decade|century|year`, Baum) und auf
welchen `facet_*`-Indexfeldern sie filtern. Namen: `<feld>`, `<gruppe>__<kind>`,
`inherited_<t>_<f>`, `related_*`, `relfacet_<key>` (`PortalConfig.relation_facets`). `is_facet`
ist von `show_in_detail` entkoppelt, Reihenfolge über `facet_fields`, Sortierung je Facette über
`portal_config.facet_sort_overrides` (Migration 0085, `count`|`alpha`). Aggregationen schließen
den eigenen Filter aus (self-excluding); Relationsfacetten liefern ausgewählte Werte immer mit
(Sub-Aggregation `selected`), auch außerhalb der Top-100-Buckets.

# Begründung

Relations- und Datumsfacetten sind Kernfunktion, kein Theme-Workaround. Abgeleitete Felder
unter `facet_*` brauchen kein Mapping-Update (dynamisches Keyword-Template).

# Citations

- `backend/src/katalon/services/facet_service.py`
- `backend/src/katalon/integrations/elasticsearch.py` (`_self_excluding_agg`, `selected`)
- `almanac/decisions/frontend/schema-configured-portal-facets.md`
- [Facet-All-Materialisierung](facet-all-materialisierung.md)
