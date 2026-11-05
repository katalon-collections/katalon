---
type: Decision
title: LIDO-DDB-Export über Mapping-Konfiguration, Normalisierung zur Renderzeit
description: DDB-Anforderungen an LIDO werden über Regel-Settings und institution_config abgebildet; Datumsgrenzen, Lizenz- und Normdaten-URIs entstehen beim Rendern, Relationen zweiter Stufe nur für per Mapping angeforderte Typen.
tags: [export, lido, ddb, oai-pmh, backend]
timestamp: 2026-10-16T12:00:00Z
---

# Kontext

Der Bestand Historische Bildpostkarten (DE-3066) soll per OAI-PMH/LIDO an die DDB.
Die DDB-Fehlerliste zum alten CA-Export verlangt Terminologie-URIs, vollständige
Rechteangaben je Digitalisat, Normdaten für Akteure/Orte, Orte über den Verlagssitz
und keine leeren oder doppelten Elemente. Nichts davon darf bestandsspezifisch im
Code stehen.

# Entscheidung

- Alles Bestandsspezifische liegt in `MappingSpec.settings`, `source_config`
  (`via` für eine zweite Relationsstufe) und `institution_config` (`require_media_license`,
  `allowed_license_uris`,
  `actor_id_fields`, `place_id_fields`, `actor_types`, `resource_rights_fallback`, …).
  Damit ist ein Mapping per YAML portabel.
- Datumsgrenzen (EDTF-lite → `earliestDate`/`latestDate`), Datumsanzeige,
  Lizenz-Schreibweise (nur über `allowed_license_uris`) und Normdaten-URIs werden beim Rendern berechnet, nicht im
  Export-Kontext gespeichert. Kein Index-Neuaufbau nötig, keine zweite
  Datumslogik (Validierung über `search_service.date_bounds`).
- Der Export-Kontext bekommt nur, was ohne DB nicht ableitbar ist: Vokabular-URIs
  (eine Query für alle Terme), Medien-Rechte/IIIF-Basis, Subtyp-Alternativkonzepte,
  `target_relations` für die von veröffentlichten Mappings verlangten `via`-Typen.
- Normdaten-URIs zentral in `integrations/authority_uris.py`, Lizenzen in
  `integrations/licenses.py`, LIDO-Terminologie als `LIDO_TERMS` im Builder.
- Leere Elemente werden nach dem Aufbau generisch entfernt, identische
  Geschwister dedupliziert, statt jede Stelle einzeln abzusichern.

- Kein Aggregator im Kern (Korrektur nach Review, 2026-10-16): Ein zuerst gebautes
  `profile: ddb` mit fest eingebauter Lizenzliste und DDB-Schreibweise als Default wurde
  durch neutrale Schalter ersetzt; die DDB-Werte stehen nur im Beispiel-Mapping.
  Grundsatz in `AGENTS.md` („Export: aggregator-agnostisch“).

# Begründung

Renderzeit-Normalisierung hält das Indexformat stabil und wirkt sofort auch auf
bestehende Indexkopien. Zweistufige Relationen pauschal zu laden hätte den Index
bei großen Sammlungen erneut aufgebläht (vgl. 46-MB-Dokumente); deshalb nur die
angeforderten Typen. Bekannte Schwäche: Ändert sich eine verknüpfte Entität oder
deren Sitz, bleibt die Indexkopie des Objekts bis zu dessen Reindex alt (gilt schon
für `target_values` erster Stufe).

Abgelehnt: eine DB-Spalte pro DDB-Option oder ein eigenes „DDB-Format“ — das wäre
ein zweiter LIDO-Renderer mit derselben Struktur.

# Citations

[1] backend/src/katalon/integrations/lido/builder.py
[2] backend/src/katalon/services/export_context_service.py
[3] backend/tests/fixtures/lido_ddb_mapping.yaml
[4] almanac/architecture/workflows/oai-and-export-mappings.md
