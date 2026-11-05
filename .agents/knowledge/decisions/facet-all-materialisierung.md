---
type: Decision
title: Facetten-Materialisierung als facet_all_* mit Queryzeit-Whitelist statt Opt-in-Indexfeldern
status: accepted
date: 2026-09-10
---

# Kontext

Bisher wurden `facet_<field>`-/`number_facet_<field>`-Felder nur für Felder mit `is_facet=true` in den Suchindex geschrieben. Jeder Facetten-Toggle in den Admin-Einstellungen löste deshalb einen vollständigen Typ-Reindex aus (~30 Min bei 31k Objekten). Die öffentlichen Portal-Search-Endpunkte akzeptieren beliebige, clientseitig übergebene Facetten-Namen; das war nur sicher, weil nicht konfigurierte Felder im Doc fehlten (implizite Whitelist über die Index-Form).

# Entscheidung

Index-Dokumente führen `facet_all_<field>` (keyword) und `number_facet_all_<field>` (double) für **jedes öffentliche Feld**, unabhängig von `is_facet`. Ob ein Feld aggregiert werden darf, entscheiden die öffentlichen Search-Endpunkte (`portal_public.py`) zur Anfragezeit anhand einer serverseitigen Whitelist gegen `is_facet`-Felddefinitionen (plus `inherited_*`- und Relations-Facetten). Unbekannte Namen werden verworfen. `schema_admin.update_field()` triggert den Reindex nur noch bei `is_public`- oder geerbten Relations-Einstellungs-Änderungen, nicht mehr bei `is_facet`-Toggles. Vererbte Facetten behalten ihre legacy `facet_inherited_*`-Felder.

# Begründung

Doc-Inhalte hängen damit nicht mehr von der Facetten-Konfiguration ab — Facetten-Toggles wirken sofort, die Reindex-Klasse "Schema-Konfiguration" entfällt weitgehend. Die Alternative (alle Felder inkl. non-public indizieren und nur zur Queryzeit filtern) wurde verworfen: Sie hätte das Sicherheitsmodell "Non-Public kommt nicht in den Index" (robust, auch bei Query-Bugs) zu "Non-Public liegt im Index und wird gefiltert" (fragil) umgekehrt — bei einem öffentlichen Endpoint mit clientseitigen Facetten-Namen. Messung bei 31.6k Objekten: Index wächst ~25 % (~+50 MB auf 202 MB), einmaliger Migrations-Reindex; Aggregations-Antwortform und Frontend unverändert.

# Citations

- `backend/src/katalon/services/search_service.py` (`_build_doc` facet_all-Block)
- `backend/src/katalon/integrations/elasticsearch.py` (`_facet_doc_field`, dynamic templates `^facet_.*`/`^number_facet_.*`)
- `backend/src/katalon/api/v1/portal_public.py` (`_filter_facet_names`)
- `backend/src/katalon/api/v1/schema_admin.py` (Reindex-Trigger ohne is_facet)
- `almanac/decisions/frontend/schema-configured-portal-facets.md`
- `almanac/architecture/workflows/search-and-indexing.md`

# Aktueller Umfang

Die Sofortwirkung betrifft einfache `facet_all_*`-Facetten. Der heutige
[Facetten-Katalog](facetten-katalog.md) ergänzt materialisierte Datums-Buckets,
Vokabularpfade und Relationsfacetten. Änderungen an solchen Quell-Einstellungen
(z. B. `facet_granularity`) können einen Reindex erfordern; die frühere Aussage
„Doc-Inhalte unabhängig von Facetten-Konfiguration“ gilt nicht pauschal für
alle späteren Facettenarten.
