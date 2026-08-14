---
title: "Schema Driven Record Forms"
summary: "Admin record forms use one schema-driven React workflow for full editing and draft quick creation across objects, entities, places, occurrences, and procedures."
topics: [architecture, workflows, frontend, records, schema]
sources:
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: authority-input
    type: file
    path: frontend/admin/src/components/AuthorityInput.tsx
  - id: screen-list
    type: file
    path: frontend/admin/src/components/screens/ScreenList.tsx
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: objects-api
    type: file
    path: backend/src/katalon/api/v1/objects.py
  - id: entities-api
    type: file
    path: backend/src/katalon/api/v1/entities.py
  - id: procedures-api
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: form-variants-api
    type: file
    path: backend/src/katalon/api/v1/form_variants.py
  - id: form-variants-models
    type: file
    path: backend/src/katalon/core/models.py
  - id: form-variants-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenFormVariants.tsx
  - id: form-variants-lib
    type: file
    path: frontend/admin/src/lib/formVariants.ts
  - id: form-variants-tests
    type: file
    path: backend/tests/test_form_variants_validation.py
  - id: relations-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: changelog
    type: file
    path: CHANGELOG.md
---

Schema-driven record forms are the admin workflow that turns Katalon's configurable metadata model into editable screens. One `ScreenForm` component handles objects, entities, places, occurrences, and procedures by selecting the correct API module, loading the record and field definitions, rendering inputs from `field_type`, validating the local draft, then saving a payload that combines record scalars with `metadata_` [@screen-form] [@admin-client]. The backend repeats the same contract for each record type: prepare metadata through schema rules, validate required fields unless the status is `draft`, synchronize schema relation fields, log the change, and update the search index [@objects-api] [@entities-api] [@procedures-api].

## List-To-Form Flow

The list screen chooses an API module from `recordType`, loads records with pagination, status filters, search, and procedure-specific filters, and opens the form with the selected id [@screen-list]. List columns are also schema-driven: `ScreenList` fetches `schema.list(recordType)`, keeps fields marked `show_in_list`, sorts them by `sort_order`, and reads display values from each record's metadata [@screen-list].

`ScreenForm` uses the same `recordType` to choose its endpoint wrapper and to enable type-specific scalars: object collection status and media, place coordinates, procedure dates and reference number, and subtype fields for the supported record types [@screen-form]. On new forms it asks the ID-number endpoint for the next id, loads subtypes when needed, and loads schema definitions for the current record type and subtype [@screen-form].

## Dynamic Metadata Inputs

Field definitions control both default values and rendered controls. The form applies `settings.default_value` on new records, reloads subtype-specific definitions when a new record's subtype changes, and renders specialized controls for vocabularies, free vocabulary text, authority links, schema relation fields, groups, PID fields, booleans, numbers, dates, and text [@screen-form].

Repeatable fields are represented as arrays in local state, while group fields are arrays of child-field objects [@screen-form]. Vocabulary and relation fields call their own lookup endpoints through the admin API client; relation-field inputs use search results and relation-type vocabularies when configured [@screen-form] [@admin-client].

The component also handles object media after a record has an id. It loads existing media, uploads a selected or dropped file, patches rights and media type data, marks a primary image, deletes media, and polls until pending uploads finish processing [@screen-form] [@admin-client].

## Form Variants (#275)

Admins can configure multiple named form variants per record type and optional subtype (Konfiguration → Formularvarianten, `ScreenFormVariants`) [@form-variants-screen]. A variant is a `FormVariant` row (`target_type`, optional `target_subtype`, `name`, `label`, an ordered `field_names` array referencing existing `field_definitions.name` values, `is_default_global`, `sort_order`) — it never copies field definitions or introduces a second metadata store; records keep saving to the same `metadata_` JSONB regardless of which variant was active [@form-variants-models] [@changelog]. `FormVariantRoleDefault` rows map `(target_type, target_subtype, role)` to one variant, enforced unique at the database level so setting a new role default for a scope automatically supersedes the previous one [@form-variants-api] [@form-variants-models].

`ScreenForm` fetches available variants alongside field definitions for the active `recordType`/subtype and resolves which one is active through a priority chain, implemented as the pure function `resolveActiveVariant` [@form-variants-lib]: an optional context-override prop (`variantHint`, exposed as a hook for future workflow/quick-add callers but not yet wired to any caller) beats a manually remembered choice in `localStorage` (keyed per record type and subtype), which beats the current user's role-based default, which beats a variant flagged as the global default for that scope. If none match, the form falls back to the full schema — identical to pre-#275 behavior — which is also what happens when the user explicitly picks the "Vollständig" tab, stored as a distinct sentinel so it isn't silently overridden by a role or global default on the next visit [@form-variants-lib]. A tab bar above the dynamic fields lets the user switch variants manually; the active variant filters and reorders the already-loaded `FieldDefinition[]` by `field_names`, so group parent/child rendering is unaffected as long as the group's own name is included [@screen-form].

