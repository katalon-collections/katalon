---
type: Decision
title: Beta-Release-Scope — Zugänglichkeit vor Feature-Vollständigkeit
description: Vier Hardening-Aufgaben als echte Blocker definiert; Inherited Fields und ES-Robustheit bewusst auf nach Beta-Start verschoben.
tags: [roadmap, priorisierung, beta]
timestamp: 2026-05-25T07:25:29Z
---

# Kontext

Bei der Restrukturierung von `.agents/IMPLEMENTIERUNGSPLAN.md` musste
entschieden werden, was den öffentlichen Beta-Start wirklich blockiert
und was danach nachgezogen werden kann.

# Entscheidung

**Echte Beta-Blocker** (vier Aufgaben):

- Rate Limiting auf Public Endpoints (#219)
- Snapshot-UI für Datenversionierung (#217)
- Cascade-Deletion verwaister Relationen (#149)
- Production Hardening: Secrets-Management, TLS-Terminierung (#20)

**Bewusst kein Blocker, sondern "vor oder kurz nach Beta-Start"**:

- Inherited Fields / ES-Denormalisierung (#213, siehe
  [Inherited Fields](inherited-fields-es.md))
- ES-Robustheit: Retry, Reconciliation, Health-Checks (#214)
- OAI-PMH- und Importer-UX-Verbesserungen

# Begründung

Strategie priorisiert Zugänglichkeit über Feature-Vollständigkeit: die
Plattform geht mit solidem CRUD, Suche und Admin-Grundfunktionen live,
Sucherweiterungen und Datenkonsistenz-Verbesserungen folgen kurz danach.
Production Hardening (Secrets, TLS) ist der einzige Punkt, der nicht
verhandelbar ist — Sicherheitslücken bei öffentlichem Start sind
inakzeptabel, fehlende Facettensuche über verlinkte Records ist es
nicht.

# Citations

[1] `.agents/IMPLEMENTIERUNGSPLAN.md`
[2] Session-Entscheidung 2026-05-25: "Beta Release Roadmap: Critical Blockers Prioritized"
