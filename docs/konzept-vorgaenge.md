# Katalon – Konzeptpapier: Vorgänge (Leihverkehr, Erwerbung, Restaurierung)

**Version:** Entwurf, Juni 2026  
**Adressat:** Stakeholder, Sammlungsverantwortliche, Projektbeteiligte  
**Status:** Geplant – Phase 14

---

## Ausgangslage

Katalon verwaltet heute vier Kerntypen: **Objekte**, **Entitäten** (Personen, Institutionen), **Orte** und **Ereignisse** (Werke, Konzepte, historische Ereignisse). Diese Typen bilden den *Bestand* – was existiert und was es bedeutet.

Was bislang fehlt: **Prozesse und Transaktionen** rund um den Bestand. Welches Objekt befindet sich gerade als Leihgabe im Ausland? Wann wurde etwas erworben, und von wem? Wann wurde ein Objekt restauriert, und mit welchem Ergebnis? Solche Vorgänge sind in Museen, Archiven und Bibliotheken täglich relevant – für Versicherung, Standortverwaltung, Berichtspflichten und institutionelles Gedächtnis.

Dieses Konzeptpapier beschreibt, wie Katalon diese Lücke mit dem neuen Typ **Vorgang** schließt.

---

## Was ist ein Vorgang?

Ein **Vorgang** (intern: *Procedure*) beschreibt einen zeitlich begrenzten, zustandsverändernden Prozess an einem oder mehreren Objekten. Er hat:

- einen **Typ** (z. B. Leihgabe ausgehend, Restaurierung)
- einen **Status** (Entwurf → aktiv → abgeschlossen / storniert)
- ein **Start- und Enddatum** (inkl. Rückgabefrist bei Leihe)
- eine **Referenznummer** (für interne und externe Korrespondenz)
- **freie Metadatenfelder** (wie alle anderen Katalon-Typen)
- **Verknüpfungen** zu Objekten, Entitäten und Orten über das bestehende Relationssystem

Vorgänge sind **keine Ereignisse** im FRBR-Sinne. Ein Konzert ist ein Ereignis; der Leihvertrag für das ausgestellte Instrument ist ein Vorgang.

---

## Vorgang-Typen

| Typ | Bezeichnung | Typisches Szenario |
|-----|-------------|-------------------|
| `loan_out` | Leihgabe ausgehend | Eigenes Objekt geht an externe Institution |
| `loan_in` | Leihgabe eingehend | Fremdes Objekt kommt zur Ausstellung ins Haus |
| `acquisition` | Erwerbung | Kauf, Schenkung, Übertragung |
| `conservation` | Restaurierung / Konservierung | Behandlung durch eigene oder externe Werkstatt |
| `object_entry` | Eingangsprüfung | Ersterfassung / Eingangsprotokoll |
| `deaccession` | Deakzession | Verkauf, Abgang, Aussonderung |

Alle Typen nutzen dieselbe technische Grundlage; was sichtbar ist und welche Felder relevant sind, bestimmt der Typ.

---

## Sammlungsstatus auf Objekten

Vorgänge verändern den **Sammlungsstatus** eines Objekts. Katalon führt dazu ein nicht-konfigurierbares Statusfeld direkt am Objekt:

| Status | Bedeutung |
|--------|-----------|
| `active` | Im Bestand, verfügbar |
| `pending` | Erwerbung läuft, noch nicht offiziell im Bestand |
| `on_loan_out` | Eigenes Objekt ist als Leihgabe außer Haus |
| `on_loan_in` | Fremdes Leihgut, vorübergehend im Haus |
| `deaccessioned` | Ausgeschieden, nicht mehr im Bestand |
| `returned` | Leihgabe zurückgegeben (vor Deakzession) |

Der Status wird **nicht automatisch** gewechselt. Beim Abschließen eines Vorgangs erscheint ein Dialog: *„Sammlungsstatus von X Objekten auf ‚active' setzen?"* – die Entscheidung liegt bei der Sachbearbeiterin.

Im Admin-Formular ist der Sammlungsstatus zusätzlich direkt am Objekt sichtbar und bearbeitbar. Vorgänge können damit den Status setzen, aber sie sind nicht die einzige Änderungsquelle.

