---
type: Decision
title: Dokumentationszuständigkeit zwischen OKF, Almanac und Entwickleranleitungen
description: OKF hält die Entscheidungsakte; Almanac das aktuelle Systemwissen; DEV.md den Entwickler-Einstieg. Historische Prozessdateien sind keine zweite Quelle für laufenden Status.
tags: [dokumentation, prozess, agents-md]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

OKF und Almanac enthielten überlappende Architekturentscheidungen, Abläufe und
Fallstricke. Dadurch konnten Begründung und Implementierungsstand auseinanderlaufen.
Eine eindeutige Zuständigkeit vermeidet konkurrierende Begründungen und
veraltete Umsetzungsbeschreibungen.

# Entscheidung

- `.agents/knowledge/decisions/` ist die maßgebliche Entscheidungsakte: Kontext,
  Alternativen, Abwägung, Konsequenzen und Status.
- `almanac/` beschreibt das aktuelle System mit Codebelegen. Bestehende
  `almanac/decisions/`-Routen bleiben als Zusammenfassung und Umsetzungsstand
  erhalten; jede benennt ihre OKF-Akte. Neue Richtungsentscheidungen werden
  zuerst in OKF geändert, danach in den betroffenen Verhaltensseiten.
- `.agents/DEV.md` ist der Entwickler-Einstieg für Setup, Werkzeuge, Tests und
  Dokumentationswege. `docs/` hält ausführliche technische Anleitungen.
- OKF-Architecture/Playbooks/Gotchas bleiben kurze Einstiege oder historische
  Befunde mit Verweis auf die aktuelle Anleitung. Bestehende fachliche Details
  werden nicht ohne Ersatz entfernt.
- Die externe Anwenderdokumentation bleibt in `katalon-docs`.

Die gemeinsamen Agent-Regeln stehen in `AGENTS.md`; `CLAUDE.md` ist dessen Symlink.
Das Root-Dokument beauftragt ausdrücklich das Lesen von
`.agents/maintainer/AGENTS.md`, falls vorhanden. Dort bleiben persönliche
Freigaben, manuelle Abnahme und private Release-Abläufe versioniert. Diese
Ergänzung bleibt vom öffentlichen Export ausgeschlossen. Gemeinsame Regeln und
`CONTRIBUTING.md` setzen weder private Werkzeuge noch private Tracker voraus.
Größere Änderungen werden mit Konzept und passenden Mockups oder technischen
Diagrammen vor der Umsetzung abgestimmt. Der aktuelle Export schließt den
gemeinsamen Kontext noch aus; dessen Freigabe ist ein separater Schritt.
Reine Implementierungsänderungen brauchen keine neue Decision. Überholte Entwürfe werden entfernt; weiterhin offene Vorschläge behalten
einen klaren Status.
Bei Widersprüchen bestimmt Code das tatsächliche Verhalten; eine Abweichung von
einer gültigen Entscheidung muss benannt und geklärt werden.

# Begründung

Eine Stelle für die Begründung verhindert konkurrierende Entscheidungshistorien.
Almanac kann das aktuelle Verhalten mit Quellen erklären, ohne alte Alternativen
laufend umzuschreiben. Vorhandene Pfade bleiben erhalten, damit Links und
Agent-Lesetrigger gültig bleiben. Die private Ergänzung hält persönliche Arbeitsweisen aus dem gemeinsamen
Beitragsworkflow heraus. Optionale Werkzeuge dürfen den Einstieg anhand der
Quelldateien nicht blockieren.

# Lebenszyklus

Erledigte Planungsstände und vollständig abgelöste Akten werden entfernt.
Weiterhin gültige Abwägungen, technische Grenzen und Sicherheits-Learnings bleiben
kurz dokumentiert. Änderungen sind in Git nachvollziehbar; ein separates
Dokumentations-Pflegelog wird nicht geführt. Laufende Planung gehört in den
Tracker, fachliche Entwürfe sind als Vorschlag vom implementierten Vertrag zu
unterscheiden.

# Citations

[1] `AGENTS.md` — Dokumentationszuständigkeit und Doku-Pflicht
[2] `.agents/DEV.md` — Documentation and agent entry points
[3] `almanac/README.md` — Maintenance Boundary
[4] `scripts/publish-open-source.sh` — aktueller Exportumfang, README ersetzt
[5] `CONTRIBUTING.md` — gemeinsamer Beitragsworkflow und Konzeptanforderungen
