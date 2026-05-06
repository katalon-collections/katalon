# Katalon – CSV-Importer

## Zweck

Der CSV-Importer dient der Massenerfassung von Datensätzen aus tabellarischen Quelldaten. Typische Anwendungsfälle:

- Migration aus einem Altsystem (Excel-Listen, Access-Datenbanken als CSV-Export)
- Initialerfassung von Beständen aus vorhandenen Inventartabellen
- Übernahme von extern erstellten Metadatenlisten

Der Importer erstellt ausschließlich neue Datensätze. Für das Aktualisieren bestehender Datensätze ist er nicht vorgesehen.

Der Importer ist in der Admin-UI unter **Importer** erreichbar.

---

## Unterstützte Formate

| Eigenschaft | Details |
|---|---|
| Dateiformate | CSV, TSV |
| Zeichenkodierung | UTF-8 (mit oder ohne BOM) |
| Trennzeichen | Automatische Erkennung: Komma (`,`), Semikolon (`;`), Tabulator (`\t`), Pipe (`\|`) |
| Kopfzeile | Pflicht — erste Zeile wird als Spaltennamen interpretiert |
| Maximale Dateigröße | 10 MB |
| Excel-Dateien (.xlsx) | Nicht unterstützt. Excel-Dateien vorher als CSV exportieren: Datei → Speichern unter → CSV (UTF-8). |

Die Trennzeichenerkennung analysiert die ersten 4 KB der Datei und wählt das häufigste Zeichen aus den unterstützten Trennzeichen.

---

## Schritt-für-Schritt: Upload → Mapping → Probelauf → Import

### Schritt 1: Upload

1. Im oberen Bereich des Importers den **Ziel-Typ** wählen (Objekte, Entitäten, Orte, Occurrences). Dieser bestimmt, welche Felder im Mapping-Schritt zur Verfügung stehen.
2. Die CSV-Datei per Drag & Drop in den Upload-Bereich ziehen oder durch Klick auswählen.
3. Nach dem Upload zeigt der Importer: Anzahl der erkannten Zeilen, Liste der Spaltenköpfe, Vorschau der ersten fünf Zeilen.

Wenn der Upload fehlschlägt:
- Datei ist größer als 10 MB → Datei aufteilen
- Dateiformat nicht unterstützt → Datei als CSV exportieren
- Kodierungsfehler → Datei als UTF-8 speichern

### Schritt 2: Mapping

Das Mapping bestimmt, welche CSV-Spalte welchem Katalon-Feld entspricht.

Die Mapping-Tabelle zeigt:
- **CSV-Spalte**: Spaltenname aus der Datei
- **Beispielwert**: Inhalt der ersten Datenzeile in dieser Spalte
- **Katalon-Feld**: Dropdown mit allen Feldern des gewählten Typs

Für jede Spalte kann entweder ein Katalon-Feld gewählt oder **— ignorieren —** ausgewählt werden. Ignorierte Spalten werden nicht importiert.

Pflichtfelder sind in der Dropdown-Liste mit einem Stern (`*`) gekennzeichnet.

#### Auto-Mapping

Nach dem Upload versucht der Importer, Spalten automatisch zuzuordnen. Eine Spalte wird automatisch gemappt, wenn:

1. Der Spaltenname (nach Normalisierung auf Kleinbuchstaben und Unterstriche) exakt dem internen Feldnamen entspricht, **oder**
2. Der Spaltenname exakt dem deutschen Label eines Feldes entspricht (Groß-/Kleinschreibung ignoriert).

Beispiele für automatisches Matching:

| CSV-Spalte | Matched auf Feld |
|---|---|
| `title` | Feld mit `name = "title"` |
| `Titel` | Feld mit `label.de = "Titel"` |
| `date-created` | Feld mit `name = "date_created"` (Bindestrich → Unterstrich) |

Das Auto-Mapping ist ein Vorschlag und kann manuell korrigiert werden.

### Schritt 3: Probelauf (Dry Run)