---

## User Stories

### Leihgabe ausgehend (loan_out)

**Als Leiterin des Leihverkehrs möchte ich** einen ausgehenden Leihvertrag für ein Objekt anlegen, das für sechs Monate an das Museum B geht – **damit** Versicherung, Standort und Rückgabefrist dokumentiert sind.

*Umsetzung in Katalon:*
1. Neuen Vorgang anlegen → Typ „Leihgabe ausgehend"
2. Rückgabefrist als `due_date` setzen
3. Empfangende Institution (Entität im System) verknüpfen
4. Objekt(e) verknüpfen – Katalon prüft: gibt es bereits eine aktive Leihgabe für dieses Objekt? Falls ja, Fehlermeldung
5. Vorgang auf „aktiv" setzen → Dialog schlägt vor, Objekt-Status auf `on_loan_out` zu setzen
6. Abschluss bei Rückkehr → Status des Vorgangs auf „abgeschlossen", Objekt zurück auf `active`

**Als Registrar möchte ich** auf einen Blick alle Objekte sehen, deren Rückgabefrist in den nächsten 30 Tagen abläuft – **damit** ich rechtzeitig Erinnerungen versenden kann.

*Umsetzung in Katalon:*  
Vorgangsliste mit Filter auf `loan_out + due_date ≤ heute+30 + status=active`.

---

### Leihgabe eingehend (loan_in)

**Als Ausstellungskuratorin möchte ich** ein fremdes Objekt für unsere Ausstellung erfassen, auch wenn wir es nicht besitzen – **damit** es im Kontext der Ausstellung dokumentiert und versichert ist.

*Umsetzung in Katalon:*
1. Objekt anlegen (Sammlungsstatus: `on_loan_in`)
2. Vorgang „Leihgabe eingehend" anlegen
3. Leihgebende Institution (Entität) verknüpfen
4. Rückgabedatum, Versicherungswert als Metadatenfelder
5. Nach Rückgabe: Vorgang abschließen, Objekt auf `returned` setzen

---

### Erwerbung (acquisition)

**Als Sammlungsverantwortlicher möchte ich** den Ankauf eines Objekts dokumentieren – von der ersten Anfrage bis zur Übernahme in den Bestand – **damit** die Provenienz lückenlos nachvollziehbar ist.

*Umsetzung in Katalon:*
1. Objekt anlegen (Sammlungsstatus: `pending`)
2. Vorgang „Erwerbung" anlegen
3. Verkäufer/Schenkende (Entität), Kaufpreis, Erwerbungsart als Metadaten
4. Genehmigungsweg in Notizen dokumentieren
5. Bei Abschluss → Dialog: Sammlungsstatus auf `active` setzen

---

### Restaurierung / Konservierung (conservation)

**Als Restauratorin möchte ich** alle durchgeführten Maßnahmen an einem Objekt chronologisch festhalten – **damit** zukünftige Behandlungen den Zustand besser einschätzen können.

*Umsetzung in Katalon:*
1. Vorgang „Restaurierung" anlegen
2. Durchführende (Entität: intern oder externe Werkstatt) verknüpfen
3. Befundbeschreibung, Maßnahmen, Materialien als freie Metadatenfelder
4. Mehrere Restaurierungen pro Objekt möglich (keine Einschränkung, keine Statusänderung nötig)
5. Vollständige History im Audit Log

---

### Deakzession (deaccession)

**Als Direktor möchte ich** den Abgang eines Objekts mit Begründung und Genehmigung dokumentieren – **damit** der Vorgang revisionssicher nachvollziehbar ist, auch wenn das Objekt aus dem Bestand verschwunden ist.

*Umsetzung in Katalon:*
1. Vorgang „Deakzession" anlegen
2. Begründung, Genehmigungsbeschluss als Metadaten
3. Empfangende Institution / Käufer (Entität) verknüpfen
4. Bei Abschluss → Objekt-Status auf `deaccessioned` (bleibt im System, ist nicht gelöscht)

---

## Gleichzeitige Vorgänge

Mehrere Vorgänge können gleichzeitig aktiv sein:

