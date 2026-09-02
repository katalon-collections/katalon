---
name: Katalon
description: Professioneller kuratorischer Arbeitsplatz für GLAM-Sammlungen
colors:
  archive-navy: "#0b1a33"
  collection-blue: "#1e3a8a"
  collection-blue-deep: "#15296b"
  collection-blue-pale: "#eef2fb"
  workspace: "#f4f5f7"
  paper: "#ffffff"
  ink: "#181a1f"
  muted-ink: "#5a6173"
  rule: "#e4e6eb"
typography:
  headline:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.012em"
  body:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.2
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.collection-blue}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "0 11px"
    height: "30px"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 11px"
    height: "30px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px"
---

# Design System: Katalon

## Overview

**Creative North Star: "Kuratorischer Arbeitsplatz"**

Katalon wirkt wie ein präziser, zeitgemäßer Arbeitsplatz für professionelle Sammlungsarbeit. Oberfläche bleibt flach und ruhig. Dichte Fachinformationen sind klar gegliedert; Interaktionen bleiben vertraut und direkt.

System verbindet kompakte Verwaltungsoberflächen mit zugänglichen Abständen und eindeutigen Zuständen. Es vermeidet generische SaaS-Dashboards ohne fachlichen Bezug, verspielte Museumsästhetik und Desktop-only-Oberflächen.

**Key Characteristics:**

- Ruhige, helle Arbeitsfläche mit dunkler Navigation
- Kompakte, aber lesbare Informationsdichte
- Klare Grenzen statt dekorativer Schatten
- Ein zurückhaltender blauer Aktionsakzent
- Responsive Struktur ohne entfernte Kernfunktionen

## Colors

Gedämpftes Archiv-Navy rahmt neutrale Arbeitsflächen; Sammlungsblau markiert Aktionen und Auswahl.

### Primary

