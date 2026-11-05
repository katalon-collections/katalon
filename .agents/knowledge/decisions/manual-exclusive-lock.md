---
type: Decision
title: Manuelle exklusive Sperre zusätzlich zu Presence und Versionsprüfung
description: Persistente Reservierung mit Besitzer, optionalem Grund und Ablauf; eigene Freigabe, Admin-Force-Unlock und Prüfung in Schreibpfaden.
tags: [concurrency, backend, frontend, governance]
timestamp: 2026-10-30T00:00:00Z
---

# Kontext

Presence zeigt eine offene Bearbeitung an und läuft nach kurzem TTL ab.
Eine bewusste Reservierung muss dagegen Tab-Schließen überleben. Die in
[Presence Lock](presence-lock.md) zunächst zurückgestellte Phase 2 ist im
aktuellen Code implementiert; dieser Nachtrag dokumentiert den bestehenden
Vertrag und führt kein neues Verhalten ein.

# Entscheidung

`resource_locks` speichert Typ/ID, Besitzer, Grund und optionales Ablaufdatum.
`POST /v1/locks` verlangt das Feature `manual_lock`. Der Besitzer kann die
Sperre aufheben; `force-unlock` verlangt `admin` oder den Superuser-Bypass.
Ein abgelaufener Eintrag gilt nicht als aktive Sperre. Setzen, Freigeben und
Force-Unlock werden auditiert. Das Objekt-/Recordformular zeigt die Sperre,
bietet Grund und Ablaufdatum an und unterscheidet eigene Freigabe von
administrativem Aufheben.

`enforce_not_locked` blockiert einen fremden aktiven Lock mit
`409 {"error":"resource_locked","locked_by":...,"reason":...}`.
Die Prüfung wird in Record-Updates sowie Import- und Batch-Schreibpfaden genutzt.
Auch ein Admin muss einen fremden Lock explizit aufheben; die Schreibprüfung
enthält keinen stillen Rollen-Bypass.

# Begründung und Grenzen

Persistenz ist hier erforderlich: eine Reservierung ist eine ausdrückliche
fachliche Aktion, kein flüchtiges Anwesenheitssignal. Presence und der
[If-Match-Vertrag](optimistic-locking.md) bleiben daneben bestehen. Eine
Sperrprüfung ist kein Ersatz für Berechtigungen oder Versionsprüfung und
behauptet nicht, beliebige direkte Datenbankschreibzugriffe zu verhindern.

# Citations

[1] `backend/src/katalon/api/v1/locks.py`
[2] `backend/src/katalon/services/lock_service.py`
[3] `backend/src/katalon/core/models.py` — ResourceLock
[4] `backend/src/katalon/workers/import_tasks.py`
[5] `backend/src/katalon/services/batch_service.py`
[6] `frontend/admin/src/components/screens/ScreenForm.tsx`
[7] `docs/rollenkonzept.md`
