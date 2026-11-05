---
type: Decision
title: Footer, Nutzungshinweis, Header-Logo und Theme-Skript als Kernkonfiguration
status: accepted
date: 2026-10-13
---

# Kontext

Instanzen (BPK) brauchten einen eigenen Footer, einen einmaligen Nutzungshinweis und ein
anderes Header-Logo und lösten das mit Theme-Workarounds (CSS/JS-Overrides).

# Entscheidung

`PortalConfig` trägt `footer` (Spalten + Fußzeile), Nutzungshinweis, Header-Logo-Optionen und ein
Theme-Skript; Admin-Oberfläche unter den Portal-Einstellungen. Leere Werte behalten das
eingebaute Verhalten. Instanzspezifisches (BPK) wird über `ca2katalon portal-setup` in diese
Konfiguration geschrieben, nicht in Theme-Dateien.

# Begründung

Was mehrere Institutionen brauchen, gehört in die Konfiguration des Kerns; Theme-Workarounds
brechen bei Updates still.

# Citations

- `backend/src/katalon/core/models.py` (`PortalConfig.footer` u. a.)
- [Portal-loser Custom-Betrieb](portal-loser-custom-betrieb.md), [Docker-Customization-Strategie](docker-customization-strategy.md)
