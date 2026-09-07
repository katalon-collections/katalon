// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export type Status = 'draft' | 'internal' | 'public'
export type ProcedureStatus = 'draft' | 'active' | 'completed' | 'cancelled'
export type RecordType = 'object' | 'entity' | 'place' | 'occurrence' | 'procedure' | 'collection' | 'storage_location'
/** RecordType members handled by the generic ScreenList/ScreenForm/BatchEditModal trio.
 *  `storage_location` has its own dedicated tree screen (ScreenStorageLocation) instead. */
export type ListableRecordType = Exclude<RecordType, 'storage_location'>

export interface KatalonObject {
  id: string
  idno: string | null
  object_type: string | null
  collection_status?: string
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface Entity {
  id: string
  idno: string | null
  entity_type: string
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface Place {
  id: string
  idno: string | null
  place_type: string | null
  status: Status
  lat: number | null
  lon: number | null
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface Occurrence {
  id: string
  idno: string | null
  occurrence_type: string
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface Procedure {
  id: string
  idno: string | null
  procedure_type: string
  status: ProcedureStatus
  start_date: string | null
  end_date: string | null
  due_date: string | null
  reference_number: string | null
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface KatalonCollection {
  id: string
  idno: string | null
  collection_type: string | null
  parent_id: string | null
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface KatalonStorageLocation {
  id: string
  idno: string
  storage_location_type: string | null
  parent_id: string | null
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
  version: number
}

export interface StorageLocationObject {
  id: string
  idno: string | null
  title: string
  object_type: string | null
  status: string
  relation_type: string | null
  storage_location_id: string
  storage_location_idno: string | null
}

export type AnyRecord = KatalonObject | Entity | Place | Occurrence | Procedure | KatalonCollection | KatalonStorageLocation

export interface FieldDefinition {
  id: string
  target_type: string
  target_subtype: string | null
  name: string
  label: Record<string, string>
  field_type: 'text' | 'date' | 'number' | 'geo' | 'vocab' | 'vocab_free' | 'relation' | 'boolean' | 'richtext' | 'pid' | 'url' | 'authority' | 'group'
  is_required: boolean
  is_repeatable: boolean
  is_translatable: boolean
  sort_order: number
  settings: Record<string, unknown>
  show_in_detail: boolean
  show_in_list: boolean
  detail_slot?: 'main' | 'sidebar'
  detail_role?: 'none' | 'description'
  is_public?: boolean
  is_facet: boolean
  is_searchable: boolean
  parent_id?: string | null
  children?: FieldDefinition[]
}

export interface FormVariant {
  id: string
  target_type: string
  target_subtype: string | null
  name: string
  label: Record<string, string>
  field_names: string[]
  is_default_global: boolean
  sort_order: number
  is_deleted: boolean
  default_for_roles: string[]
}

export interface FieldAIConfig {
  enabled: boolean
  mode: 'text' | 'vision'
  prompt: string
  include_fields: string[]
  send_existing_value: boolean
}

export interface MetadataMapping {
  id: string
  field_definition_id: string
  format_key: string
  target_path: string
  settings: Record<string, unknown>
  sort_order: number
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface Vocabulary {
  id: string
  name: string
  is_hierarchical: boolean
  kind: 'term' | 'relation'
  canonical_uri?: string | null
}

export interface VocabularyTerm {
  id: string
  vocabulary_id: string
  term: string
  label: Record<string, string>
  inverse_label: Record<string, string>
  metadata_: Record<string, unknown>
  parent_id: string | null
  applies_from: string[]
  applies_to: string[]
  uri?: string | null
  exact_match_uris?: string[]
}

export interface VocabularyImportResult {
  strategy: string
  dry_run: boolean
  total?: number
  created: number
  updated: number
  deleted: number
  errors: { row: number | null; message: string }[]
  detected_schemes?: { uri: string; label: string }[]
  detected_top_concepts?: { uri: string; label: string }[]
  total_concepts_found?: number
  total_concepts_selected?: number
}

export interface Relation {
  id: string
  from_type: string
  from_id: string
  to_type: string
  to_id: string
  relation_type: string
  metadata_: Record<string, unknown>
  is_schema_derived: boolean
  created_at: string
  from_label: string | null
  to_label: string | null
}

export type BatchOperationType =
  | 'set_status'
  | 'set_field'
  | 'append_field'
  | 'clear_field'
  | 'add_relation'
  | 'remove_relation'

export interface BatchSetStatus {
  type: 'set_status'
  value: string
}

export interface BatchSetField {
  type: 'set_field'
  field: string
  value: unknown
}

export interface BatchAppendField {
  type: 'append_field'
  field: string
  value: unknown
}

export interface BatchClearField {
  type: 'clear_field'
  field: string
}

export interface BatchAddRelation {
  type: 'add_relation'
  relation_to_type: RecordType
  relation_to_id: string
  relation_type: string
}

export interface BatchRemoveRelation {
  type: 'remove_relation'
  relation_to_type: RecordType
  relation_to_id: string
  relation_type: string
}

export type BatchOperation =
  | BatchSetStatus
  | BatchSetField
  | BatchAppendField
  | BatchClearField
  | BatchAddRelation
  | BatchRemoveRelation

export interface BatchRequest {
  operation: BatchOperation
  ids?: string[]
  filters?: Record<string, unknown>
}

export interface BatchResponse {
  affected: number
  errors: string[]
  batch_job_id: string | null
  task_id: string | null
}

export interface AuditEntry {
  id: string
  record_type: string
  record_id: string
  record_label: string | null
  user_id: string | null
  user_name: string | null
  action: 'create' | 'update' | 'delete' | 'publish' | 'media_add' | 'media_update' | 'media_delete' | 'relation_add' | 'relation_update' | 'relation_delete' | 'ai_schema_assist'
  changed_fields: Record<string, unknown>
  created_at: string
}

export interface Page<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface Token {
  access_token: string
  token_type: string
}

export interface SearchResult {
  id: string
  record_type: string
  title: string
  idno?: string | null
  status: string | null
  score: number | null
}

export interface SearchResponse {
  total: number
  page: number
  page_size: number
  items: SearchResult[]
  facets: Record<string, { value: string; count: number }[]>
}

export interface AdminSearchResult {
  id: string
  kind: string
  title: string
  subtitle: string | null
  route: string
  edit_id: string | null
}

export interface AdminSearchResponse {
  items: AdminSearchResult[]
}

export interface Snapshot {
  id: string
  record_type: string
  record_id: string
  label: string
  snapshot: Record<string, unknown>
  created_by: string | null
  created_at: string
}

export interface PortalConfigRead {
  site_title: string
  site_subtitle: string
  hero_text: string
  featured_object_ids: string[]
  facet_fields: Record<string, string[]>
  subtitle_fields: Record<string, string[]>
  browse_enabled_types: string[]
  accent_color: string
  logo_url: string
  placeholder_image_url: string
  color_tokens: Record<string, string>
  detail_sidebar_position: 'left' | 'right'
  facet_sort: 'count' | 'alpha'
  facet_initial_count: number
}

export interface UserRead {
  id: string
  email: string
  role: string
  is_active: boolean
  created_at: string
  onboarding_completed_at: string | null
  last_login_at: string | null
}

export interface RolePermission {
  role: 'admin' | 'editor' | 'cataloger' | 'viewer'
  record_type: RecordType
  action: 'read' | 'create' | 'update' | 'delete'
}

export interface ApiKey {
  id: string
  user_id: string
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
  expires_at: string | null
}

export interface ApiKeyCreated extends ApiKey {
  /** The full plaintext key – only available immediately after creation */
  key: string
}

export interface RecordSubtype {
  id: string
  primary_type: string
  name: string
  label: Record<string, string>
  description: string
  sort_order: number
  is_default: boolean
}

export interface Banner {
  id: string
  message: string
  color: 'blue' | 'yellow' | 'red' | 'green'
  show_admin: boolean
  show_portal: boolean
  is_active: boolean
  expires_at: string | null
  created_at: string
  updated_at: string
}

/** Return the best available label from a vocabulary term, field, etc.
 *  Falls back to `fallback` (default: term/name itself) if all labels are empty.
 */
export function getLabel(
  item: { label?: Record<string, string>; term?: string; name?: string } | null | undefined,
  fallback?: string,
): string {
  if (!item) return fallback ?? ''
  const label = item.label
  if (label) {
    const de = label.de?.trim()
    if (de) return de
    const en = label.en?.trim()
    if (en) return en
    // Try any non-empty language key
    for (const key of Object.keys(label)) {
      const v = label[key]?.trim()
      if (v) return v
    }
  }
  return fallback ?? item.term ?? item.name ?? ''
}

export const IMPORTER_STATE_KEY = 'katalon_importer_state'

export interface WorkingSet {
  id: string
  name: string
  description: string | null
  record_type: string
  user_id: string
  user_name: string | null
  is_shared: boolean
  item_count: number
  created_at: string
  updated_at: string
}

export interface WorkingSetItem {
  id: string
  set_id: string
  record_id: string
  sort_order: number
  note: string | null
  created_at: string
  label: string | null
  idno: string | null
  status: string | null
  thumbnail_url: string | null
}

export interface WorkingSetDetail extends WorkingSet {
  items: WorkingSetItem[]
}

export interface WorkingSetCreate {
  name: string
  description?: string | null
  record_type: string
  is_shared?: boolean
}

export interface WorkingSetUpdate {
  name?: string | null
  description?: string | null
  is_shared?: boolean | null
}

export interface WorkingSetItemCreate {
  record_id: string
  sort_order?: number
  note?: string | null
}

export interface WorkingSetItemUpdate {
  sort_order?: number | null
  note?: string | null
}
