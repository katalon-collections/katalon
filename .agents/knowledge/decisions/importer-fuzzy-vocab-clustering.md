---
type: Decision
title: Importer — Fuzzy-Clustering von Vokabular-Varianten via rapidfuzz statt k-means/stdlib
description: Greedy Single-Linkage-Clustering auf normalisierter Levenshtein-Similarity (rapidfuzz), kanonischer Wert = häufigster Cluster-Wert, User bestätigt im UI bevor vocab_map angewendet wird.
tags: [importer, vocab, fuzzy-matching, scope]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Issue #269: Vokabular-Spalten im Importer enthalten Schreibweisen-Varianten
(`Berlin`/`berlin`/`Brlin`), die beim Import als separate `VocabularyTerm`s
angelegt werden statt zusammengeführt zu werden. Frage: welcher
Clustering-Ansatz und welche Bibliothek.

# Entscheidung

1. **`rapidfuzz` (Levenshtein) statt k-means**: k-means braucht einen
   Vektorraum/Embeddings — für Strings ungeeignet ohne zusätzliche
   Infrastruktur. `rapidfuzz.distance.Levenshtein.normalized_similarity`
   reicht für Tippfehler-/Schreibweisen-Erkennung.
2. **Greedy Clustering statt echtem Hierarchical/Agglomerative Clustering**:
   häufigster unassignter Wert wird Pivot/Cluster-Kandidat, alle Werte mit
   Similarity ≥ 0.82 (normalisiert, lowercased+trimmed) werden zugeordnet,
   Cluster-Größe hart auf 10 begrenzt. O(n²), aber für typische
   Spalten-Kardinalität (Dry-Run-Kontext, keine Hot-Path-Operation) völlig
   ausreichend — kein Grund für eine komplexere Implementierung.
3. **Kanonischer Wert = häufigster Wert im Cluster**, nicht z. B.
   kürzester oder alphabetisch erster — Annahme: die häufigste
   Schreibweise ist am ehesten korrekt.
4. **Kein stilles Auto-Merge**: Cluster-Vorschläge werden im UI angezeigt
   (`StepDryRun.tsx`), User bestätigt einzeln über "Zusammenführen".
   Bestätigung wird intern als `vocab_map`-Transform auf die
   Mapping-Spalte angewendet — kein neues Datenmodell, nutzt bestehenden
   Transform-Mechanismus.
5. **Scope**: nur `field_type: "vocab"`-Felder. Generische Text-Felder
   sind laut Issue ein möglicher Folgeschritt, bewusst nicht in Scope.

# Begründung

rapidfuzz war im Issue selbst bereits als Bibliothek vorgeschlagen und ist
die naheliegende Wahl für Editierdistanz auf Strings — kein Grund, hier
gegen den eigenen Vorschlag zu argumentieren. Greedy statt vollem
Hierarchical Clustering spart Komplexität, ohne im Dry-Run-Kontext (kleine
bis mittlere Spalten-Kardinalität, kein Hot Path) messbar schlechtere
Ergebnisse zu liefern. Silent-Merge wurde explizit im Issue
ausgeschlossen — Datenintegrität bei GLAM-Metadaten hat Vorrang vor
Automatisierungskomfort.

# Citations

[1] GitHub Issue #269
[2] `backend/src/katalon/services/importer_service.py` — `_cluster_values`, `_collect_vocab_values`
[3] `backend/src/katalon/api/v1/importer.py` — `/dry-run` Response-Shaping
[4] `frontend/admin/src/components/screens/importer/StepDryRun.tsx`, `useImporterState.ts` — `applyVocabCluster`
[5] Commit `d5a7533`, Tag `v0.5.6`
