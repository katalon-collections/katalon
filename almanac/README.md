---
title: CodeAlmanac Wiki
topics: [wiki, orientation]
sources:
  - id: ingest-manual
    type: file
    path: almanac/manual/ingest.md
  - id: garden-manual
    type: file
    path: almanac/manual/garden.md
  - id: claude
    type: file
    path: CLAUDE.md
---

# CodeAlmanac Wiki

This is the living wiki for this repository. It records the durable knowledge
the code cannot say: decisions, flows, invariants, incidents, gotchas, and
project context that future agents should not rediscover from scratch.

Start with [Getting Started](getting-started) for task-oriented reading paths
through the Katalon domain, runtime, development, and operations pages.
Use `almanac/manual/` only when maintaining wiki source.

## Notability Bar

Write a page when it preserves non-obvious knowledge that will help a future
agent work safely in this codebase.

Good pages explain:

- a decision that took research or trial-and-error
- a cross-file flow
- an invariant or gotcha not visible from one file
- an external dependency as this repo uses it
- a product or operational constraint that shapes future work

Do not write pages that restate nearby code.

## Maintenance Boundary

Before implementation work, agents use this wiki as a context source and check
planned changes against the relevant pages [@claude]. After implementation work
changes documented behavior, workflows, or architecture, agents update the
affected `almanac/` pages and verify them against the actual code [@claude].
Explicit CodeAlmanac maintenance workflows such as Ingest and Garden can also
edit wiki source as their main task [@ingest-manual] [@garden-manual].

Architecture decisions made during normal development are recorded first in
`.agents/knowledge/decisions/`: those OKF files own context, alternatives,
rationale and decision status. This wiki owns the current implementation,
contracts and operational flows, supported by code evidence [@claude].
Pages under `almanac/decisions/` are implementation summaries with a source
reference to their authoritative OKF record; they do not own an independent
decision history. Existing page routes stay stable for incoming links.

For a new architectural choice, update OKF first, then its affected wiki pages
and technical guides. Behavior changes without a new choice need a wiki/guide
update, not a new decision. Mark superseded decisions explicitly and never
present a proposal or dated audit as implemented behavior. Current code defines
what runs; a conflict with an accepted decision must be stated and resolved
rather than silently reinterpreted [@claude].

Developer setup and documentation entry points live in `.agents/DEV.md`;
detailed technical instructions live in `docs/`, and curator-facing manuals
live in the separate `katalon-docs` repository. This wiki, the OKF bundle and
agent rules are excluded from the curated public export [@claude].

## Topic Taxonomy

Topics live in `topics.yaml`. Pages are Markdown files directly under
`almanac/`, including nested folders.

## Links

Use normal Markdown links between pages. Put file evidence in `sources:`.
