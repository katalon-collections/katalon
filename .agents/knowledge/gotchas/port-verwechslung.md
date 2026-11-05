---
type: Gotcha
title: Port-Verwechslung Dev- vs. Prod-like Compose-Stack
description: 3000/3001 = normaler Stack, 4000/4001 = nur Dev-Compose-Stack, 5173/5174 = lokal ohne Docker. Ohne expliziten Dev-Hinweis immer 3000/3001 für Browser-Checks.
tags: [ports, docker, dev-workflow]
timestamp: 2026-07-09T00:00:00Z
---

# Symptom

Browser-Check schlägt fehl oder zeigt falsche/alte Version, weil der falsche Port für
den gerade laufenden Compose-Stack verwendet wurde.

# Regel

| Port | Kontext |
|------|---------|
| `3000` / `3001` | Admin/Portal im normalen bzw. production-like Compose-Stack — **Standard**, wenn Dev-Stack nicht explizit erwähnt wird |
| `4000` / `4001` | Admin/Portal **nur** im Dev-Compose-Stack (`docker-compose.dev.yml`) |
| `5173` / `5174` | Admin/Portal bei lokaler Entwicklung ohne Docker (`npm run dev`) |

# Citations

[1] Root `AGENTS.md`, Abschnitt "Port-Regel Dev vs. Prod-Compose"
[2] `.agents/DEV.md`
