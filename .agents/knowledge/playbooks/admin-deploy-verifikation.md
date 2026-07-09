---
type: Playbook
title: Admin-Deploy-Verifikation (VITE_BASE_PATH)
description: Nach jedem Deploy, das Dockerfile.admin/nginx.admin.conf/vite.config.ts berührt, Admin-UI im Browser auf 404 für JS/CSS prüfen.
tags: [deployment, admin, gotcha]
timestamp: 2026-07-09T00:00:00Z
---

# Trigger

Änderung an `docker/Dockerfile.admin`, `docker/nginx.admin.conf` oder
`frontend/admin/vite.config.ts` — oder jeder Deploy danach.

# Warum

`VITE_BASE_PATH=/admin/` in `docker/Dockerfile.admin` ist deployment-kritisch. Fehlt
der Wert, baut Vite Assets mit absolutem Pfad `/assets/`, den das äußere nginx zum
Portal statt zum Admin-Container routet. Der Build selbst schlägt dabei **nicht** fehl
— die App lädt einfach nicht (siehe
[Gotcha: VITE_BASE_PATH](../gotchas/vite-base-path.md)).

# Schritte

1. Vor der Änderung prüfen, ob `VITE_BASE_PATH` und nginx-`location`-Blöcke konsistent
   sind.
2. Nach dem Deploy `https://katalon.kraegelin.dev/admin/` im Browser öffnen.
3. DevTools → Network: JS/CSS-Requests müssen 200 liefern, nicht 404.

# Citations

[1] Root `AGENTS.md`, Abschnitt "Kritische Build-Konfigurationen"
[2] `.agents/rules/frontend.md`
