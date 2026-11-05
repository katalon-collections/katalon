---
title: "BagIt Preservation Export"
summary: "Katalon produces BagIt/METS/PREMIS preservation packages per Object with a configurable destination (local download, SFTP, S3, or custom REST PUT), scoped without an Archivematica API integration."
topics: [decisions, preservation, media, export, architecture]
sources:
  - id: oai-mapping
    type: file
    path: docs/07_export_mappings.md
  - id: subsystem-decision
    type: file
    path: almanac/decisions/platform/subsystem-extensions-vs-plugin-architecture.md
  - id: preservation-service
    type: file
    path: backend/src/katalon/services/preservation_service.py
  - id: preservation-api
    type: file
    path: backend/src/katalon/api/v1/preservation.py
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: admin-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: preservation-tests
    type: file
    path: backend/tests/test_preservation_service.py
  - id: preservation-integration-tests
    type: file
    path: backend/tests/integration/test_preservation_integration.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/bagit-preservation-export.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/bagit-preservation-export.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Katalon commits to a bounded first version of digital preservation export: standards-compliant BagIt bags with METS structural metadata and PREMIS preservation events, produced per Object, with a **configurable destination** — local ZIP download, or server-side deposit to SFTP, S3-compatible object storage, or a custom REST-capable repository via HTTP PUT. Direct API integration with a specific preservation system (Archivematica, Rosetta, Preservica) is explicitly excluded from this scope.


## Current Contract

Preservation export is descoped from "vision" to a planned, buildable feature, tracked as issue #127 under the media/long-term-availability roadmap (#266). The scope for the first version:

**Package format** — one bag per Object: `bagit.txt`, `manifest-sha256.txt`, `bag-info.txt`, `data/metadata/mets.xml` (structural metadata: master vs. derivative relationships), `data/metadata/premis.xml` (preservation events: ingest, fixity checks, derived from the existing audit log), `data/metadata/descriptive.xml` (Dublin Core, reusing the existing OAI-PMH `oai_dc` mapping [@oai-mapping]), `data/files/master/…` and `data/files/derivatives/…`.

**Rights metadata** — sourced from `MediaFile.license_uri` / `MediaFile.rights_holder`, falling back to the settings-level defaults; no new schema field required.

**Technical metadata extraction** — a tool such as `exiftool` or `mediainfo` runs in the Celery worker container to capture format, resolution, and color-profile facts into the PREMIS record; this is a new worker-image dependency, not yet present.

**Destination** — configurable per instance, not hard-coded to one transport:
- local ZIP download (manual "Export preservation package" action in the admin UI);
- server-side deposit to a configured SFTP target;
- server-side deposit to an S3-compatible bucket (reusing whatever object-storage client dependency #121 introduces, if that lands first — otherwise a minimal direct client);
- a generic HTTP PUT to a configured REST-capable repository endpoint (covers "any repository that can receive a file over HTTP" without naming a specific vendor).

Trigger stays manual per Object for the first version (a button, not a scheduled Celery task or an event-driven trigger on `public` status); scheduling and event triggers are a later increment once the manual path is proven, not part of this decision.

**Explicitly not in scope**: any vendor-specific submission API (Archivematica REST API, Rosetta, Preservica). If institutions need that later, it is a separate integration issue layered on top of the same bag-generation core, not a blocker for shipping bag export itself.

## Implementation Constraints

Bag generation, METS/PREMIS serialization, and destination handling become three separable concerns: a bag-builder service (pure, produces bytes), a destination adapter (download / SFTP / S3 / HTTP PUT, each a small interface implementation), and a trigger (manual endpoint now, scheduling later). This mirrors the existing pattern of keeping storage/export transports swappable rather than baking one destination into the export logic.

Because the destination is configurable rather than fixed, the settings model needs new instance-level configuration (destination type, credentials, target path/bucket/URL) analogous to the existing `media_default_license_uri` singleton pattern — this is new schema surface this decision commits to, and should live in customization config per [Subsystem Extensions vs. Plugin Architecture](../platform/subsystem-extensions-vs-plugin-architecture) [@subsystem-decision] rather than a bespoke settings table.

Because no vendor API is targeted, there is no dependency on any external preservation system being reachable or licensed — export always succeeds or fails based on the configured generic transport (filesystem, SFTP, S3, HTTP), which keeps the feature usable by institutions without an existing Archivematica/Rosetta/Preservica deployment. A future Archivematica-specific integration, if requested, is additive and does not require revisiting the bag-generation core.

## Umsetzungsstand

**Inkrement 1 (POC, 2026-09, v1.26.0):** Manueller Export pro Object als ZIP-Download. Umgesetzt sind Bag-Assembly (`services/preservation_service.py`, rein, Bytes rein/raus), METS (Master-/Derivative-Dateigruppen), PREMIS (Events aus dem Audit-Log, technische Merkmale nur Größe/MIME/SHA-256), Dublin Core über das veröffentlichte oai_dc-Mapping (Fallback: Identifier + Titel), Master-Original plus Pyramid-TIFF-Derivate [@preservation-service] [@preservation-tests]. Endpoint `GET /v1/preservation/objects/{object_id}/bag`, hinter dem Feature-Flag `export`; der Admin-Client lädt die ZIP-Datei herunter, und das Objektformular zeigt den Button im Medien-Header nur für gespeicherte Objects mit Export-Feature [@preservation-api] [@admin-client] [@admin-form]. Die Integrationstests prüfen erfolgreichen ZIP-Download, Dateinamen, BagIt-Dateien, Manifest und 404 für unbekannte Objects [@preservation-integration-tests].

**Noch offen aus dieser Entscheidung:** Destination-Adapter (SFTP/S3/REST-PUT) und serverseitige Ablage, Batch-/Scheduler-Trigger über Celery, `exiftool`/`mediainfo` im Worker für echte technische Metadaten (EXIF/XMP), konfigurierbare Ziel-Settings inkl. Credentials (`app_secrets`), Rechte-Metadaten (`license_uri`/`rights_holder`) als eigenes METS `rightsMD`-Segment statt nur implizit über das DC-Mapping.
