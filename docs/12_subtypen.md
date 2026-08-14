# Katalon – Subtypen

## Übersicht

Subtypen unterteilen einen Datensatztyp in fachlich unterschiedliche Ausprägungen – zum Beispiel Person und Organisation bei Entitäten, oder Leihgabe ausgehend und Erwerbung bei Vorgängen. Die Verwaltung erfolgt in der Admin-UI unter **Konfiguration → Subtypen**.

Nur Benutzer mit der Rolle `admin` oder `superuser` sehen diesen Menüpunkt und können Subtypen anlegen, ändern oder löschen.

Subtypen gibt es für Objekte, Entitäten, Orte, Occurrences und Vorgänge. Für Objekte, Entitäten, Orte und Occurrences ist kein Subtyp vorkonfiguriert – Institutionen legen sie nach Bedarf selbst an. Bei Vorgängen sind sechs Typen bereits vorhanden: `loan_out` (Leihgabe ausgehend), `loan_in` (Leihgabe eingehend), `acquisition` (Erwerbung), `conservation` (Restaurierung/Konservierung), `object_entry` (Eingangsprüfung) und `deaccession` (Deakzession).

Ein Datensatz ohne konfigurierten Subtyp verwendet nur das Schema des Primärtyps. Sobald für einen Primärtyp Subtypen existieren, muss ein neuer Datensatz (außer im Entwurfsstatus) einen davon auswählen.

---

## Subtypen anlegen

1. Admin-UI öffnen, im linken Menü unter **Konfiguration** den Punkt **Subtypen** wählen.
2. Oben den Primärtyp wählen (Objekte, Entitäten, Orte, Occurrences, Vorgänge).
3. **Neuer Subtyp** klicken.
4. Deutsches und englisches Label eingeben.
5. Optional eine Beschreibung des institutionellen Einsatzes hinterlegen – hilfreich für andere Sachbearbeiter:innen, die später denselben Subtyp verwenden.
6. Interner Name eintragen (z. B. `person`, `organisation`). Dieser Name ist nach dem Speichern nicht mehr änderbar, da er als stabiler Schlüssel für Datensätze und Felddefinitionen dient.
7. Optional als **Standard-Subtyp** markieren – dieser wird beim Anlegen neuer Datensätze und bei der Schnellerfassung vorausgewählt.
8. Speichern.

---

## Wofür Subtypen verwendet werden

- **Felder eingrenzen**: In der Schema-Verwaltung (**Konfiguration → Schemata**) kann ein Feld auf einen `target_subtype` eingeschränkt werden. Ohne diese Einschränkung gilt ein Feld für alle Subtypen des Primärtyps. Details siehe [Schema-Verwaltung](02_schema_verwaltung.md#subtyp-felder).
- **Formularvarianten eingrenzen**: Formularvarianten lassen sich ebenfalls pro Subtyp konfigurieren, siehe [Formularvarianten](11_formularvarianten.md).
- **Relations-Suche eingrenzen**: Ein Relationsfeld kann einen festen Ziel-Subtyp vorgeben. Die Suche nach Zieldatensätzen und die Schnellerfassung sind dann auf diesen Subtyp beschränkt.
- **Listenfilter**: In der Datensatzliste erscheint ein Subtyp-Filter, sobald für den jeweiligen Primärtyp Subtypen konfiguriert sind. Die Auswahl eines Subtyps blendet zusätzlich dessen subtypspezifische Listenspalten ein.

---

## Subtypen löschen

Ein Subtyp lässt sich löschen, solange kein Datensatz diesen Subtyp verwendet. Verwendet mindestens ein Datensatz den Subtyp, blockiert Katalon das Löschen.

Beim Löschen eines unbenutzten Subtyps werden dessen subtypspezifische Felddefinitionen und Formularvarianten deaktiviert (Soft-Delete, wie beim Löschen einzelner Felder). Datensätze anderer Subtypen sind davon nicht betroffen.

Das gilt auch für die sechs vorkonfigurierten Vorgangstypen: Solange kein Vorgang einen der sechs Typen verwendet, kann er wie ein selbst angelegter Subtyp gelöscht werden.

---

## Subtypen bei Vorgängen

Vorgänge nutzen denselben Subtyp-Mechanismus wie die vier Bestandstypen. Neben den sechs vorkonfigurierten Typen lassen sich institutionsspezifische Vorgangstypen anlegen, etwa für lokale Workflows ohne Entsprechung in der Standardliste.

Nur der technische Typ `loan_out` hat eine eingebaute Fachregel: Katalon verhindert, dass ein Objekt gleichzeitig Teil von zwei aktiven Vorgängen dieses Typs ist. Eigene Vorgangstypen haben keine impliziten Automatismen – der Sammlungsstatus eines verknüpften Objekts wird beim Abschließen eines Vorgangs nur vorgeschlagen, nie automatisch gesetzt. Details zum Vorgangs-Konzept: [Konzeptpapier Vorgänge](konzept-vorgaenge.md).
