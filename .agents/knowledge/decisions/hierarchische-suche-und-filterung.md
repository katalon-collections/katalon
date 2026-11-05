---
type: Decision
title: Hierarchische Suche und Filterung – Pragmatische CTE-Query-Expansion statt ES-Denormalisierung
description: Transitive Hierarchieabfragen für Sammlungen (Portal/Suche) und Standorte (Admin) werden zur Abfragezeit über PostgreSQL-CTEs aufgelöst. Vokabular-Volltext-Expansion wird wegen Polyhierarchie- und Präzisionsproblemen (YAGNI) zurückgestellt.
tags: [suche, sammlungen, standortverwaltung, elasticsearch, postgresql, discovery]
timestamp: 2026-09-07T00:00:00Z
---

# Kontext

In Issue #362 wurde untersucht, ob und wie hierarchische Record-Typen (`VocabularyTerm`, `Collection`, `StorageLocation`) mit transitiver Unterbaum-Semantik durchsucht werden sollen (z. B. "Suche nach Oberbestand findet auch Artefakte in Teilbeständen", "Objekte in Gebäude A inkl. aller Räume und Regale").

Zur Diskussion standen:
1. Rekursive CTEs in PostgreSQL zur Abfragezeit
2. Closure-Tabellen in PostgreSQL
3. Denormalisierung von Vorfahren-IDs direkt in Elasticsearch-Dokumenten

# Entscheidung

1. **Ablehnung von Denormalisierung in Elasticsearch (Option 3):**
   Dokumente speichern keine rekursiven Vorfahren-IDs. Ein Umhängen (`reparent`) oder Umbenennen von Sammlungen oder Vokabularen würde unbegrenzte, kaskadierende Reindex-Jobs in Celery auslösen und das strikte Ein-Hop-Kaskaden-Prinzip (`almanac/decisions/search/inherited-fields-in-elasticsearch.md`) verletzen.
2. **Ablehnung von Closure-Tabellen (Option 2):**
   Bei den typischen Beständen (Dutzende Sammlungen, hunderte Lagerorte, Tiefe 2–5) bringen Closure-Tabellen gegenüber rekursiven CTEs keinen messbaren Geschwindigkeitsgewinn, erfordern aber zusätzliche Tabellen und Synchronisationslogik.
3. **Wahl von Query-Time CTEs (Option 1):**
   - **Sammlungen (Feature C, #366):** Die Portal-Suche expandiert `rel_collection` per CTE auf die Titel aller Kind-Sammlungen und nutzt einen `terms`-Filter in Elasticsearch. Die Detailansicht (`CollectionDetailPage`) und `/relations?include_subcollections=true` binden Teilsammlungen direkt ein.
   - **Standorte (Feature B, #367):** Standorte bleiben aus Portal und anonymer Suche ausgeschlossen. Die heutige interne Such-/Reconciliation-Registry umfasst alle sieben Kerntypen einschließlich Lagerorten; die frühere pauschale Aussage „nicht in Elasticsearch“ gilt nicht mehr. Die Admin-Lagerortverwaltung (`ScreenStorageLocation`) und die Objektliste (`/v1/objects?storage_location_id=...&include_sublocations=true`) bieten relationale Unterbaumabfragen über PostgreSQL.
4. **Zurückstellung von Vokabular-Volltext-Expansion (Teil A):**
   Monohierarchische Volltext-Expansion ("Verkehr" findet "Eisenbahn") führt bei komplexen Thesauri zu drastischem Präzisionsverlust und bricht bei Polyhierarchien. Echtes semantisches Schließen gehört in die Linked-Data/SPARQL-Schicht (#268), nicht in die Keyword-Suchmaschine.

# Begründung

- **Performance & Konsistenz:** Eine rekursive CTE auf 100 Sammlungen oder 500 Standorten benötigt im Schnitt < 2 ms und ist transaktionssicher ohne Reindex-Kosten.
- **YAGNI & Scope:** Provenienzorientierte Sammlungsbäume und physische Depot-Logistik sind reale Anforderungen von Kuratoren; semantische Volltexterweiterung für kontrollierte Vokabulare erzeugt in der Praxis Rauschen und Verwirrung.
