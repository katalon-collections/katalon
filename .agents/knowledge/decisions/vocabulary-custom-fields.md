---
type: Decision
title: Vokabular-Metadaten über die gemeinsame Schema-Engine
description: VocabularyTerm nutzt JSONB und field_definitions mit vocabulary_term als Zieltyp sowie der Vokabular-UUID als Subtyp.
tags: [vokabulare, datenmodell, field-definitions]
timestamp: 2026-07-06T08:10:50Z
---

# Kontext

Vokabularterme benötigen konfigurierbare Zusatzfelder und strukturierte
Normdatenverweise. Eine getrennte Feldverwaltung würde Schema-, Validierungs-
und Formularlogik für dieselbe Aufgabe verdoppeln.

# Entscheidung

`VocabularyTerm.metadata_` speichert Zusatzwerte als JSONB. Felddefinitionen
verwenden `target_type="vocabulary_term"` und die Vokabular-UUID als
`target_subtype`. Der Umfang ist auf `text`, `number`, `boolean` und `authority`
begrenzt. Normdatenwerte tragen `{source, external_id, label}` unter dem jeweils
konfigurierten Feldnamen; sie verwenden das vorhandene Authority-System.

`Vocabulary.kind` unterscheidet Begriffs- und Relationstyp-Vokabulare. Die
Metadatenverwaltung bleibt unabhängig von dieser fachlichen Unterscheidung.

# Begründung

Die gemeinsame Schema-Engine vermeidet eine zweite Konfigurations- und
Validierungsschicht. Das begrenzte Feldtypangebot hält den Termeditor auf
Zusatzangaben ausgerichtet, ohne das vollständige Recordformular zu duplizieren.

# Citations

[1] `backend/src/katalon/core/models.py` — Vocabulary und VocabularyTerm
[2] `backend/src/katalon/api/v1/schema_admin.py` — Zieltyp und Subtypscope
[3] `frontend/admin/src/components/screens/ScreenVocab.tsx`
