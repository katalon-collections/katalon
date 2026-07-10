# Bundle Update Log

## 2026-07-10
* **Creation**: [Testsuite braucht KATALON_SECRETS_KEY](gotchas/pytest-secrets-key.md) — wiederkehrender Collection-Abbruch bei blankem `pytest`; Env-Var-Workaround dokumentiert.

## 2026-07-09
* **Creation**: Bundle scaffolded for Issue #271, seeded with [Vier Bestandstypen](decisions/vier-bestandstypen.md).
* **Update**: Mined git history and claude-mem session memory for undocumented architectural decisions; added [Tech-Stack](decisions/tech-stack.md), [Relationen-Design](decisions/relationen-design.md), [Vokabular-Custom-Fields](decisions/vocabulary-custom-fields.md), [Inherited Fields (ES)](decisions/inherited-fields-es.md), [XML-Importer-Scope](decisions/xml-importer-scope.md), [Importer-Plugin-Architektur](decisions/importer-multi-format-architektur.md), [Docker-Customization-Strategie](decisions/docker-customization-strategy.md), [Beta-Release-Scope](decisions/beta-release-scope.md).
* **Update**: Wired lazy-loading into root `AGENTS.md` (Decisions-Nachschlagepflicht + Pflicht, neue architektonische Entscheidungen als Konzepte nachzutragen).
* **Creation**: Added four new sections — [Playbooks](playbooks/), [Gotchas](gotchas/), [Architecture](architecture/), [Glossary](glossary/) — with real seed concepts extracted from `AGENTS.md`, `docs/`, and code config, not invented.
* **Creation**: `.agents/rules/backend.md` and `.agents/rules/frontend.md` — coding rules extracted from `pyproject.toml`, `tsconfig.json`, `AGENTS.md`, and `docs/CODE_QUALITY_ASSESSMENT.md`; wired into `AGENTS.md` as conditional lazy-load (backend/frontend touched → read corresponding rules file).
* **Update**: Extended `AGENTS.md` lazy-loading to living process/product docs (`IMPLEMENTIERUNGSPLAN.md`, `DEV.md`, `KONZEPT.md`, `PRODUCT.md`, `DESIGN.md`) via new "Kontext-Dateien" section; recorded the split as [Knowledge vs. Prozessdokumente](decisions/knowledge-vs-prozessdokumente.md).
