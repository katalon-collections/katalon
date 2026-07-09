---
type: Decision
title: Vokabular-Metadaten — JSONB-Spalte statt eigenem field_definitions-System, dann vereinheitlicht
description: Dreistufige Entscheidungsgeschichte — Lücke erkannt, minimale JSONB-Lösung, dann volle Vereinheitlichung mit dem bestehenden Schema-Engine-Mechanismus.
tags: [vokabulare, datenmodell, field-definitions]
timestamp: 2026-07-06T08:10:50Z
---

# Kontext

`VocabularyTerm` hatte anders als Object/Entity/Place/Occurrence keine
`metadata_`-Spalte und keine Möglichkeit für konfigurierbare
Zusatzfelder — eine strukturelle Asymmetrie in der Schema-Engine
(siehe [Vier Bestandstypen](vier-bestandstypen.md)). Das äußerte sich
konkret als Bug: `external_id` beim Import ging still verloren
(Issue #257), weil kein Speicherpfad existierte.

# Entscheidung — Verlauf

**Schritt 1 (2026-07-05, Issue #258)**: Einzelne `metadata` JSONB-Spalte
auf `VocabularyTerm`, nach dem Muster der Primärtypen — bewusst *kein*
volles `field_definitions`-System (YAGNI), um die Lücke schnell und
minimal zu schließen.

**Schritt 2 (2026-07-05)**: Für Normdaten/Autorität wird die
strukturierte Form `{source, external_id, label}` in
`metadata.authority` gewählt statt eines simplen String-Felds — um das
bestehende, produktionsreife Authority-System (GND, Geonames, Wikidata,
Iconclass, VIAF, TGN) wiederzuverwenden. `AuthorityInput` wird aus
`ScreenForm.tsx` in eine geteilte Komponente extrahiert. Löst Issue #257
als Nebeneffekt.

**Schritt 3 (2026-07-06)**: Vollständige Vereinheitlichung —
`FieldDefinition.target_type` wird um `vocabulary_term` erweitert
(jeder `Vocabulary.name` wird zum Subtyp), Speicherung weiter in
`VocabularyTerm.metadata_`. Neues `Vocabulary.kind`-Feld
(`term`/`relation`) unterscheidet Begriffslisten von
Relationstyp-Vokabularen. Feldtyp-Scope bewusst auf
text/number/boolean/authority begrenzt, um ein Refactoring der
Render-Logik in `ScreenForm.tsx` zu vermeiden. Die alte, hartkodierte
`AuthoritiesEditor`-Komponente entfällt vollständig.

# Begründung

Jeder Schritt löst die unmittelbare Lücke mit der kleinstmöglichen
Erweiterung, bevor der nächste Schritt sie in die bestehende
Schema-Engine integriert — kein Neubau eines Parallelsystems für
Vokabulare. `FieldDefinition.target_type` war bereits als generischer
String erkennbar (wird auch für `procedure` verwendet, obwohl das kein
primärer DB-Typ ist) — das bestätigte, dass das System für genau diese
Erweiterung ausgelegt war.

# Citations

[1] Session-Entscheidung 2026-07-05: "Proposed metadata JSONB column for VocabularyTerm..." (Issue #258)
[2] Session-Entscheidung 2026-07-05: "Approved: Structured authority metadata for VocabularyTerm..."
[3] `.agents/PLAN_vocab_field_definitions.md`, Session-Entscheidung 2026-07-06
