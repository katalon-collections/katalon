# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [1.26.13] - 2026-09-10

### Fixed
- Admin → Einstellungen → Facetten: Toggling eines Feldes vom Typ `authority`
  (Normdaten-Feld) als Facette schlug fehl, sobald die im Feld hinterlegte
  `settings.source` unbekannt oder deaktiviert war — auch wenn nur `is_facet`
  geändert wurde. Die Validierung in `schema_admin._validate_field_settings`
  greift jetzt nur noch, wenn sich `source` tatsächlich ändert (analog zum
  bestehenden PID-Provider-Grandfathering). Da das PUT bei Fehlschlag
  komplett verworfen wurde, ohne den lokalen Checkbox-Zustand zurückzusetzen,
  wirkten Facetten- und „Ergebnis-Untertitel"-Auswahl im UI gespeichert,
  obwohl der Server nichts übernommen hatte — sichtbar erst nach einem
  manuellen Reload.

### Added
- Admin → Einstellungen → Facetten → „Ergebnis-Untertitel": Die ID-Nummer
  (`idno`) steht jetzt immer als Option zur Verfügung, unabhängig davon, ob
  sie als Facette aktiviert ist — analog zu Typ/Status. Der öffentliche
  Portal-Search-Endpunkt löst `idno` direkt aus dem Datensatz auf, da es kein
  Feld mit `facet_all_*`-Aggregation ist.

