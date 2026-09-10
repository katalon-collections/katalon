// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { recordTitle } from '../utils/renderFieldValue'

export const BASE = import.meta.env.VITE_API_URL ?? ''
export const PORTAL_API = '/portal/v1'
// Admin app's origin. Same-origin deployments (docker/nginx.conf) serve admin under
// `/admin/` alongside portal at `/`, so the fallback appends that path segment; deployments
// where admin lives on its own origin (dev Caddy subdomains, docker/nginx.prod.conf) override
// via VITE_ADMIN_URL, mirroring admin's own VITE_PORTAL_URL.
export const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? (typeof window !== 'undefined' ? `${window.location.origin}/admin` : '')
localStorage.removeItem('katalon_token')
localStorage.removeItem('katalon_refresh_token')
let token: string | null = null

export function mediaThumbnailUrl(objectId: string, mediaId: string): string {
  return `${BASE}${PORTAL_API}/objects/${objectId}/media/${mediaId}/thumbnail`
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const payload = await res.json().catch(() => null) as { detail?: string } | null
    if (payload?.detail) return payload.detail
  } catch {
    // ignore JSON parse error
  }
  return res.statusText || `${res.status} ${res.status === 404 ? 'Not Found' : 'Error'}`
}

async function get<T>(path: string): Promise<T> {
  const res = await portalFetch(path)
  if (!res.ok) throw new Error(await extractErrorMessage(res))
  return res.json()
}

async function portalFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (res.status !== 401 || !retry) return res

  const refresh = await fetch(`${BASE}/v1/auth/refresh`, {
    method: 'POST', credentials: 'include',
  })
  if (!refresh.ok) {
    setToken(null)
    return res
  }
  const pair = await refresh.json() as Token
  setToken(pair.access_token)
  return portalFetch(path, init, false)
}

export interface Token { access_token: string; token_type: string }
export interface PortalUser { email: string; role: string }

export function currentUser(): PortalUser | null {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1])) as PortalUser
    return payload.email && payload.role ? payload : null
  } catch {
    return null
  }
}

const ADMIN_EDIT_ROUTE: Record<string, string> = {
  object: 'form',
  entity: 'entities-form',
  place: 'places-form',
  occurrence: 'occurrences-form',
  collection: 'collections-form',
}

/** True if a signed-in staff user is allowed to edit records (any role above read-only viewer). */
export function canEdit(user: PortalUser | null): boolean {
  return !!user && user.role !== 'viewer'
}

/** URL of the admin app's edit screen for a given record type + id (admin uses hash-based routing). */
export function adminEditUrl(recordType: string, id: string): string {
  return `${ADMIN_URL}/#${ADMIN_EDIT_ROUTE[recordType] ?? 'form'}/${id}`
}

export function setToken(accessToken: string | null) {
  token = accessToken
}

export async function restoreSession(): Promise<PortalUser | null> {
  const response = await fetch(`${BASE}/v1/auth/refresh`, { method: 'POST', credentials: 'include' })
  if (!response.ok) return null
  const pair = await response.json() as Token
  setToken(pair.access_token)
  return currentUser()
}

