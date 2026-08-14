---
title: "AI Field Completion"
summary: "Admin forms can request AI suggestions for configured metadata fields through one OpenAI-compatible backend proxy, with group-subfield context and usage logging."
topics: [architecture, workflows, metadata, schema, admin, ai]
sources:
  - id: ai-api
    type: file
    path: backend/src/katalon/api/v1/ai.py
  - id: ai-service
    type: file
    path: backend/src/katalon/services/ai_service.py
  - id: admin-config-api
    type: file
    path: backend/src/katalon/api/v1/admin_config.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: screen-schema
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: screen-settings
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: authority-input
    type: file
    path: frontend/admin/src/components/AuthorityInput.tsx
  - id: ai-tests
    type: file
    path: backend/tests/test_ai_service.py
---

AI field completion is a form workflow, not an autonomous enrichment job. An admin enables `settings.ai_config` on a field definition or group child field, the record form shows a "KI" action for that field, and the backend returns a suggestion without writing record metadata itself [@screen-schema] [@screen-form] [@ai-api]. This keeps the write in the normal [schema driven record forms](schema-driven-record-forms) save path while letting the AI service own prompt construction, provider calls, coercion, audit logging, and token accounting [@ai-service].

## Configuration Surface

Field-level AI configuration lives in `FieldDefinition.settings.ai_config`. The schema editor persists the same shape for top-level fields and for subfields inside group fields: `enabled`, `mode`, `prompt`, `include_fields`, and `send_existing_value` [@screen-schema]. The form only renders a KI button when `ai_config.enabled` is present, so the schema is the feature gate for each field [@screen-form].

Provider configuration is central for the instance. `AdminConfig` stores `ai_enabled`, `ai_base_url`, `ai_model`, `ai_max_input_tokens`, `ai_max_output_tokens`, and user/global token limits, while the API key is stored separately in `AppSecret` under the `ai_api_key` secret key [@models] [@admin-config-api]. The admin settings screen exposes the base URL, model, key, and token controls [@screen-settings].

The provider contract is OpenAI-compatible Chat Completions. The service posts to `{ai_base_url}/chat/completions`, sends the configured model and messages, and reads `choices[0].message.content` plus OpenAI-style `usage` fields [@ai-service]. OpenAI, Deepseek, Ollama-compatible endpoints, or other compatible gateways are configuration changes; a native provider with a different request or response shape needs service code [@ai-service].

## Runtime Flow

`POST /v1/ai/complete` requires an admin or editor and accepts the record type, record id, field definition id, and optional group context (`group_index`, `group_instance`) [@ai-api]. The service rejects missing or inactive field definitions, mismatched record types, unsupported field types, missing prompts, disabled/incomplete AI configuration, and exhausted daily or monthly token limits before returning a suggestion [@ai-service].

For text mode, `_build_messages()` serializes configured context fields, the current value when `send_existing_value` is true, field metadata, and group sibling values when the request is for a group subfield [@ai-service]. For vision mode, the service loads the object's primary ready media file, applies EXIF orientation, and sends a base64 image capped at 1024 px on its longest edge. Opaque images are encoded as JPEG; images with alpha are encoded as PNG [@ai-service].

The provider response must be JSON with a `value` key. The service strips code fences, parses JSON, coerces repeatable, boolean, number, and text-like values to the target field shape, writes an `AIUsageEvent`, logs an `ai_complete` audit entry with provider/model/token metadata, and returns the value, confidence, warning, and usage to the frontend [@ai-service]. Backend tests cover code-fence stripping, content-part extraction, type coercion, and isolation of the selected group instance from sibling group instances [@ai-tests].

## Form Behavior And Gaps

Top-level fields call `runAIForField`; group child fields call `runAIForGroupSubField` with the selected group instance and index [@screen-form]. Both paths set a busy indicator, call the API, and write the returned value only into local form state; the user still has to save the record through the normal form flow [@screen-form].

Empty fields receive the suggestion directly into local form state. For an existing value, the form opens an overlay after the provider response with the current value, an editable proposal, and accept/discard actions. Accepting still changes only local form state; the ordinary form save remains responsible for persistence [@screen-form].

The service enforces `ai_max_input_tokens` before the provider request, in addition to daily user and monthly global totals. Image data is excluded from this conservative text-context estimate; provider-reported prompt tokens remain the source for later usage accounting [@admin-config-api] [@ai-service].

## Boundary

AI field completion is not batch processing, training, search ranking, or a second write model. It is one authenticated suggestion endpoint plus schema-configured form buttons. Authority values are still stored by `AuthorityInput` as `{source, external_id, label}` rather than as full authority hit payloads, so AI suggestions that need durable external URIs must use a field type or metadata shape that actually stores those URIs [@authority-input].
