# Katalon – Weg zum MVP

*Stand: 2026-07-06. Historische MVP-Notiz. Aktueller Fokus: Phase 12 Hardening und Phase 13 Inherited Fields.*

## Aktueller Status

Der ursprüngliche MVP-Zuschnitt war Phase 0–6. Der Kern ist umgesetzt. Phase 7–11 sind ebenfalls umgesetzt. Offen bleibt nur Restarbeit rund um Hardening und inherited fields.

| Phase | Status | Kurzstand |
|---|---|---|
| 0–1 | ✅ | Infra + Core-DB |
| 2 | ✅ | Schema-Engine |
| 3 | ✅ | CRUD 4 Typen |
| 4 | ✅ | Auth + Audit |
| 5 | ✅ | Media + IIIF |
| 6 | ✅ | Admin-UI |
| 7 | ✅ | Elasticsearch + Snapshots |
| 8 | ✅ | Public-Portal |
| 9 | ✅ | Authority-Plugin-System |
| 10 | ✅ | Importer-Wizard |
| 11 | ✅ | OAI-PMH |
| 12 | ⚠️ | Hardening |
| 13 | ⚠️ | Inherited Fields |
| 14 | ✅ | Procedure-Typ |

## Was heute noch offen ist

- Phase 12: TLS-Terminierung, Perf-Tests, OpenAPI-Dokumentation
- Phase 13: Inherited Fields / ES-Denormalisierung (#213)
- Importer-UX-Polish: Auto-Mapping (#199), Vorschau (#201), Diff-Preview (#202), Streaming-Upload (#204)

## Was das praktisch heißt

Die früheren MVP-Blocker sind erledigt:

- IIIF/Cantaloupe-End-to-End
- Benutzer-Verwaltung in der Admin-UI
- Rate Limiting auf öffentlichen Endpunkten
- OAI-PMH mit ListSets und ResumptionToken
- Importer mit Excel, XML, Upsert und Auto-Publish

Aktuelle Prioritäten stehen im Implementierungsplan und in der GitHub Roadmap.
