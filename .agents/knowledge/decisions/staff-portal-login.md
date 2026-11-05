---
type: Decision
title: Staff-Login im Portal statt zweitem Account-System
description: Bestehende Katalon-Staff-Konten erhalten im Portal interne Lesesicht; künftige öffentliche Accounts bleiben getrennt.
tags: [portal, authentication, staff]
timestamp: 2026-08-31T00:00:00Z
---

# Kontext

Interne Mitarbeitende brauchen für Recherche und Sichtprüfung im Portal auch
Entwürfe und nicht öffentliche Felder. Öffentliche Registrierung, Merkliste,
Workspace, gespeicherte Suchen und Kommentare sind ein späteres Produkt.

# Entscheidung

Das Portal verwendet die vorhandenen `/v1/auth/token`-JWTs und akzeptiert nur
die bekannten Staff-Rollen. Datensätze bleiben dabei an die bestehenden
Backend-Leserechte gebunden. Ein späterer öffentlicher Account-Typ fällt ohne
neuen Portal-Code auf die anonyme Projektion zurück.

# Begründung

Eine zweite Benutzerverwaltung, SMTP-Registrierung und eigene
Portal-Berechtigungen lösen kein aktuelles Problem. Die explizite Staff-Liste
verhindert zugleich, dass ein späterer öffentlicher Account versehentlich
interne Metadaten erhält.

# Citations

[1] `backend/src/katalon/api/v1/portal_public.py`
[2] `frontend/portal/src/api/client.ts`
