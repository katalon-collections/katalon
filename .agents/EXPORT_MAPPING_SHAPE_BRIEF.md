# Shape-Brief: UX-geführte Export-Mappings

Status: Fachliche Referenz und weiterführende Anforderungen; kein Nachweis des Umsetzungsstands

## 1. Festgelegter Rahmen

Der Export-Mapper ist eine Admin-Arbeitsfläche für Fachadministrator:innen, die lokale Felder und Beziehungen kennen, aber XML oder LIDO nicht beherrschen müssen. Metadaten-Spezialist:innen prüfen technische Details und veröffentlichen den Stand. Die wichtigste Aktion ist deshalb nicht das Anlegen einer einzelnen Regel, sondern ein nachvollziehbar geprüftes Mapping zu veröffentlichen.

Register: `product`. Farbstrategie: `Restrained` gemäß `DESIGN.md`. Szene: Eine Fachadministratorin arbeitet tagsüber konzentriert an einem großen Monitor, vergleicht lokale Sammlungsdaten mit einem Lieferprofil und muss vor der Veröffentlichung sicher erkennen, welche Angaben fehlen oder anders ausgegeben werden.

Interaktionsanker sind GitHub Settings für klare Zustände und explizite Veröffentlichungsaktionen, Figma Inspector für die Auswahl-und-Eigenschaften-Struktur und OpenRefine für datenbezogene Vorschau und Fehlerprüfung. Katalons vorhandene Navigation, Buttons, Eingaben und Statusdarstellung bleiben maßgeblich.

Scope dieser Shape-Phase: drei Wireframes als Skizzen, der vollständige Arbeitsfluss und fünf konkrete BPK-Mappings. Kein interaktiver Prototyp und keine Codeänderung. Visuelle Bildproben entfallen, weil der Shape-Brief nur Sketch-Fidelity verlangt und die bestehende Designsprache in `DESIGN.md` festgelegt ist.

## 2. Informationsarchitektur

`Exporte` behält die Bereiche `Datenexport` und `Mappings`. Der Datensatztyp bleibt ein Filter auf Bereichsebene. Der Mapping-Bereich beginnt mit einer Formatübersicht. Ein komplexes Profil öffnet einen eigenen Arbeitsbereich; Dublin Core darf später eine kompakte Tabellenbearbeitung behalten.

Der Arbeitsbereich hat drei stabile Ebenen:

1. Format und Revision: Profil, Datensatztyp, veröffentlichter Stand, Entwurf und Prüfstatus.
2. Fachliche Zuordnung: Zielgruppe, fachliches Ziel, Quelle und Zielparameter.
3. Nachweis: Referenzdatensatz, Vorschau, Herkunft jedes Werts und Diagnosen.

XML-Pfade, Regel-UUIDs und rohe Konfiguration erscheinen nur im Expertenbereich. Sie sind keine primären Navigations- oder Eingabeelemente.

## 3. Wireframe: Formatübersicht

```text
┌ Exporte ────────────────────────────────────────────────────────────────────┐
│ [Datenexport] [Mappings]                         Datensatztyp [Objekte ▾]   │
│                                                                            │
│ Export-Mappings                                           [Neuer Entwurf]  │
│                                                                            │
│ LIDO  · BPK/DDB-Profil 1.0                                                   │
│ Veröffentlicht: Revision 3 · 05.09.2026                                    │
│ Entwurf: Revision 4 · 7 Änderungen                                         │
│ Prüfung: 2 Fehler · 3 Warnungen                       [Mapping bearbeiten]  │
│ ────────────────────────────────────────────────────────────────────────── │
│ Dublin Core · Standard                                                      │
│ Veröffentlicht: Revision 2 · kein Entwurf             [Kompakt bearbeiten] │
│ ────────────────────────────────────────────────────────────────────────── │
│ METS/MODS · Standard                                                        │
│ Noch nicht eingerichtet                                  [Entwurf anlegen] │
└────────────────────────────────────────────────────────────────────────────┘
```

Keine Kartenmatrix. Formate stehen als scanbare Zeilen auf einer gemeinsamen Fläche. Der primäre Zustand steht vor Kennzahlen. `Mapping bearbeiten` öffnet vorhandenen Entwurf oder den veröffentlichten Stand schreibgeschützt. `Entwurf anlegen` klont die veröffentlichte Revision erst nach expliziter Aktion.

Zustände:

