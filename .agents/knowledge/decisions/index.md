# Decisions

* [Tech-Stack](tech-stack.md) - Backend/DB/Suche/Bildserver/Queue/Frontend/Deployment als Paket festgelegt
* [Vier Bestandstypen](vier-bestandstypen.md) - vier getrennte primäre Tabellen statt generischer Intrinsic-Tabelle
* [Relationen — strukturierte Felder und freie Zusatzbeziehungen](relationen-strukturierte-und-freie-beziehungen.md) - kanonische Aufgabenverteilung zwischen Relationsfeldern und Beziehungen-Karte
* [Relationen-Design](relationen-design.md) - abgelöst: flexibel statt feldgebunden, gefiltert über konfigurierbares Vokabular
* [Vokabular-Custom-Fields](vocabulary-custom-fields.md) - JSONB-Metadaten für VocabularyTerm, später vereinheitlicht mit field_definitions
* [Inherited Fields (ES)](inherited-fields-es.md) - Denormalisierung nur im Suchindex, Reindex-Kaskade auf 1 Ebene begrenzt
* [XML-Importer-Scope](xml-importer-scope.md) - generisches Parsing, nutzer-wählbare Record-Granularität, 100 MB Limit
* [Importer-Plugin-Architektur](importer-multi-format-architektur.md) - SourceFormat-ABC + Registry statt formatspezifischer Funktionen
* [Docker-Customization-Strategie](docker-customization-strategy.md) - Volume Mounts + Override-Datei statt Image-Rebuilds
* [Beta-Release-Scope](beta-release-scope.md) - Zugänglichkeit vor Feature-Vollständigkeit
* [Knowledge vs. Prozessdokumente](knowledge-vs-prozessdokumente.md) - OKF-Bundle bleibt getrennt von DEV.md/KONZEPT.md/PRODUCT.md/DESIGN.md (Roadmap jetzt in GitHub-Issues #260–#267), beide lazy-geladen
* [Importer Fuzzy-Vokabular-Clustering](importer-fuzzy-vocab-clustering.md) - rapidfuzz + Greedy-Clustering statt k-means, User bestätigt vor Merge (#269)
* [Production-Readiness-Posture](production-readiness-posture.md) - tiefer /health (DB+ES, kein Redis, kein Liveness-Split), Optimistic Locking bewusst als Issue vertagt (#272, #273)
* [Optimistic Locking](optimistic-locking.md) - version-Spalte + If-Match + 409, feldweiser 3-Wege-Merge in der Admin-UI, nur Metadaten (#272)
* [Broker-toleranter Enqueue](broker-tolerant-enqueue.md) - fire-and-forget schluckt+loggt Broker-Ausfall, Job-ID-Pfade liefern 503 statt 500 (#274)
* [Mehrsprachigkeit](mehrsprachigkeit.md) - konfigurierbare Sprachliste, is_translatable + {lang: text}-Dict, dependency-freies Portal-i18n
* [Medien-Multiformat](medien-multiformat.md) - MIME-Kategorie-Dispatch, Nicht-Bild überspringt Cantaloupe, Viewer-Dispatch im Portal
* [Medienzuordnung aus dem Metadatenimport](medienzuordnung-aus-metadatenimport.md) - nutzergewählter Datei-Selector, offene Referenzen je Objekt und automatische Auflösung im Batch-Import
* [Management-CLI-Ergonomie](management-cli-ergonomics.md) - Repo-Root als uv-Workspace, source-relative `.env`, lesbarer Secrets-Fehler ohne Stacktrace
* [Massenbearbeitung](batch-editing.md) - Batch-Operationen auf Record-Listen mit seitenübergreifender Auswahl, Audit-Log-Transparenz, ohne Rollback/Snapshots
* [Export-Format-Plugin-Registry](metadata-format-plugin-registry.md) - metadata_formats-Tabelle analog authority_sources, OAI/Export liefern Format nur bei tatsächlichem Mapping, Heuristik-Fallback entfernt
