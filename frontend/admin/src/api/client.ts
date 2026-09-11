// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { AdminSearchResponse, ApiKey, ApiKeyCreated, AuditEntry, Banner, BatchRequest, BatchResponse, Entity, ExportMappingRule, ExportMappingSet, ExportProfileCapabilities, FeaturePermission, FieldDefinition, FormSection, FormVariant, KatalonCollection, KatalonObject, KatalonStorageLocation, MappingDiagnostic, MappingPreviewResult, MetadataMapping, Occurrence, Page, Place, Procedure, RecordSubtype, Relation, RolePermission, SearchResponse, Snapshot, SourceKind, StorageLocationObject, Token, UserRead, Vocabulary, VocabularyImportResult, VocabularyTerm, VocabularyTermNode, WorkingSet, WorkingSetCreate, WorkingSetDetail, WorkingSetItem, WorkingSetItemCreate, WorkingSetItemUpdate, WorkingSetUpdate } from '../types'

export const BASE = import.meta.env.VITE_API_URL ?? ''
export const PORTAL_URL = import.meta.env.VITE_PORTAL_URL || (typeof window !== 'undefined' ? window.location.origin : '')

localStorage.removeItem('katalon_token')
localStorage.removeItem('katalon_refresh_token')
let _token: string | null = null
let _onUnauthorized: (() => void) | null = null
let _refreshPromise: Promise<string | null> | null = null

function resolveUrl(path: string) {
  return path.startsWith('http') ? path : `${BASE}${path}`
}

function buildHeaders(init?: HeadersInit): Record<string, string> {
  return { ...(init as Record<string, string> ?? {}) }
}

export function setToken(t: string | null) {
  _token = t
}

export function hasToken(): boolean {
  return Boolean(_token)
}

export function getTokenUser(): { email: string; role: string; features: string[] } | null {
  if (!_token) return null
  try {
    const payload = JSON.parse(atob(_token.split('.')[1]))
    return { email: payload.email ?? '', role: payload.role ?? '', features: payload.features ?? [] }
  } catch {
    return null
  }
}

export function onUnauthorized(cb: () => void) {
  _onUnauthorized = cb
}

async function refreshAccessToken(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = (async () => {
    const res = await fetch(resolveUrl('/v1/auth/refresh'), {
      method: 'POST',
      credentials: 'include',
    })
    if (res.status === 401) {
      setToken(null)
      _onUnauthorized?.()
      return null
    }
    if (!res.ok) throw new Error('Sitzung konnte nicht erneuert werden.')
    const token = await res.json() as Token
    setToken(token.access_token)
    return token.access_token
  })().finally(() => {
    _refreshPromise = null
  })
  return _refreshPromise
}

export async function authorizedFetch(path: string, init: RequestInit = {}, allowRefresh = true): Promise<Response> {
  const headers = buildHeaders(init.headers)
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(resolveUrl(path), { ...init, headers, credentials: 'include' })
  if (res.status !== 401 || !allowRefresh || path === '/v1/auth/refresh') return res

  const refreshedToken = await refreshAccessToken()
  if (!refreshedToken) return res

  const retryHeaders = buildHeaders(init.headers)
  retryHeaders['Authorization'] = `Bearer ${refreshedToken}`
  return fetch(resolveUrl(path), { ...init, headers: retryHeaders, credentials: 'include' })
}

export function restoreSession(): Promise<string | null> {
  return refreshAccessToken()
}

export async function logout(): Promise<void> {
  setToken(null)
  await fetch(resolveUrl('/v1/auth/logout'), { method: 'POST', credentials: 'include' }).catch(() => {})
}

export class ConflictError extends Error {
  related_count: number
  constructor(message: string, related_count: number) {
    super(message)
    this.name = 'ConflictError'
    this.related_count = related_count
  }
}

/** Optimistic-locking conflict: the record was changed by someone else since load. */
export class VersionConflictError extends Error {
  current_version: number
  constructor(current_version: number) {
    super('Datensatz wurde zwischenzeitlich von jemand anderem geändert.')
    this.name = 'VersionConflictError'
    this.current_version = current_version
  }
}

/** Blocking-mode presence lock: another user is currently editing this record. */
export class PresenceLockedError extends Error {
  locked_by: string
  constructor(locked_by: string) {
    super(`Wird aktuell von ${locked_by} bearbeitet.`)
    this.name = 'PresenceLockedError'
    this.locked_by = locked_by
  }
}

/** Manual exclusive lock: another user has explicitly locked this record. */
export class ResourceLockedError extends Error {
  locked_by: string
  reason: string
  constructor(locked_by: string, reason: string) {
    super(`Datensatz ist durch ${locked_by} exklusiv gesperrt.`)
    this.name = 'ResourceLockedError'
    this.locked_by = locked_by
    this.reason = reason
  }
}

function ifMatch(version?: number): Record<string, string> | undefined {
  return version != null ? { 'If-Match': String(version) } : undefined
}

export async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string> ?? {}) }
  const res = await authorizedFetch(path, { ...init, headers })
  if (res.status === 401) {
    setToken(null)
    _onUnauthorized?.()
    throw new Error('Sitzung abgelaufen. Bitte neu anmelden.')
  }
  if (res.status === 409) {
    const body = await res.json().catch(() => ({ detail: {} }))
    const d = body.detail ?? {}
    if (d.error === 'version_conflict') {
      throw new VersionConflictError(typeof d.current_version === 'number' ? d.current_version : 0)
    }
    if (d.error === 'presence_locked') {
      throw new PresenceLockedError(typeof d.locked_by === 'string' ? d.locked_by : 'unbekannt')
    }
    if (d.error === 'resource_locked') {
      throw new ResourceLockedError(typeof d.locked_by === 'string' ? d.locked_by : 'unbekannt', typeof d.reason === 'string' ? d.reason : '')
    }
    throw new ConflictError(
      typeof d === 'string' ? d : typeof d.detail === 'string' ? d.detail : 'Datensatz ist mit anderen Datensätzen verknüpft.',
      typeof d.related_count === 'number' ? d.related_count : 0,
    )
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : (err.detail ? JSON.stringify(err.detail) : res.statusText)
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Auth
export const auth = {
  login: async (email: string, password: string): Promise<Token> => {
    const body = new URLSearchParams({ username: email, password })
    const res = await fetch(`${BASE}/v1/auth/token`, {
      method: 'POST',
      body: body.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      credentials: 'include',
    })
    if (res.status === 401) throw new Error('Falsche E-Mail oder Passwort.')
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : res.statusText)
    }
    return res.json()
  },
  requestPasswordReset: (email: string) =>
    req<{ detail: string }>('/v1/auth/password-reset', { method: 'POST', body: JSON.stringify({ email }) }),
  confirmPasswordReset: (token: string, new_password: string) =>
    req<void>('/v1/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ token, new_password }) }),
}

