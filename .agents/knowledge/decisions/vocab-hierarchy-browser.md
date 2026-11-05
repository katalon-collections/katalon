---
type: Decision
title: Vokabular-Hierarchie-Browser — Tree-Ansicht im Feld-Dropdown, kein Lazy-Loading, nur interne Vokabulare
description: Issue #342 — Browse-Modus neben der Textsuche im VocabInput/VocabFreeInput, Daten kommen fertig vom bestehenden /tree-Endpoint.
tags: [vokabulare, ui, schema]
timestamp: 2026-09-09T13:45:00Z
---

# Kontext

Vokabularfelder im Record-Editor boten nur Textsuche. Bei hierarchischen
Vokabularen (Broader/Narrower) kennen Nutzer den exakten Begriff oft
nicht. Das Backend hatte den Baum bereits (`GET /v1/vocabularies/{id}/tree`,
`VocabularyTermNode`, plus `/ancestors` für Breadcrumbs) — es fehlte nur
die UI. Das Issue nannte drei offene Fragen: Tree vs. Breadcrumb-Drilldown,
Performance bei großen Vokabularen, Geltungsbereich (interne Vokabulare
vs. Authority-Quellen wie GND).

# Entscheidung

1. **Tree-Ansicht statt Breadcrumb-Drilldown**: rekursives Rendering mit
   Expand/Collapse direkt im Feld-Dropdown. Der Endpoint liefert den
   ganzen Baum auf einmal; ein Drilldown hätte pro Ebene zusätzliches
   State-Management gebracht und wäre trotzdem schlechter überblickbar.
   Der ausgewählte Wert zeigt weiterhin den Pfad als Breadcrumb (bestehende
   `/ancestors`-Logik).
2. **Kein Lazy-Loading vorbauen**: der Baum wird einmal geladen, wenn der
   Modus zum ersten Mal geöffnet wird. Bei mehreren hundert Termen
   unkritisch; lazy pro Ebene erst nachrüsten, wenn ein reales Vokabular
   das Problem macht (YAGNI).
3. **Nur interne Vokabulare**: Authority-Quellen liefern über die Adapter
   keine Baumstruktur — ein Drilldown dort wäre ein eigenes Feature mit
   eigenem Backend-Aufwand.

UI: Baum-Button (`ListTree`-Icon) neben dem Eingabefeld öffnet das
Dropdown direkt im Browse-Modus; Tab-Leiste („Suche"/„Struktur") im
Dropdown wechselt zwischen Modi; Tippen im Eingabefeld kehrt zum
Such-Modus zurück. Beide Widgets (`VocabInput`, `VocabFreeInput`,
Code historisch dupliziert in `ScreenForm.tsx`) bekamen denselben
`useVocabTree`-Hook und dieselbe `VocabTreeRows`-Komponente.

# Begründung

Minimaler Eingriff, kein Datenmodell- und kein Backend-Change — das
Feature war reine Frontend-Arbeit am bestehenden Endpoint. Alle drei
Unterentscheidungen halten den Scope klein und lassen sich später ohne
Migration erweitern (lazy-loading, Authority-Bäume).
