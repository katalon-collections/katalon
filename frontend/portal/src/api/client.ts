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

export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export const api = {
  objects: {
    list: (p?: { page?: number; q?: string; status?: string }) => {
      const qs = new URLSearchParams(
        Object.entries({ status: 'public', page_size: '24', ...p })
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
      return get<Page<ObjectSummary>>(`/v1/objects?${qs}`)
    },
    get: (id: string) => get<ObjectSummary>(`/v1/objects/${id}`),
  },
}
