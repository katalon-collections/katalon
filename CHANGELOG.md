# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [1.34.7] - 2026-09-14

### Fixed
- **Integrationstests Session-Isolation:** In `test_batch_editing.py` und
  `test_import_authorization.py` wurde der statische Modul-Import von
  `AsyncSessionLocal` durch dynamische Aufrufe über `database_module` ersetzt,
  wodurch die Verbindung zur dynamisch allokierten Testdatenbank im CI-Container
  stets aktuell bleibt.
- **Audit-Autorisierungstests:** Korrektur des Plural-Routings für `entity` in
  `_create_record` (`/v1/entities` statt `/v1/entitys`) und Einbindung der neuen
  Paritäts-Endpunkte für Lagerorte in
  `backend/tests/integration/test_audit_read_authorization.py`.
- **Lagerort Batch-Tests:** Hinzufügen des Pflichtfelds `label` in `metadata_`
  und Korrektur des Audit-Listen-Parsings in `test_batch_storage_location.py`.
- **Soft-Delete Rollback-Simulation:** Umstellung des Fehler-Monkeypatchings auf
  `log_change` in `test_soft_delete.py`, um Transaktionsabbrüche deterministisch
  über den FastAPI/get_db-Lebenszyklus auszulösen.

