# Katalon – Architekturelle Bewertung

*Stand: 2026-05-16. Basiert auf vollständiger Codebase-Analyse.*

---

## Gesamturteil

Die Kernentscheidungen sind korrekt und nicht trivial. Das Datenmodell und die Erweiterungspunkte (Schema-Engine, Relationen, Authority-Plugins) spiegeln echtes Domänenwissen wider. Die Schwächen liegen überwiegend in der Betriebsschicht — ES-Kopplung, fehlende FK-Constraints, Copy-Paste über vier Typ-Module — nicht in der Grundstruktur. Keine der Schwächen erfordert architektonisches Umbauen.

**Status:** Solide Grundlage, umsetzbar bis zur Produktion ohne strukturelle Neuentwicklung.

---

## Was gut gelöst ist

### JSONB-Metadaten + `field_definitions` als Schema-Engine

Die richtige Wahl für den GLAM-Sektor. Jede Institution hat andere Metadatenfelder. Die Constraints liegen in der Applikationsschicht (`schema_service.validate_metadata()`), nicht in der DB — das gibt Flexibilität ohne das Schema jedes Mal migrieren zu müssen. Der Trade-off (kein DB-Level-Constraint, GIN-Index statt typisierter Spalten) ist bei dieser Skalierung angemessen.

### Vier separate Tabellen statt einer generischen `records`-Tabelle

Explizit entschieden und richtig. Eine polymorphe Tabelle klingt elegant, wird aber zur Wartungsfalle:
- Places brauchen PostGIS-Geometrie
- Objects brauchen Media-Verknüpfung
- Entities haben andere Suchsemantik

Die Codeduplizierung über die vier CRUD-Module ist der Preis — er ist sichtbar, aber navigierbar. Die Alternative wäre eine Tabelle mit 40+ nullable Spalten.

### Generische `relations`-Tabelle

```sql
relations (from_type, from_id, to_type, to_id, relation_type, metadata JSONB)
```

Erlaubt beliebige Verknüpfungen aller vier Typen untereinander, ohne kombinatorische Explosion an Junction-Tabellen. `relation_type` referenziert ein Vokabular-Term. `metadata JSONB` auf der Relation selbst ist weitsichtig — ermöglicht z. B. Rollen ("Auftraggeber", "Dargestellt") direkt auf der Beziehung.

### Authority-Plugin-System

Die abstrakte Basisklasse `AuthoritySource(ABC)` mit `search()` / `fetch()`, DB-Registry und Lazy Loading ist sauber erweiterbar. Sechs Adapter bereits implementiert; ein siebter berührt genau eine Datei. Dieses Muster verdient seine Abstraktion.

### IIIF als First-Class-Feature

Manifeste entstehen als Teil des Media-Workflows, nicht als nachträglicher Export. `iiif_manifest`-Spalte auf `MediaFile`, Portal-Viewer verdrahtet. Noch nicht End-to-End (Cantaloupe-Tiles fehlen), aber die Grundlage ist am richtigen Ort.

### Audit Log + Snapshots als getrennte Concerns

- `audit_log`: feld-genaues Diff für Compliance und Nachvollziehbarkeit
- `record_snapshots`: vollständige JSON-Snapshots für nutzer-seitige Versionierung

Unterschiedliche Use Cases, richtig getrennt gehalten.

---

## Reale Schwächen

### Elasticsearch-Kopplung ohne Sicherheitsnetz

ES ist primärer Suchindex, Records leben aber in Postgres. Wenn ES und Postgres auseinanderlaufen — und das passiert (Downtime, fehlgeschlagene Indexierungen) — gibt es keine automatische Reconciliation. Der Massen-Reindex-Task ist geplant aber nicht gebaut.

**Risiko:** Produktionsinstanzen mit divergentem Suchindex, die niemand bemerkt bis ein Nutzer ein Objekt nicht findet.

**Mitigation:** Hintergrund-Job, der Postgres- und ES-Record-Counts täglich vergleicht, plus ein Admin-UI-Button "Vollständig reindexieren".

