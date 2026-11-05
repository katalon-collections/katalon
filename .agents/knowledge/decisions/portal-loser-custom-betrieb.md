---
type: Decision
title: Portal-loser Custom-Betrieb ohne Preset-Matrix
description: Kein gepflegter Satz von Deployment-Topologien; nur ein Frontend-Flag plus dokumentiertes manuelles nginx-Rezept.
tags: [deployment, portal, admin-ui, docs]
timestamp: 2026-09-12T00:00:00Z
---

# Kontext

Issue #305 fragte nach einer Instanz-Option "kein öffentliches Portal". Naheliegend wäre eine Matrix aus einzeln
schaltbaren Flächen gewesen (Portal-Frontend, `/portal/v1`, `/oai`, `/sparql`, ARK-Resolver, `robots.txt`/`llms.txt`,
IIIF) — sieben unabhängige Schalter, kombinatorisch schnell unwartbar (2^7 Zustände), inklusive `katalon-cli`-Wizard-
Integration und mehreren gepflegten nginx-Varianten.

# Entscheidung

Kein Code für mehrere Presets. Stattdessen:

1. Ein Build-Flag `VITE_PORTAL_ENABLED` (Default an) in `frontend/admin/src/api/client.ts`, blendet in
   `ScreenForm.tsx` ("Im Portal ansehen") und `ScreenOAISets.tsx` (OAI-Endpunkt-Anzeige) die entsprechenden Links
   aus, wenn eine Instanz gezielt ohne Portal betrieben wird. Passthrough über `docker/Dockerfile.admin` als
   neuer `ARG`/`ENV`.
2. Alles Weitere (welche nginx-`location`-Blöcke tatsächlich entfernt werden, welcher Compose-Service wegfällt)
   bleibt unkodiert — nur als knappes Rezept im öffentlichen `katalon-docs`-Repo dokumentiert
   (`administration/production.md`), nicht als gepflegte zweite Compose-/nginx-Variante in diesem Repo.
3. `katalon-cli` bekommt keine Wizard-Option dafür. Wer das braucht, editiert selbst oder bucht Umsetzung.
4. Laufzeit-Sperrung (temporär, reversibel) bleibt getrennte Baustelle (#304/#377), hier nicht mitgelöst.

# Begründung

YAGNI: Zwei genannte Varianten (komplett zu / headless API) sind schon Kombinationen aus den sieben Flächen, keine
davon ist eine eigene wiederkehrende Anforderung. Ein voll konfigurierbares System wäre spekulative Flexibilität
für Institutionen, die (noch) niemand konkret angefragt hat. Die einzige echte UI-Korrektheitslücke — tote
"Im Portal ansehen"-Buttons — ist mit einem einzelnen Flag behoben; alles andere bleibt Self-Hoster-DIY mit
Anleitung statt Produktfeature.

# Citations

[1] `frontend/admin/src/api/client.ts`
[2] `frontend/admin/src/components/screens/ScreenForm.tsx`
[3] `frontend/admin/src/components/screens/ScreenOAISets.tsx`
[4] `docker/Dockerfile.admin`
[5] https://github.com/karkraeg/Katalon/issues/305
