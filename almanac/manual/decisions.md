---
title: Decisions
topics: [manual]
---

# Decisions

## Katalon ownership rule

The authoritative decision record lives in `.agents/knowledge/decisions/`,
as required by `AGENTS.md`. Record new choices and changes of direction there
first. Pages in this wiki summarize that choice and describe its current
implementation, supported by source evidence. Include the OKF record as a
`type: file` source and cite it in the body. Do not maintain a second history
of alternatives or reverse a decision only in the wiki. Existing routes remain
valid; mark superseded behavior and link the replacement. The guidance below
describes what belongs in the underlying decision, not a requirement to copy
the full record into the wiki.

Use this manual when writing a page under `almanac/decisions/`. A decision page
records one architecturally meaningful choice so future maintainers do not have
to accept or reverse it blindly.

Write a decision page for choices that affect the structure of the system,
dependencies, interfaces, workflows, persistence, provider boundaries,
construction techniques, or important operational behavior.

The lead should summarize the choice, the context that made it necessary, and
the consequence future work must respect.

A decision page should usually cover:

- context
- decision
- status
- consequences

The context explains the forces at play. Name the tradeoffs, constraints,
alternatives, and pressures that made the choice meaningful. Keep this section
factual and value-neutral.

The decision states the chosen path clearly. Use full sentences and active
voice. Say what the project does or will do.

The consequences explain the resulting situation after the decision. Include
positive, negative, and neutral consequences. A useful consequence says what is
now easier, harder, required, forbidden, risky, or intentionally deferred.

If a later page reverses the decision, keep the old decision page and mark it as
superseded or link to the replacement. The old decision still matters because it
records what used to be true and why.

Write decision pages as a conversation with a future maintainer. Use
paragraphs, not bullet fragments. Bullets are fine for readability, but they
should not replace explanation.

Do not bundle several unrelated choices into one decision page.
