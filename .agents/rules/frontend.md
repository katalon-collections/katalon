# Frontend Coding Rules (React / TypeScript)

Gilt für `frontend/admin/` und `frontend/portal/`. Extrahiert aus `tsconfig.json`, root `AGENTS.md` und `docs/CODE_QUALITY_ASSESSMENT.md`.

## Tooling & Ausführung

- Zwei getrennte Vite/React/TS-Apps, kein Root-`package.json` — Kommandos immer aus `frontend/admin/` bzw. `frontend/portal/` ausführen.
- `npm run lint` → `eslint src --ext .ts,.tsx` vor Commit.
- `npm run build` → `tsc && vite build` — TypeScript-Fehler blockieren den Build, nicht nur den Linter.
- TypeScript `strict: true` (siehe `tsconfig.json`), Pfad-Alias `@/*` → `src/*`.

## Muster, die im Code bereits gelten (einhalten)

- **Kein `any`** — Codebase ist aktuell frei davon, das soll so bleiben.
- **Kein `console.log`** im committeten Code.
- `dangerouslySetInnerHTML` nur mit `DOMPurify`-Sanitisierung, nie roh.
- Screen-Komponenten unter `src/components/screens/` — Schema/Formular/Vokabular/Beziehungen folgen dem bestehenden `Screen*.tsx`-Namensschema (siehe "Full-Stack Exploration Rule" in `AGENTS.md` für die Backend↔Frontend-Zuordnung).

## Kritische Build-Konfiguration — nicht ohne Test ändern

`docker/Dockerfile.admin`: `VITE_BASE_PATH=/admin/` ist deployment-kritisch. Ohne diesen Wert baut Vite Assets mit absolutem Pfad `/assets/`, den das äußere nginx zum Portal statt zum Admin-Container routet — Admin-UI lädt dann nicht (404 für JS/CSS), ohne dass der Build selbst fehlschlägt. Vor jeder Änderung an `docker/Dockerfile.admin`, `docker/nginx.admin.conf` oder `frontend/admin/vite.config.ts` explizit prüfen, ob `VITE_BASE_PATH` und nginx-`location`-Blöcke konsistent bleiben. Nach Deploy `https://katalon.kraegelin.dev/admin/` im Browser öffnen und JS/CSS-Requests in DevTools prüfen.

## Ports (nicht verwechseln)

- `3000`/`3001` = Admin/Portal im normalen bzw. production-like Compose-Stack (Standard für Browser-Checks, wenn nicht explizit Dev-Stack gemeint ist).
- `4000`/`4001` = Admin/Portal **nur** im Dev-Compose-Stack (`docker-compose.dev.yml`).
- `5173`/`5174` = Admin/Portal bei lokaler Entwicklung ohne Docker (`npm run dev`).

## Citations

[1] `frontend/admin/tsconfig.json`, `frontend/admin/package.json`
[2] Root `AGENTS.md`, Abschnitte "Kritische Build-Konfigurationen", "Port-Regel Dev vs. Prod-Compose"
[3] `docs/CODE_QUALITY_ASSESSMENT.md`
