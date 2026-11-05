---
type: Decision
title: Export-Formate — Plugin-Registry statt hartcodiertem OAI-DC-Pfad
description: metadata_formats-Tabelle (analog authority_sources) mit MetadataFormat-ABC ersetzt fest verdrahtetes oai_dc-only-Rendering in oaipmh_service; OAI/Export liefern ein Format nur, wenn es tatsächlich gemappt ist.
tags: [export, oai-pmh, architektur, plugin]
timestamp: 2026-08-29T22:05:00+02:00
---

# Kontext

OAI-PMH rendere nur `oai_dc`, hartcodiert an vier Stellen in `oai.py`
(`prefix != "oai_dc"`) und mit DC-spezifischer XML-Bau-Logik direkt in
`oaipmh_service._hit_to_oai_record()`. Ohne Mapping griff ein
Heuristik-Fallback (rät Titel/Urheber/Beschreibung aus generischen
Feldnamen). `ExportMappingPanel` in `ScreenSchema.tsx` konfigurierte nur
dieses eine Format, pro Feld einzeln aufgeklappt; LIDO/METS-MODS waren
UI-Stubs ohne Backend. Anforderung: OAI-DC, LIDO, METS/MODS produktiv ab
Werk, spätere Formate (DataCite, MARC21XML) und institutionsspezifische
Sonderformate müssen ergänzbar/überschreibbar sein, ohne Core-Code zu
ändern.

# Entscheidung

`MetadataFormat`-ABC (`key`, `label`, `targets`, `schema_url`,
`namespace`, `render(hit, mappings) -> ET.Element`) plus
`metadata_format_service.py`, das `authority_service.py`s Muster 1:1
übernimmt: `_BUILTIN`-Dict mit immer verfügbaren Instanzen
(`OaiDcFormat`, `LidoFormat`, `MetsModsFormat`), eine
`metadata_formats`-Tabelle (`id`, `label`, `adapter_class`, `config`,
**kein** `is_enabled`) patcht Config auf einen bestehenden Key oder lädt
per `importlib` eine neue `adapter_class` für einen neuen Key.

`oai.py` prüft `metadataPrefix` gegen die Schnittmenge aus Registry-Keys
und `mapped_format_keys()` (Formate mit ≥1 aktivem Feld-Mapping) statt
gegen `"oai_dc"`; die ES-Query filtert zusätzlich auf
`mapped_record_types()`. Der Heuristik-Fallback in `oai_dc_format.py`
entfällt komplett — auch `oai_dc` liefert ohne Mapping nichts mehr
(Breaking Change für Bestandsinstallationen ohne konfiguriertes
Mapping, bewusst in Kauf genommen).

Neuer Export-Bereich (`ScreenExport.tsx`) ersetzt `ExportMappingPanel`:
ein Dumps-Tab (CSV/JSON direkt aus Postgres, XML über dieselbe
Registry+ES-Pipeline wie OAI) und ein Mapping-Tab (Tabelle Felder ×
Formate statt Konfiguration pro Feld).

**Bekannte Lücke:** Registry-Cache ist prozesslebenslang, es gibt (anders
als bei `authority_service`) noch keinen Endpoint, der
`invalidate_cache()` nach einem `metadata_formats`-Write auslöst —
Custom-Format hinzufügen/Override ändern braucht aktuell einen
`api`-Container-Neustart.

# Begründung

Ohne Registry hätte jedes neue Format erneut vier Call-Sites in `oai.py`
plus DC-spezifische Sonderfälle in `oaipmh_service.py` angefasst — genau
das Muster, das `authority_service.py` für Normdaten-Adapter schon gelöst
hatte. Wiederverwendung des bewährten Musters statt zweiter
Sonderlösung. Gating auf "nur wenn gemappt" (statt Toggle-UI) vermeidet
leere/halbgare XML-Blöcke für Harvester und hält die Konfigurationsfläche
klein (eine Entscheidung — Mapping pflegen — statt zwei: Mapping pflegen
+ Format aktivieren).

# Citations

[1] `backend/src/katalon/services/authority_service.py` (Vorbild-Pattern)
[2] `backend/src/katalon/integrations/metadata_format.py`,
    `oai_dc_format.py`, `lido_format.py`, `mets_mods_format.py`
[3] `backend/src/katalon/services/metadata_format_service.py`
[4] `backend/migrations/versions/0045_metadata_formats.py`
[5] `almanac/architecture/workflows/oai-and-export-mappings.md`
