# Katalon – Schema-Verwaltung

## Übersicht

Das Schema bestimmt, welche Felder ein Datensatz eines bestimmten Primärtyps hat. Die Verwaltung erfolgt in der Admin-UI unter **Konfiguration → Schemata**. Felder können ohne Datenbankmigrationen angelegt, bearbeitet und gelöscht werden.

Nur Benutzer mit der Rolle `admin` oder `superuser` können Felder anlegen, ändern oder löschen.

---

## Felder anlegen (Admin-UI)

1. Admin-UI öffnen, im linken Menü **Schemata** wählen.
2. Links den Primärtyp auswählen (Objekte, Entitäten, Orte, Occurrences).
3. Rechts oben **Neues Feld** klicken.
4. Im Formular die Feldeigenschaften ausfüllen und speichern.

Nach dem Speichern ist das Feld sofort in allen Erfassungsformularen sichtbar. Bestehende Datensätze ohne den neuen Feldwert sind weiterhin gültig, sofern das Feld nicht als Pflichtfeld markiert ist.

Das Löschen eines Feldes ist ein Soft-Delete: Das Feld wird als `is_deleted` markiert und aus der UI ausgeblendet, die gespeicherten Feldwerte in bestehenden Datensätzen bleiben in der Datenbank erhalten.

Im selben Feld-Detailbereich gibt es den Abschnitt `Metadaten-Export`. Dort kann ein Feld auf Exportformate wie `oai_dc` gemappt werden. Die Tabs fuer `LIDO` und `METS/MODS` sind bereits angelegt, aber noch Stub-UI.

---

## Eigenschaften einer Felddefinition

| Eigenschaft | Pflicht | Beschreibung |
|---|---|---|
| `name` | Ja | Interner Bezeichner (Kleinbuchstaben, Unterstriche). Unveränderlich nach dem Anlegen. Beispiel: `photographer` |
| `label.de` | Empfohlen | Deutsches Anzeigelabel. Erscheint in der UI. |
| `label.en` | Optional | Englisches Anzeigelabel. |
| `field_type` | Ja | Feldtyp (siehe unten). |
| `is_required` | Nein | Wenn gesetzt, muss das Feld beim Speichern eines Datensatzes befüllt sein. |
| `is_repeatable` | Nein | Wenn gesetzt, können mehrere Werte pro Datensatz gespeichert werden. |
| `sort_order` | Nein | Numerische Sortierreihenfolge im Formular. Kleinere Zahlen erscheinen zuerst. |
| `target_subtype` | Nein | Wenn gesetzt, gilt das Feld nur für den angegebenen Subtyp. |
| `settings` | Nein | Feldtyp-spezifische Optionen als JSON-Objekt (siehe unten). |

---

## Alle Feldtypen

### `text` – Einzeiliger Freitext

Für kurze Texte ohne Formatierung. Kann mit einem Regex validiert werden.

Beispiele:
- Titel
- Inventarnummer (als zusätzliche Kennung neben `idno`)
- ISBN, ISSN, DOI
- Herstellerbezeichnung

**Settings:**

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `validation_regex` | String | Optionaler regulärer Ausdruck. Eingabe wird beim Speichern gegen diesen Ausdruck geprüft. |

Beispiel:
```json
{"validation_regex": "^97[89]-[0-9]{10}$"}
```

---

### `richtext` – Mehrzeiliger formatierbarer Text

Für längere Beschreibungen mit einfacher Formatierung (Fett, Kursiv, Listen). Der Wert wird als HTML gespeichert.

Beispiele:
- Beschreibungstext
- Provenienzangaben
- Restaurierungsnotizen

---

### `date` – Datum nach EDTF

Unterstützt den Extended Date/Time Format-Standard (EDTF). Damit lassen sich auch unscharfe oder unvollständige Datumsangaben ausdrücken.

