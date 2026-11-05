---
type: Decision
title: S3 als optionales Medien-Speicherbackend — strikt opt-in, RADOSGW-kompatibel
description: StorageBackend-Protokoll in media_storage.py mit LocalStorage (Default, unverändert) und S3Storage (boto3 in asyncio.to_thread); Cantaloupe liest via nativen S3Source direkt aus dem Bucket; Zielklasse sind alle S3-kompatiblen Implementierungen (Ceph RADOSGW, MinIO, Hetzner, Garage, AWS), boto3-Prüfsummen-Default muss per request_checksum_calculation="when_required" überschrieben werden; kein Migrationsskript, MinIO nur im Dev-Stack (#121).
tags: [media, storage, s3, radosgw, cantaloupe, backend, operations]
timestamp: 2026-09-10T12:00:00Z
---

# Kontext

Issue #121 (Post-MVP): Alle Mediendateien liegen auf dem lokalen Server-Dateisystem
(`MEDIA_ROOT`-Bind-Mount, geteilt zwischen api/worker/cantaloupe). Für größere
Institutionen oder Cloud-Deployments fehlen damit horizontale Skalierung des
Speichers, geografische Redundanz und einfache Auslagerung. Voraussetzung #335
(relative, geshardete `storage_key`s statt absoluter Pfade) ist bereits umgesetzt —
die Keys (`ab/uuid--name.jpg`, daneben `{stem}_pyramid.tif`) sind backend-agnostisch
und direkt als Objekt-Keys verwendbar.

Die Zielklasse wurde explizit nicht auf AWS S3 enggeführt: Bestandteile des
GLAM-Umfelds betreiben On-Prem-Ceph, und "S3-kompatibel" ist die eigentliche
Anforderung. RADOSGW, MinIO, Hetzner Object Storage, Garage und Wasabi haben
jeweils eigene Stolperstellen gegenüber boto3-Defaults.

# Entscheidung

**1. Strikt opt-in, Default bleibt local.** `STORAGE_BACKEND` defaultet auf
`local`; ohne explizite Aktivierung ändert sich nichts — keine Pflicht-Env-Vars,
keine neuen Services im Basis-/Prod-Compose, unverändertes Verhalten bestehender
Instanzen. Cantaloupe, nginx-Gate und IIIF-URLs sind backend-unabhängig.

**2. Kleines StorageBackend-Protokoll in `katalon/core/media_storage.py`, kein
Plugin-System.** Zwei Implementierungen hinter `get_storage()`-Factory:
`LocalStorage` (aktuelles Verhalten inkl. Traversal-Check) und `S3Storage`
(boto3 synchron, gewrappt in `asyncio.to_thread` — etabliertes Muster im
Codebase, kein aiobotocore, keine neue Async-Dependency). YAGNI: keine Registry,
keine dritte Implementierung, keine provider-spezifischen Code-Pfade.

**3. Cantaloupe liest via nativen S3Source direkt aus dem Bucket**
(BasicLookupStrategy + Key-Prefix). Identifier bleiben die encodierten relativen
Keys, der nginx-`auth_request`-Gate und alle IIIF-Manifeste ändern sich nicht.
Verworfene Alternative: Backend-Streaming-Proxy vor Cantaloupe — der hätte zwar
keine Cantaloupe-Konfiguration gebraucht, schleust aber jede Tile-Anfrage
(Dutzende pro Viewer-Seite) durchs API, genau der dokumentierte Cantaloupe-
Bottleneck (vgl. Helm-Chart-Pitfall). Der Derivat-Cache liegt standardmäßig auf persistentem lokalen Speicher;
`tmpfs` ist nur noch eine Betreiberoption. Siehe
[Cantaloupe-Cache](cantaloupe-derivat-cache-und-vorschaubilder.md).

**Einschränkung aus der Umsetzung (Cantaloupe 5.0.x):** S3Source kennt kein
Path-Style — der AWS-SDK-v2-Default (virtual-hosted addressing,
`<bucket>.<endpoint-host>`) gilt auch bei Endpoint-Override. Deployment-
Konsequenz: `<bucket>.<gateway-host>` muss DNS-seitig auflösbar sein
(Wildcard-Eintrag aufs RADOSGW oder expliziter Bucket-DNS). Nur das Backend
(boto3) spricht Path-Style und kommt ohne jede DNS-Vorbereitung aus. Für den
MinIO-Dev-Override löst ein Compose-Network-Alias (`<bucket>.minio`) das
DNS-Problem lokal.

**4. Portabilität gegenüber boto3-Defaults sicherstellen.** Der S3-Client wird
fest mit diesen Abweichungen vom boto3-Default gebaut, weil sie für
RADOSGW/Kompatibilität entscheidend sind:

- `request_checksum_calculation="when_required"` — botocore ≥1.36 sendet
  Default `x-amz-checksum-crc32`, viele kompatible Implementierungen quittieren
  mit `400 Bad Request`. Häufigster realer Breaker.
- Path-Style als Default (`S3_FORCE_PATH_STYLE=true`) — funktioniert überall
  ohne DNS-Wildcard; Virtual-Hosted-Style erfordert bei RADOSGW Subdomain-
  Einträge pro Bucket.
- SigV4 mit konfigurierbarer Region (RADOSGW ignoriert sie, SigV4 braucht
  trotzdem einen Wert, Default `us-east-1`).
- TLS-Verifikation konfigurierbar (`S3_VERIFY_TLS`, `S3_CA_BUNDLE`) für
  On-Prem-Ceph mit interner/self-signed CA.

Multipart-Upload (boto3-Default, 8 MB Threshold) wird von allen
Zielimplementierungen unterstützt — kein Sonderhandling.

**5. Kein Migrationsskript local→s3.** Nur neue Instanzen starten mit
`STORAGE_BACKEND=s3`; bestehende local-Instanzen bleiben unverändert. Ein
Sync-Kommando kann bei Bedarf später nachgeliefert werden, ist aber jetzt
spekulative Komplexität (YAGNI). DB-Schema bleibt unverändert, Keys sind
backend-agnostisch — ein Cutover wäre rein konfigurativer Natur.

**6. Nicht-Ziele klar abgegrenzt.** Logos/Themes (`media_root/logos`, `themes/`)
und Batch-Import-Staging (`_batch_imports`) bleiben lokal — Instanz-Konfiguration
bzw. temporäre Dateien, kein Skalierungsproblem. MinIO wird nur als Dev-Stack-
Option zum Testen ohne Cloud-Account mitgeliefert, nicht im Basis-/Prod-Compose.
Private Medien (`is_public: false`) werden durchs Backend gestreamt, nicht über
Presigned-URLs — sonst Auth-Bypass am nginx-`auth_request`-Gate vorbei.

## Historischer Follow-up: Silo statt MinIO

Stand des damaligen Vorschlags; externe Release-/Security-Angaben sind keine
aktuelle Freigabe und müssen vor einem Wechsel neu geprüft werden. Im
Repository bleibt MinIO der Dev-Companion. Silo
ist als späterer Ersatz bevorzugt: Der aktiv gepflegte AGPL-Fork hält das
S3-Protokoll, `MINIO_*`-Variablen und das On-Disk-Format kompatibel und liefert
ein arm64-Container-Image [1]. Der Wechsel bleibt auf
`docker-compose.minio.yml` begrenzt und erfolgt erst mit einem veröffentlichten
Silo-Release, das SN-2026-011 enthält; das letzte veröffentlichte Server-Release
ist davon noch betroffen, während der Fix nur auf `main` liegt [2]. Dann Image
per Digest pinnen und Upload, Pyramid-Generierung sowie Cantaloupe-IIIF gegen
den lokalen S3-Dienst prüfen. Basis- und Produktions-Compose bleiben
provider-neutral.

# Betroffene Stellen

- `backend/src/katalon/core/media_storage.py` — Protokoll + LocalStorage + S3Storage + `get_storage()`
- `backend/src/katalon/config.py` — `storage_backend`, `s3_*`-Einstellungen
- `backend/src/katalon/api/v1/media.py` — Upload (Tempfile → MIME-Check → `put_file`), `/file` (`StreamingResponse` bei s3, `FileResponse` bleibt bei local), Delete
- `backend/src/katalon/workers/media_tasks.py` — Pyramid: `read_bytes` → `pyvips.Image.new_from_buffer` → `put_bytes`
- `backend/src/katalon/workers/purge_tasks.py` — `delete()`
- `backend/src/katalon/services/preservation_service.py`, `services/ai_service.py` — Bytes statt Pfad (`BytesIO`)
- `backend/src/katalon/main.py` — `_check_media_root_writable` nur bei `local`
- `docker-compose.s3.yml` (neu), `docker-compose.minio.yml` (neu, Dev-only), `Dockerfile.*` — boto3-Dependency

Die `MEDIA_ROOT`-Bind-Mounts bleiben auch im S3-Betrieb bestehen: Logos und
Portal-Themes liegen weiterhin lokal, nur die Medien-Dateien laufen über S3.
Die Pyramid-TIFF-Ableitung lädt den Master bei S3 in eine Temp-Datei, konvertiert
mit dem unveränderten `_make_pyramid_tiff` (pyvips braucht Random-Access) und
lädt die Pyramide hoch; fehlende Master fallen wie bei local aufs Original zurück.

Siehe auch [IIIF-Pyramid-TIFF](iiif-pyramid-tiff.md), [Medien-Sichtbarkeit und
Cantaloupe-Gate](media-visibility-und-cantaloupe-gate.md), GitHub-Issue #121.

# Citations

[1] https://github.com/pgsty/silo
[2] https://github.com/pgsty/silo/releases/tag/RELEASE.2026-09-03T13-18-01Z
