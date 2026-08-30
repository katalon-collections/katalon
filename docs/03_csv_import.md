# Katalon: Metadaten- und Medienimport

## Zweck

Der Metadatenimport dient der Massenerfassung von Datensätzen aus tabellarischen oder XML-basierten Quelldaten. Typische Anwendungsfälle:

- Migration aus einem Altsystem (Excel-Listen, Access-Datenbanken als CSV-Export)
- Initialerfassung von Beständen aus vorhandenen Inventartabellen
- Übernahme von extern erstellten Metadatenlisten

Der Importer legt neue Datensätze an und kann bestehende Datensätze je nach Upsert-Strategie `skip`, `merge` oder `replace` behandeln.

Der Importer ist in der Admin-UI unter **Importer** erreichbar.

## Vokabulare importieren

Für kontrollierte Vokabulare im Importer den Reiter **Vokabulare** öffnen. Zuerst das Zielvokabular wählen, dann eine CSV-, TSV- oder JSON-Datei hochladen. Bei CSV und TSV die Spalten auf **ID**, **Parent-ID**, **Label** oder bei Relationstypen auf **Gegenrichtung** mappen. Ein **Dry-Run** zeigt die geplanten Änderungen, bevor der Import sie schreibt. Relationstypen sind flach und haben keine Parent-ID.

---

## Unterstützte Formate

| Eigenschaft | Details |
|---|---|
| Dateiformate | CSV, TSV, Excel (.xlsx), XML |
| Zeichenkodierung | UTF-8 (mit oder ohne BOM) |
| Trennzeichen | Automatische Erkennung: Komma (`,`), Semikolon (`;`), Tabulator (`\t`), Pipe (`\|`) |
| Kopfzeile | Pflicht — erste Zeile wird als Spaltennamen interpretiert |
| Maximale Gesamtgröße | 100 MB pro Upload-Anfrage; bei mehreren XML-Dateien zählt ihre Summe |
| XML | Zwei-Schritt-Flow: Upload, dann Record-Element wählen |

Die Trennzeichenerkennung analysiert die ersten 4 KB der Datei und wählt das häufigste Zeichen aus den unterstützten Trennzeichen.

---

## Schritt-für-Schritt: Upload → Mapping → Probelauf → Import

### Schritt 1: Upload

1. Im oberen Bereich des Importers den **Ziel-Typ** wählen (Objekte, Entitäten, Orte, Occurrences). Dieser bestimmt, welche Felder im Mapping-Schritt zur Verfügung stehen.
2. Die Datei per Drag & Drop in den Upload-Bereich ziehen oder durch Klick auswählen.
3. Nach dem Upload zeigt der Importer: Anzahl der erkannten Zeilen, Liste der Spaltenköpfe, Vorschau der ersten fünf Zeilen.

Wenn der Upload fehlschlägt:
- Datei oder Summe der gemeinsam gewählten Dateien ist größer als 100 MB → Upload aufteilen
- Dateiformat nicht unterstützt → CSV, TSV, Excel oder XML verwenden
- Kodierungsfehler → Datei als UTF-8 speichern

### Schritt 2: Mapping

Das Mapping bestimmt, welcher Quell-Selector welchem Katalon-Feld entspricht. Bei CSV und Excel ist der Selector eine Spalte, bei XML ein Elementpfad.

Die Mapping-Tabelle zeigt:
- **Quell-Selector**: Spaltenname oder XML-Elementpfad aus der Datei
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

#### Cookbook: häufige Transformationen

Die Vorschau im Transformationsdialog zeigt die ersten drei Werte nach jedem gespeicherten Schritt. Immer zuerst den Probelauf ausführen.

