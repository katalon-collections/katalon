# Katalon – Weg zum MVP

*Stand: 2026-05-16. Projektstand: Late Alpha / Pre-Beta.*

---

## Aktueller Status

Der Implementierungsplan definiert **Phasen 0–6 als MVP**. Diese Phasen sind technisch abgeschlossen, aber mit Lücken die für einen produktiven Einsatz relevant sind.

```
Phase 0  Infra            ✅
Phase 1  Core-DB          ✅
Phase 2  Schema-Engine    ✅
Phase 3  CRUD 4 Typen     ✅
Phase 4  Auth + Audit     ✅
Phase 5  Media / IIIF     ⚠️  Media OK, IIIF-Tiles nicht End-to-End
Phase 6  Admin-UI         ⚠️  Grundgerüst OK, 3 Screens unvollständig
```

---

## Was MVP bedeutet

Ein MVP für Katalon ist eine Instanz, mit der eine reale Institution:
- Objekte, Entitäten, Orte, Werke erfassen und verwalten kann
- Bilder hochladen und im Portal mit IIIF-Viewer anzeigen kann
- Benutzerkonten mit Rollen verwalten kann
- Das Public-Portal für die Öffentlichkeit freischalten kann

Das ist heute **fast** möglich. Die folgenden Lücken verhindern es.

---

## MVP-Blocker (Pflicht vor Release)

### 1. IIIF / Cantaloupe End-to-End

**Problem:** Bilder werden hochgeladen und als `ready` markiert, aber Cantaloupe generiert keine echten IIIF-Tiles. Der IIIF-Viewer im Portal fällt auf das Fallback-`<img>`-Tag zurück.

**Was fehlt:**
- Cantaloupe muss die hochgeladenen Dateien lesen können (Volume-Mount korrekt verdrahten)
- `fetch_image_info()` in `integrations/cantaloupe.py` muss eine funktionierende Antwort zurückgeben
- IIIF-Manifest-URL muss auf den öffentlichen Cantaloupe-Endpunkt zeigen

**Dateien:** `backend/src/katalon/integrations/cantaloupe.py`, `docker-compose.yml` (Volume-Konfiguration), `backend/src/katalon/workers/media_tasks.py`

**Aufwand:** ~1 Tag (vor allem Infrastruktur, wenig Code)

---

### 2. Benutzer-Verwaltungs-Screen

**Problem:** `ScreenUsers.tsx` zeigt nur API-Key-Verwaltung. Es gibt keinen Weg, über die UI Benutzerkonten anzulegen, Rollen zu ändern oder Accounts zu deaktivieren. Institutionen müssen über die CLI oder direkt in der DB arbeiten.

**Was fehlt:**
- Benutzerliste mit Rollen anzeigen
- Benutzer erstellen / Passwort setzen
- Rolle ändern (admin / editor / viewer)
- Account deaktivieren (`is_active = false`)

**Dateien:** `frontend/admin/src/components/screens/ScreenUsers.tsx`, `backend/src/katalon/api/v1/users.py` (Endpoints prüfen ob vorhanden)

**Aufwand:** ~1 Tag

---

### 3. Rate Limiting aktivieren

**Problem:** `slowapi` ist eingebunden und konfiguriert, aber **keine einzige Route ist dekoriert**. Öffentliche Endpunkte sind ohne Begrenzung:

```python
# main.py – Limiter konfiguriert, aber nie verwendet
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
```

Vor einem öffentlichen Release müssen mindestens diese Endpunkte begrenzt werden:
- `GET /v1/search` — teuer, öffentlich
- `GET /v1/oai` — teuer, öffentlich, für Harvester-Bots
- `GET /v1/authorities/search` — ruft externe APIs auf

**Dateien:** `backend/src/katalon/api/v1/search.py`, `backend/src/katalon/api/v1/oai.py`, `backend/src/katalon/api/v1/authority.py`

**Aufwand:** ~2 Stunden

---

## Wichtige Verbesserungen (sollten ins MVP, kein Blocker)

### Elasticsearch-Reconciliation

Wenn ES beim Speichern nicht erreichbar ist, wird der Fehler geloggt (seit letztem Fix), aber der Record fehlt im Suchindex. Ohne Reconciliation kann eine Institution Datensätze erfassen, die nie gefunden werden.

**Mitigation kurzfristig:** Admin-Button "Suchindex neu aufbauen" (triggert Celery-Task `reindex_all`)
**Mitigation langfristig:** Hintergrund-Job der Postgres/ES-Counts täglich vergleicht

**Aufwand:** ~0.5 Tag für den Admin-Button (Task existiert bereits), ~2 Tage für den Reconciliation-Job

---

### OAI-PMH Pagination (ResumptionToken)

Ohne ResumptionToken bricht ein Harvester bei einer Collection mit mehr als ~100 Objekten ab oder bekommt unvollständige Daten. Für Bibliotheken und Archive ist OAI-PMH oft das zentrale Austauschformat.

**Was fehlt:** `ListRecords` und `ListIdentifiers` müssen bei großen Trefferzahlen ein `<resumptionToken>` zurückgeben, der Offset + Filter enkodiert.

**Dateien:** `backend/src/katalon/api/v1/oai.py`, `backend/src/katalon/services/oaipmh_service.py`

**Aufwand:** ~1 Tag

---

### Produktions-Secrets

`docker-compose.prod.yml` enthält noch `dev-secret-key` als JWT-Secret-Fallback. Vor Release muss ein Mechanismus sicherstellen, dass kein Default-Secret in Produktion landet (z. B. Startup-Check der abbricht wenn `SECRET_KEY == "dev-secret-key"`).

**Aufwand:** ~1 Stunde

---

## Nicht im MVP (Post-Release)

| Feature | Warum zurückgestellt |
|---|---|
| Importer-Wizard (Phase 10) | Daten können via API importiert werden; UI ist Nice-to-have |
| Batch-Medienimport (Phase 10.1) | Single-Upload reicht für Pilotbetrieb |
| Snapshot-UI im Admin (Phase 7) | Backend vorhanden; UI ist Komfort-Feature |
| OAI-Sets-Verwaltung | Grundfunktion ohne Sets nutzbar |
| Authority-Autocomplete im Formular | Felder funktionieren ohne Autocomplete |
| „Zurück zur Suche" im Portal | UX-Verbesserung, kein Blocker |
| Perf-Tests (locust) | Für Pilotbetrieb mit kleiner Nutzerzahl nicht kritisch |

---

## Geschätzte Restarbeit bis MVP-Release

| Aufgabe | Aufwand |
|---|---|
| Cantaloupe End-to-End verdrahten | ~1 Tag |
| ScreenUsers: User-CRUD | ~1 Tag |
| Rate Limiting aktivieren | ~2 Stunden |
| Produktions-Secret-Check | ~1 Stunde |
| OAI-PMH ResumptionToken | ~1 Tag |
| ES-Reindex-Button im Admin | ~0.5 Tag |
| **Gesamt** | **~4–5 Tage** |

---

## Empfohlene Reihenfolge

```
1. Cantaloupe verdrahten          ← größter sichtbarer Effekt
2. ScreenUsers: User-CRUD         ← Voraussetzung für echten Betrieb
3. Rate Limiting                  ← 2 Stunden, kein Grund zu warten
4. Secret-Check beim Start        ← 1 Stunde, Sicherheits-Pflicht
5. ES-Reindex-Button              ← operativer Sicherheitsnetz
6. OAI-PMH Pagination             ← für Bibliotheks-Integrationen
```

Nach diesen sechs Schritten ist Katalon bereit für einen Pilotbetrieb mit einer realen Institution.