| Situation | Erlaubt? |
|-----------|----------|
| Objekt in Restaurierung + aktive Ausstellung (Leihgabe aus) | ✅ Ja |
| Zwei gleichzeitige Restaurierungen am selben Objekt | ✅ Ja |
| Zwei gleichzeitige ausgehende Leihgaben desselben Objekts | ❌ Nein – ein Objekt kann physisch nur an einem Ort sein |

Die letzte Einschränkung wird systemseitig geprüft: Beim Aktivieren einer zweiten `loan_out`-Leihgabe für dasselbe Objekt erscheint eine Fehlermeldung.

---

## Verlängerung von Leihgaben

Leihgaben werden verlängert, indem das `due_date` des bestehenden Vorgangs aktualisiert wird – kein neuer Vorgang nötig. Die komplette Änderungshistorie (wer hat wann verlängert) ist im Audit Log sichtbar.

---

## Was Katalon *nicht* verwaltet

Um den Scope realistisch zu halten, sind folgende Funktionen bewusst ausgespart:

- **Dateianhänge auf Vorgängen** (Leihverträge, PDFs): Referenznummern werden als Freitext gespeichert; Dokumente liegen im DMS
- **Automatische Statusübergänge** (z. B. Objekt wird automatisch „zurückgegeben" wenn Rückgabedatum verstrichen): Bewusste Entscheidung für manuelle Kontrolle
- **Automatische Referenznummernvergabe**: Generierung nach institutionsspezifischer Logik ist zu divers; Feld ist Freitext
- **Per-Objekt strukturierte Zusatzfelder auf Vorgangs-Relationen** (z. B. individuelle Versicherungswerte pro Objekt innerhalb einer Mehrfach-Leihgabe): Post-MVP

---

## Sichtbarkeit im Portal

- Das öffentliche Portal zeigt standardmäßig nur Objekte mit Sammlungsstatus `active`
- Die öffentliche Elasticsearch-Suche filtert anonyme Treffer ebenfalls auf aktive Objekte. Nach Deployments, die `collection_status` neu in den Index aufnehmen, muss der Objektindex neu aufgebaut werden.
- Leihgaben, Erwerbungen, Restaurierungen sind **nicht öffentlich** (interne Vorgänge)
- Ausnahme: Sammlungsverantwortliche können einzelne Vorgangsdetails manuell in Objektbeschreibungen einarbeiten

---

## Technische Umsetzung (Kurzfassung für Interessierte)

- Neue Datenbanktabelle `procedures` mit Pflichtfeldern und freiem `metadata_`-JSONB
- Sammlungsstatus auf `objects` als nicht-konfigurierbares Systemfeld
- Verknüpfung mit Objekten, Entitäten, Orten über das bestehende Relationssystem
- Admin-Listenfilter für Vorgangstyp, Status, Fälligkeit und Referenznummer
- Öffentliche Suche über Elasticsearch respektiert `collection_status=active`
- Vollständiges Audit Log bei jedem Statuswechsel
- Neue Admin-Screens: Vorgangsliste, Vorgangs-Formular
- Kein neues Datenbankvolumen nötig, keine Architekturänderung

### API-Endpunkte

- `GET /v1/procedures` mit `status`, `procedure_type`, `due_before`, `reference_number`, `q`
- `POST /v1/procedures`
- `GET /v1/procedures/{id}`
- `PUT /v1/procedures/{id}`
- `DELETE /v1/procedures/{id}`
- `POST /v1/procedures/{id}/complete` mit optionalem `collection_status`

### Reindex nach Deployment

Für bestehende Daten muss nach dem Deployment mindestens der Objektindex neu aufgebaut werden, damit öffentliche Suche den neuen Sammlungsstatus kennt:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex/object
```

Alternativ vollständig neu indexieren:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex
```

---

## Zeitplan

Phase 14 ist als **Post-Beta**-Feature geplant. Beta-kritische Arbeiten (Suche, Indexierung, Importer) haben Vorrang. Sobald diese abgeschlossen sind, ist Phase 14 der nächste logische Schritt.

Geschätzter Aufwand: 3–4 Entwicklungstage für Backend + Admin-UI (ohne Dateianhänge, ohne automatische Statusübergänge).