| Aufgabe | Einstellung oder Expression | Beispiel |
|---|---|---|
| Leerzeichen entfernen | `trim` | `  Peter Müller  ` → `Peter Müller` |
| Mehrere Werte übernehmen | `split`, Trennzeichen `;` | `Rot; Blau` → zwei Werte |
| Namen umdrehen | Bei `expression` **Beispiel: „Nachname, Vorname“ umdrehen** wählen | `Müller, Peter` → `Peter Müller` |
| Präfix ergänzen | Expression `Inventar-${value}` | `42` → `Inventar-42` |
| Schreibweise vereinheitlichen | `vocab_map` | `DE` → `Deutsch` |

Expressions laufen beim Import serverseitig. Die Vorlage für Namen erwartet genau ein Komma; Werte ohne Komma bleiben unverändert.

#### Containerfelder importieren

Containerfelder bestehen aus wiederholbaren Einträgen mit Subfeldern. Im Mapping-Dropdown stehen sie als `Container → Subfeld`, zum Beispiel `Person → Vorname` und `Person → Nachname`.

Ordne die Quellspalten den einzelnen Subfeldern zu. Pro Importzeile wird eine Containerinstanz angelegt:

| CSV-Spalte | Katalon-Feld | Ergebnis |
|---|---|---|
| `vorname` | `Person → Vorname` | `{"person": [{"vorname": "Peter"}]}` |
| `nachname` | `Person → Nachname` | `{"person": [{"vorname": "Peter", "nachname": "Müller"}]}` |

Pflicht-Subfelder prüft der Probelauf wie andere Pflichtfelder. Eine einzelne Quellspalte kann derzeit nicht gleichzeitig auf mehrere Subfelder gemappt werden; dafür die Daten vorher in getrennte Spalten aufteilen.

Wiederholte XML-Subfelder werden positionsweise zu mehreren Containerinstanzen zusammengeführt. Haben die beteiligten XML-Elemente unterschiedlich viele Werte, stoppt der Probelauf mit einem Fehler statt Werte falsch zu kombinieren.

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

#### Medienzuordnung bei Objekten

Beim Ziel-Typ **Objekte** kann zusätzlich eine Spalte oder ein XML-Element mit Bilddateinamen gewählt werden. Diese Medienzuordnung ist optional und kein Metadatenfeld. Wiederholte XML-Elemente dürfen mehrere Dateinamen für dasselbe Objekt enthalten.

Erkennt der Importer einen passenden Selector wie `resourceID`, zeigt er einen Vorschlag. Die Zuordnung wird erst übernommen, wenn **verwenden** angeklickt oder der Selector im Auswahlfeld gewählt wurde.

Die Bilddateien werden noch nicht hochgeladen. Der Metadatenimport speichert zunächst nur die Zuordnung zwischen Objekt und Dateiname. Sie wird im späteren Batch-Medienimport verwendet.

### Schritt 3: Probelauf (Dry Run)

Der Probelauf prüft die gemappten Daten, ohne etwas zu speichern.

**Was wird geprüft:**

| Prüfung | Ergebnis bei Fehler |
|---|---|
| Pflichtfelder gemappt | Hinweis (Warning) — nicht zwingend ein Fehler pro Zeile |
| Pflichtfeld in gemappter Spalte ist leer | Fehler für die betroffene Zeile |
| Zeile hat nach Mapping keine Felder | Fehler — Zeile wird übersprungen |
| Gewählter Medien-Selector fehlt | Fehler für den Import |
| Ein Dateiname gehört zu mehreren Datensätzen | Fehler für die betroffenen Zeilen |

**Ausgabe des Probelaufs:**

- **Zeilen gesamt**: Gesamtanzahl Datenzeilen in der Datei
- **Gültig**: Anzahl Zeilen ohne Fehler
- **Fehler**: Anzahl Zeilen mit Fehlern, mit Detailtabelle (Zeilennummer + Fehlermeldung)
- **Hinweise**: Warnungen, die nicht zwingend einen Import-Fehler bedeuten (z.B. nicht gemappte Pflichtfelder)
- **Vorschau**: Die ersten fünf Datensätze in gemappter Form
- **Medienzuordnung**: Anzahl der Datensätze mit Medien, erkannte Dateinamen, Datensätze ohne Dateinamen und Konflikte

