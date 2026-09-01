# Walkthrough: eine eigene Sammlung einrichten

Dieser Einstieg richtet eine kleine fotografische Sammlung ein. Das Beispiel trennt die Fotografie selbst, die fotografierende Person, den Aufnahmeort und eine Ausstellung. Dadurch bleibt die Information später suchbar und lässt sich ohne doppelte Eingaben weiterverwenden.

> **Bild vorgesehen: Startseite der Admin-UI mit hervorgehobener Navigation.**
> Zeigen: die Bereiche **Konfiguration**, **Objekte**, **Entitäten**, **Orte**, **Occurrences** und **Vorgänge**. Alt-Text: „Navigation der Katalon-Admin-UI mit den Bereichen für Konfiguration und Datensätze.“

Für die Konfiguration ist eine Rolle `admin` oder `superuser` nötig. Die Onboarding-Tour beim ersten Login führt durch dieselben Bereiche; dieser Text ist absichtlich ausführlicher und kann unabhängig von der Tour benutzt werden.

## Das Beispielmodell

| Katalon-Typ | Beispiel | Aufgabe im Modell |
|---|---|---|
| Objekt | Fotografie „Marktplatz im Winter“ | Das verwahrte oder beschriebene Artefakt. |
| Entität | Marta Keller | Person oder Organisation, hier die Fotografin. |
| Ort | Marktplatz Neustadt | Geografischer Aufnahmeort. |
| Occurrence | Ausstellung „Winter in der Stadt“ | Werk, Ereignis oder Konzept ohne physischen Träger. |

Ein Objekt erhält keine Freitextkopien von Name und Ort. Es wird mit den eigenen Datensätzen verknüpft. Korrigiert sich etwa der Ortsname, erscheint die Korrektur dadurch an allen verknüpften Stellen.

## Subtypen anlegen

Subtypen sind optional. Sie lohnen sich, wenn ein Primärtyp unterschiedliche Formulare braucht. Für dieses Beispiel genügen die vier Subtypen `fotografie`, `person`, `stadt` und `ausstellung`.

1. Unter **Konfiguration → Subtypen** den jeweiligen Primärtyp auswählen.
2. **Neuer Subtyp** wählen und deutsches sowie englisches Label eingeben.
3. Den vorgeschlagenen internen Namen prüfen, etwa `fotografie`. Nach dem Speichern ist dieser Name der stabile Schlüssel und nicht mehr änderbar.
4. Bei einem häufigen Typ **Standard-Subtyp** aktivieren.

> **Bild vorgesehen: Formular „Neuer Subtyp“ für Objekt.**
> Zeigen: Labels in zwei Sprachen, interner Name und Standard-Subtyp. Alt-Text: „Subtyp Fotografie mit dem internen Namen fotografie.“

Felder ohne Subtyp gelten für alle Datensätze eines Primärtyps. Ein Feld, das an `fotografie` gebunden ist, erscheint nur dort. Die vollständige Erklärung steht unter [Subtypen](12_subtypen.md).

## Relationstypen vor den Relationsfeldern festlegen

Relationen brauchen eine fachliche Bedeutung. Unter **Konfiguration → Vokabulare** ein Relationsvokabular anlegen und mindestens diese Terme eintragen:

| Richtung vom Objekt aus | Gegenrichtung | Erlaubte Kombination |
|---|---|---|
| fotografiert von | hat fotografiert | Objekt → Entität |
| aufgenommen in | ist Aufnahmeort von | Objekt → Ort |
| gezeigt in | zeigt | Objekt → Occurrence |

Der erste Ausdruck gilt vom Ausgangsdatensatz zum Ziel. Die Gegenrichtung erscheint, wenn dieselbe Verbindung vom Ziel aus gelesen wird. Die Beschränkung auf Typkombinationen verhindert hier zum Beispiel, dass eine Fotografie mit einem Ort als „fotografiert von“ verknüpft wird.

> **Bild vorgesehen: Editor eines Relationstyps.**
> Zeigen: Label, Gegenrichtungslabel sowie Auswahl von Quell- und Zieltyp. Alt-Text: „Relationstyp fotografiert von für Objekt zu Entität.“

## Erfassungsfelder konfigurieren

Unter **Konfiguration → Schemata** werden Felder angelegt. Für den Anfang reichen wenige Felder:

| Typ | Feld | Feldtyp | Einstellung |
|---|---|---|---|
| Objekt | Titel | Text | Pflichtfeld |
| Objekt | Entstehungsdatum | Datum | optional |
| Objekt | Fotograf:in | Relation | Zieltyp Entität, Relationstyp „fotografiert von“, wiederholbar wenn mehrere Personen möglich sind |
| Objekt | Aufnahmeort | Relation | Zieltyp Ort, Relationstyp „aufgenommen in“ |
| Objekt | Gezeigt in | Relation | Zieltyp Occurrence, Relationstyp „gezeigt in“, wiederholbar |
| Entität | Name | Text | Pflichtfeld |
| Ort | Name | Text | Pflichtfeld |
| Ort | Koordinaten | Geo | optional |
| Occurrence | Titel | Text | Pflichtfeld |