Beispiele für gültige Werte:
- `1923` — nur das Jahr
- `1923-05` — Jahr und Monat
- `1923-05-14` — exaktes Datum
- `1920~` — ungefähr 1920
- `1910/1930` — Zeitraum
- `[1920, 1930]` — eines der genannten Jahre

Beispiele für Felder:
- Entstehungsdatum
- Erwerbsdatum
- Ausstellungsdatum

---

### `number` – Numerischer Wert

Für ganzzahlige oder Dezimalzahlen.

Beispiele:
- Höhe in Millimetern
- Gewicht in Gramm
- Auflage (Anzahl)
- Seitenzahl

---

### `boolean` – Ja/Nein

Für binäre Eigenschaften.

Beispiele:
- Ist digitalisiert?
- Ist restauriert?
- Enthält Personendaten?

---

### `vocab` – Vokabularfeld

Ermöglicht die Auswahl eines Terms aus einem kontrollierten Vokabular. Das zugehörige Vokabular wird in `settings.vocabulary_id` referenziert.

**Settings:**

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `vocabulary_id` | UUID | ID des Vokabulars aus der Vokabular-Verwaltung. Pflicht für `vocab`-Felder. |

Beispiel:
```json
{"vocabulary_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
```

Die UUID des Vokabulars findet man in der Admin-UI unter **Konfiguration → Vokabulare**.

Beispiele für Felder:
- Materialart (Vokabular: Materialien)
- Kameratyp (Vokabular: Kameratypen)
- Genre (Vokabular: Genres)

---

### `vocab_free` – Vokabularfeld mit Freitext

Texteingabe mit optionalem Vokabular als Autocomplete-Quelle. Im Gegensatz zu `vocab` ist der eingegebene Wert nicht an einen Term im Vokabular gebunden — der User kann beliebige Texte eintragen oder einen Vorschlag aus der Autocomplete-Liste wählen.

**UX-Unterschied zu `vocab`:**

| | `vocab` | `vocab_free` |
|---|---|---|
| Eingabe | Strikter Picker, nur Vokabular-Terms wählbar | Freitextfeld mit optionalen Vorschlägen |
| Gespeichertes Format | `{"id": "uuid", "label": "Begriff"}` | `"Begriff"` (plain string) |
| Referenz-Integrität | Term-ID bleibt verknüpft | Kein referenzieller Bezug |

**Settings:**

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `vocabulary_id` | UUID | Optional. Vokabular, dessen Terms als Autocomplete-Vorschläge angezeigt werden. Ohne Angabe: reines Freitextfeld ohne Vorschläge. |

Beispiel:
```json
{"vocabulary_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
```

Beispiele für Felder:
- Technik / Herstellungsverfahren (viele Freitextvarianten, Vokabular als Hilfe)
- Schlagwort (freie Eingabe, aber Kontrolle über bekannte Begriffe)

---

### `relation` – Verknüpfung zu einem anderen Datensatz

Verknüpft den Datensatz mit einem anderen Datensatz (Object, Entity, Place oder Occurrence). Die Relation wird in der `relations`-Tabelle gespeichert.

Beispiele:
- Fotograf:in → Entity (Person)
- Aufnahmeort → Place
- Vorlage → Object (ein anderes Objekt)
- Exemplar von → Occurrence (ein bibliografisches Werk)

Relationsfelder sind für fachlich benannte Beziehungen im Erfassungsformular
bestimmt, etwa „Autor:in“ oder „Aufnahmeort“. Sie können einen Zieltyp, ein
Relationstyp-Vokabular und optional einen festen Relationstyp festlegen. Ohne
festen Typ kann die Person, die katalogisiert, einen passenden Typ aus dem
Vokabular wählen. Mit festem Typ wird genau diese Semantik verwendet.

Die Beziehungen-Karte eines gespeicherten Datensatzes ist keine zweite
Bearbeitungsoberfläche für solche Felder: Sie zeigt den vollständigen
Beziehungsgraphen und fügt nur weitere, freie Beziehungen zu anderen
Haupttypen hinzu. So bleibt eine fachlich konfigurierte Beziehung im zugehörigen
Formularfeld bearbeitbar, während zusätzliche Graph-Beziehungen weiterhin
möglich sind.

