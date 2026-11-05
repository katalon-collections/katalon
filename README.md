# Katalon Collections

Katalon Collections ist ein Open-Source-System zur Erfassung, Verwaltung und
Veröffentlichung von Metadaten für Museen, Archive, Bibliotheken und Sammlungen.
Institutionen installieren und betreiben ihre eigene Instanz.

Felder, Subtypen, Vokabulare und Formulare werden in der Admin-Oberfläche
konfiguriert. Ein öffentliches Portal erschließt freigegebene Datensätze über
Suche, Facetten und Medienansichten. REST-API, OAI-PMH und konfigurierbare
Export-Mappings ermöglichen die Anbindung anderer Systeme.

Das Projekt ist unabhängig vom Test-Automatisierungsprodukt
[katalon.com](https://katalon.com/).

## Funktionen

- **Metadaten konfigurieren:** Feldtypen, Gruppen, wiederholbare und
  mehrsprachige Werte, Pflichtfelder und Subtypen in der Oberfläche verwalten.
- **Datensätze verknüpfen:** Fachliche Beziehungen als Schemafelder erfassen und
  durch freie Beziehungen ergänzen; ausgewählte verknüpfte Werte für Suche und
  Facetten verwenden.
- **Daten importieren:** CSV, TSV, Excel und XML zuordnen, transformieren und im
  Probelauf prüfen. Der generische Metadatenimport unterstützt Objects, Entities,
  Places und Occurrences. Ein separater Medienimport ordnet Dateien zu.
- **Kontrollierte Begriffe verwenden:** Hierarchische Vokabulare pflegen und
  Normdaten unter anderem aus GND, GeoNames, VIAF, Wikidata, Getty und ICONCLASS
  suchen und verknüpfen.
- **Medien präsentieren:** Bilder über IIIF anzeigen sowie PDFs, Audio, Video und
  unterstützte 3D-Dateien einbinden. Masterdateien und Bildpyramiden bleiben
  getrennt; Medien können einzeln von der öffentlichen Anzeige ausgenommen werden.
- **Metadaten ausgeben:** Feld-Mappings unter anderem für Dublin Core, LIDO und
  METS/MODS konfigurieren, OAI-PMH bereitstellen und Daten als CSV oder JSON
  exportieren. Fachliche Export-Mappings werden pro Installation eingerichtet.
- **Redaktionelle Arbeit unterstützen:** Rollenrechte, Arbeitslisten,
  Massenbearbeitung, Audit-Log, Snapshots für unterstützte Typen, Versionsprüfung
  und Bearbeitungssperren nutzen.
- **Portal gestalten:** Titel, Logo, Farben, Startseite, Footer und
  Detaildarstellung konfigurieren; eigene Theme-Pakete ohne Frontend-Neubau laden.
- **Optionale Erweiterungen nutzen:** RDF-Projektion in Oxigraph, lesende
  SPARQL-Abfragen und KI-gestützte Vorschläge bei entsprechender Konfiguration
  aktivieren.

Admin und Portal bieten deutsche und englische Oberflächentexte.
Mehrsprachige Metadaten und Labels können weitere institutionell konfigurierte
Sprachen verwenden. Zusätzliche UI-Sprachen benötigen passende Übersetzungen.
Tastaturbedienung, sichtbarer Fokus und zugängliche Formulare gehören zu den
Designzielen.

## Datensatztypen

| Typ | Zweck |
|---|---|
| Object | Sammlungsgut, Dokumente und Digitalisate |
| Entity | Personen und Körperschaften |
| Place | Geografische Orte |
| Occurrence | Werke, Ereignisse und Konzepte |
| Collection | Sammlungen, Bestände und Archivtektonik |
| Storage Location | Interne Lagerorte mit Gebäude-/Raum-/Regalhierarchie |
| Procedure | Vorgänge wie Leihverkehr, Erwerbung und Restaurierung |

Alle sieben Kerntypen besitzen eigene Tabellen, Versionen und konfigurierbare
Metadaten. Lagerorte und Vorgänge bleiben interne Verwaltungsdaten. Die fünf
Bestands- und Sammlungstypen können nach Freigabe im Portal erscheinen.

## Installation und Betrieb

Für eine Produktionsinstanz wird die separate
[katalon-cli](https://github.com/katalon-collections/katalon-cli) verwendet.
Sie installiert veröffentlichte, versionierte Container-Images und verwaltet
Updates im Instanzverzeichnis. Voraussetzungen sind Docker mit Compose v2 und
[uv](https://docs.astral.sh/uv/) für die Installation der CLI.

```bash
uv tool install katalon-cli
katalon install
```

Die Installation fragt die Instanzkonfiguration ab. Das Portal ist am
konfigurierten Host erreichbar, die Admin-Oberfläche unter `/admin/` und die
API-Dokumentation unter `/api/docs`. Erstzugang und weitere Installationsoptionen
sind in der [Anwenderdokumentation](https://katalon-collections.github.io/katalon-docs/)
beschrieben.

Die Betreiberinstitution verantwortet Zugriffsschutz, Updates, Monitoring,
Backups und Wiederherstellung ihrer Installation. Katalon ist kein zentral
betriebener Hostingdienst. Vor dem produktiven Einsatz sollten die eigenen
Erfassungs-, Veröffentlichungs- und Wiederherstellungsabläufe geprüft werden.

## Architektur und Integration

PostgreSQL mit PostGIS ist der Primärspeicher. Elasticsearch hält die
Suchprojektion, Celery und Redis übernehmen Hintergrundaufgaben, Cantaloupe
liefert IIIF-Bilder. Admin und Portal sind getrennte React-/TypeScript-Apps vor
einem Python-/FastAPI-Backend. Oxigraph ist optional.

Die authentifizierte API liegt unter `/v1/`, das öffentliche Read-Modell unter
`/portal/v1/`. Updates versionierter Records benötigen den aktuellen
`If-Match`-Wert. Integrationen sollten die OpenAPI-Beschreibung der jeweiligen
Installation verwenden.

Theme-Pakete bestehen aus einem `theme.json` und den referenzierten lokalen
Dateien. Sie werden über einen Mount und `PORTAL_THEME` in der
Backend-Konfiguration eingebunden. Das Backend liefert die Theme-Styleschicht;
Portal-Einstellungen ergänzen die institutionellen Farben und Inhalte.
Die [Theme-Anleitung](https://katalon-collections.github.io/katalon-docs/administration/portal-themes/)
erklärt Einrichtung und Priorität der beiden Ebenen.

## Entwicklung am Quellcode

Für Entwicklung und Beiträge kann dieses Repository lokal gebaut werden:

```bash
git clone https://github.com/katalon-collections/katalon.git
cd katalon
make dev
```

Der Docker-Dev-Stack bietet Live-Reload für Backend und Frontends. Admin läuft
unter `http://localhost:4000`, Portal unter `http://localhost:4001` und die
API-Dokumentation unter `http://localhost:8000/api/docs`.

`make up` startet den produktionsnahen Source-Stack. Dort werden Admin über
`http://localhost/admin/` und Portal über `http://localhost/` aufgerufen.
Dieser Entwicklungsweg ist von der Installation über die CLI getrennt.

## Dokumentation und Sicherheitsmeldungen

Die [Anwenderdokumentation](https://katalon-collections.github.io/katalon-docs/)
erklärt Bedienung und Konfiguration. Die OpenAPI-Dokumentation der Instanz
beschreibt die verfügbaren API-Endpunkte.

Für Sicherheitsmeldungen gilt [SECURITY.md](SECURITY.md).

## Lizenz

[AGPL-3.0-or-later](LICENSE)

### Haftungsausschluss

Katalon Collections wird als freie Open-Source-Software unter der GNU Affero General Public License v3.0 (AGPL-3.0) bereitgestellt.

Die Software wird "wie besehen" und ohne jegliche Gewährleistung bereitgestellt, wie in der Lizenz näher spezifiziert.

Katalon Collections kann zur Speicherung, Verwaltung und Veröffentlichung wertvoller, vertraulicher oder personenbezogener Daten eingesetzt werden. Betreiberinstitutionen sind allein verantwortlich für den sicheren Einsatz und Betrieb ihrer Installation, insbesondere für:

- regelmäßige und getestete Backups,
- Zugriffskontrolle und Authentifizierung,
- TLS und Netzwerksicherheit,
- sichere Konfiguration und Secrets-Management,
- Einspielen von Sicherheits- und Abhängigkeits-Updates,
- Einhaltung geltender datenschutzrechtlicher und sonstiger gesetzlicher Anforderungen,
- Prüfung und Test vor dem Einsatz in Produktivumgebungen.

Keine Software kann vollständigen Schutz vor Softwarefehlern, Datenverlust, unbefugtem Zugriff oder anderen Sicherheitsvorfällen garantieren.

Bitte [LICENSE](LICENSE), [DISCLAIMER.md](DISCLAIMER.md) und [SECURITY.md](SECURITY.md) vor dem Produktiveinsatz von Katalon Collections lesen.
