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
  - id: translatable-input
    type: file
    path: frontend/admin/src/components/ui/TranslatableInput.tsx
---

AI assistance is a form workflow, not an autonomous enrichment job. An admin enables `settings.ai_config` on a field definition or group child field, and the record form returns a suggestion without writing record metadata itself [@screen-schema] [@screen-form] [@ai-api]. A non-repeatable multilingual text or rich-text field may instead enable `settings.ai_translation`; the form then offers target-language actions and still requires explicit acceptance before local form state changes. Both paths keep the eventual write in the normal [schema driven record forms](schema-driven-record-forms) save path while the AI service owns prompt construction, provider calls, audit logging, and token accounting [@ai-service].

## Configuration Surface

Field completion configuration lives in `FieldDefinition.settings.ai_config`: `enabled`, `mode`, `prompt`, `include_fields`, and `send_existing_value`. Translation uses the independent `settings.ai_translation.enabled` flag, shown only when the field is multilingual and a complete global provider configuration, including API key, exists [@screen-schema]. Translation does not accept a custom prompt because source, target, and preservation rules are fixed by the operation [@screen-schema].

Provider configuration is central for the instance. `AdminConfig` stores `ai_enabled`, `ai_base_url`, `ai_model`, `ai_max_input_tokens`, `ai_max_output_tokens`, and user/global token limits, while the API key is stored separately in `AppSecret` under the `ai_api_key` secret key [@models] [@admin-config-api]. The admin settings screen exposes the base URL, model, key, and token controls [@screen-settings].

The provider contract is OpenAI-compatible Chat Completions. The service posts to `{ai_base_url}/chat/completions`, sends the configured model and messages, and reads `choices[0].message.content` plus OpenAI-style `usage` fields [@ai-service]. OpenAI, Deepseek, Ollama-compatible endpoints, or other compatible gateways are configuration changes; a native provider with a different request or response shape needs service code [@ai-service].

## Runtime Flow

`POST /v1/ai/complete` requires an admin or editor and accepts the record type, record id, field definition id, and optional group context (`group_index`, `group_instance`) [@ai-api]. `POST /v1/ai/translate` accepts a multilingual text or rich-text field, source/target language codes, and the current source value. It validates both languages against `supported_languages`, the field's translation flag, and the target record before calling the provider [@ai-api] [@ai-service].

For text completion, `_build_messages()` serializes configured context fields, the current value when `send_existing_value` is true, field metadata, and group sibling values when the request is for a group subfield [@ai-service]. Translation builds a fixed JSON-only prompt; rich-text translations must preserve HTML structure, attributes, and link targets. For vision mode, the service loads the object's primary ready media file, applies EXIF orientation, and sends a base64 image capped at 1024 px on its longest edge. Opaque images are encoded as JPEG; images with alpha are encoded as PNG [@ai-service].

The provider response must be JSON with a `value` key. The service strips code fences, parses JSON, validates the response, writes an `AIUsageEvent`, logs either `ai_complete` or `ai_translate` with provider/model/token metadata, and returns the value, confidence, warning, and usage to the frontend [@ai-service]. Backend tests cover code-fence stripping, content-part extraction, type coercion, translation prompt construction, and isolation of the selected group instance from sibling group instances [@ai-tests].

## Form Behavior And Gaps

Top-level fields call `runAIForField`; group child fields call `runAIForGroupSubField` with the selected group instance and index [@screen-form]. Every completion opens the editable proposal dialog before it changes local form state; the user still has to accept and save through the normal form flow [@screen-form]. Text and rich-text values retain the `KI-generiert` disclosure only when the accepted text has more than 70% normalized edit similarity to the suggestion. Other field types retain it only when accepted unchanged, avoiding an AI disclosure for materially rewritten values [@screen-form].

For a translation, the action belongs to the target-language row. With one filled source language it reads “Translate from XX”; with several it exposes a source-language selector. The proposal dialog compares the target's current value with the suggestion, and acceptance writes only the target language key. Provenance is stored as `<field>.<language>`, so manually changing one language clears only that language's disclosure [@screen-form] [@translatable-input].

The service enforces `ai_max_input_tokens` before the provider request, in addition to daily user and monthly global totals. Image data is excluded from this conservative text-context estimate; provider-reported prompt tokens remain the source for later usage accounting [@admin-config-api] [@ai-service].

## Boundary

AI field completion is not batch processing, training, search ranking, or a second write model. It is one authenticated suggestion endpoint plus schema-configured form buttons. Authority values are still stored by `AuthorityInput` as `{source, external_id, label}` rather than as full authority hit payloads, so AI suggestions that need durable external URIs must use a field type or metadata shape that actually stores those URIs [@authority-input].
