# Changelog

Diese Übersicht zeigt neu eingeführte Funktionen von Katalon Collections, Version für
Version. Bugfixes, Regressionen, interne Refactorings, CI-/Test-Infrastruktur und reine
Dokumentationsänderungen sind bewusst nicht enthalten, um die Historie lesbar zu halten.

## [1.39.0]

- **KI-Vorschläge im Editor prüfen:** KI-Vervollständigungen werden vor dem Übernehmen
  in einem bearbeitbaren Dialog angezeigt. So bleibt die fachliche Kontrolle erhalten;
  weitgehend übernommene Vorschläge sind weiterhin transparent als KI-generiert markiert.

## [1.38.0]

- **Automatische & manuelle Papierkorb-Bereinigung:** In den Admin-Einstellungen kann
  die automatische endgültige Löschung aktiviert und eine Aufbewahrungsfrist in Tagen
  festgelegt werden. Gelöschte Einträge können zudem manuell endgültig aus dem
  Papierkorb entfernt werden.
- **METS/MODS-Export & Einzelsatz-Download:** Grundlegend überarbeiteter METS/MODS-Standardexport
  sowie die Möglichkeit, Exporte einzelner Datensätze direkt aus der Bearbeitungsansicht
  herunterzuladen.
- **Hinweis auf leere öffentliche Sammlungen:** Die Admin-Oberfläche weist darauf hin,
  wenn eine als öffentlich markierte Sammlung keine sichtbaren Objekte enthält.

## [1.37.0]

- **Autoritätsdaten für Objekt-Subtypen:** Subtypen können mit AAT-, GND- oder
  URI-Normdaten verknüpft werden; der LIDO-Export nutzt diese Verknüpfung wahlweise
  als Klassifikationsquelle.
- **Verbesserter Beziehungs-Export:** Export-Mappings können jetzt auch Beziehungen
  auswerten, bei denen der aktuelle Datensatz das Ziel statt die Quelle ist (z. B.
  Objekte, auf die ein Vorgang verweist). Die Auswahl der Beziehungsart im
  Mapping-Editor ist jetzt eine geführte Auswahlliste statt Freitext.
- **Benutzer per Kommandozeile anlegen:** Neuer `katalon-manage create-user`-Befehl
  für Betreiber, die Konten ohne die Admin-Oberfläche einrichten möchten.

## [1.36.0]

- **KI-gestützte Übersetzung im Editor:** Mehrsprachige Textfelder können direkt im
  Formular per KI-Assistent in die konfigurierten Zielsprachen übersetzt werden.
- **Mehrsprachiges Portal-Branding:** Site-Titel, Untertitel und Hero-Texte lassen sich
  in den Admin-Einstellungen für jede unterstützte Sprache separat pflegen und wechseln
  im Portal mit der gewählten Nutzersprache.
- **Lokalisierte Vokabulare im Portal:** Begriffe aus kontrollierten Vokabularen werden
  in der Suche und auf Detailseiten automatisch in der aktiven Sprache angezeigt.
- **Einheitliche Typ-Kennzeichnung in der Portalsuche:** Suchtreffer tragen in Listen-
  und Kachelansicht eine konsistente Subtyp-Pill am Titel; redundante Standarduntertitel
  entfallen.
- **KI-Transparenz für Sammlungen und Lagerorte:** KI-generierte Feldwerte werden nun
  auch für Sammlungen und Standorte mit Modell und Zeitstempel transparent markiert.

## [1.35.0]

- **Subtyp-Facette in der Portal-Suche:** Objekte, Entitäten, Orte und Occurrences
  lassen sich jetzt zusätzlich nach ihrem konkreten Subtyp filtern (z. B.
  Gemälde/Skulptur/Archivalie), inklusive Trefferzahlen und Anzeige in der Trefferliste.

## [1.34.6]

- **Batch-Operationen für Lagerorte:** Massenbearbeitung von Feldern und Beziehungen
  steht jetzt auch für Lagerorte zur Verfügung, analog zu den übrigen Kerntypen.

## [1.34.4]