- Noch nicht eingerichtet: erklärt, welche lokale Datenart benötigt wird.
- Nur veröffentlicht: bietet Lesen und Entwurf anlegen.
- Entwurf vorhanden: zeigt Änderungszahl und letzten Prüfstand.
- Prüfung läuft: zeigt Fortschritt, verhindert aber keine weitere Navigation.
- Blockiert: nennt die Zahl blockierender Diagnosen und öffnet direkt den ersten Fehler.
- Veraltet: Profil- oder Schemaänderung ist sichtbar; Veröffentlichung bleibt gesperrt.
- Ladefehler: bestehende Stände bleiben unberührt, erneuter Abruf ist möglich.

## 4. Wireframe: Mapping-Arbeitsbereich

```text
┌ BPK/DDB-LIDO 1.0 · Objekte · Entwurf R4 ───────────────────────────────────┐
│ ← Formate     7 Änderungen     Letzte Prüfung: 2 Fehler       [Prüfen]     │
├──────────────────────┬────────────────────────────────┬────────────────────┤
│ Ziele                │ Regel bearbeiten               │ Referenz & Ausgabe │
│                      │                                │                    │
│ Suche [             ]│ Geistige Schöpfung / Akteur   │ os_ub_0029908 [▾] │
│                      │ Empfohlen · mehrfach           │ [Struktur] [XML]   │
│ Identifikation  3/4  │                                │                    │
│ Klassifikation  2/3  │ Quelle                         │ Paul Barbier       │
│ Ereignisse      8/11 │ [Relation ▾]                   │ ← Relation fotograf│
│  Herstellung      ✓  │ Relationsart [fotograf ▾]     │                    │
│  Geistige Schöpfung  │ Zielwert     [Name bevorzugt]  │ <eventActor>…      │
│   Akteur          ●  │ LIDO-Rolle   [Fotograf ▾]      │                    │
│  Gebrauch        !2  │ Sprache      [wie Quelle ▾]    │ ✓ Profilregel      │
│ Rechte            !1 │                                │ ✓ LIDO 1.0 XSD     │
│ Medien            2/2│ [Experteninformationen ▸]      │                    │
│                      │                                │ [Wert hervorheben] │
│ + Nur ungemappte     │ [Regel entfernen]   [Speichern]│                    │
└──────────────────────┴────────────────────────────────┴────────────────────┘
```

Links navigiert die Person nach fachlichen LIDO-Bereichen. Zähler bedeuten `belegte Ziele / relevante Ziele`, nicht `lokale Felder / alle XML-Pfade`. Ein Ziel kann mehrere Regeln besitzen. Die Liste zeigt getrennte Regelzeilen darunter, statt die letzte Regel zu überschreiben.

Die Mitte bearbeitet genau eine Regel. Die Quellenauswahl beginnt mit einer Quellart und filtert danach vorhandene Felder, Relationen, Datensatzattribute, Medienwerte oder Institutionskonstanten. Unpassende Quellen bleiben auffindbar, nennen aber den konkreten Grund der Ablehnung.

Rechts bleibt der ausgewählte Referenzdatensatz sichtbar. Strukturansicht ist Standard. XML ist eine gleichrangige Prüfoption, aber nicht der Einstieg. Ein Klick auf einen ausgegebenen Wert markiert Quelle, Regel und XML-Fragment. Vorschau wird über `Prüfen` oder eine eigene Aktualisieren-Aktion erzeugt, nicht pro Tastendruck.

Schmale Viewports verwenden drei beschriftete Ansichten `Ziele`, `Regel`, `Vorschau`. Der aktuelle Zielname und der Entwurfsstatus bleiben im Kopf sichtbar. Vor und zurück wechseln in logischer Reihenfolge; keine Funktion fällt weg.

## 5. Wireframe: Validieren und veröffentlichen

```text
┌ Entwurf R4 prüfen ──────────────────────────────────────────────────────────┐
│ BPK/DDB-LIDO 1.0 · Objekte                                                  │
│                                                                            │
│ Referenzfälle  1/3 geprüft      XSD gültig      Profil: 2 Fehler, 3 Warn. │
│                                                                            │
│ Fehler                                                                     │
│  1  Gebrauch / Datum         Enddatum hat kein gültiges ISO-Datum [Öffnen] │
│  2  Medien / Rechte          Unbekannter Rechtewert             [Öffnen] │
│                                                                            │
│ Warnungen                                                                  │
│  3  Geistige Schöpfung       Rolle bei 1 Beziehung fehlt        [Öffnen] │
│                                                                            │
│ Änderung gegenüber Revision 3                                              │
│  + Fotografenrelation ergänzt                                              │
│  ~ Medienrechte geändert                                                   │
│  - Veraltete Regel für Verlag entfernt                                     │
│                                                                            │
│ Veröffentlichung gesperrt, solange Fehler bestehen.                        │
│                                               [Zurück] [Erneut prüfen]      │
└────────────────────────────────────────────────────────────────────────────┘
```