export const users = {
  me: () => req<UserRead>('/v1/users/me'),
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
  setOwnOnboarding: (completed: boolean) =>
    req<UserRead>('/v1/users/me/onboarding', { method: 'PUT', body: JSON.stringify({ completed }) }),
  permissions: () => req<RolePermission[]>('/v1/users/permissions'),
  updatePermissions: (role: RolePermission['role'], permissions: RolePermission[]) =>
    req<RolePermission[]>(`/v1/users/permissions/${role}`, { method: 'PUT', body: JSON.stringify({ permissions }) }),
  features: () => req<FeaturePermission[]>('/v1/users/features'),
  updateFeatures: (role: FeaturePermission['role'], features: FeaturePermission[]) =>
    req<FeaturePermission[]>(`/v1/users/features/${role}`, { method: 'PUT', body: JSON.stringify({ features }) }),
}

// Objects
export const objects = {
  list: (params?: { page?: number; page_size?: number; status?: string; object_type?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<KatalonObject>>(`/v1/objects${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<KatalonObject>(`/v1/objects/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/objects/${id}/audit-log`),
  create: (data: Partial<KatalonObject>) => req<KatalonObject>('/v1/objects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<KatalonObject>, version?: number) => req<KatalonObject>(`/v1/objects/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/objects/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  publish: (id: string) => req<{ ok: boolean; errors?: string[] }>(`/v1/objects/${id}/publish`, { method: 'POST' }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/object', { method: 'POST', body: JSON.stringify(data) }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/objects/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/objects/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string, version?: number) => req<KatalonObject>(`/v1/objects/${id}/snapshots/${snapId}/restore`, { method: 'POST', headers: ifMatch(version) }),
  },
}

// Entities
export const entities = {
  list: (params?: { page?: number; page_size?: number; status?: string; entity_type?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Entity>>(`/v1/entities${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Entity>(`/v1/entities/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/entities/${id}/audit-log`),
  create: (data: Partial<Entity>) => req<Entity>('/v1/entities', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Entity>, version?: number) => req<Entity>(`/v1/entities/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/entities/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  publish: (id: string) => req<{ ok: boolean; errors?: string[] }>(`/v1/entities/${id}/publish`, { method: 'POST' }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/entity', { method: 'POST', body: JSON.stringify(data) }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/entities/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/entities/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string, version?: number) => req<Entity>(`/v1/entities/${id}/snapshots/${snapId}/restore`, { method: 'POST', headers: ifMatch(version) }),
  },
}

// Places
export const places = {
  list: (params?: { page?: number; page_size?: number; status?: string; place_type?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Place>>(`/v1/places${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Place>(`/v1/places/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/places/${id}/audit-log`),
  create: (data: Partial<Place>) => req<Place>('/v1/places', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Place>, version?: number) => req<Place>(`/v1/places/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/places/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  publish: (id: string) => req<{ ok: boolean; errors?: string[] }>(`/v1/places/${id}/publish`, { method: 'POST' }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/place', { method: 'POST', body: JSON.stringify(data) }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/places/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/places/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string, version?: number) => req<Place>(`/v1/places/${id}/snapshots/${snapId}/restore`, { method: 'POST', headers: ifMatch(version) }),
  },
}

// Occurrences
export const occurrences = {
  list: (params?: { page?: number; page_size?: number; status?: string; occurrence_type?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Occurrence>>(`/v1/occurrences${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Occurrence>(`/v1/occurrences/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/occurrences/${id}/audit-log`),
  create: (data: Partial<Occurrence>) => req<Occurrence>('/v1/occurrences', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Occurrence>, version?: number) => req<Occurrence>(`/v1/occurrences/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/occurrences/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  publish: (id: string) => req<{ ok: boolean; errors?: string[] }>(`/v1/occurrences/${id}/publish`, { method: 'POST' }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/occurrence', { method: 'POST', body: JSON.stringify(data) }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/occurrences/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/occurrences/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string, version?: number) => req<Occurrence>(`/v1/occurrences/${id}/snapshots/${snapId}/restore`, { method: 'POST', headers: ifMatch(version) }),
  },
}

// Procedures
export const procedures = {
  list: (params?: { page?: number; page_size?: number; status?: string; procedure_type?: string; due_before?: string; reference_number?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Procedure>>(`/v1/procedures${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Procedure>(`/v1/procedures/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/procedures/${id}/audit-log`),
  create: (data: Partial<Procedure>) => req<Procedure>('/v1/procedures', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Procedure>, version?: number) => req<Procedure>(`/v1/procedures/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/procedures/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  complete: (id: string, collection_status?: string | null) =>
    req<Procedure>(`/v1/procedures/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({ collection_status: collection_status ?? null }),
    }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/procedure', { method: 'POST', body: JSON.stringify(data) }),
}

// Collections
export const collections = {
  list: (params?: { page?: number; page_size?: number; status?: string; collection_type?: string; parent_id?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<KatalonCollection>>(`/v1/collections${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<KatalonCollection>(`/v1/collections/${id}`),
  audit:  (id: string) => req<AuditEntry[]>(`/v1/collections/${id}/audit-log`),
  create: (data: Partial<KatalonCollection>) => req<KatalonCollection>('/v1/collections', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<KatalonCollection>, version?: number) => req<KatalonCollection>(`/v1/collections/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/collections/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  publish: (id: string) => req<{ ok: boolean; errors?: string[] }>(`/v1/collections/${id}/publish`, { method: 'POST' }),
  batch: (data: BatchRequest) => req<BatchResponse>('/v1/batch/collection', { method: 'POST', body: JSON.stringify(data) }),
  snapshots: {
    list:    (id: string) => req<Snapshot[]>(`/v1/collections/${id}/snapshots`),
    create:  (id: string, label: string) => req<Snapshot>(`/v1/collections/${id}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
    restore: (id: string, snapId: string, version?: number) => req<KatalonCollection>(`/v1/collections/${id}/snapshots/${snapId}/restore`, { method: 'POST', headers: ifMatch(version) }),
  },
}

// Storage Locations
export const storageLocations = {
  list: (params?: { page?: number; page_size?: number; storage_location_type?: string; parent_id?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<KatalonStorageLocation>>(`/v1/storage-locations${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<KatalonStorageLocation>(`/v1/storage-locations/${id}`),
  audit:  (id: string) => audit.list({ record_type: 'storage_location', record_id: id }),
  create: (data: Partial<KatalonStorageLocation>) => req<KatalonStorageLocation>('/v1/storage-locations', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<KatalonStorageLocation>, version?: number) => req<KatalonStorageLocation>(`/v1/storage-locations/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: ifMatch(version) }),
  delete: (id: string, force?: boolean) => req<void>(`/v1/storage-locations/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
  objects: (id: string, params?: { include_sublocations?: boolean; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<StorageLocationObject>>(`/v1/storage-locations/${id}/objects${qs ? `?${qs}` : ''}`)
  },
}

export interface SchemaImportResult {
  created: number
  updated: number
  skipped: number
  errors: string[]
  fields: FieldDefinition[]
}

export interface SchemaAiChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SchemaAiVocabularyProposal {
  tmp_id: string
  name: string
  kind: 'term' | 'relation'
  is_hierarchical: boolean
  terms: { term: string; label: Record<string, string> }[]
}

export interface SchemaAiFieldProposal {
  name: string
  label: Record<string, string>
  field_type: FieldDefinition['field_type']
  is_required: boolean
  is_repeatable: boolean
  is_translatable: boolean
  settings: Record<string, unknown>
  children?: SchemaAiFieldProposal[]
}

export interface SchemaAiProposal {
  vocabularies: SchemaAiVocabularyProposal[]
  fields: SchemaAiFieldProposal[]
}

export interface SchemaAiAssistResult {
  reply: string
  proposal: SchemaAiProposal | null
  usage: { input_tokens: number; output_tokens: number }
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
  duplicate: (id: string) => req<FieldDefinition>(`/v1/schema/${id}/duplicate`, { method: 'POST' }),
  resetSummary: (targetType: string, subtype?: string) => req<{ deletable_fields: number }>(`/v1/schema/${targetType}/reset-summary${subtype ? `?subtype=${encodeURIComponent(subtype)}` : ''}`),
  reset: (targetType: string, subtype?: string) => req<{ deletable_fields: number, deleted_fields: number }>(`/v1/schema/${targetType}/reset${subtype ? `?subtype=${encodeURIComponent(subtype)}` : ''}`, { method: 'POST' }),
  import: async (file: File, opts: { dryRun?: boolean; overwrite?: boolean } = {}): Promise<SchemaImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const qs = new URLSearchParams()
    if (opts.dryRun) qs.set('dry_run', 'true')
    if (opts.overwrite) qs.set('overwrite', 'true')
    const res = await authorizedFetch(`/v1/schema/import${qs.toString() ? `?${qs}` : ''}`, { method: 'POST', body: formData })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen. Bitte neu anmelden.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  aiAssist: (targetType: string, targetSubtype: string | null, messages: SchemaAiChatMessage[]) =>
    req<SchemaAiAssistResult>('/v1/schema/ai-assist', {
      method: 'POST',
      body: JSON.stringify({ target_type: targetType, target_subtype: targetSubtype, messages }),
    }),
}

export interface MetadataFormatInfo {
  key: string
  label: string
  targets: string[]
  capabilities?: ExportProfileCapabilities | null
}

export const exportProfiles = {
  list: () => req<ExportProfileCapabilities[]>('/v1/export-profiles'),
  get: (formatKey: string, profileId: string) =>
    req<ExportProfileCapabilities>(`/v1/export-profiles/${encodeURIComponent(formatKey)}/${encodeURIComponent(profileId)}`),
}

export const exportMappingSets = {
  list: (params?: { record_type?: string; format_key?: string; status?: string }) => {
    const qs = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v).map(([k, v]) => [k, String(v)])
    ).toString()
    return req<ExportMappingSet[]>(`/v1/export-mapping-sets${qs ? `?${qs}` : ''}`)
  },
  get: (id: string) => req<ExportMappingSet>(`/v1/export-mapping-sets/${encodeURIComponent(id)}`),
  create: (data: {
    format_key: string
    profile_id: string
    profile_version?: string
    record_type: string
    target_subtype?: string | null
    name: string
    based_on_id?: string | null
    institution_config?: Record<string, unknown>
  }) =>
    req<ExportMappingSet>('/v1/export-mapping-sets', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: { name?: string; institution_config?: Record<string, unknown> }, version?: number) =>
    req<ExportMappingSet>(`/v1/export-mapping-sets/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: version !== undefined ? { 'If-Match': String(version) } : undefined,
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    req<void>(`/v1/export-mapping-sets/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  createRule: (setId: string, data: {
    rule_key?: string
    source_kind?: SourceKind
    field_definition_id?: string | null
    source_config?: Record<string, unknown>
    target_key: string
    settings?: Record<string, unknown>
    sort_order?: number
    is_enabled?: boolean
  }) =>
    req<ExportMappingRule>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/rules`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateRule: (setId: string, ruleId: string, data: Partial<{
    source_kind: SourceKind
    field_definition_id: string | null
    source_config: Record<string, unknown>
    target_key: string
    settings: Record<string, unknown>
    sort_order: number
    is_enabled: boolean
  }>) =>
    req<ExportMappingRule>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/rules/${encodeURIComponent(ruleId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteRule: (setId: string, ruleId: string) =>
    req<void>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/rules/${encodeURIComponent(ruleId)}`, { method: 'DELETE' }),
  validate: (setId: string) =>
    req<MappingDiagnostic[]>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/validate`, { method: 'POST' }),
  preview: (setId: string, recordId: string) =>
    req<MappingPreviewResult>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/preview`, {
      method: 'POST',
      body: JSON.stringify({ record_id: recordId }),
    }),
  publish: (setId: string, version?: number) =>
    req<ExportMappingSet>(`/v1/export-mapping-sets/${encodeURIComponent(setId)}/publish`, {
      method: 'POST',
      headers: version !== undefined ? { 'If-Match': String(version) } : undefined,
    }),
}

export const metadataMappings = {
  list: (params?: { format_key?: string; field_definition_id?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v).map(([k, v]) => [k, String(v)])).toString()
    return req<MetadataMapping[]>(`/v1/metadata-mappings${qs ? `?${qs}` : ''}`)
  },
  listFormats: () => req<MetadataFormatInfo[]>('/v1/metadata-mappings/formats'),
  setFieldFormat: (fieldId: string, formatKey: string, data: { target_path: string | null; settings?: Record<string, unknown>; sort_order?: number; is_enabled?: boolean }) =>
    req<MetadataMapping | null>(`/v1/metadata-mappings/field/${fieldId}/${encodeURIComponent(formatKey)}`, {
      method: 'PUT',
      body: JSON.stringify({
        target_path: data.target_path,
        settings: data.settings ?? {},
        sort_order: data.sort_order ?? 0,
        is_enabled: data.is_enabled ?? true,
      }),
    }),
}

export interface ExportFormatInfo {
  key: string
  label: string
  kind: 'flat' | 'xml'
}

export const exportApi = {
  listFormats: (recordType: string) => req<ExportFormatInfo[]>(`/v1/export/formats?record_type=${encodeURIComponent(recordType)}`),
  download: async (recordType: string, format: string, subtype?: string): Promise<void> => {
    const qs = new URLSearchParams({ format, ...(subtype ? { subtype } : {}) }).toString()
    const res = await authorizedFetch(`/v1/export/${recordType}?${qs}`)
    if (!res.ok) throw new Error(`Export fehlgeschlagen (${res.status}).`)
    const blob = await res.blob()
    const ext = format === 'csv' ? 'csv' : format === 'json' ? 'json' : `${format}.xml`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${recordType}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  },
}

export const preservationApi = {
  downloadBag: async (objectId: string): Promise<void> => {
    const res = await authorizedFetch(`/v1/preservation/objects/${encodeURIComponent(objectId)}/bag`)
    if (!res.ok) throw new Error(`Preservation-Export fehlgeschlagen (${res.status}).`)
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const match = /filename="([^"]+)"/.exec(disposition)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = match?.[1] ?? 'preservation-package.zip'
    a.click()
    URL.revokeObjectURL(url)
  },
}

// Vocabularies
export const vocabularies = {
  list:       () => req<Vocabulary[]>('/v1/vocabularies'),
  create:     (data: Omit<Vocabulary, 'id'>) => req<Vocabulary>('/v1/vocabularies', { method: 'POST', body: JSON.stringify(data) }),
  listTerms:  (vocabId: string, filter?: { from_type?: string; to_type?: string }) => {
    const params = new URLSearchParams()
    if (filter?.from_type) params.set('from_type', filter.from_type)
    if (filter?.to_type) params.set('to_type', filter.to_type)
    const qs = params.toString()
    return req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms${qs ? `?${qs}` : ''}`)
  },
  searchTerms: (vocabId: string, q: string) => req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms?q=${encodeURIComponent(q)}`),
  ancestors: (vocabId: string, termId: string) => req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms/${termId}/ancestors`),
  tree:       (vocabId: string) => req<VocabularyTermNode[]>(`/v1/vocabularies/${vocabId}/tree`),
  createTerm: (vocabId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/${vocabId}/terms`, { method: 'POST', body: JSON.stringify(data) }),
  updateTerm: (termId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/terms/${termId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTerm: (termId: string) => req<void>(`/v1/vocabularies/terms/${termId}`, { method: 'DELETE' }),
  duplicateTerm: (termId: string) => req<VocabularyTerm>(`/v1/vocabularies/terms/${termId}/duplicate`, { method: 'POST' }),
  importTerms: async (
    vocabId: string,
    file: File,
    opts: { dryRun?: boolean; strategy?: 'append' | 'replace'; mapping?: Record<string, string> } = {},
  ): Promise<VocabularyImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    if (opts.mapping) {
      formData.append('mapping', JSON.stringify(opts.mapping))
    }
    const qs = new URLSearchParams()
    qs.set('dry_run', String(opts.dryRun ?? true))
    qs.set('strategy', opts.strategy ?? 'append')
    const res = await authorizedFetch(`/v1/vocabularies/${vocabId}/import?${qs}`, { method: 'POST', body: formData })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen. Bitte neu anmelden.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  importSkos: async (
    vocabId: string,
    file: File,
    opts: {
      dryRun?: boolean
      strategy?: 'append' | 'replace'
      conceptScheme?: string
      topConcept?: string
      maxDepth?: number
      maxTerms?: number
      format?: string
    } = {},
  ): Promise<VocabularyImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    if (opts.conceptScheme) formData.append('concept_scheme', opts.conceptScheme)
    if (opts.topConcept) formData.append('top_concept', opts.topConcept)
    if (opts.maxDepth !== undefined && opts.maxDepth !== null) formData.append('max_depth', String(opts.maxDepth))
    if (opts.maxTerms !== undefined && opts.maxTerms !== null) formData.append('max_terms', String(opts.maxTerms))
    if (opts.format) formData.append('format', opts.format)

    const qs = new URLSearchParams()
    qs.set('dry_run', String(opts.dryRun ?? true))
    qs.set('strategy', opts.strategy ?? 'append')

    const res = await authorizedFetch(`/v1/vocabularies/${vocabId}/import-skos?${qs}`, { method: 'POST', body: formData })
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
  category: string
  status: string
  is_primary: boolean
  is_public: boolean
  media_type: string | null
  license_uri: string | null
  rights_holder: { name: string; uri?: string } | null
  created_at: string
  _links?: { thumbnail?: { href: string } }
}

export interface MediaBatchStatus {
  state: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | string
  result?: {
    batch_id: string
    total_files: number
    planned: number
    created: number
    skipped: number
    failed: number
    report: {
      missing_files: { row: number | null; filename: string }[]
      duplicate_files: { row: number | null; filename: string; count?: number }[]
      unmatched_files: { filename: string }[]
      errors: { row: number | null; message: string }[]
    }
  }
  meta?: { total: number; processed: number; created: number; skipped: number; failed: number }
  error?: string
}

type FolderFile = File & { webkitRelativePath?: string }

function fileFormName(file: FolderFile): string {
  return file.webkitRelativePath || file.name
}

function uploadWithProgress<T>(path: string, formData: FormData, onProgress?: (fraction: number) => void): Promise<T> {
  const { promise, resolve, reject } = Promise.withResolvers<T>()
  const xhr = new XMLHttpRequest()
  xhr.open('POST', resolveUrl(path))
  if (_token) xhr.setRequestHeader('Authorization', `Bearer ${_token}`)
  xhr.withCredentials = true
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) onProgress?.(e.loaded / e.total)
  }
  xhr.onerror = () => reject(new Error('Netzwerkfehler beim Hochladen.'))
  xhr.onload = () => {
    if (xhr.status === 401) {
      setToken(null)
      _onUnauthorized?.()
      reject(new Error('Sitzung abgelaufen. Bitte neu anmelden.'))
      return
    }
    if (xhr.status < 200 || xhr.status >= 300) {
      let detail: unknown
      try { detail = JSON.parse(xhr.responseText).detail } catch { /* not JSON */ }
      reject(new Error(typeof detail === 'string' ? detail : xhr.statusText || 'Upload fehlgeschlagen.'))
      return
    }
    onProgress?.(1)
    resolve(xhr.responseText ? JSON.parse(xhr.responseText) : (undefined as T))
  }
  xhr.send(formData)
  return promise
}

export const media = {
  list: (objectId: string) => req<MediaFile[]>(`/v1/objects/${objectId}/media`),
  upload: (objectId: string, file: File, onProgress?: (fraction: number) => void): Promise<MediaFile> => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadWithProgress<MediaFile>(`/v1/objects/${objectId}/media`, formData, onProgress)
  },
  patch: (objectId: string, mediaId: string, data: { media_type?: string | null; is_primary?: boolean; is_public?: boolean; license_uri?: string | null; rights_holder?: { name: string; uri?: string } | null }) =>
    req<MediaFile>(`/v1/objects/${objectId}/media/${mediaId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (objectId: string, mediaId: string) => req<void>(`/v1/objects/${objectId}/media/${mediaId}`, { method: 'DELETE' }),
  batchImport: async (archive: File | null, mapping: File | null, files: File[]): Promise<{ status: string; task_id: string; batch_id: string }> => {
    const formData = new FormData()
    if (archive) formData.append('archive', archive)
    if (mapping) formData.append('mapping', mapping)
    for (const file of files) formData.append('files', file, fileFormName(file as FolderFile))
    const res = await authorizedFetch('/v1/media/batch-import', { method: 'POST', body: formData })
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
  update: (id: string, data: { relation_type?: string; metadata_?: Record<string, unknown> }) =>
    req<Relation>(`/v1/relations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/relations/${id}`, { method: 'DELETE' }),
}

// Search
export const search = {
  query: (q: string, type?: string, pageSize = 8) => {
    const params: Record<string, string> = { q, page_size: String(pageSize) }
    if (type) params.type = type
    return req<SearchResponse>(`/v1/search?${new URLSearchParams(params)}`)
  },
  admin: (q: string) => req<AdminSearchResponse>(`/v1/search/admin?q=${encodeURIComponent(q)}`),
}

// Authority
export interface AuthorityHit {
  source: string; external_id: string; label: string; description: string; extra: Record<string, unknown>
}
export interface AuthoritySource {
  id: string; label: string; is_enabled: boolean
}
export const authority = {
  list: () => req<AuthoritySource[]>('/v1/authorities/'),
  search: (source: string, q: string, limit = 10) =>
    req<AuthorityHit[]>(`/v1/authorities/search?source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}&limit=${limit}`),
  fetch: (source: string, id: string) =>
    req<AuthorityHit>(`/v1/authorities/fetch?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}`),
  setEnabled: (id: string, is_enabled: boolean) =>
    req<AuthoritySource>(`/v1/authorities/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ is_enabled }) }),
}

export type PidMintResult = {
  pid: string
  resolver_url: string
  provider: 'dnb_urn' | 'ark'
  value: { value: string; label: string }
}

export const pids = {
  mint: (data: {
    record_type: string
    record_id: string
    field_name: string
    target_url?: string
    label?: string
  }) => req<PidMintResult>(
    '/v1/pids/mint',
    { method: 'POST', body: JSON.stringify(data) },
  ),
}

// Record Subtypes
export const subtypes = {
  list: (primaryType?: string) => {
    const qs = primaryType ? `?primary_type=${encodeURIComponent(primaryType)}` : ''
    return req<RecordSubtype[]>(`/v1/record-subtypes${qs}`)
  },
  create: (data: { primary_type: string; name: string; label: Record<string, string>; description?: string; sort_order?: number; is_default?: boolean }) =>
    req<RecordSubtype>('/v1/record-subtypes', { method: 'POST', body: JSON.stringify({ description: '', sort_order: 0, is_default: false, ...data }) }),
  update: (id: string, data: { primary_type: string; name: string; label: Record<string, string>; description?: string; sort_order?: number; is_default?: boolean }) =>
    req<RecordSubtype>(`/v1/record-subtypes/${id}`, { method: 'PUT', body: JSON.stringify({ description: '', sort_order: 0, is_default: false, ...data }) }),
  delete: (id: string) => req<void>(`/v1/record-subtypes/${id}`, { method: 'DELETE' }),
}

export type FormVariantData = { target_type: string; target_subtype?: string | null; name: string; label?: Record<string, string>; field_names?: string[]; is_default_global?: boolean; sort_order?: number }

export const formVariants = {
  list: (targetType: string, subtype?: string) => {
    const qs = new URLSearchParams({ target_type: targetType, ...(subtype ? { subtype } : {}) })
    return req<FormVariant[]>(`/v1/form-variants?${qs}`)
  },
  create: (data: FormVariantData) => req<FormVariant>('/v1/form-variants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: FormVariantData) => req<FormVariant>(`/v1/form-variants/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/form-variants/${id}`, { method: 'DELETE' }),
  setRoleDefault: (id: string, role: string) => req<void>(`/v1/form-variants/${id}/role-defaults/${role}`, { method: 'POST' }),
  removeRoleDefault: (id: string, role: string) => req<void>(`/v1/form-variants/${id}/role-defaults/${role}`, { method: 'DELETE' }),
}

export type FormSectionData = { target_type: string; target_subtype?: string | null; label?: Record<string, string>; field_names?: string[]; sort_order?: number }

export const formSections = {
  list: (targetType: string, subtype?: string) => {
    const qs = new URLSearchParams({ target_type: targetType, ...(subtype ? { subtype } : {}) })
    return req<FormSection[]>(`/v1/form-sections?${qs}`)
  },
  create: (data: FormSectionData) => req<FormSection>('/v1/form-sections', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: FormSectionData) => req<FormSection>(`/v1/form-sections/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/form-sections/${id}`, { method: 'DELETE' }),
}

// Audit
export const audit = {
  list: (params?: { record_type?: string; record_id?: string; action?: string; limit?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<AuditEntry[]>(`/v1/audit${qs ? `?${qs}` : ''}`)
  },
  search: (params?: { q?: string; record_type?: string; record_id?: string; user_id?: string; action?: string; created_from?: string; created_to?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])).toString()
    return req<Page<AuditEntry>>(`/v1/audit/search${qs ? `?${qs}` : ''}`)
  },
}

// Static Pages
export interface StaticPage {
  id: string
  slug: string
  title: Record<string, string>
  content: Record<string, string>
  is_published: boolean
  placement: 'header' | 'footer' | 'none'
  sort_order: number
}

export const staticPages = {
  list:   () => req<StaticPage[]>('/v1/pages/admin'),
  create: (data: { slug: string; title: Record<string, string>; content: Record<string, string>; is_published: boolean; placement: 'header' | 'footer' | 'none'; sort_order: number }) =>
    req<StaticPage>('/v1/pages', { method: 'POST', body: JSON.stringify(data) }),
  update: (slug: string, data: Partial<{ title: Record<string, string>; content: Record<string, string>; is_published: boolean; placement: 'header' | 'footer' | 'none'; sort_order: number }>) =>
    req<StaticPage>(`/v1/pages/${slug}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (slug: string) => req<void>(`/v1/pages/${slug}`, { method: 'DELETE' }),
}

// Importer
export interface UploadResult {
  source_type?: 'csv' | 'excel' | 'xml'
  upload_id: string
  headers: string[]
  row_count: number
  preview: Record<string, string>[]
  suggestions: Record<string, string>
}

export interface XmlElementTag {
  clark_tag: string
  label: string
}

export interface XmlElementLevel {
  depth: number
  tags: XmlElementTag[]
}

export interface XmlSelector {
  path: string
  label: string
  sample: string
  kind: string
}

export interface XmlUploadResult {
  source_type: 'xml'
  upload_id: string
  element_levels: XmlElementLevel[]
}

export interface XmlSelectorsResult {
  source_type: 'xml'
  upload_id: string
  headers: string[]
  selectors: XmlSelector[]
  row_count: number
  preview: Record<string, string>[]
  suggestions: Record<string, string>
}

export interface DryRunResult {
  total: number
  valid: number
  errors: { row: number | null; message: string }[]
  warnings: { row: number | null; message: string }[]
  preview: Record<string, unknown>[]
  media_references?: {
    selector_found: boolean
    objects: number
    files: number
    empty: number
    conflicts: { filename: string; rows: number[] }[]
  } | null
  vocab_warnings?: { field: string; label: string; unique_count: number; new_count: number; high_cardinality: boolean }[]
  vocab_clusters?: {
    field: string
    label: string
    clusters: { canonical: string; variants: string[]; counts: Record<string, number> }[]
  }[]
}

export interface TaskStatus {
  state: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | string
  result?: { created: number; updated: number; skipped: number; published: number; publish_failed: number; publish_fail_reasons?: string[]; media_references_created?: number; errors: { row: number; error: string }[] }
  error?: string
  meta?: { current: number; total: number; stage: string }
}

export interface CreatedField {
  id: string
  name: string
  field_type: string
  label: Record<string, string>
}

export interface TransformConfig {
  type: 'split' | 'replace' | 'regex_extract' | 'trim' | 'vocab_map' | 'expression' | 'combine'
  // split
  delimiter?: string
  filter_empty?: boolean
  // replace
  search?: string
  replace?: string
  case_sensitive?: boolean
  // regex_extract
  pattern?: string
  group?: number
  // trim
  trim?: boolean
  // vocab_map
  vocab_map?: Record<string, string>
  strict?: boolean
  // expression
  expression?: string
  // combine
  sources?: string[]
  separator?: string
  template?: string
}

export interface MappingEntry {
  target: string
  transforms?: TransformConfig[]
}

export interface ImportMapping {
  id: string
  name: string
  record_type: string
  subtype: string | null
  media_selector: string | null
  mapping: Record<string, MappingEntry>
  created_by: string | null
  created_at: string
  updated_at: string
}

export const importer = {
  upload: async (files: File | File[]): Promise<UploadResult> => {
    const formData = new FormData()
    for (const f of Array.isArray(files) ? files : [files]) formData.append('file', f)
    const res = await authorizedFetch('/v1/importer/upload', { method: 'POST', body: formData })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  dryRun: (recordType: string, uploadId: string, mapping: Record<string, MappingEntry>, subtype?: string | null, fieldsToCreate?: { name: string; field_type: string; label_de?: string; label_en?: string; is_repeatable?: boolean }[], mediaSelector?: string | null, mappingId?: string | null): Promise<DryRunResult> =>
    req<DryRunResult>('/v1/importer/dry-run', { method: 'POST', body: JSON.stringify({ record_type: recordType, upload_id: uploadId, mapping, subtype: subtype ?? null, fields_to_create: fieldsToCreate ?? [], media_selector: mediaSelector ?? null, mapping_id: mappingId ?? null }) }),
  import: (recordType: string, uploadId: string, mapping: Record<string, MappingEntry>, opts?: { idno_strategy?: string; upsert_strategy?: string; auto_publish?: boolean; subtype?: string | null; fields_to_create?: { name: string; field_type: string; label_de?: string; label_en?: string; is_repeatable?: boolean }[]; media_selector?: string | null; mapping_id?: string | null }): Promise<{ task_id: string; status: string }> =>
    req('/v1/importer/import', { method: 'POST', body: JSON.stringify({ record_type: recordType, upload_id: uploadId, mapping, idno_strategy: opts?.idno_strategy ?? 'auto', upsert_strategy: opts?.upsert_strategy ?? 'skip', auto_publish: opts?.auto_publish ?? false, subtype: opts?.subtype ?? null, fields_to_create: opts?.fields_to_create ?? [], media_selector: opts?.media_selector ?? null, mapping_id: opts?.mapping_id ?? null }) }),
  taskStatus: (taskId: string): Promise<TaskStatus> =>
    req<TaskStatus>(`/v1/importer/task/${taskId}`),
  cancelTask: (taskId: string): Promise<{ cancelled: boolean }> =>
    req(`/v1/importer/task/${taskId}/cancel`, { method: 'POST' }),
  createFields: (recordType: string, fields: { name: string; field_type: string; label_de?: string; label_en?: string; is_repeatable?: boolean }[]): Promise<{ created: number; fields: CreatedField[]; restored?: string[] }> =>
    req('/v1/importer/create-fields', { method: 'POST', body: JSON.stringify({ record_type: recordType, fields }) }),
  xmlUpload: async (file: File): Promise<XmlUploadResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await authorizedFetch('/v1/importer/upload', { method: 'POST', body: formData })
    if (res.status === 401) { setToken(null); _onUnauthorized?.(); throw new Error('Sitzung abgelaufen.') }
    if (!res.ok) { const err = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(err.detail ?? res.statusText) }
    return res.json()
  },
  xmlSelectors: (uploadId: string, recordXpath: string): Promise<XmlSelectorsResult> =>
    req<XmlSelectorsResult>('/v1/importer/xml-selectors', { method: 'POST', body: JSON.stringify({ upload_id: uploadId, record_xpath: recordXpath }) }),
  listMappings: (recordType?: string): Promise<ImportMapping[]> =>
    req<ImportMapping[]>(`/v1/importer/mappings${recordType ? `?record_type=${encodeURIComponent(recordType)}` : ''}`),
  getMapping: (id: string): Promise<ImportMapping> =>
    req<ImportMapping>(`/v1/importer/mappings/${id}`),
  createMapping: (data: { name: string; record_type: string; subtype?: string | null; media_selector?: string | null; mapping: Record<string, MappingEntry> }): Promise<ImportMapping> =>
    req<ImportMapping>('/v1/importer/mappings', { method: 'POST', body: JSON.stringify(data) }),
  updateMapping: (id: string, data: { name?: string; subtype?: string | null; media_selector?: string | null; mapping?: Record<string, MappingEntry> }): Promise<ImportMapping> =>
    req<ImportMapping>(`/v1/importer/mappings/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteMapping: (id: string): Promise<void> =>
    req(`/v1/importer/mappings/${id}`, { method: 'DELETE' }),
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

export interface AdminConfigRead {
  idno_schemas: Record<string, string>
  idno_patterns: Record<string, string>
  reconciliation_enabled: boolean
  reconciliation_threshold: number
  reconciliation_id_diff_enabled: boolean
  supported_languages: string[]
  ai_enabled: boolean
  ai_base_url: string | null
  ai_model: string | null
  ai_max_input_tokens: number
  ai_max_output_tokens: number
  ai_daily_user_token_limit: number
  ai_monthly_global_token_limit: number
  media_default_license_uri: string | null
  media_default_rights_holder: { name: string; uri?: string } | null
  presence_lock_mode: 'warning' | 'blocking'
  pid_providers: ('ark' | 'dnb_urn')[]
  ai_secret: {
    has_key: boolean
    updated_at: string | null
  }
  ai_usage: {
    daily_user_tokens: number
    monthly_global_tokens: number
  }
}

export const adminConfig = {
  get: () => req<AdminConfigRead>('/v1/admin/config'),
  changelog: () => req<{ content: string }>('/v1/admin/config/changelog'),
  update: (data: Partial<AdminConfigRead>) =>
    req<AdminConfigRead>('/v1/admin/config', { method: 'PUT', body: JSON.stringify(data) }),
  setAiSecret: (api_key: string) =>
    req<AdminConfigRead['ai_secret']>('/v1/admin/config/ai-secret', { method: 'PUT', body: JSON.stringify({ api_key }) }),
  deleteAiSecret: () => req<AdminConfigRead['ai_secret']>('/v1/admin/config/ai-secret', { method: 'DELETE' }),
  checkAi: () => req<{ ok: boolean; message: string }>('/v1/admin/config/ai-check', { method: 'POST' }),
}

export const idno = {
  next: (type: string) => req<{ next: string | null }>(`/v1/idno/next?type=${encodeURIComponent(type)}`),
}

export interface ActivePresence {
  user_id: string
  user_email: string
  since: string
}

/** Random per-tab id so two tabs of the same user each get their own presence row. */
export function presenceSessionId(): string {
  const key = 'katalon_presence_session'
  let id = sessionStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem(key, id)
  }
  return id
}

export const presence = {
  heartbeat: (resourceType: string, resourceId: string) =>
    req<ActivePresence[]>(`/v1/presence/${resourceType}/${resourceId}/heartbeat`, {
      method: 'POST',
      body: JSON.stringify({ session_id: presenceSessionId() }),
    }),
  release: (resourceType: string, resourceId: string) =>
    req<void>(`/v1/presence/${resourceType}/${resourceId}?session_id=${encodeURIComponent(presenceSessionId())}`, {
      method: 'DELETE',
    }),
  list: (resourceType: string, resourceId: string) =>
    req<ActivePresence[]>(`/v1/presence/${resourceType}/${resourceId}`),
  batch: (resourceType: string, resourceIds: string[]) =>
    req<Record<string, ActivePresence[]>>('/v1/presence/batch', {
      method: 'POST',
      body: JSON.stringify({ resource_type: resourceType, resource_ids: resourceIds }),
    }),
}

export interface LockInfo {
  resource_type: string
  resource_id: string
  locked_by: string
  locked_by_email: string
  locked_at: string
  expires_at: string | null
  reason: string
}

export const locks = {
  get: (resourceType: string, resourceId: string) =>
    req<LockInfo | null>(`/v1/locks/${resourceType}/${resourceId}`),
  set: (resourceType: string, resourceId: string, reason?: string, expires_at?: string) =>
    req<LockInfo>('/v1/locks', {
      method: 'POST',
      body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId, reason: reason ?? '', expires_at }),
    }),
  release: (resourceType: string, resourceId: string) =>
    req<void>(`/v1/locks/${resourceType}/${resourceId}`, { method: 'DELETE' }),
  forceUnlock: (resourceType: string, resourceId: string) =>
    req<void>(`/v1/locks/${resourceType}/${resourceId}/force-unlock`, { method: 'POST' }),
  batch: (resourceType: string, resourceIds: string[]) =>
    req<Record<string, LockInfo>>('/v1/locks/batch', {
      method: 'POST',
      body: JSON.stringify({ resource_type: resourceType, resource_ids: resourceIds }),
    }),
}

export interface AICompleteResponse {
  field_name: string
  value: unknown
  confidence: number | null
  warning: string | null
  usage: {
    input_tokens: number
    output_tokens: number
  }
}

export const ai = {
  complete: (data: { field_definition_id: string; record_type: string; record_id: string; group_index?: number; group_instance?: Record<string, unknown> }) =>
    req<AICompleteResponse>('/v1/ai/complete', { method: 'POST', body: JSON.stringify(data) }),
}

export interface SparqlStatus {
  enabled: boolean
  reachable: boolean
  triples_count: number | null
  endpoint_url: string
  require_auth: boolean
  query_timeout: number
}

export interface SavedSparqlQuery {
  id: string
  title: string
  description: string | null
  query: string
  tags: string[]
  is_shared: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface SavedSparqlQueryPayload {
  title: string
  description?: string | null
  query: string
  tags?: string[]
  is_shared?: boolean
}

export interface SparqlQueryResultBinding {
  type: 'uri' | 'literal' | 'bnode'
  value: string
  datatype?: string
  'xml:lang'?: string
}

export interface SparqlQueryResults {
  head: {
    vars: string[]
  }
  results: {
    bindings: Record<string, SparqlQueryResultBinding>[]
  }
  boolean?: boolean
}

export interface NL2SparqlResponse {
  sparql: string
  explanation?: string | null
}

export const sparql = {
  status: () => req<SparqlStatus>('/v1/sparql/status'),
  rebuild: () => req<{ status: string }>('/v1/sparql/rebuild', { method: 'POST' }),
  query: (sparqlQuery: string, accept: string = 'application/sparql-results+json') =>
    req<SparqlQueryResults>('/sparql', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/sparql-query',
        'Accept': accept,
      },
      body: sparqlQuery,
    }),
  queryRaw: async (sparqlQuery: string, accept: string): Promise<string> => {
    const res = await authorizedFetch('/sparql', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/sparql-query',
        'Accept': accept,
      },
      body: sparqlQuery,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : res.statusText)
    }
    return res.text()
  },
  listQueries: (params?: { tag?: string; q?: string }) => {
    const sp = new URLSearchParams()
    if (params?.tag) sp.set('tag', params.tag)
    if (params?.q) sp.set('q', params.q)
    const qs = sp.toString() ? `?${sp.toString()}` : ''
    return req<SavedSparqlQuery[]>(`/v1/sparql/queries${qs}`)
  },
  getQuery: (id: string) => req<SavedSparqlQuery>(`/v1/sparql/queries/${id}`),
  createQuery: (payload: SavedSparqlQueryPayload) =>
    req<SavedSparqlQuery>('/v1/sparql/queries', { method: 'POST', body: JSON.stringify(payload) }),
  updateQuery: (id: string, payload: Partial<SavedSparqlQueryPayload>) =>
    req<SavedSparqlQuery>(`/v1/sparql/queries/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteQuery: (id: string) =>
    req<void>(`/v1/sparql/queries/${id}`, { method: 'DELETE' }),
  nl2sparql: (prompt: string) =>
    req<NL2SparqlResponse>('/v1/sparql/nl2sparql', { method: 'POST', body: JSON.stringify({ prompt }) }),
}

export const workingSets = {
  list: (params?: { record_type?: string; record_id?: string }) => {
    const sp = new URLSearchParams()
    if (params?.record_type) sp.set('record_type', params.record_type)
    if (params?.record_id) sp.set('record_id', params.record_id)
    const qs = sp.toString() ? `?${sp.toString()}` : ''
    return req<WorkingSet[]>(`/v1/working-sets${qs}`)
  },
  get: (id: string) => req<WorkingSetDetail>(`/v1/working-sets/${id}`),
  create: (data: WorkingSetCreate) =>
    req<WorkingSet>('/v1/working-sets', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: WorkingSetUpdate) =>
    req<WorkingSet>(`/v1/working-sets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    req<void>(`/v1/working-sets/${id}`, { method: 'DELETE' }),
  addItems: (id: string, payload: { items?: WorkingSetItemCreate[]; record_ids?: string[] } | WorkingSetItemCreate[]) => {
    const body = Array.isArray(payload) ? { items: payload } : payload
    return req<WorkingSetItem[]>(`/v1/working-sets/${id}/items`, { method: 'POST', body: JSON.stringify(body) })
  },
  updateItem: (setId: string, itemId: string, data: WorkingSetItemUpdate) =>
    req<WorkingSetItem>(`/v1/working-sets/${setId}/items/${itemId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteItem: (setId: string, itemId: string) =>
    req<void>(`/v1/working-sets/${setId}/items/${itemId}`, { method: 'DELETE' }),
  reorder: (setId: string, itemIds: string[]) =>
    req<void>(`/v1/working-sets/${setId}/reorder`, { method: 'PUT', body: JSON.stringify({ item_ids: itemIds }) }),
}
