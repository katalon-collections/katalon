---
type: Decision
title: Digitale Ausstellungen als eigene kuratierte Portal-Ressource
description: Ausstellungen sind keine Records, Collections oder Working Sets, sondern gestaltbare Portal-Ressourcen; die spätere Seiten-/Blockstruktur wird in einer ergänzenden Entscheidung festgelegt.
tags: [portal, ausstellungen, storytelling, theming, accessibility]
timestamp: 2026-09-17T00:00:00Z
status: proposed
---

**Statusabgleich 2026-10-30:** weiterhin Entwurf, keine implementierte Portalfläche. `docs/konzept-ausstellungen.md` enthält noch den älteren Entwurfsverlauf; für Hierarchie und Blocktypen gilt die Seiten-/Blockentscheidung. Ein Konzeptverweis ist kein Nachweis gelieferter Funktionen.


# Digitale Ausstellungen als eigene kuratierte Portal-Ressource

## Kontext

Katalon besitzt fachliche Records, Collections, interne Working Sets, statische Seiten und eine konfigurierbare Portal-Startseite. Keines dieser Konzepte bildet eine digitale Sonderausstellung ab: eine öffentliche, gestaltete Interpretation vorhandener Datensätze mit eigener Reihenfolge und kuratorischen Texten.

Die Recherche zu Europeana und weiteren GLAM-Beispielen zeigt, dass digitale Ausstellungen eine geführte Erzählung und zugleich den Wechsel in die freie Exploration benötigen. Der mögliche Funktionsumfang reicht von einfachen Text-/Bildfolgen bis zu Karten, Timelines, 3D und interaktiven Lernformaten. Ohne Scope-Grenze würde daraus ein allgemeiner Page Builder.

## Entscheidung

- Digitale Ausstellungen werden als eigene persistente Portal-Ressource modelliert, nicht als achter Katalon-Kerntyp.
- Eine Ausstellung referenziert bestehende öffentliche Records und dupliziert deren fachliche Metadaten nicht.
- Gliederung erfolgt technisch immer über `sections`; ungegliederte Ausstellungen verwenden einen internen Standardbereich mit ausgeblendeter öffentlicher Überschrift.
- Eingebundene Records erscheinen in kuratierten Pages mit ausgewählten live geladenen Metadaten und Link zum vollständigen Record.
- Die Inhaltsstruktur folgt der ergänzenden Entscheidung [Ausstellungsseiten mit geordneten Inhaltsblöcken](ausstellungsseiten-und-inhaltsbloecke.md): Exhibition → Section → Page → Block.
- Phase 1 verwendet `text`, `record` und `records`; der ursprünglich erwogene freie `image`-Typ entfällt.
- Das Datenmodell bleibt durch diskriminierte Blockvarianten erweiterbar, ohne jetzt eine Plugin-Architektur zu bauen.
- Navigation, Sichtbarkeitsprüfung und Accessibility sind Bestandteil des Grundvertrags.
- Die bestehende Portal-Startseite kann Ausstellungen später über einen neuen `exhibitions`-Block referenzieren.

## Begründung

Collections beschreiben Bestände, Working Sets unterstützen interne Arbeit, Occurrences beschreiben Ereignisse und statische Seiten besitzen keine kuratierte Exponatstruktur. Eine eigene Ressource hält fachliche Erschließung und Vermittlung getrennt.

Bereiche übertragen die räumliche beziehungsweise thematische Logik einer Sonderausstellung. Ein ausblendbarer Standardbereich hält das Backendmodell einheitlich, ohne kleine Ausstellungen zu einer sichtbaren Gliederung zu zwingen. Pages ermöglichen Interpretation und mehrere Perspektiven, ohne vollständige Katalogdatensätze in die Ausstellung zu kopieren.

Drei Blocktypen und eine eigene Page-Ebene decken den ersten nutzbaren Umfang ab. Layoutvarianten und Theme-Tokens liefern visuelle Unterschiede, ohne die Implementierungs- und Testmatrix durch freie Bild- oder Spezialblöcke zu vervielfachen.

## Konsequenzen

- Backend, Admin und Portal benötigen eigene Exhibition-Ressourcen, Endpunkte und Berechtigungen.
- Referenzen auf Records müssen bei Veröffentlichung und Rendering gegen deren öffentliche Sichtbarkeit geprüft werden.
- Hero- und Bereichsbilder sowie Record-Blöcke verwenden optionale öffentliche Vorschaumedien; fehlende Bilder sind ein regulärer Zustand.
- Der Admin-Editor braucht Sortierung, Preview und eine verständliche Theme-Konfiguration.
- Vor der Implementierung ist ein freizugebender UI/UX-Entwurf erforderlich.
- Timeline, Karte, Quiz, Bildvergleich, 3D, freies CSS und ähnliche Erweiterungen gehören nicht zu Phase 1.

## Vollständiges Konzept

Siehe [docs/konzept-ausstellungen.md](../../../docs/konzept-ausstellungen.md) und GitHub-Issue [#341](https://github.com/karkraeg/Katalon/issues/341).

## Quellen

- https://pro.europeana.eu/index.php/post/starting-with-story-a-workshop-guide-for-your-next-storytelling-project
- https://pro.europeana.eu/post/effective-digital-storytelling-reflecting-on-our-faces-of-europe-exhibition
- https://www.museumsassociation.org/museums-journal/in-practice/2022/03/using-3d-models-to-create-emotive-online-exhibitions/
- https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1542430/full