Für die Portalsuche kann ein Relationsfeld ausgewählte Felder seines Zieltyps
in den Suchindex übernehmen. Ein fester Relationstyp beschränkt diese Werte auf
die entsprechende Beziehung; ohne festen Typ werden Werte aller Beziehungen
zum gewählten Zieltyp übernommen.

---

### `geo` – Geografische Koordinaten

Speichert einen geografischen Punkt (Längen- und Breitengrad). Für Ortstypen wird der Ort außerdem als PostGIS-Geometrie gespeichert.

Beispiele:
- Exakter Aufnahmestandort einer Fotografie
- Fundort eines Objekts

---

### `pid` – Persistenter Identifier

Für Normdaten-IDs aus externen Quellen (GND, VIAF, Geonames, ORCID …). Das Authority-Plugin-System ermöglicht die Suche in der externen Quelle direkt aus der Erfassung.

**Settings:**

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `authority` | String | ID des Authority-Adapters, z.B. `gnd`, `viaf`, `geonames`. |

Beispiel:
```json
{"authority": "gnd"}
```

Beispiele:
- GND-ID einer Person
- Geonames-ID eines Ortes
- ORCID einer Forscherin

---

## Subtyp-Felder

Bei Object, Entity, Place, Occurrence und Vorgang kann ein Feld an einen bestimmten Subtyp gebunden werden.

- **Feld ohne `target_subtype`**: Erscheint für alle Datensätze dieses Primärtyps, unabhängig vom Subtyp.
- **Feld mit `target_subtype = "person"`**: Erscheint nur bei Entitäten vom Subtyp `person`.
- **Feld mit `target_subtype = "acquisition"`**: Erscheint nur bei Vorgängen vom Typ `acquisition`.

**Anwendungsfall:**

Eine Entität kann eine Person oder eine Organisation sein. Für Personen braucht man Geburtsdatum und Sterbeort, für Organisationen Gründungsjahr und Rechtsform. Durch Subtyp-Felder lässt sich das Formular entsprechend steuern.

In der Admin-UI kann für jeden Datensatztyp ein vorhandener Subtyp gewählt werden. Wenn das Subtyp-Eingabefeld leer gelassen wird, gilt das Feld für alle Subtypen.

Subtypen werden in der Subtyp-Verwaltung angelegt und serverseitig validiert. Bei Vorgängen sind `loan_out`, `loan_in`, `acquisition`, `conservation`, `object_entry` und `deaccession` geschützte Systemtypen: Sie können nicht gelöscht, umbenannt oder verschoben werden. Eigene Vorgangstypen können zusätzlich angelegt und für Felder sowie Formularvarianten verwendet werden.

---

## Schema-Import aus YAML oder JSON

Anstatt Felder einzeln anzulegen, können Felddefinitionen als YAML- oder JSON-Datei importiert werden. Das ist sinnvoll bei der initialen Schema-Konfiguration oder beim Übertrag eines Schemas zwischen Instanzen.

Der Import erfolgt in der Admin-UI unter **Konfiguration → Schemata → Import**.

### Dateiformat

Die Datei beschreibt einen Primärtyp und eine Liste von Feldern:

```yaml
target_type: object
fields:
  - name: title
    label:
      de: Titel
      en: Title
    field_type: text
    is_required: true
    is_repeatable: false
    sort_order: 0

  - name: date_created
    label:
      de: Entstehungsdatum
      en: Date created
    field_type: date
    is_required: false
    is_repeatable: false
    sort_order: 10

  - name: material
    label:
      de: Material
    field_type: vocab
    is_required: false
    is_repeatable: true
    sort_order: 20
    settings:
      vocabulary_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6"

  - name: description
    label:
      de: Beschreibung
    field_type: richtext
    is_required: false
    is_repeatable: false
    sort_order: 30

  - name: photographer
    label:
      de: Fotograf:in
      en: Photographer
    field_type: relation
    is_required: false
    is_repeatable: true
    sort_order: 40
```

