# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.19.2] - 2026-09-03

### Fixed
- Backend: Relations-Label-Auflösung kannte den Datensatztyp `storage_location` nicht — verknüpfte Lagerorte zeigten im Objektformular "Nicht verfügbar" statt ihres Namens.
- Admin-UI: Lagerort-Suche im Beziehungs-Picker lief über die Volltextsuche, die Lagerorte gar nicht indiziert — die Suche fand nie Treffer. Fragt jetzt direkt die Lagerort-Liste ab, zeigt beim Fokussieren sofort bis zu 20 Einträge (kein Mindest-Zeichen mehr nötig) und filtert bei Eingabe weiter.
- Admin-UI: "Lagerort-Typ" hat jetzt ein Info-Popover (Zweck, wo neue Typen angelegt werden).

### Changed
- Lagerorte haben kein Entwurf/Intern/Öffentlich-Statusfeld mehr — sie waren nie im Portal oder in der öffentlichen Suche sichtbar, das Feld war wirkungslos. Die Inventarnummer/ID ist jetzt stattdessen immer Pflicht (außer bei konfigurierter automatischer Nummernvergabe), statt nur bei Nicht-Entwurf. Migration `0055` entfernt die `status`-Spalte und setzt `idno NOT NULL`.

## [1.16.0] - 2026-09-02

### Added
- Admin-Kopfsuche durchsucht neben Bestandsdaten auch Nutzer, Vokabulare und Terme, statische Seiten, OAI-Sets, Schemafelder, Subtypen, Formularvarianten, Banner und konfigurierte Normdatenquellen. Die Suche öffnet passende Admin-Bereiche direkt und verwendet für Konfigurationsdaten PostgreSQL statt eines zusätzlichen Suchindex.

### Changed
- Die Admin-Hilfe öffnet die veröffentlichte Anwenderdokumentation auf GitHub Pages statt Markdown-Dateien im Quellrepository.
- Subtypen: Beim Anlegen wird der interne Name automatisch aus dem Label abgeleitet (z. B. „Person" → `person`) und lässt sich bis zum Speichern anpassen. Nach dem Speichern bleibt er wie bisher unveränderlich.

### Fixed
- Portal-Abhängigkeiten und der IIIF-Viewer wurden auf sichere Versionen aktualisiert. Äußeres nginx liefert nun CSP-, HSTS- (Produktion), MIME-, Frame-, Referrer- und Permissions-Schutzheader aus.
- Portal-Kopfzeile: Suchfeld mit Autocomplete-Vorschlägen hatte `aria-expanded`/`aria-controls` ohne passende ARIA-Rolle gesetzt, was Screenreadern die Beziehung zur Vorschlagsliste unzugänglich machte (axe: `aria-allowed-attr`). Das Feld trägt jetzt `role="combobox"` und `aria-autocomplete="list"`.

