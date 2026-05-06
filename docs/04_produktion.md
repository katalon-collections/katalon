# Katalon – Produktionsbetrieb mit Docker Compose

Dieses Dokument beschreibt, wie Katalon auf einem Linux-Server in Produktion betrieben wird.

## Voraussetzungen

- Linux-Server (Debian/Ubuntu empfohlen), min. 4 GB RAM, 20 GB Disk
- Docker ≥ 24 und Docker Compose v2 installiert
- Öffentliche IP-Adresse, DNS-Einträge für deine Domains gesetzt
- TLS-Zertifikate (Let's Encrypt empfohlen)

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
| `DEFAULT_ADMIN_EMAIL` | E-Mail des ersten Admin-Accounts |
| `DEFAULT_ADMIN_PASSWORD` | Passwort des ersten Admin-Accounts |
| `CORS_ORIGINS` | Komma-separierte Liste erlaubter Frontends |
| `OAI_ADMIN_EMAIL` | Erscheint im OAI-PMH Identify-Response |

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

## 4. nginx-Konfiguration anpassen

In `docker/nginx.prod.conf` die Domains ersetzen:

```bash
# Alle Vorkommen von example.org und admin.example.org ersetzen
sed -i 's/example\.org/deine-domain.de/g; s/admin\.example\.org/admin.deine-domain.de/g' docker/nginx.prod.conf
```

## 5. Frontend-URLs anpassen

Die React-Apps müssen wissen, wo die API liegt. Setze VITE-Build-Argumente in `docker-compose.prod.yml`:

```yaml
admin:
  build:
    args:
      VITE_API_URL: https://admin.deine-domain.de
      VITE_PORTAL_URL: https://deine-domain.de

portal:
  build:
    args:
      VITE_API_URL: https://deine-domain.de
```

Alternativ: Die Apps lesen `VITE_API_URL` aus dem Vite-Build. Stelle sicher, dass die Dockerfiles `ARG`s für diese Variablen enthalten (→ ggf. Dockerfiles entsprechend erweitern).

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

## 9. Erster Login

1. Browser: `https://admin.deine-domain.de`
2. Login mit `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`
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

## Backups

### Datenbank

```bash
# Backup erstellen
docker compose exec db pg_dump -U katalon katalon | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backup_20260101.sql.gz | docker compose exec -T db psql -U katalon katalon
```

### Mediendateien

Das Volume `media_data` liegt unter `/var/lib/docker/volumes/katalon_media_data/_data/` (Standardpfad).

```bash
# Backup
tar czf media_backup_$(date +%Y%m%d).tar.gz \
  $(docker volume inspect katalon_media_data --format '{{ .Mountpoint }}')
```

### Elasticsearch

Elasticsearch-Daten können jederzeit aus der Datenbank neu indexiert werden (`POST /v1/search/reindex`). Ein eigenes ES-Backup ist für den normalen Betrieb nicht zwingend nötig.

## Monitoring

### Health-Check

```bash
curl https://deine-domain.de/health
# → {"status": "ok"}
```

### Logs

```bash
docker compose logs api        # API-Logs
docker compose logs worker     # Celery-Worker-Logs
docker compose logs nginx      # Zugriffslog
```

### OAI-PMH-Endpunkt testen

```bash
# Identify
curl "https://deine-domain.de/v1/oai?verb=Identify"

# Alle Sets
curl "https://deine-domain.de/v1/oai?verb=ListSets"

# Alle Records (paginiert)
curl "https://deine-domain.de/v1/oai?verb=ListRecords&metadataPrefix=oai_dc"
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
