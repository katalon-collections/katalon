# Decisions

* [Tech-Stack](tech-stack.md) - Backend/DB/Suche/Bildserver/Queue/Frontend/Deployment als Paket festgelegt
* [Sieben Kerntypen](vier-bestandstypen.md) - getrennte fachliche Tabellen statt generischer Intrinsic-Tabelle
* [Relationen — strukturierte Felder und freie Zusatzbeziehungen](relationen-strukturierte-und-freie-beziehungen.md) - kanonische Aufgabenverteilung zwischen Relationsfeldern und Beziehungen-Karte
* [Vokabular-Custom-Fields](vocabulary-custom-fields.md) - JSONB-Metadaten für VocabularyTerm über die gemeinsame Schema-Engine
* [Vokabular-Hierarchie-Browser](vocab-hierarchy-browser.md) - Tree-Ansicht im Feld-Dropdown (#342), fertiger /tree-Endpoint, kein Lazy-Loading, nur interne Vokabulare
* [Inherited Fields (ES)](inherited-fields-es.md) - Denormalisierung nur im Suchindex, Reindex-Kaskade auf 1 Ebene begrenzt
* [Erweiterte Relationssuche](advanced-relational-search.md) - typisierte Eigenfelder und begrenzte Inside-out-Auflösung über maximal zwei Relationsschritte
* [XML-Importer-Scope](xml-importer-scope.md) - generisches Parsing, nutzer-wählbare Record-Granularität, 100 MB Limit
* [Importer-Plugin-Architektur](importer-multi-format-architektur.md) - SourceFormat-ABC + Registry statt formatspezifischer Funktionen
* [Docker-Customization-Strategie](docker-customization-strategy.md) - Volume Mounts + Override-Datei statt Image-Rebuilds
* [Knowledge vs. Prozessdokumente](knowledge-vs-prozessdokumente.md) - OKF-Bundle bleibt getrennt von DEV.md/KONZEPT.md/PRODUCT.md/DESIGN.md (Roadmap jetzt in GitHub-Issues #260–#267), beide lazy-geladen
* [Importer Fuzzy-Vokabular-Clustering](importer-fuzzy-vocab-clustering.md) - rapidfuzz + Greedy-Clustering statt k-means, User bestätigt vor Merge (#269)
* [Production-Readiness-Posture](production-readiness-posture.md) - gemeinsamer Readiness-Check inkl. Redis/Worker/Cantaloupe und optional Oxigraph
* [Optimistic Locking](optimistic-locking.md) - version-Spalte + If-Match + 409, feldweiser 3-Wege-Merge in der Admin-UI, nur Metadaten (#272)
* [Presence Lock](presence-lock.md) - generische edit_presence-Tabelle, Heartbeat/TTL statt Cleanup-Worker, admin-konfigurierbarer warning/blocking-Modus serverseitig erzwungen (#371)
* [Broker-toleranter Enqueue](broker-tolerant-enqueue.md) - fire-and-forget schluckt+loggt Broker-Ausfall, Job-ID-Pfade liefern 503 statt 500 (#274)
* [LIDO-DDB-Export](lido-ddb-export-konfiguration.md) - DDB-Anforderungen über Mapping-Settings/institution_config, Normalisierung zur Renderzeit, via-Relationen nur auf Anforderung
* [OAI-Löschmeldungen](oai-deleted-records.md) - oai_record_states im Indexpfad, deletedRecord transient, keine IDs nie öffentlicher Datensätze
* [Reindex-Koordination und Streaming](reindex-koordination-und-streaming.md) - queued/dirty-Marker pro Typ, nicht-blockierende Lease mit Watchdog, batchweises Überschreiben statt Vorab-Löschen
* [Mehrsprachigkeit](mehrsprachigkeit.md) - konfigurierbare Sprachliste, is_translatable + {lang: text}-Dict, dependency-freies Portal-i18n
* [Medien-Multiformat](medien-multiformat.md) - MIME-Kategorie-Dispatch, Nicht-Bild überspringt Cantaloupe, Viewer-Dispatch im Portal
* [Medienzuordnung aus dem Metadatenimport](medienzuordnung-aus-metadatenimport.md) - nutzergewählter Datei-Selector, offene Referenzen je Objekt und automatische Auflösung im Batch-Import
* [Management-CLI-Ergonomie](management-cli-ergonomics.md) - Repo-Root als uv-Workspace, source-relative `.env`, lesbarer Secrets-Fehler ohne Stacktrace
* [Massenbearbeitung](batch-editing.md) - Batch-Operationen auf Record-Listen mit seitenübergreifender Auswahl, Audit-Log-Transparenz, ohne Rollback/Snapshots
* [Export-Format-Plugin-Registry](metadata-format-plugin-registry.md) - metadata_formats-Tabelle analog authority_sources, OAI/Export liefern Format nur bei tatsächlichem Mapping, Heuristik-Fallback entfernt
* [IIIF-Pyramid-TIFF](iiif-pyramid-tiff.md) - immer konvertieren (kein Threshold), Original bleibt + iiif_storage_key zusätzlich, kein Backfill, Fehler fällt auf Original zurück (#333)
* [Medien-Sichtbarkeit und Cantaloupe-Gate](media-visibility-und-cantaloupe-gate.md) - MediaFile.is_public + nginx auth_request vor Cantaloupe statt signierter URLs, host-relativer Thumbnail-Redirect gegen Cross-Origin-Header-Verlust
* [Staff-Login im Portal](staff-portal-login.md) - bestehende Katalon-Konten für interne Portalsicht, öffentliche Accounts bleiben anonym
* [Lizenz + Branding](license-and-branding.md) - AGPL-3.0-or-later statt BSL/MIT, extern "Katalon Collections" statt "Katalon", keine Code-Umbenennung
* [Standortverwaltung](standortverwaltung.md) - StorageLocation als sechster Primärtyp mit Hierarchie, Zuweisung über generische Relation (normal_location/current_location) statt direkter FK, SPECTRUM-Bewegungshistorie ohne Zusatztabelle
* [Dev-HTTPS mit Custom Hostname](dev-https-custom-hostname.md) - mkcert/Caddy als opt-in Host-Prozess vor Dev-Compose-Ports, Vite `server.allowedHosts` als notwendige Ergänzung (#168)
* [Hierarchische Suche und Filterung](hierarchische-suche-und-filterung.md) - Transitive Unterbaumauflösung für Sammlungen und Standorte via CTE-Query-Expansion statt ES-Denormalisierung; Vokabulare zurückgestellt (#362, #366, #367)
* [Orts-Hierarchie](orts-hierarchie.md) - places.parent_id, Unterbaumabfrage per CTE, Pfad-Import mit explizitem Trenner legt Zwischenebenen an
* [Facetten-Materialisierung als facet_all_*](facet-all-materialisierung.md) - alle Public-Felder als facet_all_* im Index, is_facet steuert nur noch Queryzeit-Whitelist im Portal-Search; Facetten-Toggles ohne Reindex, Sicherheitsmodell "Non-Public nie im Index" bleibt
* [SPARQL Query Builder](sparql-query-builder.md) - Integrierter SPARQL Query Builder in der Admin-UI mit direkter SPARQL-Ausführung gegen Oxigraph, NL2SPARQL via LLM und persistierten gespeicherten Abfragen
* [S3-Speicherbackend](s3-storage-backend.md) - optionales S3-Backend hinter StorageBackend-Protokoll (Default local unverändert), Cantaloupe S3Source, RADOSGW-Portabilität via boto3-Overrides, kein Migrationsskript, MinIO nur Dev (#121)
* [LOD-Content-Negotiation auf kanonischen URIs](lod-content-negotiation-canonical-uris.md) - Reverse-Proxy-Nachzug zu #363: `@id` zeigt seit der Portal-URL-Umstellung ins Leere ohne nginx/Caddy-seitige Accept-Header-Weiche, Tests deckten nur die Identifier-Zeichenkette ab, nicht Dereferenzierbarkeit
* [Portal-loser Custom-Betrieb](portal-loser-custom-betrieb.md) - kein Preset-Matrix, nur `VITE_PORTAL_ENABLED`-Flag + dokumentiertes manuelles nginx-Rezept statt gepflegter Zweit-Topologie (#305)
* [Schema- und Vokabularintegrität](schema-vokabular-integritaet.md) - unbekannte historische Felder bleiben unvalidiertes Legacy im Record, Vokabularlöschung nur mit Nutzungswarnung + Remapping-Angebot, kein Zwang zum Remapping (#394)
* [Soft-Delete-Relationsvertrag](soft-delete-relationsvertrag.md) - eingehende Relationen bleiben bis zum Purge unangetastet, Restore dadurch strukturell verlustfrei, "Gelöscht"-Badge statt Link in der UI (#398)
* [Manueller Purge und Auto-Purge-Config](manual-purge-und-auto-purge-config.md) - POST /{id}/purge teilt Kernlogik mit Nightly-Sweep statt Duplikat; Retention/Enable-Flag von env-var nach AdminConfig verschoben, admin-UI-konfigurierbar ohne Neustart (#414-Folgearbeit)
* [Backup-Restore-Vertrag](backup-restore-vertrag.md) - 24h RPO, 30 Tage täglich + 12 Monate monatlich, Offsite-Kopie bleibt Betreiberaufgabe (Doku, kein automatischer S3-Upload) — Katalon betreibt keine SaaS-Instanzen (#391)
* [Knowledge-Graph/RDF/SPARQL-Erweiterung](knowledge-graph-rdf-sparql.md) - optionale materialisierte Oxigraph-Projektion; Abgrenzung zu Core und Query Builder
* [Digitale Ausstellungen](digitale-ausstellungen.md) - eigene kuratierte Portal-Ressource mit strukturellen Bereichen, kontextbezogenen Record-Präsentationen und kontrollierten Theme-Tokens (#341)
* [Ausstellungsseiten mit geordneten Inhaltsblöcken](ausstellungsseiten-und-inhaltsbloecke.md) - feste Hierarchie Exhibition → Section → Page → Block, kein freier Image-Block, optionale Record-Vorschaumedien
* [DatabaseCommitMiddleware — Read-after-Write-Konsistenz](database-commit-middleware-read-after-write.md) - Transaktions-Commit vor HTTP-Response-Übertragung verhindert Race Conditions bei sofortigen Listen-Refetches
* [Kein Theme-Umschalter im Admin-UI](theme-umschalter-im-admin-verworfen.md) - Portal-Theme bleibt Datei-/Env-Var-Konfiguration; Umschalter und Theme-Store liegen außerhalb des aktuellen Umfangs

* [API-Worker mit Vorinitialisierung](api-multiple-workers.md) - einmaliger Container-Bootstrap, zwei API-Prozesse und begrenzte Verbindungspools
* [Release bestimmt Fremdservice-Images](release-bestimmt-fremdservice-images.md) - `[images]` in release-meta.toml statt CLI-Template, CLI prüft Major-Wechsel und `requires` vor dem Update
* [Facetten-Katalog](facetten-katalog.md) - Relations-, Datums- und Baumfacetten über `facet_service`, `is_facet` getrennt von `show_in_detail`, Sortierung pro Facette, `selected`-Buckets
* [Öffentliche Projektion von Relationsfeldern](oeffentliche-projektion-relationsfelder.md) - Ziel-Labels erben Sichtbarkeit, fail closed ohne `hidden_targets`, RDF mit öffentlicher Sicht, `source_field` gegen Doppelanzeige
* [Portal-HTTP-Caching und Sammel-Requests](portal-http-caching-und-sammel-requests.md) - `public, max-age=60` + `Vary: Authorization` für anonyme Reads, `objects/summaries` statt zwei Requests je Teaser
* [Nutzungsstatistik als Tageszähler und Beacon](nutzungsstatistik-tageszaehler-und-beacon.md) - anonyme Tageszähler ohne Personenbezug; Aufrufe per Portal-Beacon statt Detail-GET, Downloads nur am schaltbaren Attachment-Endpoint.
* [Cantaloupe-Derivat-Cache und Vorschaubilder](cantaloupe-derivat-cache-und-vorschaubilder.md) - Cache auf Platte, Vorschaubilder vorab rendern, direkte IIIF-URLs
* [Portal-Gestaltung als Kernkonfiguration](portal-gestaltung-als-kernkonfiguration.md) - Footer, Nutzungshinweis, Logo, Theme-Skript in PortalConfig statt Theme-Workarounds
* [SEO-Meta-Tags per Bot-Weiche statt SSR](seo-bot-weiche-statt-ssr.md) - nginx leitet Crawler per User-Agent auf einen Backend-Renderer (Meta-Tags, schema.org, Sitemap) statt SSR/Prerender (#440)
* [Admin Hash Routing](admin-hash-routing.md)
* [Auth Token Architecture](auth-token-architecture.md)
* [BagIt Preservation Export](bagit-preservation-export.md)
* [Configurable Portal Homepage Blocks](configurable-portal-homepage.md)
* [Configurable Portal Terminology](configurable-portal-terminology.md)
* [idno und label bleiben Pflicht-Systemfelder statt schemaabhängig konfigurierbar](idno-und-label-pflicht.md)
* [JSON Import ist YAGNI](json-import-yagni.md)
* [katalon-cli Distribution](katalon-cli-distribution.md)
* [LRMoo / FRBR Mapping Onto Occurrence](lrmoo-frbr-occurrence-mapping.md)
* [Subsystem-Erweiterungen (RDF/Oxigraph/SPARQL) — First-Party-Modul statt generischer Plugin-Architektur](subsystem-extensions-vs-plugin-architecture.md)

* [Manuelle exklusive Sperre](manual-exclusive-lock.md) - persistente Reservierung, eigene Freigabe und Admin-Force-Unlock; getrennt von Presence und If-Match
* [Import-Auflösung in einem Pfad](import-aufloesung-gemeinsamer-pfad.md) - Vokabular und Relationen aus Text, Dry-run rollt per Savepoint zurück
* [Feldtyp Datei mit eigener Anhang-Tabelle](feldtyp-datei-anhaenge.md) - Anhänge als Feldtyp `file` in eigener Tabelle `attachments`, Referenzprüfung beim Speichern, Portal per öffentlicher Projektion, Sichtbarkeit pro Feld, GC-Befehl mit 7 Tagen
