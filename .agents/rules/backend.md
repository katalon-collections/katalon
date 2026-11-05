# Backend Coding Rules (Python / FastAPI)

Gilt für `backend/`. Extrahiert aus `backend/pyproject.toml`, root `AGENTS.md`.

## Tooling & Ausführung

- Immer `uv` für Package-Management, `uv venv` für virtuelle Umgebungen. Nie `pip` direkt.
- Backend-Python-Kommandos nach Möglichkeit aus `backend/` ausführen. Das Repo-Root ist seit dem uv-Workspace (`pyproject.toml` mit `[tool.uv.workspace] members = ["backend"]`) für `uv run` direkt nutzbar (z. B. `uv run katalon-manage`); `Settings` löst `.env` source-relativ auf (backend + Root).
- `click-didyoumean==0.3.1` gepinnt halten — `uv` stolpert sonst über einen inkonsistenten Lock-Eintrag. Effektiver Lock ist seit dem uv-Workspace das Root-`uv.lock` (nicht `backend/uv.lock`). Nicht ändern bis Upstream sauber ist.
- Python 3.14+, `hatchling`-Build.

## Lint & Types

- `ruff` (`line-length = 100`, `target-version = "py314"`), Regeln: `E`, `W`, `F`, `I`, `UP`, `B`, `C4`, `SIM`, `ASYNC`, `RUF`, `T20`, `S`. Details/Ignores in `backend/pyproject.toml`.
- Vor Commit: `uvx ruff check --fix`.
- `mypy strict = true`, `ignore_missing_imports = true`. Neuer Code muss typisiert sein.
- `pytest`, `asyncio_mode = "auto"`, Testpfad `backend/tests/`.

## Muster, die im Code bereits gelten (einhalten)

- Klare Trennung `api/` (Endpoints) / `services/` (Business-Logik) / `integrations/` (ES, Cantaloupe, Authority-Adapter) / `workers/` (Celery Tasks). Neuer Code folgt dieser Schichtung, keine Business-Logik in Endpoint-Handlern.
- Parametrisiertes SQL durchgängig (SQLAlchemy) — nie String-Interpolation in Queries.
- Passwörter **und** API-Keys über `bcrypt`.
- Rollen/Enum-Felder (z. B. `role`) nie als freier String akzeptieren — `Literal`/`Enum` verwenden und validieren (siehe `docs/CODE_QUALITY_ASSESSMENT.md`, Finding M2 — an dieser Stelle noch offen, aber die Regel gilt für allen neuen Code).
- Selbstreferenzierende `parent_id`-Hierarchien mit **eigenständiger fachlicher Identität** je Kindknoten (self-referential FK auf die eigene Tabelle, wo Kinder unabhängig vom Elternknoten weiterbestehen sollen — `collections.parent_id`, `storage_locations.parent_id`, `vocabulary_terms.parent_id`): Jede neue Spalte dieser Art braucht verpflichtend alle drei Bausteine, nicht nur den DB-FK:
  1. **Zyklus-Prüfung beim Update** — Elternpfad vollständig hochlaufen und bei Wiederauftreten der eigenen ID mit `422` blocken (siehe `_validate_parent_id`/`_validate_parent` in `api/v1/storage_locations.py`, `api/v1/collections.py`, `api/v1/vocabularies.py`).
  2. **Kind-Guard beim Löschen** — `ondelete="SET NULL"` am FK ist nur DB-Sicherheitsnetz, nie der Lösch-Vertrag. Der Delete-Endpoint zählt aktive direkte Kinder (`count_direct_children`) und blockt mit `409`/`child_count`, solange weder `cascade=true` noch `reparent=true` übergeben wird — kein stilles Verwaisen.
  3. **Cascade/Reparent-Optionen konsistent** — `cascade=true` löscht den ganzen Teilbaum (Nutzungs-/Relations-Check atomar über den gesamten Teilbaum vor jeder Löschung), `reparent=true` hängt direkte Kinder auf den Großelternknoten um; beide Flags gleichzeitig → `400`. Referenzimplementierung: `count_direct_children`/`reparent_children`/`get_*_subtree_ids` in `services/storage_location_service.py`, `services/collection_service.py`, `services/vocabulary_reference_service.py`.

  Abzugrenzen von `field_definitions.parent_id` (Gruppenfeld → Unterfeld): Unterfelder haben **keine** eigenständige Identität ohne ihre Gruppe, deshalb ist dort `ondelete="CASCADE"` + ORM `cascade="all, delete-orphan"` bewusst korrekt und kein Fall für obige drei Bausteine — Unterscheidung vor dem Kopieren des Musters prüfen.

- **Öffentliche Ausgaben nur über die öffentliche Projektion.** Portal, Suchindex, OAI/Exporte, IIIF-Manifest und RDF ohne Leserecht lesen Metadaten über `project_public_record`/`filter_public_metadata_checked` (`services/public_metadata_service.py`), nie roh aus `record.metadata_`. Relationsfeld-Werte tragen den Namen des Ziels und erben dessen Sichtbarkeit: `hidden_targets` laden (`load_hidden_relation_targets`), ohne sie gibt die Projektion keine Relationsfeld-Werte heraus. Relationen nach außen nur zu Zielen aus `visible_record_ids`. Siehe `.agents/knowledge/decisions/oeffentliche-projektion-relationsfelder.md`.
- **Caching öffentlicher Reads:** anonyme Portal-Reads `Cache-Control: public, max-age=60`, mit `Vary: Authorization`, wo Staff eine andere Projektion bekommt; Staff-Antworten `private, no-store` (Muster in `api/v1/portal_public.py`).
- **Indexdokumente:** nur ausgehende Relationen in nested-Felder (ES-Limit 10.000 je Dokument); Facettenwerte als `facet_*`-Keyword-Felder, damit kein Mapping-Update nötig ist.

## Explizit vermeiden

- `except Exception: pass` ohne Logging — verschluckt Fehler stillschweigend (siehe Finding M4). Mindestens `logger.warning(..., exc_info=True)`.
- Neue Endpoints ohne `CurrentUser`/`require_role`-Dependency, wenn sie schreibend oder privilegiert sind (siehe Finding C1 — unauthentifizierte Self-Registration mit frei wählbarer Rolle war ein kritischer Fund).
- Synchrone Elasticsearch-Indizierung im Request-Pfad ohne Retry/Reconciliation-Pfad (siehe Finding M3, mittlerweile durch Issue #214 gelöst — Muster nicht wiederholen).

## Citations

[1] `backend/pyproject.toml`
[2] Root `AGENTS.md`, Abschnitte "Python/uv Hinweise", "Kritische Build-Konfigurationen"
[3] `docs/CODE_QUALITY_ASSESSMENT.md`
