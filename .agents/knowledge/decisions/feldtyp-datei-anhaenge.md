---
type: Decision
title: Feldtyp "Datei" mit eigener Anhang-Tabelle statt polymorpher Medien
status: accepted
date: 2026-11-10
---

# Kontext

Erfassende wollen an Datensätze Dateien hängen, die keine Digitalisate des Objekts sind: einen Leihvertrag an einem Vorgang, ein Interview-Video an einer Person, ein Programmheft-PDF an einem Werk. Medien hingen bisher nur an Objekten (`MediaFile.object_id`). Ein PDF an einem Objekt landete in der Medienleiste neben den Digitalisaten.

#442 löst den Bedarf über eine Erweiterung von `media_files` auf weitere Typen (polymorph, `record_type` + `record_id`). Das würde Hauptmedium, IIIF-Pipeline, Rechte pro Datei und Reihenfolge auch für Anhänge öffnen, die diese Eigenschaften nicht brauchen. Jede Medienabfrage müsste dann Anhänge ausfiltern, und der Fremdschlüssel auf `objects` müsste polymorph werden. Dazu kommen IIIF-Autorisierung, Export und Batch-Import.

# Entscheidung

1. **Eigene Tabelle `attachments`**, unabhängig von `media_files`. Die Tabelle speichert Datensatztyp, Datensatz-ID, Originalname, geprüften MIME-Typ, Größe, Speicherschlüssel und Anleger. Sie speichert keinen Feldnamen und keinen Pfad in einer Gruppe. Wo eine Datei steht, ergibt sich allein aus den aktuellen Metadaten des Datensatzes. #442 bleibt als eigener Weg für Medien an weiteren Typen offen.
2. **Feldtyp `file`** ist für `object`, `entity`, `place`, `occurrence` und `procedure` erlaubt, top-level und als Unterfeld einer Gruppe. Für `collection`, `storage_location` und `vocabulary_term` ist er nicht erlaubt (`schema_admin.py`).
3. **Feldwert** im JSONB enthält `id`, `filename`, `mime_type` und `size`. Beim Speichern prüft das Backend jede referenzierte ID: Sie muss zu genau diesem Datensatz (Typ und ID) gehören. Danach schreibt das Backend die drei Angaben aus der Tabelle in den Wert. Client-Angaben zu Name, Typ und Größe landen nicht in den Metadaten.
4. **Sichtbarkeit nur pro Feld und Unterfeld** (Variante A der offenen Frage). Es gibt kein Flag pro Datei. Lizenz, Rechteinhaber und Credit-Line gibt es in Phase 1 nicht. Interne Dateien liegen in nicht öffentlichen Feldern. Das Feld-Modell reicht für den Fall „interne Verträge, öffentliche Programmhefte“.
5. **Portal-Auslieferung wird bei jedem Aufruf neu geprüft** (`GET /portal/v1/attachments/{id}/file`). Der Datensatz muss öffentlich sichtbar sein und darf kein Vorgang sein. Die ID muss in der öffentlichen Projektion des aktuellen Datensatzes stehen (`filter_public_metadata_checked` plus `public_attachment_ids`). Fehlt die Datei im Feld, ist sie sofort nicht mehr abrufbar, auch wenn sie physisch noch liegt. Die Antwort kommt ohne Cache (`no-store`).
6. **Admin-Auslieferung** über `GET /v1/attachments/{id}/file` mit Leserecht auf den Datensatztyp. Für Video und Audio gibt es einen signierten Link (`GET /v1/attachments/{id}/link`). Er ist ein HMAC über Anhang-ID, Benutzer-ID und Ablaufzeit, gültig 5 Minuten (300 Sekunden). Der Stream-Endpunkt prüft beim Abruf erneut, dass der Benutzer aktiv ist und das Leserecht hat. PDF und Bild dürfen den Blob-Weg der Admin-Oberfläche nutzen.
7. **Aufräumen über einen Verwaltungsbefehl**: `katalon-manage attachments-gc --older-than 7d` (Standard 7 Tage). Der Befehl löscht Anhänge, deren ID weder in den aktuellen Metadaten des Datensatzes (auch im Papierkorb) noch in einem Snapshot vorkommt. Anhänge ohne Datensatz gelten als verwaist. Der Betrieb plant den Befehl per Cron ein. Es gibt keinen Celery-Beat-Job dafür.

# Begründung

