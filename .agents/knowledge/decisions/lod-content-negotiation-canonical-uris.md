---
type: Decision
title: LOD-Content-Negotiation auf kanonischen URIs — Reverse-Proxy-Nachzug zu #363
description: record_uri_path() zeigt seit #363 auf die reine Portal-Frontend-URL statt auf eine API-Route; diese URI war bis jetzt nicht dereferenzierbar, weil die Content-Negotiation-Schicht am Reverse Proxy fehlte.
tags: [rdf, jsonld, lod, nginx, caddy, gotcha]
timestamp: 2026-09-11T00:00:00Z
---

# Kontext

Issue #363 (Commit `0148a7b`, Release 1.19.15) hat `record_uri_path()` in
`jsonld_format.py` bewusst von `{base}/api/v1/{plural}/{id}` auf
`{base}/{plural}/{id}` umgestellt — die `@id` in jedem JSON-LD-Dokument zeigt
seitdem auf die öffentliche Portal-Frontend-Route statt auf eine API-URL.

Das ist die richtige LOD-Praxis (saubere Identifier ohne `/api/`-Präfix im
URI), führt aber eine neue implizite Abhängigkeit ein: eine dereferenzierbare
LOD-URI muss über Content Negotiation (`Accept: application/ld+json` /
`text/turtle`) die maschinenlesbare Repräsentation liefern können. Die alte
API-URL-Variante war automatisch dereferenzierbar (sie *war* die API); die
neue Frontend-URL läuft aber durch die Portal-SPA (Vite-Devserver im
Dev-Setup, statisches nginx im Compose-Stack) und wusste nichts von RDF.

Diese Lücke ist bei Abschluss von #363 nicht aufgefallen, weil die dortigen
Tests (`test_jsonld_format.py`, `test_rdf_export_integration.py`) nur die
Identifier-*Zeichenkette* prüfen (host-unabhängig gleich), über den
FastAPI-TestClient direkt — ohne jede Reverse-Proxy-Schicht. Das Repo hat
keine automatisierte Prüfung, die `nginx.conf`/`Caddyfile`-Routing gegen
echtes Verhalten testet; Änderungen an URI-Schemata, die eine Infra-Schicht
voraussetzen, sind dadurch strukturell nicht abgedeckt.

# Entscheidung

- Content Negotiation für die 5 öffentlichen Typen (`object`, `entity`,
  `place`, `occurrence`, `collection`) auf ihrer kanonischen URL
  (`/{plural}/{id}`) an **beiden** Reverse-Proxy-Schichten nachgezogen:
  - `docker/nginx.conf` (Compose-Dev-Stack) und `docker/nginx.prod.conf`
    (Produktion): `map $http_accept $rdf_negotiated` + Regex-`location`, die
    bei `application/ld+json`/`text/turtle` intern auf
    `/portal/v1/{plural}/{id}` umschreibt und an `api` statt an `portal`
    proxied.
  - `Caddyfile` / `Caddyfile.example` (Host-Caddy vor den Dev-Compose-Ports,
    siehe [Dev-HTTPS-Decision](dev-https-custom-hostname.md)): äquivalenter
    `@lod_negotiated`-Matcher mit `path_regexp`/`header_regexp` +
    `rewrite`/`reverse_proxy` auf die API.
- `/portal/v1/{type}s/{id}` und `/portal/v1/{type}s/{id}/export` zusätzlich
  öffentlich (ohne Auth) gemacht — vorher hing der dokumentierte
  `llms.txt`-Contract („kein API-Key nötig") an `/v1/{type}s/{id}/export`,
  das aber hinter der globalen `_authenticated`-Dependency des
  Staff-Routers lag. `llms.txt` korrigiert auf `/portal/v1/...`.
- `docker/nginx.static.conf`/`nginx.admin.conf` (Admin-UI) bewusst nicht
  angefasst — dort gibt es keine öffentlichen Record-Detailrouten.

# Begründung

Reverse-Proxy-Regex-Locations dürfen in nginx keinen URI-Teil im
`proxy_pass` tragen (`proxy_pass http://portal;`, nicht `.../portal/;`) —
sonst Startfehler „cannot have URI part in location given by regular
expression". Ebenso muss die Regex in nginx-Configs gequotet werden, sobald
sie `{n}`-Quantifier enthält, weil der Config-Lexer `{` sonst als
Block-Anfang liest und die Regex nach dem letzten `]` vor der Klammer
abschneidet (`pcre2_compile() failed: missing closing parenthesis`).

# Citations

[1] Issue #363, Commit `0148a7b` — Einführung der Frontend-URL als kanonische `@id`
[2] Session 2026-09-11 — Root-Cause-Analyse und Nachzug der Content-Negotiation-Infra
