# Design Prompt: Katalon Admin-UI (Eingabeoberfläche)

## Kontext & Zweck

Entwirf die Admin-Oberfläche von **Katalon**, einem Metadata Management System für Sammlungen im GLAM-Bereich. Die Admin-UI ist für Museumsmitarbeiter, Archivare und Sammlungsverwalter gedacht – Menschen, die täglich stundenlang damit arbeiten. Korrektheit und Effizienz haben Vorrang vor Schönheit.

**Leitprinzip:** Professionelles Werkzeug, keine Marketing-Seite. Weniger ist mehr – aber nichts Wichtiges darf versteckt sein.

**Vier Primärtypen** (alle gleich konfigurierbar und erfassbar):
- **Objekte** – Artefakte (Fotos, Dokumente, Gemälde)
- **Entitäten** – Personen, Organisationen
- **Orte** – Geografische Punkte
- **Occurrences** – Werke (FRBR), Ereignisse, Konzepte

**Technische Eigenheiten, die das UX prägen:**
- Alle Metadatenfelder sind dynamisch konfiguriert (Schema-Editor definiert, was in Formularen erscheint)
- Felder können wiederholbar sein (beliebig viele Werte pro Feld)
- Relationen zwischen allen Typen, mit Metadaten auf der Relation selbst
- Kontrollierte Vokabulare: on-the-fly erweiterbar während der Erfassung
- Audit Log: jede Änderung wird protokolliert

---

## Globales Layout

**Vorschlag:** App-Shell mit fester linker Sidebar (kollapsibel) und Hauptinhalt rechts.

**Sidebar-Navigation:**
- Objekte
- Entitäten
- Orte
- Occurrences
- ─── (Trennlinie)
- Vokabulare
- Schema-Editor
- Importer
- ─── (Trennlinie)
- Audit Log
- Einstellungen (Benutzer, Authority-Quellen)

---

## Zu entwerfende Screens

### Screen 1: Listen-/Übersichtsansicht (für jeden Typ gleich)

**Zweck:** Schneller Überblick, Suche, Sortierung, Massenoperationen.

Elemente:
- Persistente Suchleiste + Filterzeile (Status: draft/internal/public; Datumsbereich; dynamische Felder je nach Typ)
- **Tabelle** als Standard (nicht Kacheln): Inventarnummer, Titel/Name, Status-Badge, Erstellt, Zuletzt geändert, Aktionen (Edit, Löschen)
- Status-Badge: farbkodiert – draft (grau), internal (orange), public (grün)
- Spalten konfigurierbar (welche Metadatenfelder sichtbar?)
- Checkboxen für Mehrfachauswahl → Bulk-Aktionen (Status ändern, Löschen)
- „Neu anlegen"-Button prominent (oben rechts)
- Pagination oder virtuelles Scrollen bei großen Mengen

---

### Screen 2: Erfassungsformular (für jeden Typ gleich, Felder dynamisch)

**Zweck:** Effiziente Dateneingabe. Das Formular rendert sich aus den Schema-Definitionen.

**Layout:** Zweispaltig wenn sinnvoll (Metadaten links, Medien/Relationen rechts) – oder einspaltig mit klaren Sektionen. Sticky-Header mit Speichern/Verwerfen.

Elemente:

**Feldtypen, die das Design abdecken muss:**
- **Text** (einzeilig + mehrzeilig/Textarea)
- **Datum** inkl. Fuzzy-Datum: „um 1920", „1910–1930", „1923-05" – Input braucht Komfort-UI, kein Raw-String. Idee: Monat/Jahr/Präzisions-Selektor kombiniert.
- **Zahl** (einfaches Zahlenfeld)
- **Dropdown / Vokabular-Term:** Autocomplete aus kontrollierter Liste + „+ Neuen Term hinzufügen"-Inline-Option (ohne Seitennavigation zu verlassen)
- **Geodaten / Ort-Picker:** Mini-Karte zum Klicken oder Koordinaten-Eingabe mit Vorschau
- **Boolean** (Toggle oder Checkbox)
- **Relation-Feld:** Suche nach vorhandener Entität/Objekt/Ort/Occurrence + Rollenangabe (Metadaten auf der Relation). Mehrere Relationen desselben Typs möglich.

**Wiederholbare Felder:**
- Jeder Feldwert hat einen „+ Weiteren Wert hinzufügen"-Button
- Werte sortierbar via Drag-and-Drop
- Einzelne Werte entfernbar

**Status-Selector:** Draft / Internal / Public – prominent, nicht in einem Tab versteckt.

**Medien-Bereich (bei Objekten):**
- Upload-Dropzone
- Thumbnails hochgeladener Medien mit IIIF-Vorschau nach Verarbeitung
- Hauptbild markierbar

