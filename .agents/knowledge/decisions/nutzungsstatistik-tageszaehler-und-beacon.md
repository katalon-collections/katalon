---
type: Decision
title: Nutzungsstatistik als anonyme Tageszähler, Aufrufe per Beacon
status: accepted
date: 2026-11-09
---

# Kontext

Institutionen wollen sehen, wie oft Datensätze im Portal aufgerufen und Dateien
heruntergeladen werden, ohne Analyse-Dienst, Consent-Banner oder Personenbezug.
Anonyme Portal-Reads sind 60 Sekunden öffentlich cachebar, und das Portal lädt
dieselben Detail-Endpoints auch für Relationstitel.

# Entscheidung

- Tabelle `record_usage_daily` (Typ, ID, Tag, `views`, `downloads`), atomarer
  Upsert pro Ereignis. Keine IP, kein Cookie, keine Sitzung.
- Aufrufe zählt ein `POST` der Portal-Detailseiten, nicht der Detail-`GET`.
- Downloads zählt nur der Attachment-Endpoint `/portal/v1/media/{id}/download`,
  den das Portal nur bei `portal_config.media_download_enabled` anbietet und
  sonst für Anonyme sperrt. Inline-`/file` (Range-Requests beim Abspielen) zählt nicht.
- Nicht gezählt: Staff, Bot-User-Agents, nicht öffentliche Datensätze.
- Globaler Schalter `admin_config.usage_stats_enabled`, Portal-Anzeige
  `portal_config.show_usage_stats` getrennt.

# Begründung

Ein serverseitiger Zähler am Detail-`GET` würde durch den Cache zu wenig und durch
Titelabfragen zu viel zählen. Der Beacon läuft nur bei echtem Seitenaufruf, und
Bots ohne JS landen ohnehin auf der SEO-Seite. Tageszeilen genügen für „gesamt“
und „30 Tage“; ein Redis-Puffer mit Flush-Job lohnt bei der Last kleiner
Häuser nicht. Zahlen sind manipulierbar (anonymer POST), das Rate-Limit begrenzt
das; sie sind Orientierung, keine Abrechnungsgrundlage.

# Citations

- `backend/src/katalon/services/usage_service.py`
- `backend/src/katalon/api/v1/portal_public.py` (`record_view`, `download_portal_media_file`)
- `backend/migrations/versions/0087_record_usage_stats.py`
- `backend/tests/integration/test_usage_stats.py`