Wenn keine Fehler mehr bestehen, ersetzt der Abschlussbereich den Sperrhinweis:

```text
Bereit zur Veröffentlichung
OAI und Admin-XML verwenden bis zum abgeschlossenen Reindex weiter Revision 3.
[Abbrechen] [Revision 4 veröffentlichen]
```

Die Bestätigung ist eine eigene Seite oder ein Inline-Schritt, kein erster Reflex als Modal. Nach Veröffentlichung zeigt die Oberfläche aktive Revision, Zeitpunkt und Reindexzustand. Rücknahme bedeutet: aus einer früheren veröffentlichten Revision einen neuen Entwurf erzeugen, prüfen und wieder veröffentlichen. Ein Archivstand wird nicht direkt aktiv geschaltet.

## 6. Einsteiger- und Expertenebene

Standardmäßig sichtbar:

- fachlicher Zielname, Gruppe, Pflichtstatus und Kardinalität;
- lokale Quellart, Feldlabel oder Relationsart und ein Beispielwert;
- verständliche Zielparameter wie Ereignis, Rolle, Sprache oder Rechtewert;
- Referenzvorschau, Herkunft und lokalisierte Diagnosen;
- Entwurfs-, Prüf- und Veröffentlichungsstatus.

Eingeklappt unter `Experteninformationen`:

- `target_key`, XML-Pfad und Namespace;
- `rule_key`, Mapping-Set-ID, Profil-ID und Profilversion;
- technischer Feldname und Felddefinitions-ID;
- normalisierte `source_config`- und `settings`-Werte;
- Validatorname, Validatorversion und Diagnosecode.

Nie direkt editierbar sind freie XPath-, XSLT-, Jinja-, XML- oder Regex-Ausdrücke. Technische Informationen erklären den deterministischen Vertrag, umgehen ihn aber nicht.

## 7. Fünf durchgängige BPK-Beispiele

### Fotograf

Quelle: ausgehende Relation `fotograf` zu `entity`; Wert ist der bevorzugte öffentliche Name. Ziel: `Geistige Schöpfung / Akteur`. Parameter: Rolle `Fotograf`, Kardinalität `many`. Vorschau gruppiert jeden Akteur getrennt im Ereignis `Geistige Schöpfung`. Fehlt der Name oder ist das Ziel nicht öffentlich, zeigt die Regel eine Diagnose und erzeugt keinen leeren Akteursblock.

### Verlagsort

Quelle: Verlag über Relation `creator`, danach dessen Ortsrelation `ansaessig`; Wert sind bevorzugter Ortsname und vorhandener GeoNames-Identifier. Ziel: `Herstellung / Ort`. Die zweistufige Relationskette ist nur zulässig, wenn das LIDO-Profil sie ausdrücklich als Quellenform unterstützt. Sonst muss der Import den Verlagsort als direkte, fachlich benannte Relation anlegen. Die UI darf keine beliebigen Relationsketten zusammenklicken lassen.

### Gebrauchsdaten

Quelle: typisiertes Datumsfeld mit Anzeigeform, frühestem und spätestem Datum sowie Datierungsgrund; ergänzend Relationsquellen `wurde_abgesendet` und `wurde_empfangen` sowie kontrollierte Werte für Frankierung, Stempel, Beschriftung und Laufstatus. Ziel: Ereignis `Gebrauch`. Mehrere Werte bleiben als fachlich zusammengehörige Datumsintervalle erhalten. Die alten Regex-Regeln werden nicht übernommen; Datumsprojektion und Labelzuordnung sind Adapterlogik über typisierte Werte.

### Rechte

