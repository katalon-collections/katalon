# Cookbook: erweiterte Anwendungsfälle

Die Beispiele bauen auf dem [Walkthrough zur eigenen Sammlung](17_walkthrough_eigene_sammlung.md) auf. Jedes Rezept beschreibt eine kleine, wiederverwendbare Konfiguration.

## Mehrere Personen an einer Fotografie

Eine Fotografie kann eine Fotografin, einen Auftraggeber und eine abgebildete Person haben. Lege im Relationsvokabular dafür getrennte Typen an, etwa „fotografiert von“, „beauftragt von“ und „zeigt“. Lege dann entweder je ein Relationsfeld an, wenn die Rollen dauerhaft zum Formular gehören, oder nutze für seltene Einzelfälle die Beziehungen-Karte.

Das Feld „Fotograf:in“ darf wiederholbar sein. Jede ausgewählte Entität wird mit demselben Relationstyp verknüpft. Für verschiedene Rollen braucht es verschiedene Relationstypen, keine Notiz im Personennamen.

> **Bild vorgesehen: Relationsvokabular mit drei Rollen.**
> Zeigen: unterschiedliche Relationstypen mit Hin- und Gegenrichtungen. Alt-Text: „Relationsvokabular für Fotografin, Auftraggeber und abgebildete Person.“

## Interne Angaben getrennt von öffentlichen Metadaten halten

Für Restaurierungsnotizen, interne Kontaktangaben oder noch ungeprüfte Provenienz ein eigenes Schemafeld anlegen und **Öffentlich über APIs ausgeben** deaktivieren. Der Wert bleibt in der Admin-UI sichtbar, wird aber nicht an das Portal, anonyme API-Antworten, OAI-PMH oder IIIF ausgegeben.

Die Darstellung auf einer Portal-Detailseite ist keine Zugriffskontrolle. Die Option zur öffentlichen Ausgabe entscheidet darüber, ob ein Wert den geschützten Bereich überhaupt verlässt.

> **Bild vorgesehen: Erweiterte Optionen eines Schemafelds.**
> Zeigen: deaktivierte öffentliche API-Ausgabe und den erklärenden Hinweis. Alt-Text: „Internes Schemafeld, das nicht über öffentliche APIs ausgegeben wird.“

## Unscharfe Datierung erfassen

Das Datumsfeld speichert konkrete ISO-Angaben wie `1923`, `1923-05` oder `1923-05-14`. Für „um 1920“ oder einen Zeitraum kein Freitextdatum erfinden. Lege eine Feldgruppe `datierung` an, darin ein Datumsfeld und ein Vokabularfeld `typ` mit Werten wie `exakt`, `circa`, `vor`, `nach` und `undatiert`. Für einen Zeitraum sind zwei Datumsfelder `von` und `bis` klarer.

Die komplette Konfiguration, auch für BCE-Daten, steht in der [Schema-Verwaltung](02_schema_verwaltung.md#cookbook-datierungstyp-unscharfequalifizierte-datierung).

## Erwerbung und Restaurierung als Vorgänge

Für einen Erwerbungsvorgang ein Objekt zunächst mit Sammlungsstatus **In Bearbeitung** anlegen. Im Vorgangstyp `acquisition` können Felder wie Erwerbungsart, Kaufpreis oder Beschlussnummer angelegt werden. Beim Abschluss schlägt Katalon den Objektstatus **Aktiv** vor.

Bei einer Restaurierung (`conservation`) werden Befund, Maßnahmen und Werkstatt als Felder und Beziehungen erfasst. Mehrere Restaurierungen am selben Objekt sind möglich. Beim Abschluss schlägt Katalon für diesen Typ keinen Sammlungsstatus vor, weil eine Restaurierung nicht automatisch über die Verfügbarkeit entscheidet.

> **Bild vorgesehen: Schema für den Vorgangstyp Restaurierung.**
> Zeigen: subtypspezifische Felder Befund und Maßnahme sowie Relation zur Werkstatt. Alt-Text: „Vorgangsschema für eine Restaurierung mit eigenen Metadatenfeldern.“

## Eigene Vorgangstypen für lokale Abläufe

Ein Haus kann etwa `condition_check` für eine Zustandsprüfung anlegen. Unter **Konfiguration → Subtypen** einen Vorgangstyp mit deutschem und englischem Label erstellen; danach im Schema nur für diesen Typ Felder wie Prüfdatum, Ergebnis und nächste Prüfung anlegen.

Eigene Vorgangstypen haben keinen automatischen Sammlungsstatus und keine Sperre gegen parallele Vorgänge. Falls der Ablauf eine Regel braucht, muss sie fachlich durch das Team organisiert oder später gezielt als Produktfunktion ergänzt werden.

## Tabellenimport ohne Datenverlust vorbereiten

Vor einem Import die Ziel-Felder und Vokabulare anlegen. Im Importer Spalten zuordnen, die Vorschau lesen und immer einen **Probelauf** ausführen. Erst wenn Pflichtfelder, Trennzeichen und Transformationen stimmen, wird importiert.

Für ein Feld mit mehreren Farbwerten in einer Zelle ist die Transformation `split` mit `;` passend. Für ein kontrolliertes Vokabular zuerst die Terme importieren und anschließend `vocab_map` verwenden. Beziehungen entstehen nicht durch einen Namen in einer CSV-Spalte; dafür braucht es eine passende Auflösungs- oder Anlege-Regel im Importablauf.

> **Bild vorgesehen: Importer im Probelauf mit Mapping-Tabelle.**
> Zeigen: Quellspalte, Zielfeld, Transformation und Fehler- oder Vorschau-Bereich. Alt-Text: „CSV-Import im Probelauf mit Feldzuordnung und Transformationen.“

Die einzelnen Import-Schritte stehen unter [Metadaten- und Medienimport](03_csv_import.md).
