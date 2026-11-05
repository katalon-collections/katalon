---
type: Decision
title: Optionale RDF-Projektion in Oxigraph
description: PostgreSQL bleibt Primärspeicher; Oxigraph hält eine optionale materialisierte RDF-Projektion. Query Builder und NL2SPARQL verwenden vorhandene Berechtigungs- und Secret-Infrastruktur.
tags: [rdf, sparql, knowledge-graph, architecture]
timestamp: 2026-09-05T20:00:00Z
---

# Kontext

Semantische Recherche benötigt eine Graphsicht auf die Sammlungsdaten. Der
operative Katalog soll dafür weder auf einen Triple Store umgestellt werden
noch SPARQL oder einen LLM-Dienst als Voraussetzung erhalten.

# Entscheidung

PostgreSQL bleibt der Primärspeicher. Eine optionale First-Party-Integration
materialisiert die öffentliche RDF-Projektion in Oxigraph. Sie verwendet die
vorhandene CIDOC-CRM-/LRMoo-/SKOS-Serialisierung und das etablierte Muster aus
Einzelrecord-Synchronisation, Rebuild und Reconciliation.

Oxigraph wurde für die Compose-Integration mit begrenztem Speicher gewählt.
Fuseki war eine Alternative; zusätzliche JVM- und Betriebskomponenten waren
für den festgelegten Umfang nicht erforderlich. Ein virtuelles SQL-zu-RDF-
Mapping wurde verworfen, weil sich die konfigurierbaren Felddefinitionen zur
Laufzeit ändern und die Projektionsinfrastruktur ohnehin benötigt wird.

Der SPARQL-Zugriff ist lesend und berechtigungsgebunden. Der
[Query Builder](sparql-query-builder.md) nutzt gespeicherte Abfragen und
optional NL2SPARQL. Generierte Abfragen werden vor manueller Ausführung geprüft;
LLM-Anbindung und Secrets verwenden die vorhandene Infrastruktur.

# Begründung und Grenzen

Die getrennte Projektion ermöglicht Graphabfragen, ohne die fachlichen
Schreibpfade vom Triple Store abhängig zu machen. Dafür entstehen zusätzlicher
Speicherbedarf und ein eigener Synchronisations-/Rebuild-Vertrag. RDF ist eine
abgeleitete Sicht, keine zweite Quelle für die Bearbeitung von Records.

[Subsysteme](subsystem-extensions-vs-plugin-architecture.md) bleiben reguläre
optionale Module, keine dynamisch installierten Plugins. Die
[Hierarchiesuche](hierarchische-suche-und-filterung.md) für Sammlungen und
Standorte nutzt PostgreSQL-CTEs und benötigt keinen Triple Store.

Karten-, Timeline- und weitere Research-Ansichten sowie neue öffentliche
Forschungsrollen sind durch diese Entscheidung nicht als implementiert zugesagt.

# Citations

[1] `backend/src/katalon/services/rdf_service.py`
[2] `backend/src/katalon/services/rdf_sync_service.py`
[3] `backend/src/katalon/integrations/oxigraph.py`
[4] `backend/src/katalon/api/v1/sparql.py`
[5] `frontend/admin/src/components/screens/ScreenSparql.tsx`
