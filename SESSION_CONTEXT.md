# Session Context – 2026-06-29

## Changed

- `.agents/IMPLEMENTIERUNGSPLAN.md` auf Stand `2026-06-27` aktualisiert
- `AGENTS.md` ergänzt um Full-Stack-Exploration-Regel: Backend- und Frontend-Pfade immer gemeinsam prüfen
- Release `v0.3.1` gemerged und getaggt; Issues `#241-#244` geschlossen
- `#236` umgesetzt: Portal-Inline-Relationlabels nutzen Gegenrichtung korrekt; Backend bootstrapped `relation_types` aus vorhandenen Relationscodes
- PR-Review-Fixes für `#245` lokal vorbereitet: kein doppeltes Syncen von Gruppen-Relationsfeldern, stabilere Medienrechte-UI, klarere Gruppenfehler

## Decided

- `.claude/settings.local.json` soll nicht versioniert bleiben; Datei bleibt lokal, Git ignoriert sie

## Pending

- Issue #213 (Inherited Fields) frontend/test work weiter offen
- Importer UX backlog: #199, #201, #202, #204

## State

Main enthält Release `v0.3.1`. Nächster Commit bündelt `#236`, lokale Repo-Hygiene (`.claude/settings.local.json` raus aus Git) und PR-Review-Fixes. Tests für diesen Commit auf ausdrücklichen Wunsch übersprungen.
