# Katalon – Mehrsprachigkeit

## Zweck

Katalon unterstützt mehrere Sprachen auf drei Ebenen:

1. **Labels** (Feldnamen, Subtypen, Formularvarianten, Vokabular-Terme) – pro Sprache ein eigener Text.
2. **Übersetzbare Feldwerte** – ein Feld (z. B. „Beschreibung") kann einen deutschen und einen englischen Text enthalten.
3. **Portal-Oberfläche** – der öffentliche Katalog hat einen Sprachumschalter.

Die konfigurierbaren Sprachen gelten global für die ganze Instanz, nicht pro Feld.

---

## Sprachliste konfigurieren

Unter **Einstellungen → Sprachen** wird die Liste der unterstützten Sprachen gepflegt (ISO-639-1-Codes, kommagetrennt, z. B. `de, en, fr`).

- **Erste Sprache = Primärsprache.** Sie ist die Fallback-Sprache: Fehlt ein Text in der angezeigten Sprache, wird auf die Primärsprache zurückgegriffen.
- Änderungen wirken sofort auf alle Label-Eingabefelder (Schema, Subtypen, Vokabulare, Formularvarianten) und auf das Übersetzungsformular.
- Standard: `de, en`.

---

## Labels mehrsprachig pflegen

Überall, wo Labels gepflegt werden, erscheint **ein Eingabefeld pro konfigurierter Sprache**:

- **Schema** (Felddefinitionen): „Label DE", „Label EN", …
- **Subtypen**
- **Formularvarianten** (Anzeigename)
- **Vokabulare** (Term-Label, bei Relationstypen zusätzlich Gegenrichtung)

Es gibt keine fest verdrahteten „nur DE/EN"-Felder mehr; die Anzahl der Eingabefelder folgt der Sprachliste.

---

## Übersetzbare Feldwerte („Beschreibung" in DE und EN)

### Feld als übersetzbar markieren

Im Schema-Editor steht bei **Text-** und **Rich-Text-Feldern** (nicht wiederholbar) die Checkbox **„Mehrsprachig"**.

Nur diese Feldtypen sind übersetzbar:

| Übersetzbar | Nicht übersetzbar |
|---|---|
| Text, Rich-Text | Relation, Datum, Zahl, Boolean, Vokabular, Normdaten, PID, Containerfelder |
| – | Wiederholbare Felder |

Bei anderen Feldtypen zeigt der Editor den Hinweis: *„Dieser Feldtyp ist nicht übersetzbar (nur Text/Rich-Text, nicht wiederholbar)."*

### Werte erfassen

Im Datensatz-Formular zeigt ein übersetzbares Feld zuerst nur die Primärsprache:

```
DE  [Deutsche Beschreibung………………………………]  [+ EN]
```

- **+ EN** (bzw. + FR, …) deckt die Eingabe für weitere Sprachen auf.
- Der Platzhalter zeigt das Label in der jeweiligen Sprache (z. B. „Description").
- Bereits befüllte Sprachen bleiben sichtbar; jede hinzugefügte Sprache hat ein **×** zum Entfernen.

Gespeichert wird ein Objekt pro Sprache, z. B. `{"de": "Deutsche Beschreibung", "en": "English description"}`.

---

## Portal-Anzeige

Der öffentliche Katalog zeigt übersetzbare Inhalte in der **aktiven Sprache** mit Fallback:

- Sprachwahl-Reihenfolge: URL-Parameter `?lang=` → gespeicherte Wahl → Browsersprache → Primärsprache.
- Der Sprachumschalter sitzt oben rechts im Header.
- Fehlt ein Text in der aktiven Sprache, fällt Katalon auf Primärsprache → Deutsch → erste vorhandene Sprache zurück.

---

## Neue Sprache hinzufügen

1. **Admin → Einstellungen → Sprachen**: Sprachcode ergänzen (z. B. `de, en, fr`).
2. **Portal-Übersetzungen**: Im Quellcode `frontend/portal/src/i18n/locales/en.ts` nach `fr.ts` kopieren, Werte übersetzen und in `i18n/index.ts` registrieren.

Danach erscheinen die Label-Eingabefelder und der Portal-Umschalter automatisch in der neuen Sprache.

---

## Grenzen

- **Wiederholbare Felder** und **strukturierte Feldtypen** (Relation, Datum, Zahl, …) sind bewusst nicht übersetzbar – sie sind sprachunabhängig.
- **Primärfeld `title`/`name`** (Seitentitel, Suchtreffer, Karten) wird nicht übersetzt; es ist als eindeutiger Anzeigename konzipiert, nicht als mehrsprachiger Inhalt.
- **Suchindex**: Die Volltextsuche indiziert derzeit alle Sprachvarianten zusammen; sprachspezifische Analyzer sind nicht umgesetzt.
- **CSV-Importer**: Das Spalten-Mapping (`label:de`/`label:en`) bleibt auf Deutsch/Englisch beschränkt.