Quelle: kontrollierter Rechtewert für Datensatz und Medium, plus Institutionskonstante für Rechteinhaber. Ziele: `Datensatz / Rechte` und `Medien / Rechte`. Gespeichert und ausgegeben werden kanonische URIs wie CC0, CC BY-NC oder RightsStatements. Unbekannte Altwerte wie `;CC0 1.0;9494` blockieren die Veröffentlichung oder werden vorab in der Migration normalisiert. Keine freie Regex-Tabelle im Exportmapper.

### Medien

Quelle: alle öffentlichen Medien, geordnet nach Rollen- und Medienreihenfolge. Werte: öffentliche Original- oder IIIF-URL, MIME-Type, Identifier und Rechte. Ziel: `Medien / Ressource`. Jedes Medium erzeugt ein eigenes `resourceSet`. Nicht öffentliche Medien erscheinen weder im Picker noch in Vorschau oder XML. Ein fehlender Rechtewert erzeugt die im Profil festgelegte Warnung oder Sperre.

## 8. Fachliche Referenz aus allen 306 Mappingzeilen

Die Arbeitsmappe enthält 201 Struktur-/Mappingzeilen und 105 Konstanten. Die folgende Checkliste fasst die vollständige Baumdefinition fachlich zusammen. Die 63 dynamischen Quellen landen in 28 fachlichen Blattzielen; wiederholte XML-Hüllen sind keine eigenen Anforderungen.

### Dokument und Identifikation

- [ ] `lidoWrap` und genau ein `lido` mit LIDO-, XML-, XSI- und GML-Namespace erzeugen.
- [ ] SchemaLocation auf das aktive Profil setzen; `xalan` ist nicht fachlich nötig.
- [ ] `lidoRecID` aus ISIL plus lokaler `idno` erzeugen und als lokalen Identifier typisieren.
- [ ] Beschreibende und administrative Metadaten mit Sprache `de` ausgeben.
- [ ] `recordID` aus `idno`, `recordType` als Einzelobjekt und kanonischen Portal-Link ausgeben.

### Klassifikation

- [ ] Objektart mit AAT- und GND-URI sowie deutschem und englischem Begriff ausgeben.
- [ ] Kartentypus aus kontrolliertem Vokabular abbilden.
- [ ] Kategorie aus kontrolliertem Vokabular abbilden.
- [ ] Sammlungszugehörigkeit als wiederholbare Klassifikation abbilden.

### Benennung, Beschreibung und Maße

- [ ] Bevorzugten Objekttitel mit Präferenzkennzeichnung ausgeben.
- [ ] Gedruckte Beschriftung auf Vorder- und Rückseite als getrennte Inschriften ausgeben.
- [ ] `idno` und optionale alte Signatur als unterschiedlich typisierte Werk-IDs ausgeben.
- [ ] Bildbeschreibung als Richtext sicher in `descriptiveNoteValue` übertragen.
- [ ] Kurze und lange Seite mit Wert, Einheit `cm` und verständlichem Maßtyp ausgeben.

### Repository und Institution

- [ ] Repositorytyp `current`, ISIL-URI, Institutionsname und Website aus Institutionskonfiguration ausgeben.
- [ ] Repositoryort Osnabrück mit GeoNames- und TGN-Identifier aus Institutionskonfiguration ausgeben.
- [ ] Datensatzquelle und Rechteinhaber aus derselben versionierten Institutionskonfiguration ableiten.
- [ ] Schenker als optionale Würdigung und Förderer als optionale Creditline aus Relationen ausgeben.

### Herstellung

- [ ] Ereignis `Herstellung` mit kanonischer LIDO-Terminologie erzeugen.
- [ ] Verlag/Herausgeber aus Relation `creator` mit bevorzugtem Namen ausgeben.
- [ ] Verlagsort über die festgelegte Ortsquelle mit Name und GeoNames-URI ausgeben.
- [ ] Material und Drucktechnik als getrennte kontrollierte Angaben ausgeben.
- [ ] Leere Technikangabe unterdrücken; das Live-Beispiel enthält derzeit eine leere Hülle.

### Geistige Schöpfung

- [ ] Ereignis `Geistige Schöpfung` mit kanonischer LIDO-Terminologie erzeugen.
- [ ] Rollen getrennt abbilden: Hersteller Vorlage, Textautor, Maler/Zeichner/Illustrator, Komponist, Bühnenbildner, Stecher, Fotograf, Bildhauer, Lithograph und Scherenschneider.
- [ ] Mehrere Akteure derselben Rolle als getrennte Akteure im selben fachlichen Ereignis erhalten.
- [ ] Rollenbezeichnung explizit ausgeben; das Live-Beispiel `Paul Barbier` enthält derzeit keine Rolle.
- [ ] `Schöpfung der Expression` nur erzeugen, wenn eine konkrete fachliche Quelle belegt ist; die Arbeitsmappe enthält hierfür unvollständige Quellangaben.

