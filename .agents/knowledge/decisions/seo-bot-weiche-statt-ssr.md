---
type: Decision
title: SEO-Meta-Tags per Bot-Weiche statt SSR
description: Das Portal bleibt eine reine SPA; nginx leitet bekannte Crawler per User-Agent auf einen Backend-Renderer um, der Meta-Tags und schema.org-JSON-LD aus der öffentlichen Projektion liefert (#440).
tags: [seo, nginx, portal, schema-org, sitemap]
timestamp: 2026-10-25T00:00:00Z
---

# Kontext

Helmet setzt `title`, `description` und `og:*` erst per JavaScript. Link-Preview-Bots (Facebook, LinkedIn, Slack, Mastodon, WhatsApp) und die meisten KI-Crawler führen kein JS aus und sahen nur die leere HTML-Shell.

# Entscheidung

- nginx: `map $http_user_agent $seo_bot` + `if`-Weiche im bestehenden Record-`location` (neben `$rdf_negotiated`), Umschreibung auf `/portal/v1/seo/{plural}/{id}`.
- Backend: `services/seo_service.py` rendert ein minimales HTML (Tags + `<noscript>`-Kurzfassung + schema.org-JSON-LD, ein fester Typ pro Datensatztyp), ausschließlich aus der öffentlichen Projektion. Nicht öffentliche Records: 404.
- `/sitemap.xml` im Backend (`crawlers.py`), `Sitemap:` in `robots.txt`.
- Titel- und Beschreibungslogik lebt in Python und im Portal-Helmet (bewusste kleine Dublette).

# Begründung

- Kein SSR-Framework, kein Prerender-Dienst, kein zweiter Build: ein Endpoint und ein `map`.
- Humane Besucher und unbekannte Bots bleiben unverändert bei der SPA, der Inhalt der Bot-Antwort entspricht dem der Seite (kein Cloaking).
- schema.org dient der Auffindbarkeit im Web, nicht dem fachlichen Austausch (dafür CIDOC-CRM/LIDO/EDM); deshalb nur wenige Felder (`name`, `description`, `image`, `url`, `identifier`), weil Feldnamen pro Instanz konfigurierbar sind.

# Nachteile

- Die UA-Liste muss in drei nginx-Configs gepflegt werden; unbekannte Bots sehen weiter die Shell.
- Hinter einem eigenen Proxy muss `User-Agent` durchgereicht werden.

# Citations

[1] `docker/nginx.conf`, `backend/src/katalon/services/seo_service.py`, `backend/src/katalon/api/v1/crawlers.py`, Issue #440
