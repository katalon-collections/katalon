import type { AuditEntry, FieldDefinition, KatalonObject, Page, SearchResponse, Token, Vocabulary, VocabularyTerm } from '../types'

const BASE = import.meta.env.VITE_API_URL ?? ''

let _token: string | null = localStorage.getItem('katalon_token')

export function setToken(t: string | null) {
  _token = t
  t ? localStorage.setItem('katalon_token', t) : localStorage.removeItem('katalon_token')
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string> ?? {}) }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
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

// Schema
export const schema = {
  list:   (targetType: string) => req<FieldDefinition[]>(`/v1/schema/${targetType}`),
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

// Search
export const search = {
  query: (q: string, pageSize = 8) => {
    const qs = new URLSearchParams({ q, page_size: String(pageSize) }).toString()
    return req<SearchResponse>(`/v1/search?${qs}`)
  },
}

// Audit
export const audit = {
  list: (params?: { record_type?: string; action?: string; limit?: number }) => {
    const qs = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
    return req<AuditEntry[]>(`/v1/audit${qs ? `?${qs}` : ''}`)
  },
}
