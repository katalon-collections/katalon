import type { ApiKey, ApiKeyCreated, AuditEntry, Banner, Entity, FieldDefinition, KatalonObject, Occurrence, Page, Place, RecordSubtype, Relation, SearchResponse, Snapshot, Token, UserRead, Vocabulary, VocabularyTerm } from '../types'

export const BASE = import.meta.env.VITE_API_URL ?? ''
export const PORTAL_URL = import.meta.env.VITE_PORTAL_URL ?? (typeof window !== 'undefined' ? window.location.origin : '')

let _token: string | null = localStorage.getItem('katalon_token')
let _onUnauthorized: (() => void) | null = null

export function setToken(t: string | null) {
  _token = t
  t ? localStorage.setItem('katalon_token', t) : localStorage.removeItem('katalon_token')
}

export function hasToken(): boolean {
  return Boolean(_token)
}

export function getTokenUser(): { email: string; role: string } | null {
  if (!_token) return null
  try {
    const payload = JSON.parse(atob(_token.split('.')[1]))
    return { email: payload.email ?? '', role: payload.role ?? '' }
  } catch {
    return null
  }
}

export function onUnauthorized(cb: () => void) {
  _onUnauthorized = cb
}

export async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string> ?? {}) }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(path.startsWith('http') ? path : `${BASE}${path}`, { ...init, headers })
  if (res.status === 401) {
    setToken(null)
    _onUnauthorized?.()
    throw new Error('Sitzung abgelaufen. Bitte neu anmelden.')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Auth
export const auth = {
  login: (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password })
    return req<Token>('/v1/auth/token', { method: 'POST', body: body.toString(), headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  },
}

export const users = {
  list: () => req<UserRead[]>('/v1/users'),
  create: (data: { email: string; password: string; role: string }) =>
    req<UserRead>('/v1/users', { method: 'POST', body: JSON.stringify(data) }),
  update: (userId: string, data: { email?: string; password?: string; role?: string; is_active?: boolean }) =>
    req<UserRead>(`/v1/users/${userId}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (userId: string) => req<void>(`/v1/users/${userId}`, { method: 'DELETE' }),
  changeOwnPassword: (current_password: string, new_password: string) =>
    req<void>('/v1/users/me/password', { method: 'PUT', body: JSON.stringify({ current_password, new_password }) }),
  changeOwnEmail: (new_email: string, current_password: string) =>
    req<UserRead>('/v1/users/me/email', { method: 'PUT', body: JSON.stringify({ new_email, current_password }) }),
}

// Objects
export const objects = {
  list: (params?: { page?: number; page_size?: number; status?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<KatalonObject>>(`/v1/objects${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<KatalonObject>(`/v1/objects/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/objects/${id}/audit-log`),
  create: (data: Partial<KatalonObject>) => req<KatalonObject>('/v1/objects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<KatalonObject>) => req<KatalonObject>(`/v1/objects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/objects/${id}`, { method: 'DELETE' }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/objects/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/objects/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string) => req<KatalonObject>(`/v1/objects/${id}/snapshots/${snapId}/restore`, { method: 'POST' }),
  },
}

// Entities
export const entities = {
  list: (params?: { page?: number; page_size?: number; status?: string; entity_type?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Entity>>(`/v1/entities${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Entity>(`/v1/entities/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/entities/${id}/audit-log`),
  create: (data: Partial<Entity>) => req<Entity>('/v1/entities', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Entity>) => req<Entity>(`/v1/entities/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/entities/${id}`, { method: 'DELETE' }),
}

// Places
export const places = {
  list: (params?: { page?: number; page_size?: number; status?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Place>>(`/v1/places${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Place>(`/v1/places/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/places/${id}/audit-log`),
  create: (data: Partial<Place>) => req<Place>('/v1/places', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Place>) => req<Place>(`/v1/places/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/places/${id}`, { method: 'DELETE' }),
}

// Occurrences
export const occurrences = {
  list: (params?: { page?: number; page_size?: number; status?: string; occurrence_type?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Occurrence>>(`/v1/occurrences${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Occurrence>(`/v1/occurrences/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/occurrences/${id}/audit-log`),
  create: (data: Partial<Occurrence>) => req<Occurrence>('/v1/occurrences', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Occurrence>) => req<Occurrence>(`/v1/occurrences/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/occurrences/${id}`, { method: 'DELETE' }),
}

export interface SchemaImportResult {
  created: number
  updated: number
  skipped: number
  errors: string[]
  fields: FieldDefinition[]
}

// Schema
export const schema = {
  list:   (targetType: string, subtype?: string) => {
    const qs = subtype ? `?subtype=${encodeURIComponent(subtype)}` : ''
    return req<FieldDefinition[]>(`/v1/schema/${targetType}${qs}`)
  },
  create: (data: Omit<FieldDefinition, 'id'>) => req<FieldDefinition>('/v1/schema', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Omit<FieldDefinition, 'id'>) => req<FieldDefinition>(`/v1/schema/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/schema/${id}`, { method: 'DELETE' }),
  import: async (file: File, opts: { dryRun?: boolean; overwrite?: boolean } = {}): Promise<SchemaImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const headers: Record<string, string> = {}
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    const qs = new URLSearchParams()
    if (opts.dryRun) qs.set('dry_run', 'true')
    if (opts.overwrite) qs.set('overwrite', 'true')
    const res = await fetch(`${BASE}/v1/schema/import${qs.toString() ? `?${qs}` : ''}`, { method: 'POST', body: formData, headers })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen. Bitte neu anmelden.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
}

// Vocabularies
export const vocabularies = {
  list:       () => req<Vocabulary[]>('/v1/vocabularies'),
  create:     (data: Omit<Vocabulary, 'id'>) => req<Vocabulary>('/v1/vocabularies', { method: 'POST', body: JSON.stringify(data) }),
  listTerms:  (vocabId: string) => req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms`),
  searchTerms: (vocabId: string, q: string) => req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms?q=${encodeURIComponent(q)}`),
  createTerm: (vocabId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/${vocabId}/terms`, { method: 'POST', body: JSON.stringify(data) }),
  updateTerm: (termId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/terms/${termId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTerm: (termId: string) => req<void>(`/v1/vocabularies/terms/${termId}`, { method: 'DELETE' }),
  importTerms: async (
    vocabId: string,
    file: File,
    opts: { dryRun?: boolean; strategy?: 'append' | 'replace'; mapping?: Record<string, string> } = {},
  ): Promise<{ strategy: string; dry_run: boolean; created: number; updated: number; deleted: number; errors: { row: number | null; message: string }[] }> => {
    const formData = new FormData()
    formData.append('file', file)
    if (opts.mapping) {
      formData.append('mapping', JSON.stringify(opts.mapping))
    }
    const headers: Record<string, string> = {}
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    const qs = new URLSearchParams()
    qs.set('dry_run', String(opts.dryRun ?? true))
    qs.set('strategy', opts.strategy ?? 'append')
    const res = await fetch(`${BASE}/v1/vocabularies/${vocabId}/import?${qs}`, { method: 'POST', body: formData, headers })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen. Bitte neu anmelden.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
}

// Media
export interface MediaFile {
  id: string
  filename: string
  mime_type: string
  status: string
  is_primary: boolean
  media_type: string | null
  created_at: string
}

export interface MediaBatchStatus {
  state: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | string
  result?: {
    batch_id: string
    total_files: number
    planned: number
    created: number
    failed: number
    report: {
      missing_files: { row: number | null; filename: string }[]
      duplicate_files: { row: number | null; filename: string; count?: number }[]
      unmatched_files: { filename: string }[]
      errors: { row: number | null; message: string }[]
    }
  }
  meta?: { total: number; processed: number; created: number; failed: number }
  error?: string
}

type FolderFile = File & { webkitRelativePath?: string }

function fileFormName(file: FolderFile): string {
  return file.webkitRelativePath || file.name
}

export const media = {
  list: (objectId: string) => req<MediaFile[]>(`/v1/objects/${objectId}/media`),
  upload: async (objectId: string, file: File): Promise<MediaFile> => {
    const formData = new FormData()
    formData.append('file', file)
    const headers: Record<string, string> = {}
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    const res = await fetch(`${BASE}/v1/objects/${objectId}/media`, { method: 'POST', body: formData, headers })
    if (res.status === 401) {
      setToken(null)
      _onUnauthorized?.()
      throw new Error('Sitzung abgelaufen. Bitte neu anmelden.')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? res.statusText)
    }
    return res.json()
  },
  patch: (objectId: string, mediaId: string, data: { media_type?: string | null; is_primary?: boolean }) =>
    req<MediaFile>(`/v1/objects/${objectId}/media/${mediaId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (objectId: string, mediaId: string) => req<void>(`/v1/objects/${objectId}/media/${mediaId}`, { method: 'DELETE' }),
  batchImport: async (archive: File | null, mapping: File | null, files: File[]): Promise<{ status: string; task_id: string; batch_id: string }> => {
    const formData = new FormData()
    if (archive) formData.append('archive', archive)
    if (mapping) formData.append('mapping', mapping)
    for (const file of files) formData.append('files', file, fileFormName(file as FolderFile))
    const headers: Record<string, string> = {}
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    const res = await fetch(`${BASE}/v1/media/batch-import`, { method: 'POST', body: formData, headers })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen. Bitte neu anmelden.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  batchTaskStatus: (taskId: string): Promise<MediaBatchStatus> =>
    req<MediaBatchStatus>(`/v1/media/batch-import/task/${taskId}`),
}

// Relations
export const relations = {
  list: (params?: { from_type?: string; from_id?: string; to_type?: string; to_id?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Relation[]>(`/v1/relations${qs ? `?${qs}` : ''}`)
  },
  create: (data: { from_type: string; from_id: string; to_type: string; to_id: string; relation_type: string; metadata_?: Record<string, unknown> }) =>
    req<Relation>('/v1/relations', { method: 'POST', body: JSON.stringify({ metadata_: {}, ...data }) }),
  delete: (id: string) => req<void>(`/v1/relations/${id}`, { method: 'DELETE' }),
}

// Search
export const search = {
  query: (q: string, type?: string, pageSize = 8) => {
    const params: Record<string, string> = { q, page_size: String(pageSize) }
    if (type) params.type = type
    return req<SearchResponse>(`/v1/search?${new URLSearchParams(params)}`)
  },
}

// Authority
export interface AuthorityHit {
  source: string; external_id: string; label: string; description: string; extra: Record<string, unknown>
}
export const authority = {
  search: (source: string, q: string, limit = 10) =>
    req<AuthorityHit[]>(`/v1/authorities/search?source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}&limit=${limit}`),
  fetch: (source: string, id: string) =>
    req<AuthorityHit>(`/v1/authorities/fetch?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}`),
}

export const pids = {
  registerDnbUrn: (data: {
    record_type: string
    record_id: string
    field_name: string
    target_url: string
    label?: string
  }) => req<{ urn: string; resolver_url: string; value: { value: string; label: string } }>(
    '/v1/pids/urn/register',
    { method: 'POST', body: JSON.stringify(data) },
  ),
}

// Record Subtypes
export const subtypes = {
  list: (primaryType?: string) => {
    const qs = primaryType ? `?primary_type=${encodeURIComponent(primaryType)}` : ''
    return req<RecordSubtype[]>(`/v1/record-subtypes${qs}`)
  },
  create: (data: { primary_type: string; name: string; label: Record<string, string>; sort_order?: number; is_default?: boolean }) =>
    req<RecordSubtype>('/v1/record-subtypes', { method: 'POST', body: JSON.stringify({ sort_order: 0, is_default: false, ...data }) }),
  update: (id: string, data: { primary_type: string; name: string; label: Record<string, string>; sort_order?: number; is_default?: boolean }) =>
    req<RecordSubtype>(`/v1/record-subtypes/${id}`, { method: 'PUT', body: JSON.stringify({ sort_order: 0, is_default: false, ...data }) }),
  delete: (id: string) => req<void>(`/v1/record-subtypes/${id}`, { method: 'DELETE' }),
}

// Audit
export const audit = {
  list: (params?: { record_type?: string; action?: string; limit?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<AuditEntry[]>(`/v1/audit${qs ? `?${qs}` : ''}`)
  },
}

// Static Pages
export interface StaticPage {
  id: string
  slug: string
  title: Record<string, string>
  content: Record<string, string>
  is_published: boolean
  sort_order: number
}

export const staticPages = {
  list:   () => req<StaticPage[]>('/v1/pages/admin'),
  create: (data: { slug: string; title: Record<string, string>; content: Record<string, string>; is_published: boolean; sort_order: number }) =>
    req<StaticPage>('/v1/pages', { method: 'POST', body: JSON.stringify(data) }),
  update: (slug: string, data: Partial<{ title: Record<string, string>; content: Record<string, string>; is_published: boolean; sort_order: number }>) =>
    req<StaticPage>(`/v1/pages/${slug}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (slug: string) => req<void>(`/v1/pages/${slug}`, { method: 'DELETE' }),
}

// Importer
export interface UploadResult {
  headers: string[]
  row_count: number
  preview: Record<string, string>[]
  rows: Record<string, string>[]
}

export interface DryRunResult {
  total: number
  valid: number
  errors: { row: number | null; message: string }[]
  warnings: { row: number | null; message: string }[]
  preview: Record<string, unknown>[]
}

export interface TaskStatus {
  state: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | string
  result?: { created: number; errors: { row: number; error: string }[] }
  error?: string
}

export const importer = {
  upload: async (file: File): Promise<UploadResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const headers: Record<string, string> = {}
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    const res = await fetch(`${BASE}/v1/importer/upload`, { method: 'POST', body: formData, headers })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  dryRun: (recordType: string, rows: Record<string, string>[], mapping: Record<string, string>): Promise<DryRunResult> =>
    req<DryRunResult>('/v1/importer/dry-run', { method: 'POST', body: JSON.stringify({ record_type: recordType, rows, mapping }) }),
  import: (recordType: string, rows: Record<string, string>[], mapping: Record<string, string>): Promise<{ task_id: string; status: string }> =>
    req('/v1/importer/import', { method: 'POST', body: JSON.stringify({ record_type: recordType, rows, mapping }) }),
  taskStatus: (taskId: string): Promise<TaskStatus> =>
    req<TaskStatus>(`/v1/importer/task/${taskId}`),
}

// OAI Sets
export interface OAISet {
  id: string
  set_spec: string
  set_name: string
  filter_record_type: string | null
  filter_q: string | null
  filter_status: string | null
  filter_metadata: Record<string, string>
  created_at: string
  updated_at: string
}

export interface OAISetPayload {
  set_spec: string
  set_name: string
  filter_record_type: string | null
  filter_q: string | null
  filter_status: string | null
  filter_metadata: Record<string, string>
}

export const oaiSets = {
  list:   () => req<OAISet[]>('/v1/oai-sets'),
  create: (data: OAISetPayload) => req<OAISet>('/v1/oai-sets', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: OAISetPayload) => req<OAISet>(`/v1/oai-sets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/oai-sets/${id}`, { method: 'DELETE' }),
}

export const apiKeys = {
  /** List API keys for the current user */
  listOwn: () => req<ApiKey[]>('/v1/users/me/api-keys'),
  /** Create a new API key for the current user */
  createOwn: (name: string, expires_at?: string | null) =>
    req<ApiKeyCreated>('/v1/users/me/api-keys', { method: 'POST', body: JSON.stringify({ name, expires_at: expires_at ?? null }) }),
  /** Revoke an API key owned by the current user */
  revokeOwn: (keyId: string) => req<void>(`/v1/users/me/api-keys/${keyId}`, { method: 'DELETE' }),
  /** (Admin) List API keys for a specific user */
  listForUser: (userId: string) => req<ApiKey[]>(`/v1/users/${userId}/api-keys`),
  /** (Admin) Create an API key for a specific user */
  createForUser: (userId: string, name: string, expires_at?: string | null) =>
    req<ApiKeyCreated>(`/v1/users/${userId}/api-keys`, { method: 'POST', body: JSON.stringify({ name, expires_at: expires_at ?? null }) }),
  /** (Admin) Revoke an API key for a specific user */
  revokeForUser: (userId: string, keyId: string) => req<void>(`/v1/users/${userId}/api-keys/${keyId}`, { method: 'DELETE' }),
}


export const bannersApi = {
  list: () => req<Banner[]>('/v1/banners'),
  create: (data: Omit<Banner, 'id' | 'created_at' | 'updated_at'>) =>
    req<Banner>('/v1/banners', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Omit<Banner, 'id' | 'created_at' | 'updated_at'>>) =>
    req<Banner>(`/v1/banners/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id: string) => req<void>(`/v1/banners/${id}`, { method: 'DELETE' }),
  activeAdmin: () => req<Banner[]>('/v1/banners/active/admin'),
  activePortal: () => req<Banner[]>('/v1/banners/active/portal'),
}
