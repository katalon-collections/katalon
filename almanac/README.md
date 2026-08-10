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
`.agents/knowledge/decisions/` under the project instruction process, not by
opportunistically editing this wiki [@claude].

## Topic Taxonomy

Topics live in `topics.yaml`. Pages are Markdown files directly under
`almanac/`, including nested folders.

## Links

Use normal Markdown links between pages. Put file evidence in `sources:`.
