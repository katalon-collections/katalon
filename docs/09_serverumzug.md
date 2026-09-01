# Katalon auf einen neuen Server umziehen

Diese Anleitung gilt für eine manuell betriebene Docker-Compose-Installation. Bei einer Installation über `katalon-cli` verwaltet das Installer-Projekt die Dateien und den Update-Pfad.

Ein Umzug übernimmt PostgreSQL, Mediendateien, die Instanzkonfiguration und TLS-Dateien. Elasticsearch wird nicht kopiert: Der Index entsteht aus der wiederhergestellten Datenbank neu.

## Vor dem Wartungsfenster

Auf dem bisherigen Server dieselbe Katalon-Version notieren, die auf dem neuen Server verwendet wird:

```bash
git describe --tags --exact-match
```

Auf dem neuen Server Docker und Docker Compose installieren. Das Repository mit genau diesem Tag auschecken und die Produktionsvoraussetzungen aus [04_produktion.md](04_produktion.md) vorbereiten. Noch keine Container starten.

## Letztes Backup und Abschalten

Schreibzugriffe müssen vor dem letzten Backup enden. Der folgende Ablauf stoppt zuerst API und Worker, erstellt dann einen zusammengehörenden Datenbank- und Medienexport und fährt den alten Stack ohne Volume-Löschung herunter:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api worker beat
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup once
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

`docker compose down -v` darf hier nicht verwendet werden. Es würde die Datenbank-Volumes löschen.

Den neuesten Backup-Satz bestimmen und prüfen:

```bash
BACKUP_ROOT="$(sed -n 's/^BACKUP_ROOT=//p' .env | tail -n 1)"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/katalon/backups}"
BACKUP_DB="$(find "$BACKUP_ROOT" -maxdepth 1 -name 'db_*.sql.gz' -print | sort | tail -n 1)"
BACKUP_ID="${BACKUP_DB##*/db_}"
BACKUP_ID="${BACKUP_ID%.sql.gz}"
test -n "$BACKUP_ID" -a -f "$BACKUP_ROOT/media_${BACKUP_ID}.tar.gz"
printf '%s\n' "$BACKUP_ID"
```

Die Ausgabe ist die Kennung des zugehörigen Datenbank- und Medienexports. Beide Dateien zusammen mit der Konfiguration auf den neuen Server übertragen. `NEW_HOST` ist dessen SSH-Name, `TARGET_DIR` das vorbereitete Repository-Verzeichnis auf dem Zielsystem:

```bash
NEW_HOST=katalon-neu.example.org
TARGET_DIR=/srv/katalon
ssh "$NEW_HOST" "mkdir -p '$TARGET_DIR/backups'"
rsync -a --protect-args .env docker/certs/ "$NEW_HOST:$TARGET_DIR/"
if [ -f docker-compose.override.yml ]; then
  rsync -a --protect-args docker-compose.override.yml "$NEW_HOST:$TARGET_DIR/"
fi
rsync -a --protect-args "$BACKUP_DB" "$BACKUP_ROOT/media_${BACKUP_ID}.tar.gz" \
  "$NEW_HOST:$TARGET_DIR/backups/"
```

## Daten auf dem neuen Server wiederherstellen

Im neuen Checkout zuerst nur PostgreSQL starten. Der Import erfolgt in eine frische Datenbank, nicht in ein vorhandenes System:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db sh -c 'until pg_isready -U "$POSTGRES_USER"; do sleep 1; done'
BACKUP_DB="$(find /srv/katalon/backups -maxdepth 1 -name 'db_*.sql.gz' -print | sort | tail -n 1)"
BACKUP_ID="${BACKUP_DB##*/db_}"
BACKUP_ID="${BACKUP_ID%.sql.gz}"
test -f "/srv/katalon/backups/media_${BACKUP_ID}.tar.gz"
gunzip -c "$BACKUP_DB" \
  | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Für den Medienexport muss der Dateiname dieselbe Kennung wie der Datenbankexport haben. Die im vorherigen Block gesetzte Variable wird jetzt verwendet:

```bash
MEDIA_ROOT="$(sed -n 's/^MEDIA_ROOT=//p' .env | tail -n 1)"
MEDIA_ROOT="${MEDIA_ROOT:-/srv/katalon/media}"
sudo install -d -o 1000 -g 1000 -m 755 "$MEDIA_ROOT"
sudo tar --no-same-owner --owner=1000 --group=1000 \
  -xzf "/srv/katalon/backups/media_${BACKUP_ID}.tar.gz" -C "$MEDIA_ROOT"
```

## Starten und prüfen

Den gesamten Produktionsstack starten und Migrationen ausführen:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

Vor der DNS-Umstellung die neue IP mit dem echten Hostnamen testen. Die TLS-Dateien müssen bereits zum Hostnamen passen:

```bash
NEW_SERVER_IP=203.0.113.10
curl --resolve deine-domain.de:443:"$NEW_SERVER_IP" -f https://deine-domain.de/health
```

Melde dich als Admin an, öffne in den Einstellungen den Abschnitt „Suche & Indexierung“ und wähle „Alles reindizieren“. Die Aufgabe läuft im Worker. Prüfe danach Portal, Admin, einen Datensatz mit Bild und die Suche.

Die alte Instanz bleibt ausgeschaltet, ihre Volumes bleiben aber erhalten. Erst nach erfolgreicher Prüfung und DNS-Umstellung darf sie außer Betrieb genommen werden.

## Zurückrollen

Scheitert die Prüfung vor der DNS-Umstellung, den neuen Stack mit `docker compose -f docker-compose.yml -f docker-compose.prod.yml down` stoppen und auf dem alten Server denselben Compose-Befehl mit `up -d` ausführen. Nach einer DNS-Umstellung zuerst den DNS-Eintrag zurücksetzen, dann die alte Instanz wieder starten. Beide Instanzen dürfen nicht gleichzeitig Schreibzugriffe annehmen.