- **Erweitertes Betriebs-Monitoring:** Der Health-Check prüft jetzt zusätzlich Redis,
  Cantaloupe, Oxigraph sowie einen Celery-Heartbeat und liefert Warteschlangenlänge
  und Backup-Alter — hilfreich für Alarmierung im Produktivbetrieb.

## [1.34.0]

- **Mobile Portal-Kopfzeile:** Kompaktes Hamburger-Menü für Sprache, Login/Logout und
  erweiterte Suche auf schmalen Bildschirmen; Facetten öffnen dort als Overlay statt
  dauerhaft Platz zu belegen.
- **`idno` als konfigurierbares Systemfeld:** Die ID-Nummer verhält sich jetzt wie das
  Titelfeld als geschütztes, aber im Anzeigenamen anpassbares Systemfeld.

## [1.32.0]

- **IIIF-Manifest-Link ein-/ausblendbar:** Neuer Schalter in den Admin-Einstellungen,
  um den öffentlichen IIIF-Manifest-Button auf Objektseiten zentral zu steuern.

## [1.31.2]

- **KI-Transparenz:** Feldwerte, die per KI-Assistent übernommen wurden, sind direkt
  am Feld als KI-generiert markiert (Modell + Zeitpunkt) — sichtbar für Redakteure
  und, bei öffentlichen Feldern, im Portal.

## [1.31.0]

- **Wiederverwendbare Import-Mappings:** Import-Zuordnungen lassen sich in der
  Admin-Oberfläche als Vorlage speichern, aktualisieren und für den jeweiligen
  Datensatztyp wiederverwenden. Die CLI akzeptiert direkt exportierte JSON-Profile.

## [1.30.2]

- **Automatisches Beschreibungsfeld für Sammlungen:** Neu angelegte Sammlungen
  erhalten automatisch ein Richtext-Beschreibungsfeld.

## [1.30.0]

- **Subtyp-Platzhalterbilder:** Pro Objekt-Subtyp konfigurierbares Platzhalterbild für
  Datensätze ohne eigenes Medium.
- **Vor-/Zurück-Navigation auf Detailseiten:** Unauffällige Pfeile führen innerhalb der
  ursprünglichen Suche weiter, inklusive Nachladen weiterer Ergebnisseiten.

## [1.29.0]

- **Konfigurierbare Portal-Terminologie:** Die Bezeichnung der Kerntypen (z. B. „Werk“
  statt „Objekt“) lässt sich pro Installation und Sprache anpassen, getrennt nach
  Singular/Plural.

## [1.28.0]

- **Konfigurierbare Startseite:** Die Portal-Startseite besteht jetzt aus frei
  anordenbaren Inhaltsbausteinen (Text, neueste Objekte, kuratierte Auswahl,
  Sammlungen) statt einer festen Reihenfolge.

## [1.27.0]

- **S3-kompatibler Objektspeicher für Medien:** Alternative zum lokalen Speicher,
  kompatibel mit Ceph, MinIO, Hetzner Object Storage, Garage und AWS S3 (opt-in).

## [1.26.2]

- **Direkter Bearbeiten-Link im Portal:** Angemeldete Mitarbeitende mit Schreibrecht
  sehen auf Detailseiten einen Link direkt ins Admin-Bearbeitungsformular.

## [1.26.1]

- **Drei Suchansichten:** Liste, Masonry und Raster mit Umschalter, dazu optionales
  Endless Scrolling neben der klassischen Seitennummerierung.

## [1.26.0]

- **Preservation-Export (BagIt):** Manuell auslösbares Langzeitarchivierungspaket pro
  Objekt (RFC 8493) mit Dublin-Core-, METS- und PREMIS-Metadaten sowie Master- und
  Ableitungsdateien.

## [1.25.2]

- **Hierarchie-Browser für Vokabularfelder:** Baumstruktur direkt im Feld-Dropdown
  neben der Textsuche.

## [1.25.0]

- **Überarbeitetes Rollenkonzept:** Vier Standardrollen (Viewer, Cataloger, Editor,
  Admin) mit feingranularen, über die Admin-UI konfigurierbaren Feature-Rechten
  (Export, SPARQL, Import, Vokabular u. a.).
