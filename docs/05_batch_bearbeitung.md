# Katalon – Massenbearbeitung (Batch Editing)

## Übersicht

Die Massenbearbeitung erlaubt es, dieselbe Operation auf viele Datensätze gleichzeitig anzuwenden, ohne jeden Datensatz einzeln zu öffnen. Sie ist in allen Listenansichten verfügbar: Objekte, Entitäten, Orte, Occurrences und Vorgänge.

## Auswahl treffen

1. In der linken Spalte der Tabelle einzelne Datensätze auswählen.
2. Über die Checkbox im Tabellenkopf alle Datensätze der aktuellen Seite auswählen.
3. Wenn mehr als eine Seite an Treffern vorhanden ist, erscheint in der Aktionsleiste der Link **„Alle N Datensätze dieser Suche auswählen"**. Damit wird die Auswahl auf alle Treffer der aktuellen Filter/Suche seitenübergreifend erweitert.
4. Auf **Massenbearbeitung** klicken.

## Unterstützte Operationen

| Operation | Beschreibung |
|---|---|
| **Status setzen** | Ändert den Veröffentlichungsstatus aller ausgewählten Datensätze. |
| **Feld setzen** | Überschreibt ein einzelnes Metadatenfeld. |
| **Feld anhängen** | Fügt bei wiederholbaren Feldern einen Wert hinzu, ohne bestehende Werte zu löschen. |
| **Feld leeren** | Setzt das Feld auf einen leeren Zustand zurück. |
| **Relation hinzufügen** | Verknüpft alle ausgewählten Datensätze mit einem Ziel-Datensatz. |
| **Relation entfernen** | Entfernt eine bestehende Verknüpfung zu einem Ziel-Datensatz. |

## Sicherheitshinweis

Ab **50 ausgewählten Datensätzen** erscheint eine Warnung. Die Aktion kann nicht automatisch rückgängig gemacht werden. Wenn Sie einen Wiederherstellungspunkt benötigen, legen Sie vorher manuell Snapshots der betroffenen Datensätze an.

Jede Massenbearbeitung wird im **Audit-Log** pro Datensatz mit einer gemeinsamen `batch_job_id` protokolliert.

## Asynchrone Verarbeitung

Ab **100 ausgewählten Datensätzen** läuft die Operation im Hintergrund über Celery. Das Frontend zeigt die Task-ID an. Aktualisieren Sie die Liste, um das Ergebnis zu sehen.

Nach Abschluss erhält die Person, die die Massenbearbeitung gestartet hat, zusätzlich eine E-Mail mit den Ergebniszahlen, sofern der Betreiber den E-Mail-Versand eingerichtet hat.