Äquivalentes JSON-Format:

```json
{
  "target_type": "object",
  "fields": [
    {
      "name": "title",
      "label": {"de": "Titel", "en": "Title"},
      "field_type": "text",
      "is_required": true,
      "is_repeatable": false,
      "sort_order": 0
    }
  ]
}
```

### Feldspezifikation (vollständig)

| Schlüssel | Typ | Pflicht | Standardwert | Beschreibung |
|---|---|---|---|---|
| `name` | String | Ja | — | Interner Name. Muss innerhalb des Typs eindeutig sein. |
| `label` | Objekt | Nein | `{}` | Labels pro Sprache: `{"de": "...", "en": "..."}` |
| `field_type` | String | Nein | `text` | Einer der gültigen Feldtypen (s.o.) |
| `is_required` | Boolean | Nein | `false` | Pflichtfeld |
| `is_repeatable` | Boolean | Nein | `false` | Wiederholbar |
| `sort_order` | Integer | Nein | Index in Liste | Reihenfolge im Formular |
| `target_subtype` | String | Nein | `null` | Nur für diesen Subtyp gültig |
| `settings` | Objekt | Nein | `{}` | Feldtyp-spezifische Optionen |

### Dry-Run

Wenn die Option **Dry-Run** aktiviert ist, wird die Datei geparst und ausgewertet, aber nichts in die Datenbank geschrieben. Das Ergebnis zeigt:
- Wie viele Felder neu angelegt würden
- Wie viele Felder aktualisiert würden (nur mit Overwrite-Option)
- Wie viele Felder übersprungen würden (bereits vorhanden, kein Overwrite)
- Fehler in der Datei (fehlende Pflichtfelder, ungültige Struktur)

### Overwrite

Standardmäßig werden Felder, die bereits unter dem gleichen `name` existieren, übersprungen. Mit der Option **Bestehende überschreiben** werden bestehende Felder mit den Werten aus der Importdatei aktualisiert.

Der `name` eines Feldes kann nach dem Anlegen nicht mehr geändert werden — er dient als Identifikationsschlüssel beim Import.

---

## Validierungs-Regex für Text-Felder

Für Felder vom Typ `text` kann ein regulärer Ausdruck als Validierungsregel hinterlegt werden. Bei der Dateneingabe wird der eingegebene Wert gegen diesen Ausdruck geprüft.

Der Ausdruck wird in `settings.validation_regex` gespeichert:

```json
{"validation_regex": "^\\d{4}$"}
```

**Nützliche Beispiele:**

| Anwendungsfall | Ausdruck |
|---|---|
| Vierstellige Jahreszahl | `^\d{4}$` |
| ISBN-13 | `^97[89]-[0-9]{10}$` |
| ISSN | `^\d{4}-\d{3}[\dX]$` |
| DOI | `^10\.\d{4,}/.+$` |
| GND-ID (numerisch) | `^\d{8,10}[\dX]$` |

In der Admin-UI gibt es ein Eingabefeld für den Regex direkt im Feld-Formular (nur sichtbar wenn `field_type = text`).

---

## Vokabularfelder konfigurieren

Um ein `vocab`-Feld mit einem Vokabular zu verknüpfen:

1. Sicherstellen, dass das gewünschte Vokabular unter **Konfiguration → Vokabulare** existiert.
2. Die UUID des Vokabulars kopieren (in der Detailansicht sichtbar).
3. Das Feld anlegen oder bearbeiten, Feldtyp `Vokabular` wählen.
4. Im Feld `settings.vocabulary_id` die UUID eintragen.

Beim Anlegen über den Schema-Import: Die UUID in `settings.vocabulary_id` einsetzen (siehe Beispiel oben).

Ohne `vocabulary_id` zeigt das Feld in der Erfassung eine leere Auswahlliste.
