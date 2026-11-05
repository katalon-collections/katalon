---
type: Decision
title: Ausstellungsseiten mit geordneten Inhaltsblöcken
description: Digitale Ausstellungen verwenden die feste Hierarchie Ausstellung → Bereich → Seite → Block; freie Abbildungsblöcke entfallen zugunsten von Record-Blöcken mit optionalen Vorschaumedien.
tags: [portal, ausstellungen, storytelling, medien, backend, admin]
timestamp: 2026-09-17T00:00:00Z
status: proposed
---

**Statusabgleich 2026-10-30:** weiterhin Entwurf, keine implementierte Portalfläche. `docs/konzept-ausstellungen.md` enthält noch den älteren Entwurfsverlauf; für Hierarchie und Blocktypen gilt die Seiten-/Blockentscheidung. Ein Konzeptverweis ist kein Nachweis gelieferter Funktionen.


# Ausstellungsseiten mit geordneten Inhaltsblöcken

## Kontext

Der erste Ausstellungsentwurf modellierte `text`, `image`, `record` und `records` als gleichrangige Exhibition Items. Dadurch war ein Item zugleich Navigationseinheit und Darstellungsblock. Eine Seite konnte nicht ohne Sondermodell mehrere Records unterschiedlicher Haupttypen, dazwischenliegenden Text und unterschiedliche Record-Layouts enthalten.

Der eigenständige Typ `image` trennte historische Fotografien oder Illustrationen zudem von ihrem Katalogdatensatz. Für kuratierte Ausstellungen soll ein fachlich erschlossenes Sammlungsgut als Record erscheinen und immer zum vollständigen Datensatz führen.

Parallel ist ein separates Vorhaben vorgesehen, das Entity, Place, Occurrence und Collection ein optionales einfaches Vorschaubild geben kann. Dieser Preview-Vertrag ist bewusst kleiner als das Object-Medienmodell: kein IIIF-Viewer, kein 3D und keine Übertragung des vollständigen Multimedia-Workflows.

## Entscheidung

- Digitale Ausstellungen verwenden die feste Hierarchie `Exhibition → Section → Page → Block`.
- Jede Ausstellung besitzt mindestens einen Section-Knoten. Ungegliederte Ausstellungen verwenden einen internen Standardbereich mit ausgeblendeter öffentlicher Überschrift.
- `section` bleibt der technische Begriff. Die öffentliche Bezeichnung ist pro Ausstellung mehrsprachig konfigurierbar und ausblendbar.
- Eine Page ist die stabile Portal- und Navigationseinheit. Sie enthält geordnete Blocks.
- Phase 1 kennt nur die Blocktypen `text`, `record` und `records`.
- Der freie Blocktyp `image` entfällt. Record-Medien werden innerhalb eines Record-Blocks präsentiert.
- Ein Record-Block referenziert Object, Entity, Place, Occurrence oder Collection und speichert nur kuratorischen Text, Layout, Medienentscheidung sowie Auswahl und Reihenfolge der Metadatenfelder.
- Record-Layouts sind auf `media_left`, `media_right`, `media_above` und `text_only` begrenzt.
- Medien sind optional. `auto` verwendet ein öffentliches Vorschaubild, `selected` ein bestimmtes öffentliches Vorschaubild und `none` rendert bewusst ohne Bild. Fehlt bei `auto` ein Bild, kollabiert das Layout ohne Platzhalterfläche.
- Jeder Record-Block und jeder Eintrag einer Record-Gruppe verlinkt verpflichtend zum kanonischen Katalon-Datensatz.
- Eine Record-Gruppe darf öffentliche Haupttypen mischen und besitzt eine eigene Reihenfolge. Sie bündelt Records, die bewusst gemeinsam auf derselben Page kuratiert werden; sie ist kein allgemeiner „Weitere Objekte“-Mechanismus.
- Records mit eigener Erzählung oder eigener Station erhalten eine eigene Page und werden über die Seitennavigation erschlossen.
- Persistenz verwendet eigene Tabellen für Exhibitions, Sections, Pages und Blocks. Blockdaten bleiben streng diskriminiertes JSONB; unbekannte Varianten werden abgelehnt.

## Begründung

Die Page trennt Navigation von Komposition. Kurator:innen können mehrere fachliche Perspektiven auf derselben Seite verbinden, ohne Datensätze zu kopieren oder für jede Textpassage eine neue Portalroute zu erzeugen.

Drei Blocktypen reichen aus. Unterschiedliche Darstellungen entstehen durch Reihenfolge, Record-Typ, Layout, optionale Medien und Feld-Auswahl. Ein allgemeiner Page Builder oder eine Plugin-Schicht ist dafür nicht nötig.

Das verpflichtende Record-Ziel hält die Ausstellung mit der fachlichen Erschließung verbunden. Optionale Vorschaumedien erlauben visuelle Präsentation aller öffentlichen Haupttypen, ohne Ausstellungen ohne Bilder zu benachteiligen.

## Konsequenzen

- Das ursprüngliche flache Exhibition-Item-Modell und dessen `image`-Variante werden nicht implementiert.
- Backend und API benötigen `ExhibitionPage` zusätzlich zu Exhibition, Section und Block.
- Admin-Sortierung existiert auf vier Ebenen: Sections, Pages, Blocks und Referenzen innerhalb einer Record-Gruppe.
- Das Portal navigiert nach Page-Slugs, nicht nach Record-IDs.
- Die Auswahl der Metadatenfelder speichert keine Werte. Das Public-Rendering lädt Werte live aus dem Record.
- Das separate Vorschaumedien-Vorhaben muss einen typübergreifenden öffentlichen Preview-Vertrag liefern; Ausstellungen dürfen dennoch ohne Preview funktionieren.
- Der bestehende Object-Medienvertrag bleibt unverändert, bis das Vorschaumedien-Vorhaben umgesetzt wird.
- `docs/konzept-ausstellungen.md` ist der vollständige fachliche und API-nahe Entwurf.

## Abgelöster Teil der früheren Entscheidung

Diese Entscheidung ersetzt in [Digitale Ausstellungen](digitale-ausstellungen.md) ausschließlich die frühere Festlegung auf vier gleichrangige Item-Typen und freie Image-Items. Die Entscheidung für eine eigene kuratierte Portal-Ressource, kontrollierte Theme-Tokens, Sichtbarkeitsprüfung und Accessibility bleibt bestehen.

## Quellen

- [Vollständiges Ausstellungskonzept](../../../docs/konzept-ausstellungen.md)
- [Digitale Ausstellungen](digitale-ausstellungen.md)
- [Medien-Multiformat](medien-multiformat.md)
