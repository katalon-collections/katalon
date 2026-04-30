# Design Prompt: Katalon Discovery Portal (Public)

## Kontext & Zweck

Entwirf das öffentliche Discovery-Portal von **Katalon**, einem Metadata Management System für Sammlungen im GLAM-Bereich (Galleries, Libraries, Archives, Museums). Das Portal ist die öffentliche Präsentationsebene: Besucherinnen entdecken, durchsuchen und betrachten Objekte, Personen, Orte und Werke einer Sammlung. Kein Login, keine Bearbeitung – nur Entdecken.

**Leitprinzip:** Das Objekt steht im Vordergrund, nicht das Interface. Die Oberfläche zieht sich zurück.

**Technologie im Hintergrund (relevant für UX):**
- Volltextsuche + Facettenfilter via Elasticsearch
- Hochauflösende Bilder über IIIF Deep Zoom (OpenSeadragon-Viewer)
- Vier durchsuchbare Typen: Objekte (Artefakte), Personen/Organisationen (Entitäten), Orte, Werke/Ereignisse (Occurrences)

---

## Zu entwerfende Screens

### Screen 1: Startseite / Homepage

**Zweck:** Einstieg in die Sammlung. Keine reine Suchmaske – Neugier wecken.

Elemente:
- Prominente Suchleiste (Volltext, sofort aktiv)
- „Highlights" oder „Empfehlungen aus der Sammlung" – kuratierte Objekte mit großem Bildanteil
- Schnelleinstieg in die vier Typen (Objekte / Personen & Orgs / Orte / Werke) als navigierbare Kacheln oder Kategorien
- Statistik: „X Objekte, Y Entitäten, Z Orte" – Größe der Sammlung spürbar machen
- Keine überladene Navigation

**Ton:** Museumsqualität. Ruhig, visuell stark, typografisch sauber.

---

### Screen 2: Suchergebnisse

**Zweck:** Schnelles Scannen und Filtern großer Ergebnismengen.

Elemente:
- Suchleiste oben (persistent, mit aktivem Suchbegriff)
- Ergebniszahl + aktive Filter als removable Tags
- **Facetten-Sidebar** (links oder als Drawer auf Mobile):
  - Typ (Objekt / Entität / Ort / Occurrence)
  - Datum / Zeitraum (Slider oder Range-Input)
  - Ort (aus kontrolliertem Vokabular)
  - Weitere dynamische Facetten je nach Typ (z.B. „Kameratyp" für Fotos)
- Ergebnisliste als **Grid** (Standard: Kacheln mit Vorschaubild + Titel + Typ-Badge) oder **Liste** (kompakter, mehr Metadaten sichtbar) – umschaltbar
- Kein Pagination-Chaos: Infinite Scroll oder „Mehr laden"
- Leerer Zustand: Vorschläge, Rechtschreibkorrektur, ähnliche Begriffe

---

### Screen 3: Objekt-Detailseite

**Zweck:** Ein Objekt vollständig präsentieren – Metadaten, Medien, Relationen.

Layout-Idee: Zweispaltig. Links: IIIF-Viewer (Deep Zoom, fullscreen-fähig). Rechts: Metadaten-Panel.

Elemente:
- **IIIF Deep Zoom Viewer** – großflächig, mit Zoom-Controls, Fullscreen-Toggle
- Inventarnummer + Sichtbarkeits-Badge (falls relevant)
- **Dynamische Metadaten:** Alle konfigurierten Felder untereinander, gruppierbar nach Feldsektionen. Wiederholbare Felder als Liste (z.B. mehrere Datierungen, mehrere Beschriftungen)
- **Relationen-Panel:** Verknüpfte Entitäten (mit Rolle), Orte, Werke – jeweils als klickbare Karte
- OAI-Link / Permalink (Copy-Button)
- Breadcrumb: Zurück zur Suche mit erhaltenen Filtern

**Besonderheit Fuzzy-Datum:** „um 1920" oder „1910–1930" soll klar lesbar dargestellt werden, nicht als technischer String.

---

### Screen 4: Orts-Detailseite (mit Karte)

**Zweck:** Einen Ort in seinem geografischen Kontext zeigen.

Elemente:
- Kartenausschnitt (Leaflet / Mapbox) mit Marker für den Ort
- Metadaten (dynamisch konfiguriert)
- Verknüpfte Objekte: „X Objekte wurden an diesem Ort aufgenommen" – kleines Grid

---

### Screen 5: Entitäts-Detailseite (Person / Organisation)

**Zweck:** Eine Person oder Organisation mit all ihren Verknüpfungen zeigen.

Elemente:
- Porträtbild (falls vorhanden als Medium verknüpft)
- Metadaten (Name, Lebensdaten, Beschreibung – dynamisch konfiguriert)
- GND/VIAF-Link falls vorhanden (Authority-Badge)
- Verknüpfte Objekte: „X Objekte, an denen diese Person beteiligt war" – Grid

---

## Visueller Stil

**Referenzton:** Ruhig, typografisch stark, viel Weißraum. Denk: zwischen einem guten Museumswebsite (MoMA, Rijksmuseum) und einer modernen Bibliothekssuche (DNB, HathiTrust). Nicht corporate, nicht verspielt.

- **Farbpalette:** Weitgehend neutral (Weiß/Hellgrau Hintergrund, Dunkelgrau/Schwarz für Text). Ein einzelner Akzentton für interaktive Elemente (z.B. gedämpftes Blau, Ocker oder Terracotta – passend zur GLAM-Welt).
- **Typografie:** Serifenlose Überschriften (klar, modern), Lesetext gerne in einer gut lesbaren Schrift mit Charakter.
- **Bilder:** Immer dominant. Kein Bild = klar erkennbarer Platzhalter (Typ-Icon, kein gebrochenes Bild-Symbol).
- **Responsive:** Mobile ist wichtig. Der IIIF-Viewer muss auf Tablet und Desktop skalieren.

---

## Was explizit nicht entworfen werden soll

- Kein Login / Registrierung
- Kein Warenkorb / keine transaktionalen UI-Elemente
- Kein Admin-Bereich (separater Prompt)