- **Manuelle exklusive Sperre:** Datensätze lassen sich mit Besitzer, Grund und
  Ablaufdatum (max. 7 Tage) gezielt sperren; Editoren und Admins können Sperren
  aufheben.

## [1.24.0]

- **Bearbeitungssperre (Presence Lock):** Zeigt an, wenn ein Datensatz gerade von
  jemand anderem bearbeitet wird — wahlweise als Warnung oder als harte Blockade
  beim Speichern.

## [1.23.1]

- **Maximalanzahl für wiederholbare Felder:** Konfigurierbares Limit, serverseitig
  durchgesetzt und im Formular sichtbar.

## [1.23.0]

- **Durchsuchbares Audit-Log:** Serverseitige Suche nach Datensatz, Kennung,
  Bearbeiter, Aktion oder Änderungsinhalt mit Datumsfilter.
- **Direktes Öffnen aus Listen:** Klick auf den Titel öffnet einen Datensatz sofort
  zur Bearbeitung.

## [1.22.0]

- **Konfigurierbare Formularabschnitte:** Schemafelder lassen sich benannten Tabs im
  Erfassungsformular zuordnen, inklusive Fehlermarkierung pro Tab.

## [1.21.0]

- **Facetten als klickbare Links auf Detailseiten:** Ein Klick auf einen als Facette
  markierten Feldwert führt direkt zur passend gefilterten Suche.

## [1.20.0]

- **Arbeitslisten (Working Sets):** Ad-hoc-Gruppierungen von Datensätzen für interne
  Workflows, mit Reordering, Notizen pro Eintrag und direkter Übergabe an die
  Massenbearbeitung.

## [1.19.19]–[1.19.22]

- **SPARQL & Linked Data:** Schreibgeschützter SPARQL-1.1-Endpunkt auf eine
  automatisch synchronisierte RDF-Projektion (Oxigraph), inklusive interaktivem
  Query Builder in der Admin-UI, gespeicherten Abfragen, Vorlagen für CIDOC-CRM/
  LRMoo sowie einer KI-gestützten Übersetzung natürlichsprachlicher Fragen in
  SPARQL-Abfragen (NL2SPARQL).

## [1.19.16]

- **Transitive Sammlungs- und Lagerort-Suche:** Ein Filter auf eine Obersammlung
  bzw. einen übergeordneten Lagerort findet automatisch auch Objekte in
  Teilbeständen bzw. Unterstandorten.

## [1.19.9]

- **Zwei weitere GND-Normdatenquellen:** Eigene, auf Personen bzw. Sachschlagwörter
  gefilterte GND-Quellen zusätzlich zur bisherigen allgemeinen Quelle.

## [1.19.8]

- **Duplizieren von Feldern und Vokabeltermen:** Felddefinitionen (inkl. Unterfelder)
  und Vokabularbegriffe lassen sich direkt kopieren.

## [1.19.7]

- **Konfigurierbare Rate-Limits und Crawler-Hinweise:** `.env`-gesteuerte Limits für
  öffentliche Endpunkte sowie `/robots.txt` und `/llms.txt` für Suchmaschinen- und
  LLM-Crawler.

## [1.19.4]

- **Kuratorische Sammlungsdetailseite:** Eigenständiges Portal-Layout mit
  Hero-Banner, Schnellsuche innerhalb der Sammlung, hierarchischem Kontextbaum und
  umschaltbarer Objektansicht (Galerie/Findbuchliste). Dazu Facettierung nach
  Sammlungen in der Suche.

## [1.19.0]

- **Neuer Primärtyp „Lagerort“:** Hierarchische Standortverwaltung physischer
  Aufbewahrungsorte (Haus → Raum → Regal → Box), mit eigenen Schemafeldern,
  Subtypen und Versionierung. Bewusst nicht im Portal sichtbar.

## [1.18.0]

- **Neuer Primärtyp „Sammlung“:** Vollwertiger Typ zur hierarchischen Erschließung
  von Sammlungen und Beständen, inklusive eigener Verwaltungsoberfläche und
  Objektzuordnung.

