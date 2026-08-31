# Katalon – Produktionsbetrieb mit Docker Compose

Dieses Dokument beschreibt, wie Katalon auf einem Linux-Server in Produktion betrieben wird.

**Empfohlener Weg für neue Instanzen:** [`katalon-cli`](https://github.com/karkraeg/katalon-cli) (`uv tool install katalon-cli`) installiert und aktualisiert Produktionsinstanzen über gepinnte Release-Images, ohne Repository-Checkout — siehe [Release-Metadaten für katalon-cli](13_release_metadata.md). Der manuelle Weg unten (Repository klonen, Compose-Dateien selbst pflegen) bleibt für Sonderfälle und zum Verständnis der zugrundeliegenden Compose-Topologie relevant, wird aber nicht mehr als primärer Installationsweg empfohlen.

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
- [ ] `MEDIA_ROOT`-Host-Verzeichnis existiert und gehört UID/GID `1000` (`install -d -o 1000 -g 1000 -m 755 /srv/katalon/media`, **nicht** `mkdir -p`) — `api`- und `worker`-Container laufen als nicht-root User `app` (UID 1000). Fehlt das, schlagen Uploads still mit `Permission denied` fehl, ohne Health-Check-Alarm — siehe Abschnitt "Medien-Upload schlägt fehl" unten.
- [ ] `docker/nginx.prod.conf` auf eigene Domain(en) angepasst
- [ ] `.env` VITE-Build-Argumente für Admin/Portal gesetzt
- [ ] Wikidata-Adapter: `WIKIDATA_USER_AGENT` setzen oder `KATALON_BASE_URL` + `OAI_ADMIN_EMAIL` vollständig pflegen (Wikidata-Policy erfordert identifizierbaren User-Agent)
- [ ] Backup-Strategie eingerichtet (Cron für DB-Dump, Media-Volume gesichert)
- [ ] Automatische Zertifikatserneuerung (certbot-Cron) eingerichtet
- [ ] Für transaktionale E-Mails: SMTP-Relay, Absender-Domain und SPF/DKIM/DMARC eingerichtet
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
| `SMTP_*` | Optionaler externer SMTP-Relay für transaktionale E-Mails. Passwort nur als Betreiber-Secret setzen. |

### ARKs einrichten

ARKs werden in Katalon lokal geprägt, aber erst über einen eigenen, bei der
ARK Alliance registrierten NAAN weltweit auflösbar. Vor der Aktivierung:

1. Einen dauerhaften öffentlichen Domainnamen und `KATALON_BASE_URL` festlegen.
2. Einen NAAN über das [NAAN-Antragsformular der ARK Alliance](https://arks.org/about/getting-started-implementing-arks/) beantragen.
3. Im NAAN-Register den lokalen Resolver `https://katalog.example.org/ark:/<NAAN>/` hinterlegen. N2T leitet dann vollständige ARKs an die Instanz weiter.

Danach in `.env` setzen:

```env
ARK_ENABLED=true
ARK_NAAN=12345
ARK_RESOLVER_URL=https://n2t.net/
ARK_SUFFIX_LENGTH=10
```

Katalon beantwortet `https://katalog.example.org/ark:/12345/<Suffix>` mit
einem Redirect auf die aktuelle öffentliche Portal-Detailseite. `ARK_ENABLED`
schaltet nur neue Vergaben ab; die Auflösung bereits vergebener ARKs bleibt
aktiv. Der Test-NAAN `99999` ist nicht für Produktionsdaten geeignet und wird
nicht aufgelöst.

### SMTP für transaktionale E-Mails

Katalon betreibt keinen eigenen Mailserver. Für Passwort-Reset und spätere Benachrichtigungen wird ein externer SMTP-Relay verwendet. Versand bleibt mit `SMTP_ENABLED=false` deaktiviert, bis Relay und Absender vollständig konfiguriert sind.

```env
SMTP_ENABLED=true
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_USERNAME=noreply@example.org
SMTP_PASSWORD=BETREIBER_SECRET
SMTP_FROM=Katalon <noreply@example.org>
SMTP_STARTTLS=true
SMTP_SSL_TLS=false
KATALON_BASE_URL=https://katalon.example.org
```

Port 587 verwendet üblicherweise STARTTLS. Für implizites TLS (meist Port 465) `SMTP_STARTTLS=false` und `SMTP_SSL_TLS=true` setzen. Bei aktiviertem SMTP muss genau ein TLS-Modus aktiv sein und `KATALON_BASE_URL` gesetzt sein, damit sichere Reset-Links erzeugt werden können. Die Absender-Domain benötigt SPF, DKIM und DMARC; außerdem muss der Server den SMTP-Host erreichen können. `SMTP_PASSWORD` gehört ausschließlich in die nicht versionierte Produktionsumgebung oder die Secret-Verwaltung.

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

### Option C: TLS wird extern terminiert (z. B. Traefik, nginx-proxy)

Läuft vor dem Stack bereits ein Reverse Proxy, der TLS terminiert (Traefik-Label-Setup,
externer nginx, …), braucht der `nginx`-Service selbst **kein** TLS mehr — er wird dann
nur noch intern per Docker-Netzwerk auf Port 80 angesprochen, Port 443 wird meist gar
nicht mehr veröffentlicht.

`docker/nginx.conf` und `docker/nginx.prod.conf` enthalten beide einen `listen 443 ssl`-Block,
der beim Start ladbare Zertifikate unter `docker/certs/` voraussetzt — auch wenn Port 443
nie extern erreichbar ist (`cannot load certificate ... BIO_new_file() failed` sonst).
Ein Self-signed-Zertifikat nur zum Booten in Produktion zu erzeugen ist kein guter Fix
(`make certs` ist explizit für lokale Entwicklung gedacht, nicht für Prod-Container).

Sauberer: eine eigene, schlanke nginx-Config **ohne** den 443-Block einbinden (identisch
zu `docker/nginx.conf`, nur `listen 443 ssl` + die beiden `ssl_certificate*`-Zeilen
entfernt) und im jeweiligen Compose-Overlay statt `docker/nginx.conf` mounten. Diese
Reverse-Proxy-spezifische Config ist Teil der Instanz-Konfiguration, nicht des Repos —
sie gehört (wie ein eigenes `docker-compose.traefik.yml`-Overlay) lokal zur Instanz.

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

Frontend-Build-Argumente in `.env` setzen (werden über `docker-compose.prod.yml` an die
Build-Stages weitergereicht):

```env
ADMIN_VITE_API_URL=https://admin.meineurl.de
PORTAL_URL=https://meineurl.de
PORTAL_VITE_API_URL=https://meineurl.de
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

Frontend-Build-Argumente in `.env`:

```env
ADMIN_VITE_API_URL=https://meineurl.de
PORTAL_URL=https://meineurl.de
PORTAL_VITE_API_URL=https://meineurl.de
```

---

### TLS-Volume in docker-compose.prod.yml (beide Optionen)

```yaml
nginx:
  volumes:
    - ./docker/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
    - ./docker/certs:/etc/nginx/certs:ro
  ports:
    - "80:80"
    - "443:443"
```

`docker/nginx.prod.conf` erwartet `fullchain.pem` und `privkey.pem` direkt unter
`/etc/nginx/certs/` (also `docker/certs/fullchain.pem` und `docker/certs/privkey.pem`).

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
werden nach `BACKUP_RETENTION_DAYS` (Default 14) automatisch gelöscht.

Konfiguration über `.env`:

| Variable | Default | Bedeutung |
|----------|---------|-----------|
| `BACKUP_ENABLED` | `true` | `false` = Service läuft, macht aber keine Backups |
| `BACKUP_ROOT` | `/srv/katalon/backups` | Host-Zielverzeichnis |
| `BACKUP_RETENTION_DAYS` | `14` | ältere Dumps werden gelöscht |
| `BACKUP_AT` | `03:00` | feste Uhrzeit `HH:MM` (Container-Zeitzone, s. u.) |
| `BACKUP_INTERVAL_SECONDS` | `86400` | nur wirksam wenn `BACKUP_AT` **leer** ist |

Zwei Zeitplan-Modi: Ist `BACKUP_AT` gesetzt, läuft das Backup täglich zur festen
Uhrzeit. Ist es leer, greift der Intervall-Modus (`BACKUP_INTERVAL_SECONDS`, Backup
sofort beim Start + dann alle N Sekunden).

**Zeitzone:** `BACKUP_AT` wird in der Container-Zeitzone interpretiert (Standard UTC).
Für lokale Zeit `TZ=Europe/Berlin` im `environment` des `backup`-Service setzen.

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

### nginx startet nicht: "cannot load certificate ... BIO_new_file() failed"

`docker/certs/` enthält keine Zertifikatsdateien. Betrifft typischerweise Deployments
hinter einem externen Reverse Proxy (Traefik, …), die weiterhin `docker/nginx.conf`
einbinden, obwohl der 443-Block dort nie gebraucht wird — siehe
[Option C](#option-c-tls-wird-extern-terminiert-z-b-traefik-nginx-proxy) oben. Kein
Zertifikat für Prod erzeugen, sondern eine eigene Config ohne `listen 443 ssl` mounten.

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

`api` und `worker` laufen als nicht-root User `app` (UID 1000). Ist das
Host-Verzeichnis hinter `MEDIA_ROOT` nicht für UID 1000 schreibbar, schlagen
Uploads mit `PermissionError` fehl. Ein Startup-Check loggt in diesem Fall
eine Warnung (`MEDIA_ROOT nicht beschreibbar für UID ...`) — in den
`api`-Logs nach dieser Meldung suchen, statt erst beim ersten Upload-Fehler
zu bemerken.

Fix (nur das Verzeichnis selbst, nicht rekursiv — bei großem Medienbestand
wäre `chown -R` potenziell sehr langsam):

```bash
sudo chown 1000:1000 "${MEDIA_ROOT:-/srv/katalon/media}"
```

Neue Unterordner (`_batch_imports`, `logos`, `themes`) erben die Rechte des
Elternverzeichnisses bei Neuanlage durch den `app`-User automatisch korrekt;
bereits bestehende Unterordner mit falschem Owner müssen einzeln behandelt
werden (`chown 1000:1000 <verzeichnis>`, ebenfalls nicht rekursiv nötig,
solange nur neue Dateien hinzukommen).

### Große IIIF-Bilder bleiben leer, obwohl Thumbnails funktionieren

Cantaloupe kann `info.json` und kleine Thumbnails ausliefern, obwohl der beschreibbare Derivat-Cache nicht korrekt angelegt wurde. Große Bildanforderungen liefern dann unter Umständen HTTP 200 mit leerem Inhalt. Der Compose-Stack verwendet für den wegwerfbaren Derivat-Cache inzwischen ein `tmpfs`; bestehende Installationen mit dem früheren Named Volume müssen den Dienst einmal neu erstellen.

```bash
docker compose up -d --force-recreate cantaloupe
```

Dadurch wird kein Datenbank- oder Medien-Volume gelöscht.

### Mehrere Instanzen auf einem Host: tmpfs-Größe des Cantaloupe-Caches

Der Cantaloupe-Derivat-Cache läuft als `tmpfs`, begrenzt über `CANTALOUPE_CACHE_TMPFS_SIZE` (Default `512m`, siehe `.env.example`). Ohne dieses Limit würde Docker pro Mount bis zu 50 % des Host-RAM erlauben. Läuft mehr als eine Katalon-artige Instanz auf demselben Host, `CANTALOUPE_CACHE_TMPFS_SIZE` je Instanz bewusst so wählen, dass die Summe aller Instanzen zusammen mit Elasticsearch- und Postgres-Speicherbedarf den verfügbaren Host-RAM nicht übersteigt.


Bei einem alten Stack, der noch das frühere Named Volume verwendet, kann der Cache alternativ repariert werden:

```bash
docker compose logs cantaloupe --tail=100 | grep -E "AccessDeniedException|FilesystemCache"
docker compose exec cantaloupe ls -ld /var/lib/cantaloupe/cache
docker compose exec cantaloupe sh -c 'chown -R cantaloupe:cantaloupe /var/lib/cantaloupe/cache && chmod -R u+rwX /var/lib/cantaloupe/cache'
curl -s -o /tmp/iiif-check.jpg -w 'HTTP %{http_code}, bytes %{size_download}\n' \
  "https://deine-domain.de/iiif/3/<media-id>.<endung>/full/max/0/default.jpg"
```

Die Daten im Medien-Volume werden dabei nicht gelöscht. Der Test muss eine positive Byte-Anzahl liefern; anschließend die betroffene Portalseite hart neu laden.

### Images nach Update nicht aktuell

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
```
