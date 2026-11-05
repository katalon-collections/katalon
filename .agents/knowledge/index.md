---
okf_version: "0.1"
---

# Katalon Knowledge Bundle

Internal, dev-only knowledge base in [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) format. Not published, not deployed — browse locally via `make knowledge-site`.

This is separate from `.agents/DEV.md` and `.agents/PLAN*.md`, which stay where they are as living process docs; roadmap and phase status now live in GitHub Issues (#260–#267). This bundle owns the authoritative architecture decision records. Almanac owns current system behavior and implementation evidence; playbook, architecture and gotcha pages here are entry points or historical notes. See [documentation ownership](decisions/knowledge-vs-prozessdokumente.md) and the developer entry point in `.agents/DEV.md`. Do not maintain independent versions of the same rationale in both systems.

# Sections

* [Decisions](decisions/) - architecture and design decisions with their rationale
* [Playbooks](playbooks/) - runbooks for recurring situations
* [Gotchas](gotchas/) - documented pitfalls, so agents don't rediscover them the hard way
* [Architecture](architecture/) - how things work, short overviews linking to docs/
* [Glossary](glossary/) - CollectiveAccess ↔ Katalon terminology mapping
