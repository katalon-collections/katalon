---
type: Decision
title: Soft Delete lässt eingehende Relationen unangetastet — Bereinigung erst beim Purge
description: Cleanup entfernt keine Verweise aus fremden Records beim Soft Delete; generische Relationstabelle und JSONB-Relationsfelder bleiben bis zum endgültigen Purge exakt wie vorher, Restore ist dadurch automatisch verlustfrei; UI zeigt Relationen zu gelöschten Zielen mit "Gelöscht"-Badge statt Link (#398).
tags: [datenmodell, relationen, soft-delete, backend, frontend, integrität]
timestamp: 2026-09-13T00:00:00Z
---

# Kontext

Production-Readiness-Audit, Abschnitt „Soft Delete und Restore sind nicht
symmetrisch“: Der bestehende Cleanup-Task entfernt beim Soft Delete Verweise
aus JSONB-Metadaten anderer Records, kann aber vor dem Commit der
Löschtransaktion laufen (Rollback-Gefahr), erzeugt keine Audit-Einträge,
reindexiert die geänderten Quellrecords nicht, und Restore stellt nur den
Zielrecord wieder her — nicht die entfernten Relationsfeldwerte anderer
Records. Generic-Relation-Zeile und JSONB-Relationsfeld können danach
auseinanderlaufen. Issue #398, blockiert durch #392 (commit-sicherer
Seiteneffekt-Mechanismus).

# Entscheidung

**Eingehende Relationen (generische Relationstabelle wie auch JSONB-
Relationsfelder anderer Records) bleiben beim Soft Delete komplett
unangetastet, bis der Zielrecord endgültig purged wird.** Kein Entfernen,
kein Rekonstruktionsprotokoll. Restore ist dadurch strukturell verlustfrei —
es gibt nichts wiederherzustellen, weil nichts verändert wurde. Erst der
endgültige Purge (nach Ablauf der Aufbewahrungsfrist, nur über den
commit-sicheren Mechanismus aus #392 ausgelöst) entfernt die Referenzen
tatsächlich, mit Audit-Eintrag und Reindex der betroffenen Quellrecords.

**UI-Behandlung:** Referenziert ein Record ein Soft-Delete-Ziel, zeigt die
Admin-UI die Relation weiterhin an, aber mit einem „Gelöscht“-Badge statt
eines anklickbaren Links (Ziel ist für normale Nutzer nicht mehr aufrufbar).
Nach Restore verschwindet das Badge automatisch, weil die zugrunde liegenden
Daten nie verändert wurden. Nach Purge verschwindet die Relation vollständig.
Dasselbe Badge-Muster wird für tote Vokabularreferenzen nach bewusst
übersprungenem Remapping verwendet, siehe
[Schema- und Vokabularintegrität](schema-vokabular-integritaet.md).

Verworfen: Entfernen beim Soft Delete + Rekonstruktion beim Restore. Hätte
zwar „keine toten Links“ auch vor dem Purge gezeigt, erfordert aber ein
verlustfreies Rekonstruktionsprotokoll (was genau wurde wo entfernt, in
welcher Reihenfolge bei mehrfachem Delete/Restore), mehr Audit-Fälle und
mehr Fehlerflächen — genau die Asymmetrie, die der Audit als Blocker nennt,
wäre nur an anderer Stelle neu entstanden.

# Begründung / Scope-Grenzen

- Radikal einfachste Lösung: „nichts anfassen“ ist per Definition symmetrisch
  zu Restore. Kein neuer State, kein neues Protokoll, kein zusätzlicher
  Audit-Fall für die Löschung selbst.
- Gilt einheitlich für alle sieben Record-Typen und beliebig viele
  eingehende/ausgehende Relationen (Acceptance-Criteria #398) — die Regel
  hat keine Typ- oder Kardinalitäts-Sonderfälle.
- Cleanup/Bereinigung der Referenzen ist damit ausschließlich eine
  Purge-Aufgabe, nicht mehr eine Soft-Delete-Aufgabe — reduziert die Anzahl
  der Stellen, an denen Referenzen verändert werden, auf eine.
- Voraussetzung #392 bleibt bestehen: der Purge-Cleanup darf weiterhin erst
  nach dem DB-Commit der Purge-Transaktion auslösen, sonst wiederholt sich
  exakt das Rollback-Problem, nur eine Stufe später.

# Citations

- `docs/production-readiness-audit-2026-09-13.md` — Abschnitt „Soft Delete
  und Restore sind nicht symmetrisch“
- `backend/src/katalon/workers/purge_tasks.py:17-76`
- `backend/src/katalon/api/v1/objects.py:524-542`
- GitHub-Issue #398 (blocked by #392)
