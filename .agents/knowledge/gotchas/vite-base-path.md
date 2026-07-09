---
type: Gotcha
title: VITE_BASE_PATH fehlt → Admin-UI lädt nicht, kein Build-Fehler
description: Ohne VITE_BASE_PATH=/admin/ baut Vite Assets mit /assets/, das äußere nginx routet zum Portal statt Admin — 404 für JS/CSS, Build selbst grün.
tags: [frontend, deployment, nginx, vite]
timestamp: 2026-07-09T00:00:00Z
---

# Symptom

Admin-UI zeigt leere Seite oder lädt nicht nach Deploy. Kein Fehler beim Docker-Build.

# Ursache

`docker/Dockerfile.admin` ohne `VITE_BASE_PATH=/admin/` lässt Vite Assets mit
absolutem Pfad `/assets/...` bauen. Das äußere nginx routet `/assets/` zum
Portal-Container, nicht zum Admin-Container — falsche Laufzeit-Pfade, aber der Build
läuft durch, weil Vite den Pfad syntaktisch korrekt generiert.

# Fix / Vorbeugung

`VITE_BASE_PATH=/admin/` in `docker/Dockerfile.admin` nicht ändern ohne Test der
Produktionsumgebung. Siehe
[Playbook: Admin-Deploy-Verifikation](../playbooks/admin-deploy-verifikation.md).

# Citations

[1] Root `AGENTS.md`, Abschnitt "Kritische Build-Konfigurationen – NICHT ÄNDERN ohne Test"