Der Probelauf prüft die gemappten Daten, ohne etwas zu speichern.

**Was wird geprüft:**

| Prüfung | Ergebnis bei Fehler |
|---|---|
| Pflichtfelder gemappt | Hinweis (Warning) — nicht zwingend ein Fehler pro Zeile |
| Pflichtfeld in gemappter Spalte ist leer | Fehler für die betroffene Zeile |
| Zeile hat nach Mapping keine Felder | Fehler — Zeile wird übersprungen |

**Ausgabe des Probelaufs:**

- **Zeilen gesamt**: Gesamtanzahl Datenzeilen in der Datei
- **Gültig**: Anzahl Zeilen ohne Fehler
- **Fehler**: Anzahl Zeilen mit Fehlern, mit Detailtabelle (Zeilennummer + Fehlermeldung)
- **Hinweise**: Warnungen, die nicht zwingend einen Import-Fehler bedeuten (z.B. nicht gemappte Pflichtfelder)
- **Vorschau**: Die ersten fünf Datensätze in gemappter Form

Zeilen mit Fehlern werden beim echten Import übersprungen. Nur gültige Zeilen werden importiert.

Der Import-Button ist nur aktiv, wenn mindestens eine gültige Zeile vorhanden ist.

### Schritt 4: Import

Der Import startet einen Hintergrundprozess (Celery-Task). Die Admin-UI zeigt den laufenden Status an und aktualisiert sich automatisch (Polling alle 1,5 Sekunden).

Mögliche Zustände:
- **Läuft…** — Task ist in der Queue oder in Bearbeitung
- **Abgeschlossen** — zeigt Anzahl angelegter Datensätze und eventuelle Fehler
- **Fehlgeschlagen** — zeigt die Fehlermeldung des Tasks

Nach dem Import: **Neuer Import** setzt den Wizard zurück.

---

## Was wird importiert

Alle erfolgreich importierten Datensätze werden mit **Status `draft`** (Entwurf) angelegt. Sie sind im Public-Portal nicht sichtbar und müssen nach der Überprüfung manuell auf `internal` oder `public` gesetzt werden.

Jeder Feldwert wird als einfacher Textwert gespeichert:
```json
{"title": [{"value": "Straße in Marrakesch"}]}
```

Das bedeutet: Relationsfelder (Verknüpfungen auf andere Datensätze), Vokabularfelder (Term-IDs) und PID-Felder werden beim CSV-Import als Rohtext importiert und müssen anschließend manuell nachbearbeitet werden. Für Relationen und Vokabulare ist der CSV-Importer daher nur dann direkt nutzbar, wenn die gemappte Spalte bereits die internen Katalon-IDs oder Term-Werte enthält.

---

## Spaltenmapping — technische Details

Das Mapping ist eine JSON-Struktur der Form:

```json
{
  "Spaltenname in CSV": "interner_feldname",
  "Titel": "title",
  "Datum": "date_created"
}
```

Spalten, die auf den leeren String gemappt sind oder nicht im Mapping erscheinen, werden ignoriert.

---

## Einschränkungen

| Einschränkung | Details |
|---|---|
| Nur CSV/TSV | Excel-Dateien (.xlsx, .xls) werden nicht unterstützt. |
| Max. 10 MB | Größere Dateien müssen aufgeteilt werden. |
| Kein Medien-Import | Bilddateien können nicht per CSV importiert werden. Für Batch-Medienimport ist ein separater Mechanismus geplant (Phase 10.1). |
| Kein Update bestehender Datensätze | Der Importer legt nur neue Datensätze an. |
| Relationen und Vokabulare als Rohtext | Keine automatische Auflösung von Feldwerten auf Datensatz-IDs oder Vokabular-Term-IDs. |
| Status immer `draft` | Importierte Datensätze können nicht direkt als `public` importiert werden. |
| Keine Zeichenkodierungskonvertierung | Die Datei muss in UTF-8 vorliegen. Latin-1 oder Windows-1252 kann zu Zeichenfehlern führen. |
