---
type: Reference
title: CollectiveAccess-Begriffe im Katalon-Kontext
description: Orientierung für Personen mit CollectiveAccess-Erfahrung; keine Funktions- oder Architekturbewertung des anderen Systems.
tags: [glossar, collectiveaccess]
timestamp: 2026-07-09T00:00:00Z
---

# Orientierung

Die Tabelle benennt Katalon-Anschlussstellen für vertraute Themen. Sie behauptet
keine vollständige Gleichheit der Datenmodelle oder Funktionsumfänge.

| Thema | Katalon-Anschlussstelle |
|---|---|
| Konfigurierbare Metadaten | `field_definitions` und typbezogene JSONB-Metadaten; [Schema-Engine](../architecture/schema-engine.md) |
| Anpassungen einer Installation | Compose-Overrides, Mounts und Portal-Themes; [Docker-Customization](../decisions/docker-customization-strategy.md) |
| Beziehungen zwischen Datensätzen | Schema-Relationsfelder und freie Zusatzbeziehungen; [Relationsvertrag](../decisions/relationen-strukturierte-und-freie-beziehungen.md) |
| Leihverkehr, Erwerbung, Restaurierung | Procedure als einer der [sieben Kerntypen](../decisions/vier-bestandstypen.md) |

# Citations

[1] `docs/01_datenmodell.md`
[2] `docs/04_anpassungen.md`
[3] `almanac/concepts/domain/procedures.md`
