---
type: Decision
title: DatabaseCommitMiddleware — Transaktions-Commit vor HTTP-Response-Übertragung
description: Verhindert Read-after-Write-Race-Conditions zwischen Frontend und Backend, indem Datenbank-Commits und after_commit-Hooks vor dem Senden von 2xx-HTTP-Headern abgeschlossen werden.
tags: [database, fastapi, asgi, concurrency, read-after-write]
timestamp: 2026-09-19T20:00:00Z
---

# Kontext

In modernen SPAs (React Admin-UI) folgt auf schreibende Operationen (z. B. Anlegen eines Nutzers, Subtyps, Banners oder Vokabularterms) unmittelbar ein `GET`-Request zur Listenaktualisierung.

Bislang verließ sich Katalon auf den FastAPI-Standardmechanismus in `get_db()`:
```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            await run_after_commit_hooks(session)
...
```
In FastAPI / Starlette laufen Dependency-Teardowns (`finally` / Code nach `yield`) jedoch im ASGI-Stack erst ab, **nachdem** die HTTP-Response über den Socket an den Client ausgeliefert wurde (`await response(scope, receive, send)`).

Dadurch entstand eine systematische Race-Condition:
1. Client sendet `POST /v1/users`.
2. Handler führt `db.add(user)`, `db.flush()` aus und liefert die Response zurück.
3. Server sendet HTTP `201 Created` an den Browser.
4. Der Browser empfängt `201` und schickt millisekundenschnell `GET /v1/users`.
5. Auf dem Server läuft erst jetzt das Teardown von Request 1 (`await session.commit()`).
6. Wenn Request 2 in PostgreSQL ankommt, bevor der Commit von Request 1 abgeschlossen ist, sieht der lesende Request den neuen Eintrag noch nicht.
7. Der neu angelegte Datensatz fehlte in der Liste; erst nach manuellem Refresh (F5) tauchte er auf.

# Entscheidung

Einführung einer dedizierten ASGI-Middleware (`DatabaseCommitMiddleware`) in `backend/src/katalon/main.py` und eines request-bezogenen Session-Holders in `backend/src/katalon/database.py`.

1. **`SessionHolder` & `ContextVar`**:
   `DatabaseCommitMiddleware` initialisiert zu Beginn jedes HTTP-Requests einen `SessionHolder` in einer `ContextVar`.
   In `get_db()` registriert sich die aktive `AsyncSession` an diesem Holder (`register_current_session(session)`). Durch den Objekt-Container bleibt die Referenz auch über verschachtelte `BaseHTTPMiddleware`-Task-Grenzen hinweg persistent.

2. **ASGI-Response-Interception**:
   Die Middleware fängt die ASGI-Nachricht `http.response.start` ab.
   Für schreibende HTTP-Methoden (`POST`, `PUT`, `PATCH`, `DELETE`) und erfolgreiche Status-Codes (`status < 400`) wird `commit_current_session()` aufgerufen:
   - `await session.commit()` wird ausgeführt und abgewartet.
   - `await run_after_commit_hooks(session)` stößt etwaige Celery-Tasks an.
   Erst danach wird `http.response.start` an den ASGI-Sendekanal übergeben und die Response zum Client übertragen. Lesende Methoden (`GET`, `HEAD`, `OPTIONS`) sowie Streaming-Responses (z. B. CSV/JSON-Export) bleiben unberührt, wodurch nebenläufige Commit-Operationen auf aktiven Query-Streams ausgeschlossen sind.

3. **Frontend Silent-Refetch**:
   In `ScreenUsers.tsx` wurde zusätzlich das Flackern behoben: `loadUsers(silent = true)` setzt bei Refetches nach Mutationen nicht mehr `loading = true`, wodurch die Tabelle gemountet bleibt und die optimistische State-Aktualisierung nahtlos mit den verifizierten Serverdaten synchronisiert wird.

# Begründung

- **Zentral statt an jedem Endpoint:** Durch die ASGI-Middleware muss nicht jeder einzelne CRUD-Endpunkt manuell `await db.commit()` aufrufen. Für die von der Middleware erfassten erfolgreichen schreibenden HTTP-Requests gilt damit derselbe Commit-Zeitpunkt.
- **Durable Consistency:** Der Client erhält `200`/`201` erst, wenn die Transaktion in PostgreSQL tatsächlich committet ist. Ein anschließender Datenbank-Read kann damit den bereits bestätigten Transaktionsstand lesen; abgeleitete Suchindizes haben weiterhin ihren eigenen Aktualisierungsablauf.
- **Idempotenz:** Sowohl `session.in_transaction()`-Prüfungen als auch das Poppen der Hooks in `run_after_commit_hooks` stellen sicher, dass mehrfache Aufrufe (Middleware + nachfolgendes Dependency-Unwinding) sicher und idempotent sind.
- **Fehlerbehandlung:** Bei Fehlern (`status >= 400` oder Exceptions) greift wie gewohnt das `rollback()` im Exception-Handler bzw. `get_db()`.

# Citations

- `backend/src/katalon/main.py` — `DatabaseCommitMiddleware`
- `backend/src/katalon/database.py` — `SessionHolder`, `register_current_session`, `commit_current_session`, `get_db`
- `backend/tests/test_database_commit_middleware.py` — Unit-Tests zur Commit-Ausführung vor Response-Delivery
- `frontend/admin/src/components/screens/ScreenUsers.tsx` — `loadUsers(silent)`
