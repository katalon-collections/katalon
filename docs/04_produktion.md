# Katalon – Produktionsbetrieb mit Docker Compose

Dieses Dokument beschreibt, wie Katalon auf einem Linux-Server in Produktion betrieben wird.

## Voraussetzungen

- Linux-Server (Debian/Ubuntu empfohlen), min. 4 GB RAM, 20 GB Disk
- Docker ≥ 24 und Docker Compose v2 installiert
- Öffentliche IP-Adresse, DNS-Einträge für deine Domains gesetzt
- TLS-Zertifikate (Let's Encrypt empfohlen)

## Checkliste vor dem ersten Produktionsstart

- [ ] Domainname(n) entschieden und DNS-Einträge gesetzt
- [ ] URL-Layout gewählt (Subdomain oder Subpfad, → Abschnitt 4)
- [ ] TLS-Zertifikate ausgestellt
- [ ] `.env` vollständig ausgefüllt — insbesondere `SECRET_KEY`, Datenbankpasswort, `KATALON_BASE_URL`, `CORS_ORIGINS`
- [ ] `docker/nginx.prod.conf` auf eigene Domain(en) angepasst
- [ ] `docker-compose.prod.yml` VITE-Build-Argumente auf eigene URLs gesetzt
- [ ] Wikidata-Adapter: `WIKIDATA_USER_AGENT` setzen oder `KATALON_BASE_URL` + `OAI_ADMIN_EMAIL` vollständig pflegen (Wikidata-Policy erfordert identifizierbaren User-Agent)
- [ ] Backup-Strategie eingerichtet (Cron für DB-Dump, Media-Volume gesichert)
- [ ] Automatische Zertifikatserneuerung (certbot-Cron) eingerichtet
- [ ] Nach erstem Start: `alembic upgrade head` ausgeführt
- [ ] Nach erstem Start: First-Run-`superuser`-Passwort geändert

## 1. Repository klonen

```bash
git clone https://github.com/karkraeg/Katalon.git
cd Katalon
```

## 2. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
nano .env
```

Mindestens diese Werte anpassen:

| Variable | Beschreibung |
|---|---|
| `POSTGRES_PASSWORD` | Starkes Datenbankpasswort |
| `DATABASE_URL` | Muss dasselbe Passwort enthalten |
| `SECRET_KEY` | JWT-Schlüssel — generieren mit `openssl rand -hex 32` |
| `KATALON_BASE_URL` | Öffentliche Basis-URL der Instanz (z.B. `https://katalon.example.org`) |
| `FIRST_RUN_CREDENTIALS_PATH` | Pfad im API-Container für die einmalig erzeugte Credentials-Datei (bei Bedarf auf ein persistentes Volume legen) |
| `DEFAULT_ADMIN_EMAIL` | Fallback-E-Mail für lokale Entwicklung ohne `KATALON_BASE_URL` |
| `DEFAULT_ADMIN_PASSWORD` | Fallback-Passwort für lokale Entwicklung ohne `KATALON_BASE_URL` |
| `CORS_ORIGINS` | Komma-separierte Liste erlaubter Frontends |
| `OAI_ADMIN_EMAIL` | Erscheint im OAI-PMH Identify-Response |
| `WIKIDATA_USER_AGENT` | Optionaler User-Agent für Wikidata. Leer = automatisch aus `KATALON_BASE_URL` + `OAI_ADMIN_EMAIL`. |

### Instanzspezifische Docker-Compose-Anpassungen

Wenn du eigene Ports, Volume-Pfade oder zusätzliche Umgebungsvariablen brauchst, ändere dafür **nicht** die zentrale `docker-compose.yml`.

Stattdessen:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

`docker-compose.override.yml` wird automatisch von Docker Compose mitgeladen und bleibt bei Updates unangetastet.

## 3. TLS-Zertifikate einrichten

### Option A: Let's Encrypt mit certbot (empfohlen)

```bash
# certbot installieren (Debian/Ubuntu)
apt install certbot

# Zertifikat ausstellen (DNS muss auf den Server zeigen)
certbot certonly --standalone -d example.org -d admin.example.org

# Zertifikate in den Docker-Pfad kopieren
mkdir -p docker/certs
cp /etc/letsencrypt/live/example.org/fullchain.pem docker/certs/
cp /etc/letsencrypt/live/example.org/privkey.pem   docker/certs/
chmod 644 docker/certs/*.pem
```

Automatische Erneuerung (crontab):
```
0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/example.org/fullchain.pem /pfad/zu/katalon/docker/certs/ && cp /etc/letsencrypt/live/example.org/privkey.pem /pfad/zu/katalon/docker/certs/ && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Option B: Eigenes Zertifikat

Lege `fullchain.pem` und `privkey.pem` in `docker/certs/`.

## 4. URL-Layout wählen und nginx anpassen

Es gibt zwei unterstützte Layouts. Einmal entscheiden, dann konsequent durchziehen.

---

### Option A — Subdomain (Standard, empfohlen)

```
https://meineurl.de           → Public-Portal
https://admin.meineurl.de     → Admin-UI
```

`docker/nginx.prod.conf` ist für dieses Layout vorbereitet. Domains ersetzen:

```bash
sed -i 's/example\.org/meineurl.de/g; s/admin\.example\.org/admin.meineurl.de/g' docker/nginx.prod.conf
```

TLS-Zertifikate für beide Domains ausstellen:

```bash
certbot certonly --standalone -d meineurl.de -d admin.meineurl.de
```

`docker-compose.prod.yml` — VITE-Build-Argumente:

```yaml
admin:
  build:
    args:
      VITE_API_URL: https://admin.meineurl.de
      VITE_PORTAL_URL: https://meineurl.de

portal:
  build:
    args:
      VITE_API_URL: https://meineurl.de
```

---

### Option B — Subpfad (eine Domain, zwei Pfade)

```
https://meineurl.de              → Public-Portal
https://meineurl.de/cataloging   → Admin-UI
```

Vite muss die Asset-Pfade beim Build einbetten. Dafür in `frontend/admin/vite.config.ts` ergänzen:

```ts
export default defineConfig({
  base: '/cataloging/',   // ← neu
  // … Rest unverändert
})
```

`docker/nginx.prod.conf` — den separaten `server`-Block für `admin.example.org` ersetzen durch einen `location`-Block im Portal-Server:

```nginx
# Im Portal-Server-Block ergänzen (nach dem /v1/-Block):
location /cataloging/ {
    proxy_pass http://admin/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Den `server`-Block für `admin.example.org` sowie den zugehörigen HTTP-Redirect-Eintrag komplett entfernen.

Nur ein Zertifikat nötig:

```bash
certbot certonly --standalone -d meineurl.de
```

`docker-compose.prod.yml`:

```yaml
admin:
  build:
    args:
      VITE_API_URL: https://meineurl.de
      VITE_PORTAL_URL: https://meineurl.de

portal:
  build:
    args:
      VITE_API_URL: https://meineurl.de
```

---

### TLS-Volume in docker-compose.prod.yml (beide Optionen)

```yaml
nginx:
  volumes:
    - ./docker/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
    - ./docker/certs/fullchain.pem:/etc/nginx/certs/fullchain.pem:ro
    - ./docker/certs/privkey.pem:/etc/nginx/certs/privkey.pem:ro
  ports:
    - "80:80"
    - "443:443"
```

## 6. Images bauen und starten

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Logs beobachten:
```bash
docker compose logs -f api worker
```

## 7. Datenbank-Migrationen ausführen

Beim ersten Start führt der API-Container automatisch keine Migrationen aus — das muss manuell angestoßen werden:

```bash
docker compose exec api alembic upgrade head
```

Nach jedem Update ebenfalls ausführen.

## 8. Elasticsearch-Index initialisieren

Nach dem ersten Start den Index und die Mappings aufbauen:

```bash
# Index anlegen (passiert automatisch beim ersten API-Start via ensure_index())
# Alle bestehenden Datensätze indexieren:
curl -X POST https://deine-domain.de/v1/search/reindex
```

Nach dem Vorgänge-Update (`0.2.x`) muss für bestehende Daten mindestens der Objektindex neu aufgebaut werden, weil `collection_status` in die öffentlichen Suchfilter aufgenommen wurde:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex/object
```

## 9. Erster Login

Beim ersten API-Start ohne vorhandenen Admin/Superuser erzeugt Katalon automatisch:

- E-Mail: `admin@<domain-aus-KATALON_BASE_URL>`
- Passwort: kryptografisch zufällig (einmalig)

Die Zugangsdaten werden im API-Log mit dem Block `====== KATALON FIRST RUN ======` ausgegeben und zusätzlich in `./first-run-credentials.txt` abgelegt (über `install.sh` via `docker cp`).

1. Browser: `https://admin.deine-domain.de`
2. Login mit den First-Run-Zugangsdaten
3. Sofort das Passwort ändern (Admin → Benutzer → eigenes Konto)

## Updates einspielen

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec api alembic upgrade head
# Falls Schema-Änderungen: Reindex anstoßen
curl -X POST https://deine-domain.de/v1/search/reindex
```

Für Updates, die nur Objekt-Suchfelder ändern, reicht:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex/object
```

## Backups

### Automatisch (backup-Service)

Der Compose-Stack enthält einen `backup`-Service (`docker/backup.sh`), der **täglich**
läuft und beides sichert:

- Datenbank: `pg_dump` → `db_<timestamp>.sql.gz`
- Mediendateien (`MEDIA_ROOT`): `media_<timestamp>.tar.gz`

Dumps landen im Host-Verzeichnis `BACKUP_ROOT` (Default `/srv/katalon/backups`) und
werden nach `BACKUP_RETENTION_DAYS` (Default 14) automatisch gelöscht. Intervall über
`BACKUP_INTERVAL_SECONDS` (Default 86400 = täglich) steuerbar.

```bash
# Einmaliges Backup sofort auslösen (z. B. vor einem Deploy)
docker compose run --rm backup once

# Vorhandene Backups ansehen
ls -lh /srv/katalon/backups
```

**Off-site empfohlen:** `BACKUP_ROOT` zusätzlich per `rsync`/S3 auf einen zweiten
Standort spiegeln — ein Backup auf demselben Host schützt nicht vor Host-Verlust.

### Restore

Datenbank:

```bash
gunzip -c /srv/katalon/backups/db_20260101_030000.sql.gz \
  | docker compose exec -T db psql -U katalon katalon
```

Mediendateien (`.` = Inhalt von `MEDIA_ROOT`):

```bash
tar xzf /srv/katalon/backups/media_20260101_030000.tar.gz -C "$MEDIA_ROOT"
```

Nach dem DB-Restore Elasticsearch neu aufbauen:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex/object   # je Typ
```

### Restore-Drill (durchgespielt 2026-07-13)

Ein Restore ist nur so viel wert wie sein letzter Test. Verifizierter Ablauf auf
frischer Umgebung:

1. Frisches Verzeichnis + `.env` mit **anderem** `POSTGRES_DB` (z. B. `katalon_restore`).
2. Nur DB starten: `docker compose up -d db`.
3. Neueste `db_*.sql.gz` per obigem `psql`-Befehl einspielen.
4. Zeilenzahl gegen Quelle prüfen:
   `docker compose exec -T db psql -U katalon -d katalon_restore -c "SELECT count(*) FROM objects;"`
5. Media-tar in ein Testverzeichnis entpacken, Dateizahl vergleichen.
6. Voll starten, `curl .../health` → `ok`, Stichprobe im Admin-UI.

Ergebnis: Dump lässt sich sauber einspielen (PostGIS-Extension inklusive), Media-tar
entpackt vollständig. Drill mindestens halbjährlich wiederholen.

### Elasticsearch

Elasticsearch-Daten können jederzeit aus der Datenbank neu indexiert werden (`POST /v1/search/reindex`). Ein eigenes ES-Backup ist für den normalen Betrieb nicht zwingend nötig.

## Monitoring

### Health-Check

```bash
curl https://deine-domain.de/health
# → {"status": "ok", "checks": {"database": "ok", "elasticsearch": "ok"}}
```

Der Endpoint prüft Datenbank und Elasticsearch aktiv. Ist eine Abhängigkeit
nicht erreichbar, liefert er HTTP `503` mit `{"status": "degraded", ...}` —
so kann ein Load Balancer einen ausgefallenen Backend-Zustand erkennen.

### Logs

```bash
docker compose logs api        # API-Logs
docker compose logs worker     # Celery-Worker-Logs
docker compose logs nginx      # Zugriffslog
```

### OAI-PMH-Endpunkt testen

```bash
# Identify
curl "https://deine-domain.de/oai?verb=Identify"

# Alle Sets
curl "https://deine-domain.de/oai?verb=ListSets"

# Alle Records (paginiert)
curl "https://deine-domain.de/oai?verb=ListRecords&metadataPrefix=oai_dc"
```

## Ressourcen-Empfehlungen

| Service | Minimum | Empfohlen |
|---|---|---|
| db (PostgreSQL) | 256 MB | 512 MB |
| redis | 64 MB | 128 MB |
| elasticsearch | 1 GB | 2 GB |
| api | 256 MB | 512 MB |
| worker (Celery) | 256 MB | 512 MB |
| cantaloupe | 256 MB | 512 MB |
| nginx | 32 MB | 64 MB |
| **Gesamt** | **~2,1 GB** | **~4 GB** |

## Häufige Probleme

### API startet nicht (Datenbankverbindung schlägt fehl)

```bash
docker compose logs db | tail -20
# Healthcheck abwarten: depends_on mit condition: service_healthy ist gesetzt
```

### Elasticsearch nicht erreichbar

Katalon startet auch ohne ES (API-Endpunkte funktionieren, Suche gibt leere Ergebnisse zurück). ES braucht beim ersten Start 30–60 Sekunden.

### Medien-Upload schlägt fehl

Prüfe, ob das Volume `media_data` vom API-Container schreibbar ist:

```bash
docker compose exec api ls -la /var/lib/katalon/media/
```

### Images nach Update nicht aktuell

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
```
