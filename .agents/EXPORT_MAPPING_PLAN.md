# Export-Mappings: Ergänzungsumfang

Dieser Entwurf hält weiterführende Anforderungen fest, nicht den aktuellen
Umsetzungsstatus. Vor einer Umsetzung sind die betroffenen Anforderungen gegen
Code und Tracker zu prüfen. Erledigte Phasenberichte werden nicht fortgeschrieben.

Aktueller Vertrag: [OAI und Export](../almanac/architecture/workflows/oai-and-export-mappings.md).
Die fachlichen Referenzfälle liegen im [Shape-Brief](EXPORT_MAPPING_SHAPE_BRIEF.md).
Offene Vorhaben werden über die Roadmap-Issues #263 und #264 geplant.

## Referenzfälle, Coverage und sichere Veröffentlichung

**Ziel:** Nutzer sehen nicht nur syntaktische Gültigkeit, sondern Auswirkungen auf reale Daten.

Aufgaben:

1. Minimierte, versionierte Referenz-Snapshots speichern.
2. Namespace-bewusste Fragmenterwartungen und Abwesenheitserwartungen unterstützen.
3. Coverage-Job für Mappingquellen und Profilzweige ergänzen.
4. Vergleich Entwurf gegen veröffentlichte Revision anbieten.
5. Veraltete Regeln nach Schema-/Profiländerungen blockieren.
6. Letzte veröffentlichte Revision rücksetzbar halten.

Abnahme:

- Eine Änderung, die Fotografen verliert, wird am BPK-Referenzfall erkannt.
- Eine Änderung an Medienrechten zeigt betroffene Datensätze in der Coverage.
- Ein Profilupgrade mit entferntem Ziel kann nicht still veröffentlicht werden.

## LLM-Assistenz

**Ziel:** Vorschläge verkürzen die Mappingarbeit, ohne Determinismus oder Datenschutz aufzugeben.

Betroffene Bereiche:

- bestehende AI-Konfiguration und Secret-Verwaltung wiederverwenden,
- neuer Backendservice für Mappingvorschläge,
- Suggestions-Inbox im Export-Arbeitsbereich,
- deutsche und englische Texte,
- Tests mit gemocktem Provider, nie mit Live-LLM in CI.

Aufgaben:

1. Promptkontext auf Capability-Profil, Felddefinitionen und freigegebene Beispielwerte begrenzen.
2. Strukturiertes Antwortschema verwenden, das nur bekannte Ziel- und Parameterwerte akzeptiert.
3. Jede Antwort serverseitig adaptervalidieren.
4. Konfidenz und Begründung anzeigen.
5. Einzelne und gesammelt markierte Vorschläge übernehmen können.
6. Keine automatische Veröffentlichung.
7. Ohne AI-Konfiguration keine leere oder defekte UX zeigen, sondern deterministische Hilfen verwenden.

Abnahme:

- Unbekannte Targets oder Operationen aus der Modellantwort werden verworfen.
- Der Nutzer sieht vor dem Senden, welche Daten den Provider erreichen.
- Abgelehnte Vorschläge verändern kein Mapping.
- Übernommene Vorschläge werden normale deterministische Regeln.

## Weitere Formate auf den gemeinsamen Kern migrieren

Diese Phase beginnt erst, wenn der BPK-LIDO-Schnitt produktiv funktioniert.

Reihenfolge:

1. METS/MODS auf Capability-Profil und Mappingrevisionen migrieren.
2. Dublin Core auf denselben Lebenszyklus umstellen, einfache UX behalten.
3. METS/PREMIS als neuer Adapter mit eigenen Struktur- und Validatorregeln ergänzen.
4. EAD erst nach Klärung der hierarchischen Exportquelle planen. EAD ist kein flacher Datensatzexport; Collection-Hierarchien und Reihenfolge sind eine eigene fachliche Anforderung.

Keine abstrakten PREMIS- oder EAD-Klassen vor dem ersten konkreten Profil und Beispieldatensatz anlegen.

## BPK-Mapping: fachliche Überführung

Die Excel-Datei wird nicht als dauerhafte Laufzeitkonfiguration importiert. Sie dient als Migrationsquelle und Abnahmecheckliste.

Überführungskategorien:

| CollectiveAccess-Konstrukt | Katalon-Ziel |
|---|---|
| Mapping mit `ca_objects.*` | Feld- oder Datensatzquelle |
| `ca_entities.*` plus `restrictToRelationshipTypes` | Relationsquelle mit Relationstyp und Zielwert |
| `ca_places.*` über Entitätsbeziehung | explizite Relationskette, nur wenn Profil sie unterstützt |
| `ca_list_items.*` | Vokabularfeld oder kanonischer Vokabular-URI |
| `ca_object_representations.*` | Medienquelle |
| `Constant` | Institutionsprofil oder Adapterkonstante |
| `prefix` | begrenzte Transformation oder kanonischer URL-Builder |
| Rechte-RegEx | kontrollierte Wertzuordnung über kanonische URIs |
| Datums-RegEx | typisierte Datumsprojektion |
| `omitIfEmpty` | Renderer-Standard; leere optionale Bundles werden nicht erzeugt |