## [1.17.2]

- **Linked-Data-Export nach CIDOC-CRM & LRMoo:** Strukturierter RDF-/JSON-LD-Export
  pro Datensatz und über OAI-PMH, inklusive Relationsauflösung und
  SKOS-Vokabularbegriffen.

## [1.17.1]

- **SKOS-Import für Vokabulare:** Selektiver Import aus Turtle, RDF/XML, JSON-LD und
  N-Triples, inklusive mehrsprachiger Labels, Cross-Konkordanzen und Hierarchie.

## [1.17.0]

- **Kanonische URIs für Vokabulare:** Eigene URI- und Cross-Konkordanz-Felder
  (`skos:exactMatch`) für Vokabulare und Terme, z. B. für Getty AAT oder GND.

## [1.16.0]

- **Erweiterte Admin-Kopfsuche:** Durchsucht jetzt auch Nutzer, Vokabulare,
  statische Seiten, Schemafelder, Subtypen, Banner und Normdatenquellen.

## [1.15.10]

- **PID-Reservierung und URL-Feldtyp:** Felder können ARKs oder DNB-URNs
  automatisch beim Veröffentlichen reservieren; ein neuer Feldtyp speichert Links
  mit optionalem Titel.

## [1.15.3]

- **Sortierbare Listenspalten:** ID-Nr., Status und „Geändert“ lassen sich per
  Klick auf den Spaltenkopf sortieren.

## [1.15.0]

- **E-Mail-Versand für Staff-Konten:** SMTP-gestützter Passwort-Reset sowie
  Benachrichtigungen zu Importen und Batch-Bearbeitungen.

## [1.14.0]

- **Konfigurierbare Facetten-Anzeige:** Sortierung (Trefferanzahl/alphabetisch) und
  Startanzahl sichtbarer Werte global im Portal-Admin einstellbar.

## [1.13.0]

- **Interne Portal-Recherche mit Staff-Login:** Bestehende Katalon-Konten
  ermöglichen berechtigten Mitarbeitenden Zugriff auf interne Datensätze und
  zusätzliche Schemafelder direkt im Portal.

## [1.12.7]

- **Starter-Helm-Chart:** Proof-of-concept für Kubernetes-Deployment.

## [1.12.5]

- **Platzierung statischer Seiten:** Wahlweise in der Kopfzeile, im Footer oder
  ganz ohne sichtbaren Link.

## [1.12.0]

- **Präzise Zahlenfacetten:** Von/Bis-Bereiche mit nativen Schiebereglern.
- **Gekachelte IIIF-Ableitungen:** Bilder werden beim Upload als Pyramid-TIFF
  vorbereitet, spürbar schnelleres Zoomen im Viewer.

## [1.10.0]

- **Vollständig zweisprachige Admin-Oberfläche:** Deutsch/Englisch für alle
  Admin-Bereiche, inklusive Sprachumschaltung.

## [1.9.2]

- **Eingebettete Karte für Ortsnormdaten:** GeoNames-Felder zeigen eine
  OpenStreetMap-Karte im Admin-Formular und auf Portal-Detailseiten.

## [1.8.0]

- **Vokabularvorschläge in der erweiterten Suche:** Feste Vokabularfelder bieten
  zulässige Begriffe an, freie Felder schlagen konfigurierte Begriffe vor.

## [1.7.0]

- **Erweiterte Portalsuche:** Kombinierbare Feldbedingungen mit UND/ODER-Gruppen
  und bis zu zwei Relationsschritten, als teilbare URL.

## [1.6.0]

- **Export-Bereich im Admin:** CSV-/JSON-Datendumps pro Bestandstyp; Export-Formate
  (OAI-DC, LIDO, METS/MODS) sind als erweiterbares Plugin-Register aufgebaut.

## [1.5.0]

- **Getty AAT als Normdatenquelle**, dazu eine Admin-Übersicht aller
  Normdatenquellen mit Aktivieren/Deaktivieren und Verbindungstest.

## [1.4.4]