Beim Relationsfeld das zuvor angelegte Relationsvokabular auswählen und den festen Relationstyp setzen. Ein fest eingestellter Typ bewahrt die Bedeutung des Feldes: In „Fotograf:in“ wird immer „fotografiert von“ gespeichert.

> **Bild vorgesehen: Feldeditor für „Fotograf:in“.**
> Zeigen: Feldtyp Relation, Zieltyp Entität, Relationsvokabular und fester Relationstyp. Alt-Text: „Schemafeld Fotograf:in als Relation von einem Objekt zu einer Entität.“

Details zu Feldtypen, Mehrsprachigkeit und Suchoptionen stehen in der [Schema-Verwaltung](02_schema_verwaltung.md). Relationsfelder werden dort auch für den Suchindex beschrieben.

## Die ersten vier Datensätze erfassen

Lege zuerst die Kontextdatensätze an: Entität, Ort und Occurrence. Anschließend unter **Objekte** die Fotografie öffnen und Titel sowie Datum ausfüllen. In den Relationsfeldern nach „Marta Keller“, „Marktplatz Neustadt“ und „Winter in der Stadt“ suchen, jeweils den Treffer wählen und speichern.

Die Trefferliste erscheint erst nach mindestens zwei eingegebenen Zeichen. Ist ein Ziel noch nicht vorhanden, kann die Schnellerfassung den passenden Datensatz direkt aus dem Relationsfeld anlegen. Sie übernimmt einen fest vorgegebenen Ziel-Subtyp, falls das Feld einen solchen hat.

> **Bild vorgesehen: Objektformular mit den drei ausgefüllten Relationsfeldern.**
> Zeigen: die Fotografie und die Chips für Fotografin, Aufnahmeort und Ausstellung. Alt-Text: „Objektformular mit verknüpfter Entität, Ort und Occurrence.“

## Fachlich definierte und freie Beziehungen

Die Relationsfelder im Formular sind der richtige Ort für wiederkehrende fachliche Aussagen wie „Fotograf:in“ oder „Aufnahmeort“. Die **Beziehungen**-Karte eines gespeicherten Datensatzes zeigt denselben Graphen, fügt aber nur zusätzliche freie Beziehungen hinzu. Dort lässt sich zum Beispiel eine Fotografie mit einem Vorgang oder mit einem verwandten Objekt verknüpfen, ohne das Schema um ein dauerhaftes Feld zu erweitern.

Nicht dieselbe Verbindung an beiden Stellen eintragen. Eine doppelte Relation schafft keine zusätzliche Information.

> **Bild vorgesehen: Beziehungen-Karte eines gespeicherten Objekts.**
> Zeigen: vorhandene fachliche Beziehungen und die Aktion zum Anlegen einer zusätzlichen freien Beziehung. Alt-Text: „Beziehungen-Karte mit bestehenden Verknüpfungen eines Objekts.“

## Einen Vorgang hinzufügen

Vorgänge dokumentieren institutionelle Arbeit am Bestand, etwa Leihverkehr, Erwerbung oder Restaurierung. Sie sind keine öffentlichen Ereignisse. Für das Beispiel wird eine ausgehende Leihgabe angelegt.

1. Unter **Vorgänge** einen neuen Datensatz anlegen und den Typ **Leihgabe ausgehend** (`loan_out`) wählen.
2. ID-Nummer, Referenznummer, Beginn und Rückgabedatum eintragen. Zusätzliche Felder, etwa Versicherungswert oder Ansprechpartner:in, werden wie bei anderen Datensätzen im Schema für den Vorgangstyp konfiguriert.
3. Den Vorgang zunächst speichern. Danach in der Beziehungen-Karte das Objekt und die empfangende Institution verknüpfen.
4. Den Status auf **Aktiv** setzen, wenn die Leihgabe läuft. Den Sammlungsstatus des Objekts bei Bedarf bewusst auf **Ausgeliehen** setzen.
5. Nach Rückkehr **Abschließen** wählen. Katalon schlägt für `loan_out` den Objektstatus **Aktiv** vor. Der Vorschlag kann bestätigt oder ohne Statusänderung abgeschlossen werden.

> **Bild vorgesehen: Vorgangsformular „Leihgabe ausgehend“.**
> Zeigen: Typ, Status, Referenznummer, Beginn, Rückgabedatum und Beziehungen-Karte. Alt-Text: „Aktiver Vorgang Leihgabe ausgehend mit verknüpftem Objekt und empfangender Institution.“

Ein Objekt kann nicht in zwei gleichzeitig aktiven Vorgängen des Typs `loan_out` stehen. Andere Vorgangstypen und selbst angelegte Typen haben keine eingebauten Fachregeln. Der Abschluss ändert Objektstatus nie ungefragt.

Weitere Fälle stehen im [Cookbook](18_cookbook.md). Die Seite [Konzeptpapier Vorgänge](konzept-vorgaenge.md) erläutert den vollständigen Vorgangsrahmen und seine Grenzen.
