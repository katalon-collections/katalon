# Session Context – 2026-06-05

## Changed

- `.env.example` — CORS_ORIGINS auf JSON-Array-Format korrigiert (Pydantic-settings v2 erwartet JSON, kein Komma-String)
- Export-Mapping eingefuehrt: `metadata_mappings`-Tabelle, `/v1/metadata-mappings`, Schema-Editor mit OAI-DC-Select und Stubs fuer LIDO + METS/MODS
- OAI-PMH nutzt jetzt die generische Export-Mapping-Schicht statt hartkodierter Dublin-Core-Zuordnung

## Decided

- Kein Validator-Workaround für Komma-Format — JSON-Standard ist ausreichend
- Export-Mapping bleibt formatneutral in eigener Tabelle (`metadata_mappings`) statt `dc_element` in `field_definitions`
- OAI-Dublin-Core ist nur der erste Consumer der Export-Mapping-Schicht

## Pending

- Issue #213: Inherited Fields (ES-Denormalisierung verlinkter Records)
- Issue #214: Robuste ES-Indexierung (Retry, Reconciliation)
- Issue #225 ist implementiert und dokumentiert, nur GitHub-Issue noch aktualisieren/schliessen
- Importer-UX: #199, #201, #202, #204 nachrangig

## State

Alle Beta-Blocker erledigt. Produktiv-Deployment läuft (Server getestet, CORS-Fix deployed). Export-Mapping ist implementiert und in der Doku verankert. Nächste sinnvolle Schritte: Issue #225 schliessen, dann Phase 13 / #214 weiterverfolgen.