### Vier Tabellen = viermal alles

Jedes neue querschnittliche Feature erfordert vier Modelländerungen, vier Migrationen, vier Endpoint-Änderungen. Die CRUD-Module (`objects.py`, `entities.py`, `places.py`, `occurrences.py`) sind heute bereits nahezu identisch. Ein generischer CRUD-Factory-Mixin oder eine Basis-Klasse würde das reduzieren, ohne die Tabellenstruktur anzutasten.

### Keine FK-Constraints auf Relationen

`from_id` und `to_id` in der `relations`-Tabelle sind plain UUIDs, keine Foreign Keys. Wird ein Objekt gelöscht, bleiben Relationen als Orphans erhalten — kein Cascade, kein automatischer Cleanup. Das akkumuliert sich still.

**Fix:** `ON DELETE CASCADE`-Trigger oder ein periodischer Cleanup-Job.

### Celery-Tasks mit `asyncio.run()` in synchronen Tasks

```python
@celery_app.task(...)
def generate_iiif_tiles(self, media_file_id: str):
    return asyncio.run(_process(...))  # neuer Event-Loop pro Task
```

Funktioniert, ist aber ineffizient: jeder Task spinnt einen neuen Event-Loop hoch, öffnet einen neuen DB-Connection-Pool. Kein Problem für geringe Last. Unter höherer Last (Batch-Import, Massen-Reindex) wird das zur Ressourcen-Verschwendung.

**Mitigation bei Bedarf:** Celery 5 + `asyncio` Task-Klasse oder Worker auf gevent-Pool umstellen.

### JWT in localStorage

Admin speichert Token in `localStorage` — XSS-zugänglich. Für internes Admin-Tooling akzeptabler Trade-off. Sollte das Portal je authentifizierte Nutzeraccounts bekommen, muss auf `httpOnly`-Cookies gewechselt werden.

---

## Was fehlt, aber bewusst so ist

**Kein Multi-Tenancy** — eine Instanz pro Institution. Richtige Entscheidung für das MVP; SaaS-Multi-Tenancy hätte jede Datenmodelldiskussion kompliziert.

**Kein Event Sourcing / CQRS** — klassisches MVC mit dünner Service-Schicht. Richtig bei dieser Skalierung. Das Audit-Log gibt die nötige Historie ohne den Overhead.

**Kein API-Versioning jenseits `/v1/`** — solange keine externen Integrationen aktiv sind, kein Problem. Vor dem ersten stabilen Release dokumentieren, wie Breaking Changes kommuniziert werden.

---

## Zukunftssicherheit

| Aspekt | Bewertung |
|---|---|
| Metadaten-Flexibilität (neue Felder) | ✅ Kein Schema-Change nötig |
| Neue Authority-Quellen | ✅ Nur ein neuer Adapter |
| Fünfter Primärtyp | ⚠️ Neue Tabelle + 4 Module |
| Höhere Last (10k+ Records) | ⚠️ GIN-Index-Performance prüfen, ES-Shard-Strategie |
| Mehrere Institutionen (SaaS) | ❌ Erfordert architektonischen Umbau (Row-Level-Security oder Schema-per-Tenant) |
| Wechsel des Suchindex (z. B. OpenSearch) | ✅ Nur `integrations/elasticsearch.py` + `search_service.py` |
| Wechsel des Bildservers | ✅ Nur `integrations/cantaloupe.py` |

---

## Wichtigste kurzfristige Maßnahmen

1. **ES-Reconciliation-Job** bauen (nicht nur bei Fehler loggen, sondern aktiv angleichen)
2. **Generischer CRUD-Mixin** für die vier Typ-Module (Maintainability)
3. **Orphan-Cleanup für Relationen** (Trigger oder Job)

Diese drei Maßnahmen beheben die einzigen echten strukturellen Risiken. Alles andere sind Feature-Lücken oder Betriebsthemen, kein Architektur-Problem.