**Relationen-Panel:**
- Verknüpfte Datensätze aller Typen
- Pro Relation: Typ + Name + Relationstyp + optionale Metadaten (Rolle, Datum, Kontext)
- Neue Relation hinzufügen: Suche über alle Typen, Relationstyp wählen, optionale Metadaten ausfüllen

**Unterhalb des Formulars:**
- **Audit Log Snippet:** Die letzten 5 Änderungen (Wer, Wann, Was) – collapsible
- **Snapshots:** „Version jetzt sichern" Button + Liste gespeicherter Versionen mit Label und Datum, wiederherstellbar

---

### Screen 3: Schema-Editor

**Zweck:** Administratoren definieren, welche Felder ein Typ hat. Das ist die Konfigurationsoberfläche – komplex, aber selten benutzt.

Layout-Idee: Zwei Panels. Links: Liste der definierten Felder (sortierbar via Drag-and-Drop). Rechts: Eigenschaften des ausgewählten Felds.

Feldeigenschaften:
- Name (intern, slug-artig)
- Label (mehrsprachig: DE / EN)
- Feldtyp (Dropdown: Text, Datum, Zahl, Vokabular, Relation, Geodaten, Boolean)
- Pflichtfeld (Toggle)
- Wiederholbar (Toggle)
- Typ-spezifische Optionen (z.B. bei Vokabular: welches Vokabular?)
- Sortierung (per Drag-and-Drop in der Liste)

Tab-Navigation oben: Objekte | Entitäten | Orte | Occurrences – jeder Typ hat eigene Felder.

---

### Screen 4: Vokabular-Verwaltung

**Zweck:** Kontrollierte Listen verwalten.

Elemente:
- Liste aller Vokabulare (Name, Anzahl Terme, hierarchisch ja/nein)
- Beim Klick: Termliste mit Baumstruktur (hierarchische Vokabulare als Baum, flache als Liste)
- Terme hinzufügen, bearbeiten, verschieben (Eltern ändern)
- Terme können mehrsprachige Labels haben

---

### Screen 5: Importer

**Zweck:** Excel/CSV-Daten in Katalon übernehmen.

**Workflow (Wizard-artig):**

**Schritt 1 – Upload:** Datei hochladen (Excel/CSV), Trennzeichen wählen, Vorschau der ersten Zeilen.

**Schritt 2 – Mapping:** Tabelle: links Excel-Spalten (mit Sample-Werten), rechts Ziel-Feld aus dem Schema (Dropdown). Regeln konfigurierbar: Split bei `;`, Trim, Datumsformat. Zieltyp wählen (Objekte / Entitäten / …).

**Schritt 3 – Dry Run:** Verarbeitungsvorschau: „X Datensätze würden erstellt, Y aktualisiert, Z Fehler" – Fehler als Tabelle mit Zeile + Fehlerbeschreibung (z.B. „Kameratyp ‚Leica M3' nicht im Vokabular"). Downloadbar als CSV.

**Schritt 4 – Import:** „Jetzt importieren" Button. Progress-Anzeige. Zusammenfassung.

---

### Screen 6: Audit Log

**Zweck:** Nachvollziehbarkeit, wer wann was geändert hat.

Elemente:
- Filterbarer Feed: nach Benutzer, Typ, Datensatz-ID, Zeitraum, Aktion (create/update/delete)
- Jeder Eintrag: Zeitstempel, Benutzer, Aktion, Datensatz (klickbar), changed_fields als strukturiertes Diff (alt → neu)

---

## Visueller Stil

**Referenzton:** Professionelles SaaS-Werkzeug. Denk: Airtable trifft Archive-Studio. Klar, dicht, funktional – aber nicht kalt.

- **Farbpalette:** Helles Grau als App-Hintergrund, Weiß für Cards/Panels. Sidebar etwas dunkler (Dunkelgrau oder Dunkelblau). Gleicher Akzentton wie das Discovery-Portal für Konsistenz.
- **Typografie:** Serifenlos, kompakt. Tabellen müssen gut lesbar sein bei hoher Informationsdichte.
- **Formulare:** Klare Labels, ausreichend Abstand zwischen Feldern, aber nicht verschwenderisch. Fehler direkt am Feld, nicht oben als Banner.
- **Status-Badges:** Konsequent farbkodiert (draft/internal/public) – dieselbe Kodierung überall im System.
- **Icons:** Sparsam, funktional. Kein dekoratives Icon-Overload.
- **Kein Dark Mode** in Phase 1 – nicht priorisieren.

---

## Was explizit nicht entworfen werden soll

- Kein öffentliches Discovery-Portal (separater Prompt)
- Kein Benutzer-Onboarding / keine Landingpage
- Kein komplexes Reporting / Dashboard mit Charts (Post-MVP)
