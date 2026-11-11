---
type: Decision
title: Orte bilden eine Hierarchie über places.parent_id; der Import legt Pfade als Ortskette an
status: accepted
date: 2026-11-08
---

# Kontext

Fundorte kommen als Pfade wie `Deutschland>Mecklenburg-Vorpommern>Schwerin>Lankower See`. `places` war flach:
der Pfad landete als ein Textlabel, "alle Objekte aus Mecklenburg-Vorpommern" ließ sich nicht abfragen.
Sammlungen und Lagerorte haben dafür `parent_id` und Unterbaumabfragen
(`hierarchische-suche-und-filterung.md`).

# Entscheidung

1. `places.parent_id` (Selbstreferenz, `ON DELETE SET NULL`), jede Ebene ist ein eigener Ortsdatensatz.
   Zyklus-Prüfung beim Speichern (422), Lösch-Guard mit `cascade`/`reparent` (409/400) wie bei Lagerorten.
2. Unterbaumabfrage zur Abfragezeit per rekursiver CTE (`place_service.get_place_subtree_ids`),
   keine ES-Denormalisierung. `GET /v1/objects?place_id=…&include_subplaces=true` (Standard) findet Objekte,
   die per Relation mit dem Ort oder einem Unterort verknüpft sind.
3. Import: Der Mapping-Eintrag des Ortstitels (`label`) trägt optional `path_separator`. Ohne ihn bleibt der
   Wert ein einzelner Name, es wird nichts geraten (Komma ist mehrdeutig, Reihenfolge nicht festgelegt).
   Mit ihm wird der Wert getrimmt zerlegt: letztes Element = Ort, davor die Vorfahren. Fehlende Ebenen entstehen
   als eigene Orte mit dem Pfad als ID-Nummer. Ebenen werden über Label unterhalb ihres Elternorts gefunden.
   Zeilen werden flach zuerst verarbeitet, damit eine eigene Zeile für eine Ebene (z. B. mit Geonames-ID) vor
   den Kindern existiert und keine Dublette entsteht. Zeilen ohne ID-Nummer erhalten den Pfad als ID-Nummer.

4. Portal: `GET /portal/v1/places/{id}` liefert `ancestors` (nur sichtbare Vorfahren, Wurzel zuerst) und `children`;
   `GET /portal/v1/places/{id}/object-ids` die sichtbaren Objekte des Orts samt Unterorten. Die Ortssuche
   (`type=place`) hängt jedem Treffer `place_path` an und liefert die Baum-Facette `place_parent` (Zähler =
   Orte im Unterbaum, nicht an die Suchanfrage angepasst). `meta_place_parent` filtert auf den Unterbaum; die IDs
   löst `place_service` aus einer In-Memory-Map aller sichtbaren Orte auf und gibt sie als ES-`ids`-Filter weiter.
   Der Index enthält weiterhin keine Vorfahren.

5. Objektsuche: Eine konfigurierte Relationsfacette (`PortalConfig.relation_facets`) mit `target_type: place`
   ist eine Baum-Facette (`kind: tree`) über die Ortshierarchie. Beschriftung und Relationstypen kommen aus der
   Konfiguration (kein Fundort-Sonderfall im Code). Zähler = verschiedene Objekte im Unterbaum, aus der Datenbank;
   eine Auswahl wird zu allen IDs des Unterbaums und über das vorhandene `facet_relid_<key>` gefiltert.

# Begründung

Gleiches Muster wie bei Sammlungen/Lagerorten, keine neue Tabelle, kein Reindex beim Umhängen. Echte Datensätze
je Ebene behalten Koordinaten, Normdaten und eigene Felder; ein hierarchisches Vokabular hätte das verloren.

# Konsequenzen

- Ein Ort ohne `parent_id` im PUT-Body verliert seinen Elternort (wie bei Lagerorten); die Admin-UI sendet das Feld immer.
- Die Ortsbaum-Map wird je Anfrage geladen (sinnvoll bis einige tausend Orte); darüber wäre ein Cache nötig.
- Die erweiterte Suche (`POST /search/advanced`) kennt die Orts-Baumfacette nicht.
- Bestehende flache Orte werden nicht automatisch umgehängt.

# Citations

- `backend/src/katalon/services/place_service.py`, `backend/src/katalon/services/place_path_import.py`
- `backend/src/katalon/workers/import_tasks.py`, `backend/src/katalon/api/v1/places.py`, `backend/migrations/versions/0086_places_parent_id.py`
