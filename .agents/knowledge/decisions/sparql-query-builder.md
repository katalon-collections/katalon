---
type: Decision
title: SPARQL Query Builder im Admin-Bereich mit NL2SPARQL und Abfragespeicher
description: Integrierter SPARQL Query Builder in der Admin-UI mit direkter SPARQL-Ausführung gegen Oxigraph, Natural-Language-to-SPARQL (NL2SPARQL) via LLM und persistierten gespeicherten Abfragen.
tags: [sparql, rdf, oxigraph, ai, llm, admin-ui, query-builder, nl2sparql]
timestamp: 2026-09-07T14:30:00+02:00
---

# Kontext

Mit der Einführung der materialisierten RDF-Projektion in Oxigraph und des read-only SPARQL 1.1 Protocol Endpoints (`/sparql`) verfügt Katalon über eine performante Graph-Schnittstelle auf Basis von CIDOC-CRM, LRMoo, SKOS und DCTERMS.

Bisher existiert in der Admin-UI lediglich eine Status- und Wartungsansicht in `ScreenSettings.tsx` (Status, Triple-Count, Rebuild-Trigger). Kuratoren, Archivare und Datenmanager müssen externe Tools (wie YASGUI, curl oder Python-Skripte) verwenden, um SPARQL-Abfragen gegen den Endpunkt zu formulieren und auszuführen.

Anforderungen für die native Einbettung in Katalon:
1. **Direktes SPARQL:** Interaktive Eingabe, Syntax-Unterstützung, Tastaturkürzel (`⌘+Enter`), Tabellenansicht mit anklickbaren URIs und Export (CSV/JSON).
2. **Natural Language to SPARQL (NL2SPARQL):** Formulierung von Forschungsfragen in natürlicher Sprache (Deutsch/Englisch) mit automatischer Übersetzung in syntaktisch valide, schreibgeschützte SPARQL-Queries über die bestehende LLM-Infrastruktur (`AdminConfig` / `ai_service.py`).
3. **Gespeicherte Abfragen (Saved Queries):** Persistierung kuratorischer Standard-Abfragen (z. B. Bestandsübersichten, Personennetzwerke, Vollständigkeitsprüfungen) mit Titeln, Beschreibungen und Tags.
4. **Nahtlose UI-Integration:** Einbettung in das bestehende Katalon-Designsystem (`var(--bg)`, `var(--fg)`, `IBM Plex Mono`, i18n de/en, Zero Clutter bei deaktiviertem Oxigraph).

# Entscheidung

1. **Strikte Oxigraph-Konditionalität & Zero Clutter (UX-Kernprinzip):**
   - Der SPARQL Query Builder ist **ausschließlich dann aktiv und sichtbar**, wenn Oxigraph in der Instanz aktiviert ist (`OXIGRAPH_ENABLED=true` und `sparql_endpoint_enabled=true`).
   - **Navigation & UI:** Solange Oxigraph nicht aktiviert ist, bleibt der Menüpunkt in der Admin-Sidebar (`Sidebar.tsx`) **vollständig unsichtbar**. Es gibt keine toten Menüeinträge, ausgegraute Buttons oder irreführende Fehlermeldungen für Standard-Installationen ohne RDF-Profil.
   - **Routen-Schutz:** Wird die Route `/sparql` direkt aufgerufen, obwohl Oxigraph inaktiv ist, schützt `AppShell.tsx` den View und leitet auf die Standardansicht um.
   - **API-Schutz:** Sämtliche Backend-Endpunkte (`/sparql`, `/v1/sparql/queries`, `/v1/sparql/nl2sparql`) prüfen `settings.oxigraph_enabled` und quittieren bei Inaktivität sofort mit `503 Service Unavailable`.
2. **Backend-Erweiterung für Saved Queries:**
   - Eigene PostgreSQL-Tabelle `saved_sparql_queries` mit `id`, `title`, `description`, `query`, `tags` (JSONB-Array), `is_shared`, `created_by`, `created_at`, `updated_at`.
   - REST-Endpunkte unter `/v1/sparql/queries` (GET, POST, PUT, DELETE) mit Berechtigungsprüfung.
   - Sichtbarkeit über `is_shared`: geteilte Abfragen sehen und bearbeiten alle Administratoren, nicht geteilte nur die Person aus `created_by` (Superuser sehen alle). Abfragen ohne `created_by` gelten als geteilt. Fremde private Abfragen beantworten GET/PUT/DELETE mit `404`.
   - Kuratierte System-Templates ("Vorgefertigte Abfragen") als Schnellstart-Vorlagen direkt in der UI hinterlegt.

3. **NL2SPARQL über existierende KI-Infrastruktur (`ai_service.py`):**
   - Endpunkt `POST /v1/sparql/nl2sparql` nutzt `ensure_ai_allowed`, Token-Limits und `call_ai_provider` mit dem konfigurierten OpenAI-kompatiblen Modell.
   - System-Prompt enthält Katalons konkrete Ontologie-Definition (CIDOC-CRM, LRMoo, SKOS), Prefix-Konventionen und Record-Typen.
   - Human-in-the-loop: Die generierte SPARQL-Query wird in den Editor geladen, vom Nutzer geprüft und erst manuell ausgeführt (keine blinde Hintergrundausführung).
   - Read-Only-Sicherheitsgarantie: Auch KI-generierte Queries durchlaufen vor Ausführung die bestehende AST-Prüfung (`validate_read_only_sparql`).

4. **Leichtgewichtiger, abhängigkeitsfreier Editor:**
   - Kein schweres Monaco/CodeMirror-Bundle (Vermeidung von Megabytes an Abhängigkeiten und komplexen Worker-Setups), sondern ein fokussierter Editor mit `IBM Plex Mono`, Zeilennummerierung, Prefix-Hilfe und Syntax-Snippets, abgestimmt auf das bestehende Katalon-Design.

# Begründung

- **Wiederverwendung statt Neubau:** Nutzung des existierenden `/sparql`-Endpunkts, der AST-Validierung und des OpenAI-kompatiblen `ai_service`.
- **Sicherheit:** Der AST-Guard im Backend verhindert Updates, Inserts oder Drops verlässlich auf Parser-Ebene, selbst wenn ein LLM fehlerhafte Update-Statements erzeugen würde.
- **Konsistenz:** Gespeicherte Abfragen in PostgreSQL teilen den Lebenszyklus mit den restlichen App-Daten (Backups via pg_dump), statt in volatilen Browser-LocalStorages verloren zu gehen.

# Citations

[1] GitHub Issue #364 (Oxigraph-Integration & RDF-Projektion)
[2] GitHub Issue #358 (SPARQL 1.1 Protocol Endpoint)
[3] `.agents/knowledge/decisions/subsystem-extensions-vs-plugin-architecture.md`
[4] `backend/src/katalon/services/ai_service.py`
[5] `backend/src/katalon/api/v1/sparql.py`
