import { recordTitle } from '../utils/renderFieldValue'

export const BASE = import.meta.env.VITE_API_URL ?? ''
export const PORTAL_API = '/portal/v1'

export function mediaThumbnailUrl(objectId: string, mediaId: string): string {
  return `${BASE}${PORTAL_API}/objects/${objectId}/media/${mediaId}/thumbnail`
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const payload = await res.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? res.statusText)
  }
  return res.json()
}

export interface ObjectSummary {
  id: string; idno: string | null; status: string
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
}

export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export interface FacetBucket { value: string; count: number }
export interface NumericFacetBounds { min: number; max: number }
export interface SearchResponse {
  total: number; page: number; page_size: number
  items: Array<{
    id: string; record_type: string; title: string; status: string | null; score: number | null
    subtitle_values?: Record<string, string | string[]> | null
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
  parent_id: string | null
  settings: Record<string, unknown>
  show_in_detail: boolean
  detail_slot: 'main' | 'sidebar'
  detail_role: 'none' | 'description'
}

export interface VocabSummary { id: string; name: string; is_hierarchical: boolean }
export interface VocabTerm { id: string; term: string; label: Record<string, string>; inverse_label: Record<string, string>; parent_id: string | null }

const TYPE_ENDPOINT: Record<string, string> = {
  object: 'objects', entity: 'entities', place: 'places', occurrence: 'occurrences',
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
    const res = await fetch(`${BASE}${PORTAL_API}/${endpoint}/${id}`)
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
  relations: {
    forRecord: (type: string, id: string) =>
      get<Relation[]>(`${PORTAL_API}/relations?from_type=${type}&from_id=${id}&limit=50`)
        .then(async fromRels => {
          const toRels = await get<Relation[]>(`${PORTAL_API}/relations?to_type=${type}&to_id=${id}&limit=50`)
          return [...fromRels, ...toRels]
        }),
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
  search: {
    query: (p: { q?: string; type?: string; status?: string; page?: number; page_size?: number; facets?: string; rel_entity?: string; rel_place?: string; rel_occurrence?: string; [key: string]: string | number | undefined }) => {
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