export async function logout(): Promise<void> {
  setToken(null)
  await fetch(`${BASE}/v1/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {})
}

export async function login(email: string, password: string): Promise<Token> {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch(`${BASE}/v1/auth/token`, { method: 'POST', body, credentials: 'include' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Anmeldung fehlgeschlagen')
  }
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await portalFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res))
  }
  return res.json()
}

export interface ObjectSummary {
  id: string; idno: string | null; status: string; object_type?: string | null
  metadata_: Record<string, unknown>
  created_at: string; updated_at: string
}

export interface EntitySummary {
  id: string; entity_type: string; status: string
  metadata_: Record<string, unknown>
  created_at: string; updated_at: string
}

export interface PlaceSummary {
  id: string; status: string
  lat: number | null; lon: number | null
  metadata_: Record<string, unknown>
  created_at: string; updated_at: string
}

export interface OccurrenceSummary {
  id: string; occurrence_type: string; status: string
  metadata_: Record<string, unknown>
  created_at: string; updated_at: string
}

export interface CollectionHierarchyItem {
  id: string
  idno: string | null
  collection_type: string | null
  title: string | null
  parent_id: string | null
}

export interface CollectionSummary {
  id: string
  idno: string | null
  status: string
  collection_type: string | null
  parent_id: string | null
  metadata_: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface CollectionDetail extends CollectionSummary {
  parent: CollectionHierarchyItem | null
  ancestors: CollectionHierarchyItem[]
  children: CollectionHierarchyItem[]
  member_objects_count: number
}

export interface MediaFile {
  id: string; filename: string; mime_type: string; category: string
  status: string; is_primary: boolean; created_at: string
  license_uri?: string | null
  rights_holder?: { name: string; uri?: string } | null
}

export interface Relation {
  id: string
  from_type: string; from_id: string
  to_type: string; to_id: string
  relation_type: string
  from_label: string | null
  to_label: string | null
}

export interface StaticPageSummary {
  id: string
  slug: string
  title: Record<string, string>
  content: Record<string, string>
  is_published: boolean
  placement: 'header' | 'footer' | 'none'
  sort_order: number
}

export interface HomepageBlock {
  id: string
  type: 'text' | 'objects' | 'collections' | 'curated'
  enabled: boolean
  title: Record<string, string>
  content?: Record<string, string> | null
  limit?: number | null
  collections_mode?: 'selected' | 'top' | 'all' | null
  collection_ids?: string[] | null
}

export interface TerminologyEntry {
  singular: Record<string, string>
  plural: Record<string, string>
}

export interface PortalConfig {
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
  supported_languages: string[]
  detail_sidebar_position: 'left' | 'right'
  facet_sort: 'count' | 'alpha'
  facet_initial_count: number
  homepage_blocks: HomepageBlock[]
  terminology: Record<string, TerminologyEntry>
}

export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export interface FacetBucket { value: string; count: number }
export interface NumericFacetBounds { min: number; max: number }
export interface SearchResponse {
  total: number; page: number; page_size: number
  items: Array<{
    id: string; record_type: string; title: string; status: string | null; score: number | null
    subtitle_values?: Record<string, string | string[]> | null
    primary_media_id?: string | null
    media_width?: number | null
    media_height?: number | null
    object_type?: string | null
  }>
  facets: Record<string, FacetBucket[]>
  numeric_facets: Record<string, NumericFacetBounds>
}

export interface PortalFieldDefinition {
  name: string
  label: Record<string, string>
  field_type: string
  is_repeatable: boolean
  is_searchable: boolean
  is_facet: boolean
  parent_id: string | null
  settings: Record<string, unknown>
  show_in_detail: boolean
  detail_slot: 'main' | 'sidebar'
  detail_role: 'none' | 'description'
}

export interface VocabSummary { id: string; name: string; is_hierarchical: boolean }
export interface VocabTerm { id: string; term: string; label: Record<string, string>; inverse_label: Record<string, string>; parent_id: string | null }
export interface RecordSubtype { primary_type: string; name: string; label: Record<string, string>; placeholder_image_url: string }

const TYPE_ENDPOINT: Record<string, string> = {
  object: 'objects', entity: 'entities', place: 'places', occurrence: 'occurrences', collection: 'collections',
}

/** Fetch the display title of any record by type + id. Returns null on failure. */
export async function fetchRecordTitle(type: string, id: string): Promise<string | null> {
  const { title } = await fetchRecord(type, id)
  return title
}

/** Fetch title + full metadata of any record. Returns null title and empty metadata on failure. */
export async function fetchRecord(type: string, id: string): Promise<{ title: string | null; metadata: Record<string, unknown> }> {
  const endpoint = TYPE_ENDPOINT[type] ?? `${type}s`
  try {
    const res = await portalFetch(`${PORTAL_API}/${endpoint}/${id}`)
    if (!res.ok) return { title: null, metadata: {} }
    const rec = await res.json() as { metadata_?: Record<string, unknown>; idno?: string | null; id: string }
    const m = rec.metadata_ ?? {}
    const title = recordTitle(m, undefined, rec.idno ?? rec.id) || null
    return { title, metadata: m }
  } catch {
    return { title: null, metadata: {} }
  }
}

export const api = {
  objects: {
    list: (p?: { page?: number; q?: string; status?: string; page_size?: number }) => {
      const qs = new URLSearchParams(
        Object.entries({ page_size: '24', ...p })
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<Page<ObjectSummary>>(`${PORTAL_API}/objects?${qs}`)
    },
    get: (id: string) => get<ObjectSummary>(`${PORTAL_API}/objects/${id}`),
    media: (id: string) => get<MediaFile[]>(`${PORTAL_API}/objects/${id}/media`),
  },
  entities: {
    get: (id: string) => get<EntitySummary>(`${PORTAL_API}/entities/${id}`),
  },
  places: {
    get: (id: string) => get<PlaceSummary>(`${PORTAL_API}/places/${id}`),
  },
  occurrences: {
    get: (id: string) => get<OccurrenceSummary>(`${PORTAL_API}/occurrences/${id}`),
  },
  collections: {
    list: (p?: { page?: number; q?: string; status?: string; page_size?: number; parent_id?: string; top_level?: boolean }) => {
      const qs = new URLSearchParams(
        Object.entries({ page_size: '24', ...p })
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<Page<CollectionSummary>>(`${PORTAL_API}/collections?${qs}`)
    },
    get: (id: string) => get<CollectionDetail>(`${PORTAL_API}/collections/${id}`),
  },
  relations: {
    forRecord: (type: string, id: string, includeSubcollections: boolean = false) => {
      const sub = includeSubcollections ? '&include_subcollections=true' : ''
      return get<Relation[]>(`${PORTAL_API}/relations?from_type=${type}&from_id=${id}&limit=50${sub}`)
        .then(async fromRels => {
          const toRels = await get<Relation[]>(`${PORTAL_API}/relations?to_type=${type}&to_id=${id}&limit=50${sub}`)
          return [...fromRels, ...toRels]
        })
    },
  },
  portal: {
    config: () => get<PortalConfig>(`${PORTAL_API}/portal/config`),
    schema: (type: string) => get<PortalFieldDefinition[]>(`${PORTAL_API}/schema/${type}`),
    searchFieldTerms: (type: string, field: string) =>
      get<VocabTerm[]>(`${PORTAL_API}/schema/${type}/fields/${encodeURIComponent(field)}/terms`),
  },
  pages: {
    list: () => get<StaticPageSummary[]>(`${PORTAL_API}/pages`),
    get:  (slug: string) => get<StaticPageSummary>(`${PORTAL_API}/pages/${slug}`),
  },
  vocabularies: {
    list: () => get<VocabSummary[]>(`${PORTAL_API}/vocabularies`),
    terms: (id: string) => get<VocabTerm[]>(`${PORTAL_API}/vocabularies/${id}/terms`),
  },
  recordSubtypes: {
    list: (primaryType: string) => get<RecordSubtype[]>(`${PORTAL_API}/record-subtypes?primary_type=${encodeURIComponent(primaryType)}`),
  },
  search: {
    query: (p: { q?: string; type?: string; status?: string; page?: number; page_size?: number; facets?: string; rel_entity?: string; rel_place?: string; rel_occurrence?: string; rel_collection?: string; [key: string]: string | number | undefined }) => {
      const qs = new URLSearchParams(
        Object.entries(p)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<SearchResponse>(`${PORTAL_API}/search?${qs}`)
    },
    advanced: (body: unknown) => post<SearchResponse>(`${PORTAL_API}/search/advanced`, body),
  },
}

export interface BannerItem {
  id: string
  message: string
  color: 'blue' | 'yellow' | 'red' | 'green'
  expires_at: string | null
}

export const banners = {
  activePortal: () => get<BannerItem[]>(`${PORTAL_API}/banners/active/portal`),
}
