---
type: Decision
title: Dev-HTTPS mit Custom Hostname — Host-Prozess-Caddy statt Compose-Service
description: mkcert/Caddy als opt-in Host-Prozess vor den Dev-Compose-Ports, kein zusätzlicher Compose-Service; Vite server.allowedHosts nötig, um Proxying zuzulassen.
tags: [dev, tooling, https, dx]
timestamp: 2026-09-05T00:00:00Z
---

# Kontext

Issue #168: lokale Entwicklung läuft auf mehreren Ports (`localhost:4000`/`4001`/`8000`/`8182`),
unhandlich für Subdomain-artige URLs und für Tests, die echtes HTTPS oder einen
Custom Hostname erzwingen (OAuth-Callbacks, IIIF-Mixed-Content).

# Entscheidung

- **Opt-in, kein Compose-Service**: `caddy` läuft als Host-Prozess (`caddy run
  --config Caddyfile`) vor den bereits veröffentlichten Dev-Compose-Ports. Kein
  Eintrag in `docker-compose.dev.yml`, keine Netzwerk-Kopplung an den Stack.
- **`tls internal`** (Caddys eigene lokale CA) statt manuellem `mkcert
  <hostname>`-Zertifikatsaufruf — weniger bewegliche Teile, gleiche
  Truststore-Garantie nach `mkcert -install`.
- **`Caddyfile`** ist gitignored, `Caddyfile.example` ist die Vorlage im Repo.
- **`VITE_PORTAL_URL`** auf dem `admin`-Service wurde parametrisierbar gemacht
  (`${VITE_PORTAL_URL:-http://localhost:4001}`), damit Admin-Links auf Portal nach
  Hostname-Wechsel konsistent bleiben.

# Begründung / Blocker, der im Issue fehlte

Vite ≥5 blockt standardmäßig unbekannte `Host`-Header ("Blocked request. This host
is not allowed") — ohne `server.allowedHosts: ['.katalon.local']` in
`frontend/admin/vite.config.ts` und `frontend/portal/vite.config.ts` hätte Caddys
Proxying sofort mit diesem Fehler versagt. Kein Compose-Service zu sein hält den
Default-Dev-Stack unverändert und macche das Feature vollständig risikofrei für
alle, die es nicht nutzen.

# Abgrenzung zu katalon-cli

Betrifft ausschließlich den Source-Dev-Loop dieses Repos. `katalon-cli` verwaltet
production-artige Instanzen aus gepinnten Release-Images mit eigenem TLS-Handling
(`tls_mode=standalone` → selbstsigniertes Zertifikat via `compose_gen.py`, kein
Caddy im dortigen Repo) — siehe
[katalon-cli-Distribution](../../../almanac/decisions/operations/katalon-cli-distribution.md).
Keine geteilte Konfiguration oder Codepfad zwischen beiden.

# Citations

[1] GitHub Issue #168
[2] `docs/dev_https.md` — mkcert/Caddy als Host-Prozess und Vite-Hostfreigabe
