# Frontend Coding Rules (React / TypeScript)

Gilt für `frontend/admin/` und `frontend/portal/`. Extrahiert aus `tsconfig.json`, root `AGENTS.md`.

## Tooling & Ausführung

- Zwei getrennte Vite/React/TS-Apps, kein Root-`package.json` — Kommandos immer mit `pnpm` aus `frontend/admin/` bzw. `frontend/portal/` ausführen.
- `pnpm run lint` → `eslint src` vor Commit (nur Admin hat ein `lint`-Skript und CI lintet nur Admin; im Portal `pnpm exec eslint <pfade>` direkt).
- `pnpm run build` → `tsc && vite build` — TypeScript-Fehler blockieren den Build, nicht nur den Linter.
- Admin und Portal: `pnpm test` → Vitest, Tests als `src/**/*.test.ts(x)` neben dem Code; läuft mit `tsc --noEmit` in CI (`.github/workflows/frontend.yml`).
- Abhängigkeiten: CI lässt `pnpm audit --audit-level=high` je App laufen (Security-Workflow). Advisories in transitiven Paketen per `overrides` in `pnpm-workspace.yaml` der App auf eine gepatchte Version derselben Major heben, Lockfile mitcommitten.
- TypeScript `strict: true` (siehe `tsconfig.json`), Pfad-Alias `@/*` → `src/*`.

## Muster, die im Code bereits gelten (einhalten)

- **Kein `any`** — Codebase ist aktuell frei davon, das soll so bleiben.
- **Kein `console.log`** im committeten Code.
- `dangerouslySetInnerHTML` nur mit `DOMPurify`-Sanitisierung, nie roh.
- Screen-Komponenten unter `src/components/screens/` — Schema/Formular/Vokabular/Beziehungen folgen dem bestehenden `Screen*.tsx`-Namensschema (siehe "Full-Stack Exploration Rule" in `AGENTS.md` für die Backend↔Frontend-Zuordnung).
- **Bestätigungs-/Lösch-Dialoge: nie `window.confirm`/`window.alert`.** Zwei bestehende Bausteine, je nach Komplexität:
  - `ui/ConfirmModal.tsx` — Ersatz für `window.confirm()` (Titel optional, Nachricht, Confirm/Cancel-Label, `danger`-Variante). Für einfache Ja/Nein-Bestätigungen; siehe Verwendung in `ScreenStorageLocation.tsx`, `ScreenForm.tsx` (`confirmState`-Pattern).
  - Dedizierte `*Modal.tsx`-Komponenten (`DeleteFieldModal`, `DeleteTermModal`, `BatchEditModal`, `AddToWorkingSetModal`) — für Dialoge mit mehreren Optionen/Radio-Buttons/eigenem Ladezustand. Teilen sich die `batch-modal-backdrop`/`batch-modal`-CSS-Klassen statt eigenes Modal-Markup zu erfinden.
  - Mehrstufige Lösch-Bestätigung bei `409`-Konflikten (z. B. verknüpfte Datensätze, künftig auch Kind-Elemente in `parent_id`-Hierarchien — siehe Backend-Regel dazu) folgt dem `ConflictError`-Retry-Muster aus `ScreenList.tsx::handleDelete`: erster Confirm, bei `ConflictError` zweiter Confirm mit Konfliktdetails und `force`/dediziertem Flag im Retry-Call, statt den Fehler nur anzuzeigen.
