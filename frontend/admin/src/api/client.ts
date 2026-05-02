import type { AuditEntry, Entity, FieldDefinition, KatalonObject, Occurrence, Page, Place, Relation, SearchResponse, Token, Vocabulary, VocabularyTerm } from '../types'

export const BASE = import.meta.env.VITE_API_URL ?? ''

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

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string> ?? {}) }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
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

// Objects
export const objects = {
  list: (params?: { page?: number; page_size?: number; status?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<KatalonObject>>(`/v1/objects${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<KatalonObject>(`/v1/objects/${id}`),
  create: (data: Partial<KatalonObject>) => req<KatalonObject>('/v1/objects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<KatalonObject>) => req<KatalonObject>(`/v1/objects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/objects/${id}`, { method: 'DELETE' }),
}

// Entities
export const entities = {
  list: (params?: { page?: number; page_size?: number; status?: string; entity_type?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Entity>>(`/v1/entities${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Entity>(`/v1/entities/${id}`),
  create: (data: Partial<Entity>) => req<Entity>('/v1/entities', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Entity>) => req<Entity>(`/v1/entities/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/entities/${id}`, { method: 'DELETE' }),
}

// Places
export const places = {
  list: (params?: { page?: number; page_size?: number; status?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Place>>(`/v1/places${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Place>(`/v1/places/${id}`),
  create: (data: Partial<Place>) => req<Place>('/v1/places', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Place>) => req<Place>(`/v1/places/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/places/${id}`, { method: 'DELETE' }),
}

// Occurrences
export const occurrences = {
  list: (params?: { page?: number; page_size?: number; status?: string; occurrence_type?: string }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<Page<Occurrence>>(`/v1/occurrences${qs ? `?${qs}` : ''}`)
  },
  get:    (id: string) => req<Occurrence>(`/v1/occurrences/${id}`),
  create: (data: Partial<Occurrence>) => req<Occurrence>('/v1/occurrences', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Occurrence>) => req<Occurrence>(`/v1/occurrences/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => req<void>(`/v1/occurrences/${id}`, { method: 'DELETE' }),
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
}

// Vocabularies
export const vocabularies = {
  list:       () => req<Vocabulary[]>('/v1/vocabularies'),
  create:     (data: Omit<Vocabulary, 'id'>) => req<Vocabulary>('/v1/vocabularies', { method: 'POST', body: JSON.stringify(data) }),
  listTerms:  (vocabId: string) => req<VocabularyTerm[]>(`/v1/vocabularies/${vocabId}/terms`),
  createTerm: (vocabId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/${vocabId}/terms`, { method: 'POST', body: JSON.stringify(data) }),
  updateTerm: (termId: string, data: Omit<VocabularyTerm, 'id'>) => req<VocabularyTerm>(`/v1/vocabularies/terms/${termId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTerm: (termId: string) => req<void>(`/v1/vocabularies/terms/${termId}`, { method: 'DELETE' }),
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

// Audit
export const audit = {
  list: (params?: { record_type?: string; action?: string; limit?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<AuditEntry[]>(`/v1/audit${qs ? `?${qs}` : ''}`)
  },
}