Zeilen mit Fehlern werden beim echten Import übersprungen. Nur gültige Zeilen werden importiert.

Der Import-Button ist nur aktiv, wenn mindestens eine gültige Zeile vorhanden ist.

### Schritt 4: Import

Der Import startet einen Hintergrundprozess (Celery-Task). Die Admin-UI zeigt den laufenden Status an und aktualisiert sich automatisch (Polling alle 1,5 Sekunden).

Mögliche Zustände:
- **Läuft…** — Task ist in der Queue oder in Bearbeitung
- **Abgeschlossen** — zeigt Anzahl angelegter Datensätze und eventuelle Fehler
- **Fehlgeschlagen** — zeigt die Fehlermeldung des Tasks

Je nach Import-Option kann der Lauf neue Datensätze nachträglich veröffentlichen.

Wenn eine Medienzuordnung gewählt wurde, speichert der Task die erkannten Dateinamen für neu angelegte und aktualisierte Objekte. Bei der Upsert-Strategie `skip` bleiben die vorhandenen Metadaten unverändert; die Medienzuordnungen werden trotzdem am bestehenden Objekt ergänzt. Das Ergebnis nennt die Anzahl der neu gespeicherten Medienreferenzen.

Nach dem Import: **Neuer Import** setzt den Wizard zurück.

### Bilder anschließend hochladen

Nach einem Metadatenimport mit Medienzuordnung führt **Medien hochladen** direkt zum Batch-Medienimport. Alternativ kann der Tab **Medien** geöffnet werden.

1. Einen Bildordner oder ein ZIP-Archiv auswählen.
2. Den Batch-Import starten.
3. Katalon vergleicht die Dateinamen mit den gespeicherten Medienreferenzen und legt die Bilder an den passenden Objekten ab.

Groß-/Kleinschreibung und die Unicode-Schreibweise werden beim Vergleich normalisiert. Ordnerbestandteile aus der Quelldatei werden nicht für den Vergleich verwendet. Ein Dateiname muss innerhalb des Imports eindeutig einem Objekt zugeordnet sein. Mehrdeutige oder doppelt hochgeladene Dateinamen werden gemeldet und nicht automatisch verknüpft.

Eine CSV- oder TSV-Datei bleibt als manueller Fallback verfügbar. Sie verwendet die Spalten `filename` oder `dateiname`, `object_id` oder `objekt_id` und optional `media_type` oder `medientyp`. Explizite CSV-Zuordnungen haben Vorrang; nicht in der CSV genannte Dateien können weiterhin über gespeicherte Referenzen oder die bisherige UUID-Konvention zugeordnet werden.

Eine fehlerhafte Mapping-Datei stoppt den Lauf: Es werden keine Bilder importiert, und Katalon wechselt nicht automatisch zur Zuordnung über gespeicherte Referenzen oder UUIDs. Die gemeldeten Mapping-Fehler müssen zuerst korrigiert werden.

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
| Unterstützte Metadatenformate | CSV, TSV, Excel (.xlsx) und XML. |
| Max. 100 MB je Upload-Anfrage | Bei mehreren XML-Dateien darf ihre Gesamtgröße 100 MB nicht überschreiten. |
| Bilddateien in separatem Schritt | Die Zuordnung kann im Metadatenimport vorbereitet werden; die Dateien werden danach im Medien-Tab hochgeladen. |
| Bestehende Datensätze | `skip`, `merge` und `replace` werden unterstützt. Bei `skip` können Medienreferenzen ergänzt werden, ohne Metadaten zu ändern. |
| Status immer `draft` | Neue Datensätze starten standardmäßig als `draft`, können aber per `auto_publish` veröffentlicht werden. |
| Keine Zeichenkodierungskonvertierung | Die Datei muss in UTF-8 vorliegen. Latin-1 oder Windows-1252 kann zu Zeichenfehlern führen. |
