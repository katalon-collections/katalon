const BASE = import.meta.env.VITE_API_URL ?? ''

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

export interface MediaFile {
  id: string; filename: string; mime_type: string
  status: string; is_primary: boolean; created_at: string
}

export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export interface FacetBucket { value: string; count: number }
export interface SearchResponse {
  total: number; page: number; page_size: number
  items: Array<{ id: string; record_type: string; title: string; status: string | null; score: number | null }>
  facets: Record<string, FacetBucket[]>
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
  search: {
    query: (p: { q?: string; type?: string; status?: string; page?: number; page_size?: number }) => {
      const qs = new URLSearchParams(
        Object.entries(p)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<SearchResponse>(`/v1/search?${qs}`)
    },
  },
}
