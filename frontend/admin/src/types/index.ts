export type Status = 'draft' | 'internal' | 'public'

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

export interface FieldDefinition {
  id: string
  target_type: string
  name: string
  label: Record<string, string>
  field_type: 'text' | 'date' | 'number' | 'geo' | 'vocab' | 'relation' | 'boolean' | 'richtext'
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

export interface AuditEntry {
  id: string
  record_type: string
  record_id: string
  user_id: string | null
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
