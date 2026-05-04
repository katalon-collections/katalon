export type Status = 'draft' | 'internal' | 'public'
export type RecordType = 'object' | 'entity' | 'place' | 'occurrence'

export interface KatalonObject {
  id: string
  idno: string | null
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Entity {
  id: string
  entity_type: string
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Place {
  id: string
  status: Status
  lat: number | null
  lon: number | null
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Occurrence {
  id: string
  occurrence_type: string
  status: Status
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type AnyRecord = KatalonObject | Entity | Place | Occurrence

export interface FieldDefinition {
  id: string
  target_type: string
  target_subtype: string | null
  name: string
  label: Record<string, string>
  field_type: 'text' | 'date' | 'number' | 'geo' | 'vocab' | 'relation' | 'boolean' | 'richtext' | 'pid'
  is_required: boolean
  is_repeatable: boolean
  sort_order: number
  settings: Record<string, unknown>
}

export interface Vocabulary {
  id: string
  name: string
  is_hierarchical: boolean
}

export interface VocabularyTerm {
  id: string
  vocabulary_id: string
  term: string
  label: Record<string, string>
  parent_id: string | null
}

export interface Relation {
  id: string
  from_type: string
  from_id: string
  to_type: string
  to_id: string
  relation_type: string
  metadata_: Record<string, unknown>
  created_at: string
}

export interface AuditEntry {
  id: string
  record_type: string
  record_id: string
  record_label: string | null
  user_id: string | null
  user_name: string | null
  action: 'create' | 'update' | 'delete' | 'publish'
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
  facet_fields: string[]
  accent_color: string
  logo_url: string
}

export interface UserRead {
  id: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}
