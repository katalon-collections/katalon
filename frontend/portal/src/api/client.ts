export const BASE = import.meta.env.VITE_API_URL ?? ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(res.statusText)
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
  id: string; filename: string; mime_type: string
  status: string; is_primary: boolean; created_at: string
}

export interface Relation {
  id: string
  from_type: string; from_id: string
  to_type: string; to_id: string
  relation_type: string
  metadata_: Record<string, unknown>
  created_at: string
}

export interface StaticPageSummary {
  id: string
  slug: string
  title: Record<string, string>
  content: Record<string, string>
  is_published: boolean
  sort_order: number
}

export interface PortalConfig {
  site_title: string
  site_subtitle: string
  hero_text: string
  featured_object_ids: string[]
  facet_fields: string[]
  accent_color: string
  logo_url: string
  placeholder_image_url: string
  color_tokens: Record<string, string>
}

export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export interface FacetBucket { value: string; count: number }
export interface SearchResponse {
  total: number; page: number; page_size: number
  items: Array<{ id: string; record_type: string; title: string; status: string | null; score: number | null }>
  facets: Record<string, FacetBucket[]>
}

export interface VocabSummary { id: string; name: string; is_hierarchical: boolean }
export interface VocabTerm { id: string; term: string; label: Record<string, string>; parent_id: string | null }

const TYPE_ENDPOINT: Record<string, string> = {
  object: 'objects', entity: 'entities', place: 'places', occurrence: 'occurrences',
}

/** Fetch the display title of any record by type + id. Returns null on failure. */
export async function fetchRecordTitle(type: string, id: string): Promise<string | null> {
  const endpoint = TYPE_ENDPOINT[type] ?? `${type}s`
  try {
    const res = await fetch(`${BASE}/v1/${endpoint}/${id}`)
    if (!res.ok) return null
    const rec = await res.json() as { metadata_?: Record<string, unknown>; idno?: string | null; id: string }
    const m = rec.metadata_ ?? {}
    const raw = m.name ?? m.title ?? m.label ?? m.display_name ?? m.place_name ?? rec.idno ?? rec.id
    if (typeof raw === 'string') return raw || null
    return String(raw) || null
  } catch {
    return null
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
      return get<Page<ObjectSummary>>(`/v1/objects?${qs}`)
    },
    get: (id: string) => get<ObjectSummary>(`/v1/objects/${id}`),
    media: (id: string) => get<MediaFile[]>(`/v1/objects/${id}/media`),
  },
  entities: {
    get: (id: string) => get<EntitySummary>(`/v1/entities/${id}`),
  },
  places: {
    get: (id: string) => get<PlaceSummary>(`/v1/places/${id}`),
  },
  occurrences: {
    get: (id: string) => get<OccurrenceSummary>(`/v1/occurrences/${id}`),
  },
  relations: {
    forRecord: (type: string, id: string) =>
      get<Relation[]>(`/v1/relations?from_type=${type}&from_id=${id}&limit=50`)
        .then(async fromRels => {
          const toRels = await get<Relation[]>(`/v1/relations?to_type=${type}&to_id=${id}&limit=50`)
          return [...fromRels, ...toRels]
        }),
  },
  portal: {
    config: () => get<PortalConfig>('/v1/portal/config'),
  },
  pages: {
    list: () => get<StaticPageSummary[]>('/v1/pages'),
    get:  (slug: string) => get<StaticPageSummary>(`/v1/pages/${slug}`),
  },
  vocabularies: {
    list: () => get<VocabSummary[]>('/v1/vocabularies'),
    terms: (id: string) => get<VocabTerm[]>(`/v1/vocabularies/${id}/terms`),
  },
  search: {
    query: (p: { q?: string; type?: string; status?: string; page?: number; page_size?: number; facets?: string; rel_entity?: string; rel_place?: string; rel_occurrence?: string; [key: string]: string | number | undefined }) => {
      const qs = new URLSearchParams(
        Object.entries(p)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<SearchResponse>(`/v1/search?${qs}`)
    },
  },
}

export interface BannerItem {
  id: string
  message: string
  color: 'blue' | 'yellow' | 'red' | 'green'
  expires_at: string | null
}

export const banners = {
  activePortal: () => get<BannerItem[]>('/v1/banners/active/portal'),
}
