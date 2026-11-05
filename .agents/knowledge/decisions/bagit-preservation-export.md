---
type: Decision
title: "BagIt Preservation Export"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/preservation/bagit-preservation-export.md
consolidated: 2026-10-30
---

Katalon commits to a bounded first version of digital preservation export: standards-compliant BagIt bags with METS structural metadata and PREMIS preservation events, produced per Object, with a **configurable destination** — local ZIP download, or server-side deposit to SFTP, S3-compatible object storage, or a custom REST-capable repository via HTTP PUT. Direct API integration with a specific preservation system (Archivematica, Rosetta, Preservica) is explicitly excluded from this scope.

## Context

GitHub issue #127 originally framed preservation export as a vision note, marked "absolutely out of scope for MVP and foreseeable future," to keep the architecture from foreclosing the path. It listed BagIt (RFC 8493), METS, PREMIS, embedded technical metadata (EXIF/XMP), and Dublin Core/DataCite as the relevant standards, and named four prerequisites: accessible media storage, technical metadata extraction, PREMIS events derived from the audit log, and a rights/license field on Objects.

The rights/license prerequisite is already resolved independently of this decision: `MediaFile` carries `license_uri` and `rights_holder` (JSONB), with instance-wide defaults `media_default_license_uri` / `media_default_rights_holder` on the settings singleton [1]. Preservation export can read this data directly instead of modeling a new field.

Institutions with a legal or funder mandate to hand over preservation packages to a national archive or trusted repository cannot use Katalon as their sole system of record without an export path. Vendor-specific ingest APIs (Archivematica, Rosetta) are a much larger integration surface — authentication, job polling, format-specific submission APIs — than most institutions need for a first working handover: many trusted repositories and network shares accept a bag by any bulk transfer mechanism, not just a vendor API.

## Decision

Preservation export is descoped from "vision" to a planned, buildable feature, tracked as issue #127 under the media/long-term-availability roadmap (#266). The scope for the first version:

**Package format** — one bag per Object: `bagit.txt`, `manifest-sha256.txt`, `bag-info.txt`, `data/metadata/mets.xml` (structural metadata: master vs. derivative relationships), `data/metadata/premis.xml` (preservation events: ingest, fixity checks, derived from the existing audit log), `data/metadata/descriptive.xml` (Dublin Core, reusing the existing OAI-PMH `oai_dc` mapping [2]), `data/files/master/…` and `data/files/derivatives/…`.

**Rights metadata** — sourced from `MediaFile.license_uri` / `MediaFile.rights_holder`, falling back to the settings-level defaults; no new schema field required.

**Technical metadata extraction** — a tool such as `exiftool` or `mediainfo` runs in the Celery worker container to capture format, resolution, and color-profile facts into the PREMIS record; this is a new worker-image dependency, not yet present.

**Destination** — configurable per instance, not hard-coded to one transport:
- local ZIP download (manual "Export preservation package" action in the admin UI);
- server-side deposit to a configured SFTP target;
- server-side deposit to an S3-compatible bucket (reusing whatever object-storage client dependency #121 introduces, if that lands first — otherwise a minimal direct client);
- a generic HTTP PUT to a configured REST-capable repository endpoint (covers "any repository that can receive a file over HTTP" without naming a specific vendor).

Trigger stays manual per Object for the first version (a button, not a scheduled Celery task or an event-driven trigger on `public` status); scheduling and event triggers are a later increment once the manual path is proven, not part of this decision.

**Explicitly not in scope**: any vendor-specific submission API (Archivematica REST API, Rosetta, Preservica). If institutions need that later, it is a separate integration issue layered on top of the same bag-generation core, not a blocker for shipping bag export itself.

## Consequences

Bag generation, METS/PREMIS serialization, and destination handling become three separable concerns: a bag-builder service (pure, produces bytes), a destination adapter (download / SFTP / S3 / HTTP PUT, each a small interface implementation), and a trigger (manual endpoint now, scheduling later). This mirrors the existing pattern of keeping storage/export transports swappable rather than baking one destination into the export logic.

Because the destination is configurable rather than fixed, the settings model needs new instance-level configuration (destination type, credentials, target path/bucket/URL) analogous to the existing `media_default_license_uri` singleton pattern — this is new schema surface this decision commits to, and should live in customization config per [Subsystem Extensions vs. Plugin Architecture](../../../almanac/decisions/platform/subsystem-extensions-vs-plugin-architecture.md) [3] rather than a bespoke settings table.

Because no vendor API is targeted, there is no dependency on any external preservation system being reachable or licensed — export always succeeds or fails based on the configured generic transport (filesystem, SFTP, S3, HTTP), which keeps the feature usable by institutions without an existing Archivematica/Rosetta/Preservica deployment. A future Archivematica-specific integration, if requested, is additive and does not require revisiting the bag-generation core.

## Umsetzungsstand

**Inkrement 1 (POC, 2026-09, v1.26.0):** Manueller Export pro Object als ZIP-Download. Umgesetzt sind Bag-Assembly (`services/preservation_service.py`, rein, Bytes rein/raus), METS (Master-/Derivative-Dateigruppen), PREMIS (Events aus dem Audit-Log, technische Merkmale nur Größe/MIME/SHA-256), Dublin Core über das veröffentlichte oai_dc-Mapping (Fallback: Identifier + Titel), Master-Original plus Pyramid-TIFF-Derivate [4] [8]. Endpoint `GET /v1/preservation/objects/{object_id}/bag`, hinter dem Feature-Flag `export`; der Admin-Client lädt die ZIP-Datei herunter, und das Objektformular zeigt den Button im Medien-Header nur für gespeicherte Objects mit Export-Feature [5] [6] [7]. Die Integrationstests prüfen erfolgreichen ZIP-Download, Dateinamen, BagIt-Dateien, Manifest und 404 für unbekannte Objects [9].

**Noch offen aus dieser Entscheidung:** Destination-Adapter (SFTP/S3/REST-PUT) und serverseitige Ablage, Batch-/Scheduler-Trigger über Celery, `exiftool`/`mediainfo` im Worker für echte technische Metadaten (EXIF/XMP), konfigurierbare Ziel-Settings inkl. Credentials (`app_secrets`), Rechte-Metadaten (`license_uri`/`rights_holder`) als eigenes METS `rightsMD`-Segment statt nur implizit über das DC-Mapping.

# Citations

[1] backend/src/katalon/core/models.py
[2] docs/07_export_mappings.md
[3] almanac/decisions/platform/subsystem-extensions-vs-plugin-architecture.md
[4] backend/src/katalon/services/preservation_service.py
[5] backend/src/katalon/api/v1/preservation.py
[6] frontend/admin/src/api/client.ts
[7] frontend/admin/src/components/screens/ScreenForm.tsx
[8] backend/tests/test_preservation_service.py
[9] backend/tests/integration/test_preservation_integration.py
