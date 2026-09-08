# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [1.22.0] - 2026-09-08

### Added
- Admin-UI / Formulare: Konfigurierbare Formularabschnitte pro Datensatztyp und Subtyp. Admins ordnen Schemafelder benannten Abschnitten zu; das Erfassungsformular zeigt diese als Tabs, lässt nicht zugeordnete Felder unter „Allgemein“ und markiert Tabs mit Validierungsfehlern.

## [1.21.0] - 2026-09-08

### Added
- Portal / Detailseiten: Metadatenfelder, die im Schema als Facette (`is_facet`) markiert sind, werden auf den Objekt-, Personen-, Orts-, Werk- und Sammlungs-Detailseiten als klickbare Links dargestellt. Ein Klick führt zur Suche, gefiltert auf denselben Wert und Datensatztyp (`meta_<feld>=<wert>` bzw. bei Zahlenfeldern `range_<feld>_from/_to`). Betrifft `DetailPageLayout.tsx` (Objekt/Person/Ort/Werk) und den manuellen Feld-Loop in `CollectionDetailPage.tsx`; Backend liefert dafür `is_facet` neu über `GET /portal/v1/schema/{target_type}`.

### Fixed
- Admin-UI / Einstellungen: Das Speichern von Facetten unter „Einstellungen → Facetten“ synchronisiert direkte Schema-Facetten (`is_facet`) und geerbte Facetten nun zuverlässig mit dem Backend. `PUT /v1/portal/config` liefert die vollständig dynamisch aufgelöste Konfiguration zurück, und die UI serialisiert Schema- und Portal-Config-Updates, sodass aktive Facetten nach dem Speichern, Tab-Wechseln und Neuladen stabil erhalten bleiben.

## [1.20.1] - 2026-09-07

### Fixed
- SPARQL / Validation: Import von `ParseException` aus `pyparsing.exceptions` korrigiert (statt fälschlich aus `rdflib.plugins.sparql.parser`), wodurch SPARQL-Validierungs- und Unit-Tests fehlschlugen.

## [1.20.0] - 2026-09-07

### Added
- Admin-UI / Arbeitslisten (Working Sets): Neuer Menüpunkt „Arbeitslisten“ (`ScreenWorkingSets.tsx`) für ad-hoc, typgebundene Gruppierungen von Datensätzen für interne Workflows (Ausstellungsvorbereitungen, Prüflisten, Dublettenbereinigung, Kuration).
- Admin-UI / Listenintegration: Auswahlen in allen Datensatzlisten (`ScreenList.tsx`) können über die Massenaktionsleiste („Zu Arbeitsliste“) direkt in bestehende oder neu angelegte Arbeitslisten übernommen werden (`AddToWorkingSetModal.tsx`).
- Admin-UI / Detailansicht & Sortierung: Detailansicht von Arbeitslisten mit Reordering (Hoch/Runter), individuellen Notizen pro Datensatz, Thumbnails und direkter Verlinkung in die Bearbeitungsmaske.
- Admin-UI / Batch-Editing-Brücke: Nahtlose Übergabe aller Datensätze einer Arbeitsliste in das bestehende `BatchEditModal` zur gemeinsamen Status-, Feld- oder Relationsänderung.
- Backend / Arbeitslisten-Datenmodell: Neue PostgreSQL-Tabellen `working_sets` und `working_set_items` (Alembic-Migration `0057_working_sets.py`) mit Kaskadenlöschung und Berechtigungskontrolle (privat vs. geteilt).
- Backend / REST-API: Vollständige Endpunkte unter `/v1/working-sets` zur Erstellung, Verwaltung, Reordering und Befüllung von Arbeitslisten inklusive automatischer Titel- und Kennungsauflösung.

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

