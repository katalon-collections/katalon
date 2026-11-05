---
type: Decision
title: Presence Lock — generische edit_presence-Tabelle + Heartbeat/TTL statt Cleanup-Worker
description: "Soft Lock zeigt an, wer einen Record gerade offen hat; Admin-Setting warning/blocking; blocking erzwingt 409 serverseitig bei allen 7 Kerntypen. Kein Cleanup-Job, kein WebSocket."
tags: [concurrency, backend, frontend, ux]
timestamp: 2026-09-09T09:20:00Z
---

# Kontext

Issue #371 (Entwurf für "Record locking & concurrent editing
protection"). Optimistic Locking ([[optimistic-locking]]) existierte bereits
vollständig (version/If-Match/409, 3-Wege-Merge) — der Entwurf führte dies
noch als offenen Scope. Tatsächlich fehlend war nur der Presence-Lock-Teil
(Phase 1) und der persistente Manual-Lock-Teil (Phase 2, damals noch offen wegen
Governance-Fragen zu Rollen).

Rollen-Abweichung: Entwurf nannte `Curator`/`Data Entry`/`Viewer`/`Administrator`,
echtes Rollenmodell ist `viewer < cataloger < editor < admin < superuser`
(`core/dependencies.py`). Die damaligen Governance-Fragen sind im heutigen Manual-Lock-Vertrag
konkretisiert, siehe [Manual Exclusive Lock](manual-exclusive-lock.md).

# Entscheidung

**1. Eine generische `edit_presence`-Tabelle** (`resource_type`, `resource_id`,
`user_id`, `session_id`, `last_seen_at`; die genaue Eindeutigkeit folgt dem
`EditPresence`-Modell),
kein Presence-Modell pro Record-Typ — analog zum bestehenden `relations`-Muster.

**2. Heartbeat alle 25s, TTL 60s, kein Cleanup-Worker.** Presence gilt als aktiv
wenn `last_seen_at >= now() - 60s`. Abgelaufene Zeilen werden einfach aus jeder
Query rausgefiltert und beim nächsten Heartbeat woanders überschrieben (Unique
Constraint macht Upsert via `ON CONFLICT DO UPDATE` möglich). Kein Celery-Task,
kein Redis, kein WebSocket — Polling reicht für ein "wer ist gerade da"-Signal.

**3. `AdminConfig.presence_lock_mode` (warning|blocking), serverseitig
durchgesetzt.** `enforce_not_blocked()` läuft in allen 7 PUT-Endpoints
(objects/entities/places/occurrences/procedures/collections/storage_locations)
vor der Payload-Übernahme — Blocking ist nicht nur UI-Hinweis, sondern per
409 `{"error":"presence_locked","locked_by":...}` erzwungen. Umgehung über
direkten API-Call ohne Formular ist damit ausgeschlossen.

**4. Presence und Manual Lock bleiben getrennte Mechanismen.** Die
ursprüngliche Vertagung von Phase 2 ist aufgehoben: persistente manuelle
Sperren, eigene Freigabe und Admin-Force-Unlock sind implementiert.
Siehe [Manual Exclusive Lock](manual-exclusive-lock.md).

# Konsequenzen

Presence-Konflikte werden sichtbar, bevor der 3-Wege-Merge-Dialog aus
[[optimistic-locking]] überhaupt greift. Blocking-Mode hat keine Karenzzeit —
schließt der blockierende User den Tab, ist der Record nach höchstens 60s
wieder frei. `frontend/admin/src/components/screens/ScreenStorageLocation.tsx`
nutzt kein `ScreenForm` (eigenes Inline-Modal) und hat deshalb kein
Heartbeat/Badge bekommen — Blocking-Mode-Schutz greift dort serverseitig
trotzdem, nur ohne Presence-Anzeige. Nachtrag bei Bedarf.
