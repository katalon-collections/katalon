# Katalon – CSV-Importer

## Zweck

Der CSV-Importer dient der Massenerfassung von Datensätzen aus tabellarischen Quelldaten. Typische Anwendungsfälle:

- Migration aus einem Altsystem (Excel-Listen, Access-Datenbanken als CSV-Export)
- Initialerfassung von Beständen aus vorhandenen Inventartabellen
- Übernahme von extern erstellten Metadatenlisten

Der Importer legt neue Datensätze an und kann bestehende Datensätze je nach Upsert-Strategie `skip`, `merge` oder `replace` behandeln.

Der Importer ist in der Admin-UI unter **Importer** erreichbar.

---

## Unterstützte Formate

| Eigenschaft | Details |
|---|---|
| Dateiformate | CSV, TSV, Excel (.xlsx/.xls), XML |
| Zeichenkodierung | UTF-8 (mit oder ohne BOM) |
| Trennzeichen | Automatische Erkennung: Komma (`,`), Semikolon (`;`), Tabulator (`\t`), Pipe (`\|`) |
| Kopfzeile | Pflicht — erste Zeile wird als Spaltennamen interpretiert |
| Maximale Dateigröße | 100 MB |
| XML | Zwei-Schritt-Flow: Upload, dann Record-Element wählen |

Die Trennzeichenerkennung analysiert die ersten 4 KB der Datei und wählt das häufigste Zeichen aus den unterstützten Trennzeichen.

---

## Schritt-für-Schritt: Upload → Mapping → Probelauf → Import

### Schritt 1: Upload

1. Im oberen Bereich des Importers den **Ziel-Typ** wählen (Objekte, Entitäten, Orte, Occurrences). Dieser bestimmt, welche Felder im Mapping-Schritt zur Verfügung stehen.
2. Die Datei per Drag & Drop in den Upload-Bereich ziehen oder durch Klick auswählen.
3. Nach dem Upload zeigt der Importer: Anzahl der erkannten Zeilen, Liste der Spaltenköpfe, Vorschau der ersten fünf Zeilen.

Wenn der Upload fehlschlägt:
- Datei ist größer als 100 MB → Datei aufteilen
- Dateiformat nicht unterstützt → CSV, TSV, Excel oder XML verwenden
- Kodierungsfehler → Datei als UTF-8 speichern

### Schritt 2: Mapping

Das Mapping bestimmt, welche CSV-Spalte welchem Katalon-Feld entspricht.

Die Mapping-Tabelle zeigt:
- **CSV-Spalte**: Spaltenname aus der Datei
- **Beispielwert**: Inhalt der ersten Datenzeile in dieser Spalte
- **Katalon-Feld**: Dropdown mit allen Feldern des gewählten Typs

Für jede Spalte kann entweder ein Katalon-Feld gewählt oder **— ignorieren —** ausgewählt werden. Ignorierte Spalten werden nicht importiert.

Pflichtfelder sind in der Dropdown-Liste mit einem Stern (`*`) gekennzeichnet.

Unterstützte Transformationsschritte pro Spalte:

- `split`
- `replace`
- `regex_extract`
- `trim`
- `vocab_map`
- `expression`

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

Je nach Import-Option kann der Lauf neue Datensätze nachträglich veröffentlichen.

Nach dem Import: **Neuer Import** setzt den Wizard zurück.

---

## Was wird importiert

Neue Datensätze werden standardmäßig mit **Status `draft`** (Entwurf) angelegt. Sie sind im Public-Portal nicht sichtbar und können nach der Überprüfung manuell veröffentlicht werden oder per `auto_publish` direkt nach dem Import live gehen.

Jeder Feldwert wird als einfacher Textwert gespeichert:
```json
{"title": [{"value": "Straße in Marrakesch"}]}
```

Mit `vocab_map` und anderen Transformationsschritten lassen sich Werte vor dem Import normalisieren.

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
| Nur CSV/TSV | Excel-Dateien (.xlsx, .xls) und XML werden ebenfalls unterstützt. |
| Max. 100 MB | Größere Dateien müssen aufgeteilt werden. |
| Kein Medien-Import | Bilddateien laufen über den separaten Batch-Medienimport im Wizard. |
| Kein Update bestehender Datensätze | Der Import unterstützt `skip`, `merge` und `replace`. |
| Status immer `draft` | Neue Datensätze starten standardmäßig als `draft`, können aber per `auto_publish` veröffentlicht werden. |
| Keine Zeichenkodierungskonvertierung | Die Datei muss in UTF-8 vorliegen. Latin-1 oder Windows-1252 kann zu Zeichenfehlern führen. |