Vor der Implementierung muss die Coding-Agentin oder der Coding-Agent die vollständigen 306 Zeilen in eine nachvollziehbare Checkliste überführen. Doppelte Strukturknoten zählen nicht als eigene fachliche Anforderung.

## Teststrategie

### Backend-Verträge

Neue fokussierte Tests:

- Capability-Vertrag jedes Adapters ist serialisierbar und intern konsistent.
- Adapter lehnt unbekannte Targets, Quellen und Einstellungen ab.
- `MappingSpec` erhält Einstellungen und Reihenfolge.
- Migration erhält vorhandene flache Mappings.
- Veröffentlichung ist atomar und versionsgeschützt.
- Nur veröffentlichte Revision wird disseminiert.
- Exportkontext filtert interne Felder und Medien.
- Relation und Relationstyp bleiben strukturiert.
- LIDO gruppiert wiederholte Ereignisse und Akteure korrekt.
- LIDO-Ausgabe besteht XSD-/Profilvalidierung.
- OAI-Resumption-Token und Format-Gating bleiben korrekt.
- Keine N+1-Datenbankabfragen im OAI-Seitenpfad.

### Referenzfixtures

Mindestens:

- BPK `os_ub_0029908` mit Verlag, Künstler, Gebrauchsdaten, Schlagwörtern und zwei Medien,
- minimaler Datensatz mit nur Pflichtangaben,
- mehrere Akteure gleicher Rolle,
- fehlende optionale Beziehungen,
- internes Feld und nicht öffentliches Medium,
- unbekannter Rechtewert,
- unvollständiges Datum,
- gelöschtes oder nicht öffentliches Relationsziel.

Fixtures enthalten nur für den Export notwendige öffentliche Werte.

### Frontend

Es gibt derzeit keine Frontend-Testbibliothek. Keine neue Testabhängigkeit allein für diese Funktion einführen. Vertragsschutz erfolgt durch TypeScript-Build, API-Integrationstests und die vorgeschriebene Browserfahrt. Eine Frontend-Testinfrastruktur ist nur dann Teil der Umsetzung, wenn sie separat beschlossen wird.

### Verifikation pro Änderung

Backend-Kommandos immer mit mindestens 32 Zeichen langem Testschlüssel, beispielsweise:

```bash
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest <fokussierte Tests>
```

Am Ende der programmatischen Änderung:

```bash
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest
cd frontend/admin && pnpm run lint && pnpm run build && pnpm run check:arch
```

Danach die tatsächliche Admin-Oberfläche über `http://localhost/admin/` und den OAI-Endpunkt über `http://localhost/oai` prüfen. Direkte Container-Ports 3000/3001 nicht verwenden.

## Performance- und Sicherheitsgrenzen

- Kein LLM-Aufruf beim Export, bei OAI oder beim Öffnen einer Vorschau.
- Keine PostgreSQL-Abfrage pro OAI-Treffer oder Mappingregel.
- Keine dynamische XSD-Netzwerkabfrage im Requestpfad.
- Keine ausführbaren Ausdrücke in Mappingregeln.
- Keine ungeprüften Regex-Ausdrücke im synchronen Exportpfad.
- Öffentliche Dissemination darf nur `is_public`-Felder und öffentliche Medien verwenden.
- Mapping- und Institutionsänderungen müssen im Audit-Log landen.
- Profil-/Rendererfehler liefern keine teilweise plausibel wirkenden XML-Dokumente als Erfolg.
- Elasticsearch-Ausfall behält das bestehende OAI-Verhalten `503` plus `Retry-After`.
- Profil- und Mappingrevision müssen im Diagnosepfad nachvollziehbar sein; kryptografisch signierte Exportkapseln sind nicht Teil des ersten Umfangs.

## Bewusst nicht im ersten Umfang

- universeller visueller XML-Baumeditor,
- freie XPath-/XSLT-/Jinja-Programmierung,
- vollständiger Import beliebiger CollectiveAccess-Exporterdefinitionen,
- automatische Veröffentlichung von LLM-Vorschlägen,
- EAD ohne konkreten Hierarchie- und Partnervertrag,
- PREMIS ohne konkretes LZA-/LZV-Profil,
- vollständige Speicherung jedes exportierten XML-Dokuments,
- kryptografische Signaturen und lückenlose Replay-Kapseln,
- Live-Tests gegen DDB oder Europeana in CI,
- Export/Import von Mapping-Sets zwischen Katalon-Instanzen (siehe Notiz unten).


## Pflege bei einer Umsetzung

Aktuelle Verhaltensdokumentation und technische Anleitungen nachziehen;
eine neue Architekturentscheidung zuerst in OKF festhalten. Backend-Verträge
gezielt testen, manuelle UI-Abnahme nach Projektregel durchführen. Der
Release- und Freigabevertrag aus `AGENTS.md` bleibt maßgeblich.