### Gebrauch

- [ ] Ereignis `Gebrauch` mit kanonischer LIDO-Terminologie erzeugen.
- [ ] Anzeige-, Frühest- und Spätestdatum aus einem typisierten Datumswert projizieren.
- [ ] Datierungsgrund aus kontrolliertem Schlüssel in verständliches Label überführen.
- [ ] Absende- und Empfangsort mit Name und GeoNames-URI getrennt ausgeben.
- [ ] Frankierung, Stempel, Beschriftungsstatus und gelaufen/ungelaufen als wiederholbare Ereignisbeschreibungen ausgeben.
- [ ] Mehrere Datumswerte nicht durch parallele, unverbundene Stringlisten falsch kombinieren.

### Themen

- [ ] Jedes Schlagwort als eigenes `subjectSet` ausgeben.
- [ ] Optionale LCSH-Terme getrennt ausgeben und Altformat-Klammern beim Import normalisieren.
- [ ] Bildbeschreibung nur dann als `displaySubject` verwenden, wenn das Profil diese Doppelung verlangt.

### Rechte und Datensatzinformation

- [ ] Werk-, Datensatz- und Medienrechte als getrennte fachliche Ziele behandeln.
- [ ] Rechteinhaber mit ISIL, Name und Website aus Institutionskonfiguration ausgeben.
- [ ] Altwerte auf kanonische CC-, DDB- oder RightsStatements-URIs normalisieren.
- [ ] Erstellungs- oder Änderungsdatum nur mit vorhandenem typisiertem Zeitstempel ausgeben.
- [ ] Keine leeren Datums- oder Rechtehüllen erzeugen.

### Medien

- [ ] Lokalen Ressourcen-Identifier ausgeben.
- [ ] Jedes öffentliche Medium als eigenes geordnetes `resourceSet` ausgeben.
- [ ] URL und MIME-Type aus dem Medium beziehen; `image/jpg` nicht als globale Konstante fest codieren.
- [ ] Ressourcentyp kontrolliert ausgeben.
- [ ] Medienrechte und Rechteinhaber pro Ressource ausgeben.
- [ ] Backend-zu-Frontend-URL-Umschreibung durch kanonische öffentliche URLs ersetzen.

### Ersetzungsregeln

Alle 52 Zeilen der Tabelle `Replacements` fallen in fünf kontrollierte Kategorien:

- GeoNames-ID aus Altserialisierung extrahieren: Importnormalisierung, danach kanonischer URL-Builder.
- Datierungsgründe übersetzen und Datumsintervalle formatieren: kontrollierte Schlüssel plus typisierte Datumsprojektion.
- HTML-Entities und `<br>` behandeln: sichere XML-Serialisierung und bewusste Richtextprojektion.
- Rechtecodes auf URIs abbilden: kontrollierte Vokabularwerte; unbekannte Werte diagnostizieren.
- Maße, Portal- und Medien-URLs sowie Creditline normalisieren: Importnormalisierung oder explizite Adapteroperation, keine freie Regex.

Damit sind alle 201 Mappingknoten, 105 Konstanten und 52 Ersetzungszeilen einem fachlichen Ziel, einer strukturellen Adapteraufgabe oder einer Importnormalisierung zugeordnet.

## 9. LIDO-Version und Validator

Entscheidung für den ersten BPK-Schnitt: Profil `BPK/DDB-LIDO 1.0`. Das bestehende BPK-Dokument deklariert `http://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd`, und DDBpro verlinkt weiterhin ausdrücklich auf LIDO 1.0. Katalons aktueller Adapter nennt dagegen LIDO 1.1. Ein stiller Wechsel würde die Anschlusskompatibilität ungeprüft verändern.

LIDO 1.1 wird später als getrennte Profilversion angeboten. Das offizielle 1.1-Schema bezeichnet sich als rückwärtskompatibel, enthält aber zusätzliche Schematron-Regeln. Diese Behauptung ersetzt keinen Partner- und Referenztest für den BPK-Feed.

Validator für BPK 1.0:

