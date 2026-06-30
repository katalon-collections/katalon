# Docker Compose — Dev vs. Prod

## Zwei Dateien, ein Prinzip

```bash
# Prod
docker compose up -d

# Dev
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Das Override-File ergänzt und überschreibt nur was sich unterscheidet. Alles andere erbt vom Base-File.

---

## Wann neu bauen (`--build`)

Neu bauen nötig wenn sich **Dateien außerhalb der gemounteten Volumes** ändern:

| Was geändert | Betroffener Service | Aktion |
|---|---|---|
| `backend/pyproject.toml` (neue Abhängigkeit) | `api`, `worker` | `--build api worker` |
| `docker/Dockerfile.*` | jeweiliger Service | `--build <service>` |
| `frontend/*/package.json` | `admin`, `portal` | `--build <service>` |
| Python-Code in `backend/src/` | — | **nichts** (Hot-Reload) |
| React-Code in `frontend/*/src/` | — | **nichts** (Vite HMR) |
| Env-Vars in `docker-compose.dev.yml` | jeweiliger Service | `up -d --no-deps <service>` (kein Build nötig) |

In Prod haben `api` und `worker` keine Source-Mounts → jede Code-Änderung braucht `--build`.

---

## Einzelnen Service neu starten

```bash
# Nur Portal neu starten (z.B. nach Env-Var-Änderung)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --no-deps portal
```

---

## Frontend-Architektur Dev vs. Prod

| | Dev | Prod |
|---|---|---|
| Läuft als | Vite Dev-Server | nginx (statische Dateien) |
| Port Admin | 4000 | 3000 |
| Port Portal | 4001 | 3001 |
| API-Calls | relative Pfade (`/v1/...`), Vite proxied nach `http://api:8000` | relative Pfade, nginx proxied |
| Hot-Reload | ja | nein |

**Merksatz:** `4000/4001` nur mit `docker-compose.dev.yml`. Für normalen Compose-Stack und für produktionsnahe Browser-Checks immer `3000/3001`.

**Wichtig:** `VITE_API_URL` muss in Dev **leer** bleiben. Der Proxy-Target für den
Vite-Prozess kommt aus `API_PROXY_TARGET`. Das verhindert, dass der Browser versucht
`http://api:8000` direkt aufzurufen (DNS nicht auflösbar vom Browser).

---

## Schnellreferenz Makefile

```bash
make dev        # Dev-Stack starten
make up         # Prod-Stack starten
make down       # Stack stoppen
make rebuild    # Alles neu bauen und starten
make logs       # Live-Logs aller Services
```
