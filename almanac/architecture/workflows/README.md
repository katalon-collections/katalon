---
title: "Workflow Architecture"
summary: "Reading path for Katalon workflows that cross backend routes, services, workers, search, and frontend screens."
topics: [architecture, workflows, backend, frontend, i18n]
---

Katalon's workflow pages explain behavior that is spread across API routers, services, workers, persistence, search indexing, and React screens. Use this hub when a task crosses one file or one layer; it points to the page that owns the end-to-end flow instead of making agents reconstruct that flow from separate backend and frontend files.

## Record And Form Workflows

Start with [Record CRUD And Publishing](record-crud-and-publishing) when the task changes object, entity, place, occurrence, or procedure lifecycle behavior. Pair it with [Schema Driven Record Forms](schema-driven-record-forms) for Admin editing, quick creation, form variants, relation-field behavior, optimistic conflict handling, audit panels, media panels, and procedure completion.

Read [Batch Editing](../../workflows/batch-editing) when record-list selection, filter-based bulk targets, batch status or metadata changes, relation batch changes, or Celery-backed bulk edit execution are in scope.

Use [AI Field Completion](ai-field-completion) when changing schema-configured KI buttons, the `/v1/ai/complete` proxy, OpenAI-compatible provider settings, group-subfield AI context, token limits, or the proposed-value overwrite flow.

Use [Multilingual Content](../../decisions/metadata/multilingual-content) when changing configured languages, translated labels, translatable text values, portal locale resolution, or importer field-creation labels.

Read [Audit And Snapshots](audit-and-snapshots) when the change touches record history, snapshots, restore behavior, version columns, or the distinction between audit entries and snapshot storage.

## Search, Public Access, And Export

Read [Search And Indexing](search-and-indexing) before changing Elasticsearch document construction, relation denormalization, visibility filtering, reindexing, or reconciliation. Use [Portal Search And Facets](portal-search-and-facets) when that search behavior reaches the public Portal, configured facets, URL state, result cards, or detail navigation.

Use [OAI And Export Mappings](oai-and-export-mappings) for OAI-PMH, OAI-DC serialization, metadata mappings, and export behavior built from indexed records.

## Async And Media Workflows

Read [Media And IIIF](media-and-iiif) for object media uploads, worker processing, Cantaloupe image delivery, manifests, portal IIIF viewing, and batch media import.

Read [Importer Pipeline](importer-pipeline) for CSV, Excel, XML, dry-run validation, transform mapping, vocabulary reconciliation, Celery-backed record creation, and importer cancellation.

## Admin Guidance

Read [Admin Onboarding Tour](admin-onboarding-tour) before changing first-login guidance, restartable tours, step targets, or `data-tour` attributes on Admin screens.
