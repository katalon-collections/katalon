---
type: Decision
title: OKF-Bundle bleibt getrennt von lebenden Prozessdokumenten, beide lazy-geladen
description: DEV.md/IMPLEMENTIERUNGSPLAN.md/KONZEPT.md/PRODUCT.md/DESIGN.md wandern nicht in .agents/knowledge/, bekommen aber dasselbe Lazy-Loading-Wiring wie die OKF-Decisions und die Coding-Rules.
tags: [dokumentation, prozess, agents-md]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Bei Anlage von [.agents/knowledge/](../index.md) stand die Frage: sollen
`DEV.md`, `IMPLEMENTIERUNGSPLAN.md`, `PLAN*.md` mit hineinwandern? Später kam
dieselbe Frage für `KONZEPT.md`, `PRODUCT.md`, `DESIGN.md` zurück — mit dem
Zusatzpunkt, dass keines dieser Dokumente in `AGENTS.md` einen klaren
Lesetrigger hatte (nur lose Erwähnung oder gar keine).

# Entscheidung

Zwei getrennte, aber beide lazy-geladene Systeme:

1. **`.agents/knowledge/`** — kuratierte, stabile Konzepte (OKF-Format):
   Architekturentscheidungen mit Begründung, Playbooks, Gotchas. Wird
   gepflegt (neue Konzepte nach jeder relevanten Entscheidung).
2. **Lebende Prozess-/Produktdokumente** an ihrem bestehenden Ort —
   `.agents/IMPLEMENTIERUNGSPLAN.md` (Roadmap/Phasenstatus),
   `.agents/DEV.md` (Setup/Workflow), `KONZEPT.md` (Datenmodell-Detail),
   `PRODUCT.md`/`DESIGN.md` (UX/Produkt). Diese werden laufend während der
   Arbeit editiert, nicht als abgeschlossene Konzepte behandelt.

Beide Systeme sind in `AGENTS.md` als Lazy-Loading-Trigger verdrahtet
(Abschnitte "Dev Knowledge Base (OKF)" und "Kontext-Dateien — Lazy
Loading") — der Unterschied ist nicht *ob* geladen wird, sondern *was für
eine Art Dokument* es ist und ob es unter Pflegepflicht steht.

# Begründung

Prozessdokumente und kuratiertes Wissen haben unterschiedliche
Lebenszyklen: `IMPLEMENTIERUNGSPLAN.md` ändert sich fast jede Session,
eine Decision in `.agents/knowledge/` soll stabil bleiben. Sie ins gleiche
Verzeichnis zu mischen hätte beides verwässert — Prozessnotizen würden
das OKF-Bundle mit Churn überfluten, echte Entscheidungen würden in
Roadmap-Rauschen untergehen. Beide brauchten trotzdem denselben
Lazy-Loading-Mechanismus, weil ohne Trigger-Zeile in `AGENTS.md` keine
Datei zuverlässig gelesen wird, egal wie wertvoll ihr Inhalt ist.

# Citations

[1] Root `AGENTS.md`, Abschnitte "Dev Knowledge Base (OKF)", "Kontext-Dateien — Lazy Loading"
