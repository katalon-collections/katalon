# Katalon – Formularvarianten

## Übersicht

Formularvarianten wählen und ordnen die vorhandenen Schemafelder eines Datensatztyps für unterschiedliche Erfassungssituationen aus – etwa eine schlanke Schnellerfassung neben der vollständigen Maske. Die Verwaltung erfolgt in der Admin-UI unter **Konfiguration → Formularvarianten**.

Nur Benutzer mit der Rolle `admin` oder `superuser` sehen diesen Menüpunkt und können Varianten anlegen, ändern oder löschen.

Eine Formularvariante legt **keine neuen Felder** an und erzeugt **keinen zweiten Metadatenspeicher**: Sie wählt nur aus den in **Konfiguration → Schemata** bereits definierten Feldern eine Teilmenge aus und legt deren Reihenfolge fest. Ein Datensatz speichert seine Werte immer in derselben `metadata`-Struktur, unabhängig davon, mit welcher Variante er erfasst wurde.

---

## Varianten anlegen

1. Admin-UI öffnen, im linken Menü unter **Konfiguration** den Punkt **Formularvarianten** wählen.
2. Oben den Datensatztyp wählen (Objekte, Entitäten, Orte, Occurrences, Vorgänge).
3. Falls für diesen Typ Subtypen konfiguriert sind, erscheint zusätzlich eine Subtyp-Auswahl. **Alle / Global** zeigt Varianten, die unabhängig vom Subtyp gelten; eine konkrete Auswahl zeigt zusätzlich subtyp-spezifische Felder.
4. **Neue Variante** klicken.
5. Namen (interner Bezeichner, z. B. `schnellerfassung`) und deutsches Label eingeben.
6. Felder aus der Liste ankreuzen. Mit den Pfeiltasten neben jedem Feld lässt sich die Reihenfolge innerhalb der Variante anpassen.
7. Optional **Globaler Default für diesen Typ/Subtyp** setzen (siehe unten).
8. Speichern.

Pflichtfelder (auch Pflichtfelder innerhalb einer Gruppe) sind in der Feldliste bereits angehakt und lassen sich nicht abwählen – eine Variante darf kein Feld verstecken, das beim Speichern zwingend benötigt wird. Das Backend prüft diese Regel unabhängig von der UI beim Anlegen und Bearbeiten einer Variante.

---

## Welche Variante wird beim Erfassen angezeigt?

Beim Öffnen eines Erfassungsformulars entscheidet folgende Priorität, welche Variante aktiv ist:

1. Eine zuletzt manuell gewählte Variante, die für Typ und Subtyp im Browser gemerkt wurde (pro Gerät/Browser, nicht kontoübergreifend).
2. Der für die eigene Rolle konfigurierte Rollen-Default (siehe unten).
3. Der globale Default für diesen Typ/Subtyp, falls eine Variante als solcher markiert ist.
4. Ohne Treffer: das vollständige Schema, also alle Felder – identisch zum Verhalten ohne Formularvarianten.

Wählt die Sachbearbeiterin oben im Formular manuell den Tab **Vollständig**, bleibt diese Wahl gemerkt und wird beim nächsten Öffnen nicht automatisch wieder von einem Rollen- oder Global-Default überschrieben.

### Rollen-Default

In der Variantenliste lässt sich pro Variante ankreuzen, für welche Rollen (Administrator, Redakteur, Katalogisierer, Betrachter) sie als Standardvariante gelten soll. Pro Rolle und Typ/Subtyp-Kombination kann jeweils nur eine Variante als Default markiert sein – das erneute Setzen bei einer anderen Variante hebt den vorherigen Rollen-Default automatisch auf.

---

## Wo Formularvarianten wirken

- Im normalen Bearbeitungsformular für bestehende und neue Datensätze der fünf Datensatztypen (Objekte, Entitäten, Orte, Occurrences, Vorgänge).
- In der Schnellerfassung, die beim Anlegen von Relationen aus einem anderen Formular heraus geöffnet wird (siehe Beziehungen-Karte in [Schema-Verwaltung](02_schema_verwaltung.md)).

Gruppenfelder werden als Ganzes über den Namen der Gruppe in die Variante aufgenommen; einzelne Kindfelder einer Gruppe lassen sich nicht separat aus- oder abwählen.

---

## Varianten löschen

Eine Formularvariante kann jederzeit gelöscht werden. Datensätze, die mit dieser Variante erfasst wurden, bleiben unverändert – ihre Metadaten sind nicht an die Variante gebunden. War die gelöschte Variante als Rollen- oder Global-Default gesetzt, entfällt dieser Default ersatzlos.