1. lokal gebündeltes offizielles LIDO-1.0-XSD einschließlich lokal aufgelöster XML-/GML-Abhängigkeiten;
2. `lxml.etree.XMLSchema`, bereits als Backend-Abhängigkeit vorhanden;
3. zusätzliche stabile Katalon-Diagnosen für BPK/DDB-Regeln, die das XSD nicht ausdrückt;
4. keine Schema- oder Importabfrage im Requestpfad.

Das offizielle LIDO-1.0-XSD erlaubt Weitergabe unter CC BY-SA 3.0 und verlangt einen konkreten Copyright- und Lizenzhinweis in Software und Dokumentation. Lokales Bündeln ist damit zulässig, wenn dieser Hinweis aufgenommen wird und die Lizenzbedingungen auch für mitgelieferte XML-/GML-Abhängigkeiten separat geprüft werden. LIDO 1.1 steht laut Schemaheader unter CC BY 4.0.

Quellen:

- BPK-OAI-Beispiel: https://bildpostkarten.uni-osnabrueck.de/backend/service.php/OAI/bpk?verb=GetRecord&identifier=oai%3Abildpostkarten.uni-osnabrueck.de%3A32644&metadataPrefix=lido
- DDBpro, LIDO v1.0: https://pro.deutsche-digitale-bibliothek.de/downloads-links/lido-v10
- LIDO 1.0 XSD und Lizenzhinweis: https://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd
- LIDO 1.1 XSD, Rückwärtskompatibilität und Lizenz: https://www.lido-schema.org/schema/v1.1/lido-v1.1.xsd

## 10. Interaktions- und Inhaltsdetails

Hilfe erklärt je Ziel Bedeutung, Pflichtstatus, erwartete Quelle, Kardinalität und Auswirkung auf DDB/Europeana, sofern belegt. Beispielwerte stammen nur aus ausgewählten Referenzfällen. Lange Labels und deutsche wie englische Texte dürfen die Bedienung nicht abschneiden.

Diagnosen haben stabilen Code, lokalisierte Meldung, Schweregrad, betroffene Regel und Sprungziel. Ein Fehler sagt, welche Eingabe nicht akzeptiert wird und wie die Person ihn behebt. Warnungen dürfen veröffentlicht werden, sofern das Profil sie nicht ausdrücklich hochstuft.

Speichern und Prüfen sind getrennt. Regeländerungen speichern den Entwurf mit Versionsschutz. `Prüfen` erzeugt eine neue Vorschau für ausgewählte Referenzfälle. `Veröffentlichen` ist erst nach erfolgreicher, nicht veralteter Prüfung derselben Entwurfsversion möglich.

## 11. Abnahmepfad für den Shape

Eine Fachadministratorin kann ohne XML-Kenntnisse:

1. in der Formatübersicht einen BPK/DDB-LIDO-Entwurf öffnen;
2. unter `Ereignisse / Geistige Schöpfung / Akteur` die Relation `fotograf` wählen;
3. die Rolle `Fotograf` setzen und am Referenzdatensatz `os_ub_0029908` prüfen;
4. Institutionswerte für Repository und Rechteinhaber bearbeiten;
5. Gebrauchsdaten, Rechte und alle öffentlichen Medien in der Strukturvorschau nachvollziehen;
6. von einer Diagnose zur verursachenden Regel springen;
7. nach erfolgreicher Prüfung Revision 4 veröffentlichen;
8. eine frühere Revision als neuen Entwurf wiederherstellen, statt den produktiven Stand direkt umzuschalten.

## 12. Offene Punkte für spätere Phasen

- Das BPK-Beispiel enthält nur ein Medium, der lokale Referenzfall der Rendererphase soll laut Plan zwei Medien enthalten.
- Der konkrete DDB-LIDO-Regelsatz über das offizielle XSD hinaus braucht vor Phase 5 eine versionierte, zitierbare Quelle.
- Die BPK-Felder müssen bei der Datenmigration auf konkrete Katalon-Felddefinitionen und Relationsarten abgebildet werden; der Shape-Brief legt nur die fachlichen Quellen fest.
- Verlagsort über eine zweistufige Relationskette bleibt eine bewusste Profilentscheidung. Der gemeinsame Kern erhält keinen allgemeinen Graph-Abfrageeditor.
- LIDO 1.0 importiert GML 3.1.1 und `xml.xsd`. Deren lokale Dateien und Lizenzhinweise werden vor dem Bündeln einzeln geprüft.