- **Sammlungsblau** (#1e3a8a): Primäraktionen, aktive Navigation und Fokus.
- **Tiefes Sammlungsblau** (#15296b): Hover-Zustände und Text auf blassblauen Flächen.
- **Blasses Sammlungsblau** (#eef2fb): Auswahl, Fokusumgebung und dezente Hervorhebung.

### Neutral

- **Archiv-Navy** (#0b1a33): Sidebar und stabiler Navigationsrahmen.
- **Arbeitsfläche** (#f4f5f7): Seitenhintergrund.
- **Papier** (#ffffff): Eingaben und Inhaltsflächen.
- **Tinte** (#181a1f): Primärtext.
- **Gedämpfte Tinte** (#5a6173): Sekundärtext und Hinweise.
- **Trennlinie** (#e4e6eb): Flächengrenzen und Tabellenzeilen.

**The One Accent Rule.** Sammlungsblau kennzeichnet Aktion, Auswahl oder Fokus, nie bloße Dekoration.

## Typography

**Display Font:** IBM Plex Sans (lokal gebündelt, mit system-ui)
**Body Font:** IBM Plex Sans (lokal gebündelt, mit system-ui)
**Label/Mono Font:** IBM Plex Mono (lokal gebündelt, mit ui-monospace)

Die Oberfläche lädt keine externen Webfonts; IBM Plex wird mit dem Admin-Bundle ausgeliefert.

**Character:** IBM Plex Sans wirkt sachlich und offen. IBM Plex Mono kennzeichnet IDs, Schlüssel, Zähler und technische Metadaten.

### Hierarchy

- **Headline** (600, 22px, 1.2): Seitentitel.
- **Title** (600, 14.5px, 1.2): Navigation und Abschnittstitel.
- **Body** (400, 13.5px, 1.45): Verwaltungsoberfläche und Datendarstellung.
- **Label** (500, 12px, 1.2): Feldbezeichnungen und kompakte Aktionen.
- **Mono** (400, 11.5px, 1.45): IDs, Schlüssel, Zähler und Statusdetails.

**The Semantic Mono Rule.** Monospace signalisiert strukturierte oder technische Daten, nicht dekorativen Stil.

## Elevation

System bleibt flach. Flächen unterscheiden sich durch Hintergrundton und 1px-Grenzen. Schatten erscheinen nur bei schwebenden Menüs, Suchvorschlägen oder temporären Dialogen.

### Shadow Vocabulary

- **Overlay** (`box-shadow: 0 8px 24px rgba(0,0,0,.12)`): Menüs und Suchvorschläge.
- **Dialog** (`box-shadow: 0 24px 80px rgba(0,0,0,.24)`): Modale Vorgangsbestätigung.

**The Flat-by-Default Rule.** Dauerhafte Flächen bleiben schattenlos; nur temporär überlagerte Elemente erhalten Tiefe.

## Components

### Buttons

- **Shape:** kompakter Radius (6px), 30px Höhe.
- **Primary:** Sammlungsblau mit weißer Schrift und 11px horizontalem Padding.
- **Hover / Focus:** tieferes Blau; sichtbarer Fokus über blassblauen Ring.
- **Secondary / Ghost:** weiße oder transparente Fläche, neutrale Kontur, ruhiger Hover-Hintergrund.

### Chips

- **Style:** 24px hoch, pillenförmig, neutrale Kontur und kompakte Beschriftung.
- **State:** Auswahl nutzt blasses Sammlungsblau; entfernbare Chips besitzen eindeutige Aktion.

### Cards / Containers

- **Corner Style:** 10px.
- **Background:** Papier auf grauer Arbeitsfläche.
- **Shadow Strategy:** kein Schatten im Ruhezustand.
- **Border:** 1px Trennlinie.
- **Internal Padding:** meist 16px.

### Inputs / Fields

- **Style:** weiße Fläche, 1px neutrale Kontur, 6px Radius, 32px Höhe.
- **Focus:** blaue Kontur mit 3px blassblauer Fokusumgebung.
- **Error / Disabled:** semantische Farbe plus verständlicher Text; Zustand nicht nur über Farbe vermitteln.

### Navigation

Dunkle Sidebar strukturiert Hauptbereiche mit kompakten Gruppenlabels. Aktiver Eintrag nutzt stärkeren Kontrast und Sammlungsblau. Mobil wird Navigation als explizit steuerbarer Drawer angeboten; aktuelle Seite bleibt im Kopfbereich erkennbar.

### Interaction & Accessibility

Interaktive Karten, Suchtreffer, Vorschläge und Facetten verwenden native Links oder Buttons. Fokus bleibt sichtbar und nutzt Sammlungsblau mit ausreichendem Abstand. Hover darf Zustand ergänzen, aber nie der einzige Zugang zu Aktion oder Information sein.

### Data Tables

Tabellen bleiben auf breiten Flächen kompakt. Mobil dürfen sie horizontal scrollen, wenn Spaltenvergleich wesentlich ist; einfache Listen wechseln zu gestapelten Zeilen mit sichtbaren Primäraktionen.

## Do's and Don'ts

### Do:

- **Do** Sammlungsblau (#1e3a8a) nur für Aktionen, Auswahl und Fokus verwenden.
- **Do** Kernfunktionen auf kleinen Bildschirmen erhalten und Informationsdichte strukturell anpassen.
- **Do** Touch-Ziele mobil auf mindestens 44px vergrößern.
- **Do** Flächen primär durch Hintergrund und 1px-Grenzen gliedern.
- **Do** IBM Plex Mono nur für strukturierte oder technische Daten einsetzen.

### Don't:

- **Don't** generische SaaS-Dashboards ohne Bezug zu fachlicher Sammlungsarbeit nachbilden.
- **Don't** verspielte oder dekorative Museumsästhetik verwenden, die Arbeitsabläufe behindert.
- **Don't** Desktop-only-Oberflächen bauen oder Kernfunktionen mobil verstecken.
- **Don't** dauerhafte Karten und Panels mit dekorativen Schatten stapeln.
- **Don't** Hover als einzigen Zugang zu Aktionen verwenden.
- **Don't** farbige Seitenstreifen stärker als 1px als Akzent einsetzen.