- **Wiederverwendung bestehender UI-Muster & Dropdowns (strikte Regel):**
  - **Keine Ad-hoc-Styles oder unpassenden nativen Widgets wie `<datalist>` einführen.** Katalon hat für alle gängigen Interaktionsfälle etablierte Komponenten und Patterns.
  - **Dropdowns, Comboboxen & Such-Picker:** Wenn ein Dropdown/Autocomplete gebraucht wird, darf kein fremdes Verhalten oder rohes `<datalist>` erfunden werden. Sie müssen zwingend dem etablierten Katalon-Muster (wie in `FieldSearch`, `NoteTypeSearch`, `SpecimenPicker`) folgen:
    1. Standard-Eingabefeld (`className="fld"`), bei löschbaren Werten mit integriertem `X`-Clear-Button.
    2. Floating Panel (`role="listbox"`, `background: var(--panel, #fff)`, `border: 1px solid var(--border)`, `borderRadius: 8`, `boxShadow: 0 4px 16px rgba(0,0,0,.08)`, `maxHeight: 240`, `overflowY: auto`).
    3. Optionen als bündige Ghost-Buttons (`btn sm gh`, `textAlign: left`, `justifyContent: flex-start`, `aria-selected`).
    4. **Interaktionsstandard:** Klick/Fokus ins Feld öffnet sofort die vollständige Liste aller Optionen (nicht vorab durch den aktuellen Text gefiltert); Tippen filtert live (ggf. zweisprachig wie bei Metadatenfeldern und LoC-Notiztypen); Klick außerhalb oder Escape schließt das Menü; falls Freitext erlaubt ist, kann dieser per Enter oder Klick auf eine explizite Freitext-Option übernommen werden.
  - Vor dem Implementieren neuer Bedienelemente **zwingend** in vorhandenen Screens nachschlagen, wie ähnliche Elemente dort aufgebaut und gestylt sind.

## Übersetzbarkeit (Pflicht)

- **Jede sichtbare Zeichenkette ist übersetzbar** und liegt mindestens auf Deutsch und Englisch vor: Beschriftungen, Platzhalter, `title`/`aria-label`, Badges, Tooltips, Fehler- und Hinweistexte, Ergebniszeilen. Keine fest kodierten deutschen oder englischen Texte in JSX oder Template-Strings.
  - Admin: `react-i18next`, Texte in `src/i18n/locales/{de,en}/<namespace>.json` (bzw. `de.json`/`en.json`), neue Namespaces in `src/i18n/index.ts` registrieren. Werte mit Platzhaltern (`{{name}}`) statt String-Verkettung.
  - Portal: `t()` aus `src/i18n`, Texte in `src/i18n/locales/de.ts` und `en.ts`.
  - Datums- und Zahlenformate mit der aktiven Sprache (`i18n.language` bzw. Portal-Locale), nicht fest mit `'de'`.
- **Vor jedem Commit prüfen**, ob die geänderten Dateien neue fest kodierte Texte enthalten (z. B. Suche nach Umlauten oder deutschen Wörtern in `.tsx`), und ob beide Sprachdateien dieselben Schlüssel haben. Für die Admin-Namespaces prüft das `src/i18n/localeParity.test.ts`.
- Werden bestehende fest kodierte Texte in einer angefassten Datei gefunden, mit übersetzen oder als offenen Punkt benennen.

## Kritische Build-Konfiguration — nicht ohne Test ändern

`docker/Dockerfile.admin`: `VITE_BASE_PATH=/admin/` ist deployment-kritisch. Ohne diesen Wert baut Vite Assets mit absolutem Pfad `/assets/`, den das äußere nginx zum Portal statt zum Admin-Container routet — Admin-UI lädt dann nicht (404 für JS/CSS), ohne dass der Build selbst fehlschlägt. Vor jeder Änderung an `docker/Dockerfile.admin`, `docker/nginx.admin.conf` oder `frontend/admin/vite.config.ts` explizit prüfen, ob `VITE_BASE_PATH` und nginx-`location`-Blöcke konsistent bleiben. Nach Deploy `https://<instanz-host>/admin/` im Browser öffnen und JS/CSS-Requests in DevTools prüfen.

## Ports (nicht verwechseln)

- `http://localhost/admin/` und `http://localhost/` (Port 80 über äußeres nginx) = **Standard für Browser-Checks** im normalen Compose-Stack.
- `3000`/`3001` = Admin/Portal-Container **direkt**, nur zum Container-Debugging. **Nicht für normale Browser-Checks** (durch `VITE_BASE_PATH=/admin/` liefert `localhost:3000/` weiße Seite wegen fehlschlagendem Asset-Loading).
- `4000`/`4001` = Admin/Portal **nur** im Dev-Compose-Stack (`docker-compose.dev.yml`).
- `5173`/`5174` = Admin/Portal bei lokaler Entwicklung ohne Docker (`pnpm run dev`).
## Citations

[1] `frontend/admin/tsconfig.json`, `frontend/admin/package.json`
[2] Root `AGENTS.md`, Abschnitte "Kritische Build-Konfigurationen", "Port-Regel Dev vs. Prod-Compose"
[3] `docs/CODE_QUALITY_ASSESSMENT.md`
