---
type: Decision
title: Manueller Admin-Purge teilt Logik mit Nightly-Sweep; Retention/Enable wandern von env-var in AdminConfig
description: POST /{id}/purge (admin-only) ruft dieselbe _purge_records-Logik wie der nächtliche Celery-Job auf statt eigener Kopie; auto_purge_enabled+purge_retention_days sind jetzt DB-Singleton (AdminConfig) statt settings.purge_after_days, damit Admins die Aufbewahrungsfrist ohne Neustart per UI ändern/abschalten können (#414-Folgearbeit).
tags: [backend, purge, soft-delete, admin-config, celery, api-design]
timestamp: 2026-09-19T00:00:00Z
---

# Kontext

Issue #414 deckte auf, dass Schema-Migrationen (`purge_field_data`,
`migrate_translatable_shape`, `migrate_repeatable_shape`) Datensätze im
Papierkorb (`deleted_at` gesetzt) beim Query-Filter ausschlossen — nach
Restore driftete die Datenform vom aktuellen Schema weg. Beim Fixen (Filter
entfernen) wurde der Umfang um folgende Punkte ergänzt: Admin-UI für
Papierkorb/Restore/Hard-Delete pro Record existierte im Frontend gar nicht
(nur Backend-Routen `restore`/`trash/list`), und die bestehende nächtliche
Auto-Purge (`purge_tasks.py`, `settings.purge_after_days`, Default 30 Tage)
war nur über env-var einstellbar, ohne Deaktivierungsmöglichkeit.

# Entscheidung

1. **Manueller Purge teilt Code mit dem Sweep.** `_purge_type` (nightly,
   iteriert über `deleted_at < cutoff`) wurde in `_purge_records` (generische
   Kernlogik: Media-Two-Phase-Delete, Relations-Cleanup, Audit) + dünnen
   Wrapper zerlegt. `purge_record_now(session, record_type, record_id,
   user_id)` prüft nur "existiert und ist soft-deleted", ruft dann
   `_purge_records` mit `cutoff=None` für genau einen Record auf. Kein
   Duplikat der Media-Handling-Logik im Endpoint.
2. **Retention + Enable-Flag wandern in `AdminConfig`** (Singleton-Row,
   existierendes Muster) statt `settings.purge_after_days` (env-var,
   Neustart nötig). Neue Felder `auto_purge_enabled: bool = True`,
   `purge_retention_days: int = 30`. `_do_purge()` liest beide vor jedem
   Lauf, überspringt komplett wenn `auto_purge_enabled=False`.
3. **Echtes Bool statt Zahlen-Konvention fürs Abschalten.** Verworfen:
   "sehr hohe Zahl = de facto aus". Begründung: nicht selbsterklärend, und
   `purge_retention_days=0` hätte sofortiges Massen-Purgen ausgelöst statt
   Deaktivierung — genau die Art Bug, die #414 überhaupt auslöste. Zwei
   getrennte Felder sind für Admin-UI klarer und fehlerresistenter.
4. **Manueller Purge-Endpoint pro Typ (`POST /{id}/purge`), `require_role
   ("admin")`.** Deckt `admin` UND `superuser` ab, weil `require_role`
   Superuser immer durchlässt (siehe RBAC-Notiz unten) — kein separater
   Superuser-Check nötig. 404 wenn Record nicht existiert oder nicht
   soft-deleted (kein Hard-Delete aktiver Records über diesen Weg möglich).
   Gilt für object/entity/place/occurrence/collection/storage_location;
   **nicht** für `procedure` (kein `deleted_at`-Lebenszyklus, archiviert
   statt soft-deleted) oder `vocabulary_term` (eigener Löschmechanismus).

# RBAC-Nebenfund (nicht Teil dieser Entscheidung, nur dokumentiert)

`admin` und `superuser` haben in `ROLE_CAPABILITIES` identische Capability-
Sets, aber `require_role()` gibt `superuser` einen unconditional Bypass
jeder Rollenprüfung, während `admin` nur Prüfungen mit editor/cataloger-
Anforderung automatisch besteht. Für einen Endpoint, der exakt `admin`
verlangt (wie hier), deckt das trotzdem beide Rollen ab. Ein Endpoint, der
stattdessen exakt `require_role("superuser")` verlangen würde, würde `admin`
umgekehrt ausschließen — im Code aktuell nirgends genutzt, aber als Falle
für künftigen Code notiert.

# Folgeschritte

Der Frontend-`canDelete`-Abgleich erfolgt über `GET /v1/users/me/record-permissions`.
Der Endpoint liefert ausschließlich die effektiven Rechte der angemeldeten Person,
einschließlich des Admin-/Superuser-Bypasses; das Frontend leitet daraus die
Löschaktionen der Datensatzlisten und Lagerorte ab. Der Lagerort-Screen nutzt seine
bereits vorhandenen `trashList`-, `restore`- und `purge`-Methoden nun über eine
admin-exklusive Papierkorbansicht. Damit bleibt die aktive Baumansicht frei von
gelöschten Knoten und ein endgültiges Löschen weiterhin eine explizite Bestätigung.