- Dateien an einem Vertrag oder einem Programmheft brauchen keine Medienpipeline. Eine eigene Tabelle hält Medien und Anhänge getrennt, ohne bestehende Medienabfragen, IIIF-Autorisierung oder Exporte zu ändern. Der Bestand bleibt unberührt.
- Die Prüfung über die aktuellen Metadaten statt über gespeicherte Feldpfade bleibt korrekt, wenn Gruppeneinträge umsortiert, Unterfelder verschoben oder Snapshots wiederhergestellt werden.
- Die Prüfung beim Speichern schließt aus, dass eine ID aus einem anderen Datensatz (etwa einem internen Vorgang) in ein öffentliches Feld geschrieben und damit veröffentlicht wird.
- Die Portal-Auslieferung prüft dieselbe öffentliche Projektion wie die Ausgabe der Metadaten. Das folgt dem Muster der Relationsfelder (fail closed).
- Signierte Links sind nötig, weil `<video>` keinen Bearer-Header senden kann. Ein Blob-Weg würde große Videos vor dem Abspielen vollständig laden.
- Ein Befehl statt Beat-Job hält den Betrieb in der Hand der Institution. Die Frist 7 Tage schützt Uploads, die noch nicht gespeichert wurden, und lässt zugleich Snapshot-Wiederherstellung zu.
- Sichtbarkeit pro Feld reicht für Phase 1. Eine Flag pro Datei oder Rechteangaben lassen sich später in `attachments` nachrüsten, ohne den Feldwert zu ändern.

# Konsequenzen

- Entfernen einer Datei aus einem Feld wirkt nach dem Speichern. Die Datei bleibt bis zum GC-Lauf im Speicher, damit Snapshots wiederherstellbar sind.
- Endgültiges Löschen eines Datensatzes (nächtlicher Purge oder manueller Purge bei Objekt, Entität, Ort und Occurrence) löscht die Anhang-Zeilen und die Dateien. Schlägt das Löschen einer Datei im Speicher fehl, bleibt die Datei ohne Zeile liegen, und GC findet sie nicht. Vorgänge haben keinen Papierkorb; `DELETE /v1/procedures/{id}` ruft denselben Helper direkt auf.
- Ein Downgrade der Migration `0088` löscht nur die Tabelle. Dateien und Referenzen bleiben zurück und müssen vorher per Purge entfernt werden.
- Anhänge gehen nicht in den Export-Kontext (OAI-PMH, LIDO, Mapping-Exporte) und nicht in den Suchindex. Dateinamen und IDs werden dort verworfen. Der RDF-Export serialisiert Metadatenwerte nicht generisch und gibt Dateiwerte deshalb nicht aus.
- Der Upload-Grenzwert `ATTACHMENT_MAX_UPLOAD_MB` (Standard 200) muss kleiner oder gleich dem `client_max_body_size` der äußeren nginx sein. Die Admin-nginx-Konfiguration (200 MB) ist nur ein Debug-Zugang.
- Spätere Anforderungen an Rechte pro Datei, Lizenzen oder Sichtbarkeit pro Datei sind eine neue Entscheidung und erweitern `attachments`.

# Citations

- `backend/src/katalon/core/models.py` (Klasse `Attachment`)
- `backend/migrations/versions/0088_attachments.py`
- `backend/src/katalon/services/attachment_service.py`
- `backend/src/katalon/api/v1/attachments.py`
- `backend/src/katalon/api/v1/portal_public.py` (`get_public_attachment_file`)
- `backend/src/katalon/services/public_metadata_service.py` (`public_attachment_ids`)
- `backend/src/katalon/services/schema_service.py` (`validate_metadata`, Aufruf der Referenzprüfung)
- `backend/src/katalon/api/v1/schema_admin.py` (erlaubte Zieltypen)
- `backend/src/katalon/workers/purge_tasks.py` (`purge_record_attachments` im Purge-Pfad)
- `backend/src/katalon/api/v1/procedures.py` (Löschpfad ruft `purge_record_attachments`)
- `backend/src/katalon/management/cli.py` (`attachments-gc`)
- `backend/src/katalon/config.py` (`attachment_max_upload_mb`)
- `.agents/knowledge/decisions/media-visibility-und-cantaloupe-gate.md`
- `.agents/knowledge/decisions/oeffentliche-projektion-relationsfelder.md`
- Offen, nicht entschieden: Medien für weitere Typen (#442)
