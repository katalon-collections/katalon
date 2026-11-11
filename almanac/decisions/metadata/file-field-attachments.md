---
title: "File Field Attachments Decision"
summary: "Attachments are a `file` schema field backed by their own table, not an extension of the object-only media model; the decision and its trade-offs live in the OKF record."
topics: [decisions, metadata, media, schema]
sources:
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/feldtyp-datei-anhaenge.md
  - id: concept-page
    type: file
    path: almanac/concepts/metadata/file-field-attachments.md
---

The authoritative rationale, alternatives and consequences live in the OKF record `.agents/knowledge/decisions/feldtyp-datei-anhaenge.md` [@decision-record]. This page summarizes the choice. Update the OKF record first when changing it, then the concept page [@concept-page].

Katalon stores non-media files as a `file` field on the five inventory and process types. The files sit in an `attachments` table with no field name or path, and metadata holds only an id plus a copy of the name, type and size. The backend checks every referenced id on save against its own record. Portal delivery re-runs the public metadata projection on each request. Visibility is set per field, not per file. The cleanup command is run from cron, with a default age of 7 days. Phase 1 has no per-file rights, licence or credit line. Media for more record types (#442) is a separate path that is still open.