- **Hierarchische Vokabularpflege:** Vokabulare lassen sich als Baum mit
  Eltern-/Unterterm-Beziehungen pflegen.

## [1.4.2]

- **WYSIWYG-Editor für Richtext-Felder:** Formatierungs-Toolbar bei weiterhin
  Markdown-basierter Speicherung.

## [1.4.0]

- **Massenbearbeitung:** Status setzen, Felder setzen/anhängen/leeren und
  Relationen hinzufügen/entfernen für ganze Auswahlen oder komplette Suchergebnisse.

## [1.3.0]

- **Konfigurierbare Detailseiten-Layouts:** Pro Feld einstellbar, ob es im
  Hauptbereich oder in der Seitenspalte erscheint, plus globale Sidebar-Position.

## [1.2.20]

- **Konfigurierbarer Trefferlisten-Untertitel:** Pro Datensatztyp wählbar aus Typ,
  Status und aktivierten Facettenfeldern.

## [1.2.15]

- **Interne Felder:** Werte lassen sich als „nur für Mitarbeitende“ markieren und
  bleiben aus allen öffentlichen Ausgaben ausgeschlossen.

## [1.2.12]

- **Browsing-Menüpunkte ein-/ausblendbar:** Pro Datensatztyp im Portal steuerbar.

## [1.2.10]

- **Management-CLI `katalon-manage`:** Kommandozeilenwerkzeuge für Datenbank-Reset,
  CSV-/XML-Import und Admin-Passwort-Reset.

## [1.2.6]

- **Mehrdatei-XML-Import:** Mehrere XML-Dateien (z. B. LIDO-Exporte) lassen sich in
  einem Lauf gemeinsam importieren.

## [1.1.2]/[1.1.1]

- **Datumsfelder mit Zeiträumen und Unschärfe (EDTF-lite):** Freitext-Eingaben wie
  „ca. 1900“, „vor 1900“ oder „1900 bis 1950“ sowie Jahre v. Chr.

## [1.1.0]

- **KI-Assistent für die Schema-Verwaltung:** Felddefinitionen per Chat mit
  konfigurierbarem OpenAI-kompatiblem Provider generieren.

## [1.0.5]

- **Soft-Delete mit Wiederherstellung:** Gelöschte Datensätze landen im Papierkorb
  mit konfigurierbarer Aufbewahrungsfrist statt sofort endgültig gelöscht zu werden.

## [1.0.0]

- **Medienformate über Bilder hinaus:** PDF, Audio, Video und 3D-Modelle sind
  hochladbar, mit passendem Viewer im Portal.
- **Mehrsprachigkeit:** Konfigurierbare Sprachliste, mehrsprachige Labels und
  übersetzbare Text-/Richtext-Felder mit Sprachumschalter im Portal.

## [0.11.8]

- **Automatische Spaltenzuordnung beim Import:** Heuristik erkennt passende
  Zielfelder für CSV-/Excel-Spalten automatisch.

## [0.11.5]

- **Anonymes Portal-API getrennt von der Arbeits-API:** Öffentliche Leserouten unter
  `/portal/v1`, während `/v1` künftig ein Token verlangt.

## [0.10.28]

- **Konfigurierbare Rollenrechte:** CRUD-Rechte pro Primärtyp und Rolle in einer
  Matrix in der Benutzerverwaltung einstellbar.

## [0.10.13]

- **Fester Relationstyp pro Feld:** Relationsfelder können einen Relationstyp aus
  ihrem Vokabular fest vorgeben.

## [0.10.12]

- **Verknüpfte Felder als Portal-Facetten:** Werte aus verknüpften Datensätzen
  lassen sich als Facette im Portal nutzen.

## [0.10.0]

- **Relationstypen mit Typ-Einschränkung:** Relationstyp-Vokabeleinträge lassen
  sich auf zulässige Quell-/Zieltypen beschränken.

## [0.9.0]

- **Geführte Onboarding-Tour** für die Admin-Erstanmeldung, jederzeit über das
  Hilfe-Icon erneut startbar.

## [0.8.1]