Form variants must include every required field path that could block saving. The backend validates create and update requests by loading active top-level field definitions (`parent_id IS NULL`), rejecting unknown `field_names`, rejecting omitted required top-level fields, and treating a group as required when any active child field under that group is required [@form-variants-api] [@form-variants-tests]. The admin variant editor mirrors that invariant by preselecting required fields and groups for new variants and disabling their checkboxes with a "Pflicht" marker [@form-variants-screen]. This keeps `validate_metadata` from requiring a field or group child that the selected variant has hidden from the editor [@schema-service].

## Embedded Field Behaviors

Current forms render group sub-fields, relation fields, authority fields, and AI settings [@screen-form]. Authority reaches group child fields through the shared keyboard-accessible `AuthorityInput` [@schema-screen] [@screen-form] [@authority-input]. Eligible group child fields can also carry the existing `ai_config`: each rendered group instance gets its own AI action, sends that instance and its index as context, and opens an editable proposal dialog before replacing a non-empty value; accepted suggestions still write only to local form state [@schema-screen] [@screen-form]. The backend provider call, usage logging, token limits, and image-size handling are covered in [AI Field Completion](ai-field-completion).

Schema relation inputs use the shared relation picker for top-level, repeatable, and group sub-fields. The field definition fixes the target record type and can also set `target_subtype`; the picker applies that subtype to search and to inline creation [@screen-form] [@admin-client]. When a relation-type vocabulary is configured, the picker asks the vocabulary API for terms allowed for the current source record type and the field's target type before rendering the relation-type select [@screen-form] [@admin-client]. Choosing an existing record or creating a new one writes `{id, label, relation_type}` only to the source form's local metadata. The backend mirrors it into the relation table when that source record is later saved; immediate writes through the generic relation API separately validate relation-type applicability and reject disallowed pairs with HTTP 422 [@screen-form] [@relations-api].

## Draft Quick Creation (#277)

The relation picker can create any of the five record types in a native modal dialog without unmounting the source form. The dialog renders `ScreenForm` in quick-create mode, so it retains the target type's scalar fields, schema fields, subtype selector, and active form variant. It always creates a `draft`; status controls, media, audit history, snapshots, relation panels, and nested quick creation are omitted [@screen-form].

A configured `target_subtype` is preselected and locked. Otherwise the form selects the default subtype when one exists and leaves the subtype selector available. Procedure quick creation uses the configured Procedure subtypes, including the six protected system subtypes and locally configured types [@screen-form]. The dialog keeps its own dirty state for discard confirmation, and closing it restores focus without changing the source form [@screen-form].

## Validation And Save

Validation runs before each save. Ordinary draft forms treat missing `idno`, subtype, and required metadata as warnings, while non-draft statuses treat them as errors. Quick creation adds a structural check for an Entity subtype and for any locked `target_subtype` [@screen-form]. The form also validates date, number, text regex, repeatable values, and required group children on the client [@screen-form].

The save payload always sends `status` and `metadata_`, then adds the scalars relevant to the active record type [@screen-form]. New records call `create`; existing records call `update` with the loaded `version`, which the API client sends as `If-Match` [@screen-form] [@admin-client]. The backend object, entity, and procedure endpoints then prepare and validate metadata, increment `version` on updates, synchronize schema relations, write audit entries, and re-index records [@objects-api] [@entities-api] [@procedures-api].

If the backend reports an optimistic-locking conflict, the form fetches the current server record and performs a metadata-only three-way merge using loaded base values, server values, and the user's current values [@screen-form]. Fields changed only on one side are merged automatically; fields changed on both sides are shown in a conflict dialog and then committed with the server's newer version [@screen-form]. The reason this stays metadata-field scoped is recorded in [Optimistic Locking](../../decisions/workflows/optimistic-locking).

## Related Panels

Existing records load both incoming and outgoing generic relations, fetch display titles for related records, and let users add or remove relations from the form side panel [@screen-form]. Its add flow first chooses one of the five target types, then a relation type and target record. A newly created draft is linked immediately through the relation API; if linking fails, the picker keeps the draft selected and offers a retry [@screen-form] [@relations-api]. Procedure forms can add related objects, and object forms can add procedures through the same picker with the fixed relation type `concerns` [@screen-form].

For saved collection records, snapshots and audit history are part of the same editing surface. Procedure forms show audit history only: they do not load, create, or restore snapshots [@screen-form] [@admin-client]. Those persistence details are covered in [Audit And Snapshots](audit-and-snapshots).

When a procedure is moved to `completed`, the form saves ordinary procedure changes first and then calls the procedure completion endpoint. If linked objects exist and the procedure type has a suggested collection status, the user chooses whether completion should update those objects [@screen-form] [@procedures-api]. That makes procedure completion a workflow step rather than a plain status edit.
