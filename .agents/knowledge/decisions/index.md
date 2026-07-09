# Decisions

* [Tech-Stack](tech-stack.md) - Backend/DB/Suche/Bildserver/Queue/Frontend/Deployment als Paket festgelegt
* [Vier Bestandstypen](vier-bestandstypen.md) - vier getrennte primäre Tabellen statt generischer Intrinsic-Tabelle
* [Relationen-Design](relationen-design.md) - flexibel statt feldgebunden, gefiltert über konfigurierbares Vokabular
* [Vokabular-Custom-Fields](vocabulary-custom-fields.md) - JSONB-Metadaten für VocabularyTerm, später vereinheitlicht mit field_definitions
* [Inherited Fields (ES)](inherited-fields-es.md) - Denormalisierung nur im Suchindex, Reindex-Kaskade auf 1 Ebene begrenzt
* [XML-Importer-Scope](xml-importer-scope.md) - generisches Parsing, nutzer-wählbare Record-Granularität, 500 MB Limit
* [Importer-Plugin-Architektur](importer-multi-format-architektur.md) - SourceFormat-ABC + Registry statt formatspezifischer Funktionen
* [Docker-Customization-Strategie](docker-customization-strategy.md) - Volume Mounts + Override-Datei statt Image-Rebuilds
* [Beta-Release-Scope](beta-release-scope.md) - Zugänglichkeit vor Feature-Vollständigkeit
* [Knowledge vs. Prozessdokumente](knowledge-vs-prozessdokumente.md) - OKF-Bundle bleibt getrennt von DEV.md/IMPLEMENTIERUNGSPLAN.md/KONZEPT.md/PRODUCT.md/DESIGN.md, beide lazy-geladen
