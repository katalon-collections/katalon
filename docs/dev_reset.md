# Dev: Datenbank und Suchindex zurücksetzen

## Kompletter Reset (DB + ES)

Alles wegwerfen und neu aufsetzen – sinnvoll nach größeren Schemaänderungen oder für einen sauberen Teststand.

```bash
# Container + Volumes löschen
docker compose down -v

# Neu starten
docker compose up -d

# Migrationen einspielen
docker compose exec api uv run alembic upgrade head

# Seed-Daten laden (optional)
docker compose exec api uv run python scripts/seed_ics_demo.py
```

Der ES-Index `katalon_records` wird beim ersten API-Start automatisch durch `ensure_index()` angelegt.

---

## Nur Datenbank zurücksetzen (Schema + Daten)

```bash
docker compose stop api worker
docker compose exec db psql -U katalon -c "DROP DATABASE katalon; CREATE DATABASE katalon;"
docker compose start api worker
docker compose exec api uv run alembic upgrade head
```

---

## Nur Daten löschen (Schema bleibt)

Alle Datensätze entfernen, Tabellenstruktur und Konfiguration behalten:

```bash
docker compose exec db psql -U katalon -d katalon -c "
TRUNCATE objects, entities, places, occurrences,
         media, relations, audit_log, record_snapshots CASCADE;
"
```

Anschließend ES-Index leeren (siehe unten).

---

## Nur Elasticsearch zurücksetzen

### Index löschen und neu anlegen

```bash
# Index löschen
curl -X DELETE http://localhost:9200/katalon_records

# Index wird beim nächsten API-Request automatisch neu erstellt (ensure_index())
# Oder API neu starten:
docker compose restart api
```

### Bestehenden Index neu befüllen (aus DB)

Alle Typen:

```bash
curl -X POST http://localhost:8000/v1/search/reindex
```

Einzelner Typ (`object`, `entity`, `place`, `occurrence`):

```bash
curl -X POST http://localhost:8000/v1/search/reindex/object
```

Der Reindex läuft als Celery-Task im Hintergrund. Status im Worker-Log:

```bash
docker compose logs -f worker
```

---

## Seed-Daten

Das Demoscript liegt unter `backend/scripts/seed_ics_demo.py`:

```bash
docker compose exec api uv run python scripts/seed_ics_demo.py
```