- **Felder per Drag & Drop umsortieren** im Schema-Editor.

## [0.8.0]

- **Schnellanlage verknüpfter Datensätze:** Objekte, Entitäten, Orte, Occurrences
  und Vorgänge lassen sich direkt aus Relationsfeldern als Entwurf anlegen und
  automatisch verknüpfen.

## [0.7.6]

- **Vollständig responsive Admin-Oberfläche:** Bedienbar bis hinunter zu 319 px
  Bildschirmbreite.

## [0.7.5]/[0.7.4]

- **KI-Unterstützung und Normdatenfelder in wiederholbaren Gruppen:** KI-Vorschläge
  und Authority-Felder stehen jetzt auch als Subfelder von Containergruppen zur
  Verfügung.

## [0.7.0]

- **Formularvarianten:** Benannte, reduzierte Feldauswahlen pro Datensatztyp und
  Subtyp (Voll-, Schnellerfassung, workflow-spezifische Masken) mit Rollen-Defaults.

## [0.6.2]

- **Optimistic Locking:** Paralleles Bearbeiten desselben Datensatzes wird über
  `If-Match`/Versionsnummer erkannt statt Änderungen stillschweigend zu
  überschreiben; Admin-UI bietet einen feldweisen 3-Wege-Merge-Dialog an.

## [0.5.10]

- **Automatisches Backup:** Täglicher Datenbank- und Medien-Dump mit
  konfigurierbarer Aufbewahrungsfrist, plus manueller One-Shot-Modus.

## [0.5.6]

- **Fuzzy-Clustering für Vokabular-Spalten im Import:** Erkennt Schreibweisen-
  Varianten und schlägt einen kanonischen Wert vor.

## [0.4.0]

- **Normdaten an Vokabulartermen:** Strukturierte Verweise auf GND, Geonames,
  Wikidata, Iconclass, VIAF und Getty TGN direkt am Vokabularbegriff.

## [0.3.3]

- **KI-gestützte Feldvorschläge:** Erste Version der KI-Unterstützung in
  Admin-Formularen für Vokabular-, Freitext-Vokabular- und Relationsfelder.

## [0.3.0]

- **Import-Fortschrittsanzeige und Abbrechen-Funktion:** Laufende Importe zeigen
  Fortschritt und Ergebnis über alle Screens hinweg an und lassen sich sauber
  abbrechen.

## [0.2.0]

- **Neuer Primärtyp „Vorgang“:** Interner Record-Typ für Leihverkehr, Erwerbung,
  Restaurierung u. a., mit Abschluss-Workflow, der verknüpfte Objekte automatisch
  aktualisiert.

## [0.1.22]

- **Gegenrichtungslabels für Relationen:** Relationstypen können ein eigenes Label
  für die umgekehrte Blickrichtung tragen.

## [0.1.9]

- **Feedback-Funktion:** Angemeldete Mitarbeitende können Feedback direkt aus der
  Admin-Oberfläche senden.

## [0.1.0] — Erste interne Testversion

- Bestandsverwaltung für Objekte, Entitäten, Orte und Occurrences mit frei
  konfigurierbarer Schema-Engine (inkl. Gruppierungsfeldern)
- Kontrollierte Vokabulare (streng und frei)
- Rollenbasierte Anmeldung (Admin, Editor, Viewer)
- Audit-Log und Versionierung/Snapshots für alle Datensätze
- Beziehungsverwaltung zwischen Datensätzen
- Medien-Upload mit IIIF-Kachelgenerierung (Cantaloupe)
- Volltextsuche und Facettierung (Elasticsearch)
- Öffentliches Portal mit Detailseiten und IIIF-Viewer
- Anbindung an Normdatenquellen: GND, VIAF, Wikidata, Geonames, Getty TGN, ICONCLASS
- Import-Assistent für CSV/TSV/Excel/XML mit Probelauf
- Massenimport von Medien (ZIP + Zuordnung)
- OAI-PMH-Schnittstelle mit Dublin-Core-Export
- Benutzerverwaltung und Subtyp-Konfiguration über die Admin-Oberfläche
