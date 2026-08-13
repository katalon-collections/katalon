---
type: Decision
title: Relationen — strukturierte Felder und freie Zusatzbeziehungen
description: Schema-Relationsfelder pflegen fachlich konfigurierte Beziehungen; die Beziehungen-Karte zeigt den Graphen und erfasst nur freie Zusatzbeziehungen.
tags: [relationen, datenmodell, ui, suche]
timestamp: 2026-08-13T00:00:00Z
---

# Kontext

Katalon speichert sowohl Relationsfeldwerte als auch über die Beziehungen-Karte
angelegte Kanten in derselben generischen `relations`-Tabelle. Wenn beide
Oberflächen dieselbe Kante unabhängig voneinander anlegen und bearbeiten,
kann ein Relationsfeld leer aussehen, obwohl die Karte bereits eine fachlich
gleichartige Beziehung zeigt. Das macht unklar, wo ein:e Katalogisierer:in
eine Beziehung pflegen soll.

Die Karte bleibt dennoch nötig: Sie zeigt auch eingehende Beziehungen,
unterstützt alle Haupttypkombinationen und erlaubt zusätzliche Kanten, die
kein Formularfeld vorhersehen kann. Umgekehrt brauchen fachlich definierte
Beziehungen wie Autor:in oder Aufnahmeort einen Platz im Formular, auch beim
Anlegen eines noch nicht gespeicherten Datensatzes.

# Entscheidung

Ein Schema-Relationsfeld ist der Bearbeitungsort für eine fachlich benannte,
strukturierte Beziehung. Es konfiguriert Zieltyp, optional Zielsubtyp und ein
Relationstyp-Vokabular. Es kann zusätzlich einen festen Relationstyp wählen;
ohne diese Festlegung wählt die katalogisierende Person einen zulässigen Typ
aus dem Vokabular.

Die Beziehungen-Karte bleibt die vollständige, bidirektionale Übersicht aller
Kanten. Feldgebundene Kanten zeigt sie mit Verweis auf ihr Formularfeld,
bearbeitet sie aber nicht selbst. Ihre Aktion lautet „Freie Beziehung zu
anderen Haupttypen hinzufügen“ und erzeugt nur zusätzliche, nicht
feldgebundene Kanten. Backend und UI verhindern, dass eine freie Anlage eine
Kombination erzeugt, die einem passenden feldgebundenen Relationsfeld
zugeordnet werden muss.

Für die Suche können Schema-Relationsfelder ausgewählte Zielmetadaten in
Elasticsearch einbetten. Bei einem festen Relationstyp berücksichtigt die
Projektion nur Kanten dieses Typs. Ohne festen Typ berücksichtigt sie alle
ausgehenden Kanten zum konfigurierten Zieltyp. Die generische Relationstabelle
und die Quellrecords bleiben dabei Source of Truth; der Suchindex ist nur die
Ein-Ebenen-Projektion.

# Begründung

Die Trennung gibt jeder Oberfläche eine eindeutige Aufgabe, ohne die
Flexibilität des generischen Graphen einzuschränken. Ein fester Relationstyp
verhindert, dass etwa die Geburtsdaten von Verleger:innen versehentlich in der
Autor:innen-Facette erscheinen. Die optionale Einstellung bewahrt aber den
Fall, dass eine Institution über mehrere Relationstypen verbunden sein kann
und ihre Gründungsdaten trotzdem gemeinsam facettierbar sein sollen.

# Konsequenzen

Die Admin-Oberfläche muss die Unterscheidung sichtbar machen und den
Relationstyp-Vokabularen weiterhin Gegenrichtungslabels und
Typkombinationsregeln entnehmen. Bestehende freie Kanten bleiben gültige
Graphdaten; für die Beta ist keine Datenmigration erforderlich. Änderungen an
Zieltyp, festem Typ oder eingebetteten Ziel-Feldern lösen einen Reindex des
Quelltyps aus, damit vorhandene Records die neue Suchprojektion erhalten.

# Citations

[1] GitHub Issue #213 "Denormalized Relation Fields in Elasticsearch Index"
[2] Session-Entscheidung 2026-08-13: Canonical dual relation UX
