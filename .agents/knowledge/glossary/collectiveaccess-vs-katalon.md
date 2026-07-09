---
type: Reference
title: CollectiveAccess → Katalon Begriffe
description: Mapping der CollectiveAccess-Konzepte, die Karl kennt, auf ihre Katalon-Entsprechung.
tags: [glossar, collectiveaccess]
timestamp: 2026-07-09T00:00:00Z
---

# Warum

Karl kennt CollectiveAccess-Konzepte (dynamische Schemata, Vokabulare,
Entitätsrelationen). Dieses Glossar spart Kontext-Ballast: bei "wie in CollectiveAccess"
direkt die Entsprechung nachschlagen statt neu zu erklären.

| CollectiveAccess | Katalon | Unterschied |
|---|---|---|
| Intrinsic-/Attribute-System, eine zentrale Tabelle, XML-Konfiguration | `field_definitions` pro Primärtyp, DB-Tabellen getrennt | Siehe [Vier Bestandstypen](../decisions/vier-bestandstypen.md) und [Schema-Engine](../architecture/schema-engine.md) |
| PHP-Theme-Overlays für Customization | `docker-compose.override.yml` + Volume Mounts | Siehe [Docker-Customization-Strategie](../decisions/docker-customization-strategy.md) |
| Relationen an feste Feldkonfiguration gebunden | Relationen überall im Formular, gefiltert über Vokabular | Siehe [Relationen-Design](../decisions/relationen-design.md) |
| Kein eigener "Vorgang"-Typ (Leihverkehr etc. oft als Zusatzmodul) | Procedure als fünfter, separater Typ (nicht gleichrangig zu den vier Primärtypen) | Siehe Tabelle in [Vier Bestandstypen](../decisions/vier-bestandstypen.md) |

# Citations

[1] Root `AGENTS.md`, Abschnitt "User-Profil"
