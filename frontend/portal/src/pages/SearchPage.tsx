import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, BASE, type FacetBucket, type SearchResponse, type MediaFile } from '../api/client'
import { saveLastSearch } from '../hooks/useBackToSearch'

const TYPE_LABELS: Record<string, string> = {
  object: 'Objekt', entity: 'Person/Org', place: 'Ort', occurrence: 'Werk/Ereignis',
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const typeFilt = params.get('type') ?? ''
  const statusFilt = params.get('status') ?? ''
  const page = parseInt(params.get('page') ?? '1', 10)
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [facetFields, setFacetFields] = useState<string[]>([])
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})

  // Load configurable facet fields from portal config
  useEffect(() => {
    api.portal.config()
      .then(c => setFacetFields(c.facet_fields ?? []))
      .catch(() => {})
  }, [])

  // Collect active meta_ filters from URL
  const metaFilters: Record<string, string> = {}
  params.forEach((value, key) => {
    if (key.startsWith('meta_')) metaFilters[key.slice(5)] = value
  })
  const relEntity = params.get('rel_entity') ?? ''
  const relPlace = params.get('rel_place') ?? ''
  const relOccurrence = params.get('rel_occurrence') ?? ''

  useEffect(() => {
    setLoading(true)
    const searchParams: Record<string, string | number | undefined> = {
      q: q || undefined,
      type: typeFilt || undefined,
      status: statusFilt || undefined,
      page,
      page_size: 20,
      facets: facetFields.length > 0 ? facetFields.join(',') : undefined,
      rel_entity: relEntity || undefined,
      rel_place: relPlace || undefined,
      rel_occurrence: relOccurrence || undefined,
    }
    // Pass meta_ filters as extra query params
    const qs = new URLSearchParams(
      Object.entries({ ...searchParams, ...Object.fromEntries(Object.entries(metaFilters).map(([k, v]) => [`meta_${k}`, v])) })
        .filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ).toString()
    fetch(`${import.meta.env.VITE_API_URL ?? ''}/v1/search?${qs}`)
      .then(r => r.json())
      .then(async (result: SearchResponse) => {
        setData(result)
        // Load thumbnails for object results
        const thumbMap: Record<string, string> = {}
        await Promise.all(
          result.items
            .filter(r => r.record_type === 'object')
            .map(r =>
              api.objects.media(r.id)
                .then(media => {
                  const ready = media.filter((m: MediaFile) => m.status === 'ready')
                  const primary = ready.find((m: MediaFile) => m.is_primary) ?? ready[0]
                  if (primary) {
                    thumbMap[r.id] = `${BASE}/v1/objects/${r.id}/media/${primary.id}/file`
                  }
                })
                .catch(() => {})
            )
        )
        setThumbnails(thumbMap)
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [q, typeFilt, statusFilt, page, facetFields.join(','), JSON.stringify(metaFilters), relEntity, relPlace, relOccurrence])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (localQ.trim()) navigate(`/search?q=${encodeURIComponent(localQ.trim())}`)
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.set('page', '1')
    setParams(next)
  }

  function setMetaFilter(field: string, value: string) {
    const key = `meta_${field}`
    setFilter(key, value)
  }

  function setRelFilter(paramKey: string, value: string) {
    setFilter(paramKey, value)
  }

  function setPage(n: number) {
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  const total = data?.total ?? 0
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1
  const typesFacet: FacetBucket[] = data?.facets?.['by_type'] ?? []
  const statusFacet: FacetBucket[] = data?.facets?.['by_status'] ?? []

  function FacetPanel({ label, buckets, active, onSelect }: {
    label: string
    buckets: FacetBucket[]
    active: string
    onSelect: (v: string) => void
  }) {
    if (!buckets.length) return null
    return (
      <div style={{ marginBottom: 20 }}>
        <h3>{label}</h3>
        <div
          className="facet-item"
          onClick={() => onSelect('')}
          style={{ cursor: 'pointer', fontWeight: !active ? 600 : undefined }}
        >
          <span>Alle</span>
        </div>
        {buckets.map(b => (
          <div
            key={b.value}
            className="facet-item"
            onClick={() => onSelect(b.value)}
            style={{ cursor: 'pointer', fontWeight: active === b.value ? 600 : undefined }}
          >
            <span>{TYPE_LABELS[b.value] ?? b.value}</span>
            <span className="ct">{b.count}</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="container page">
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          className="hero-search"
          style={{ flex: 1, background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 14px', fontSize: 14, outline: 'none', color: 'var(--fg)' }}
          value={localQ}
          onChange={e => setLocalQ(e.target.value)}
          placeholder="Suche verfeinern…"
        />
        <button type="submit" style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '0 18px', fontWeight: 600, fontSize: 13 }}>
          Suchen
        </button>
      </form>
      <div style={{ color: 'var(--fg-3)', fontSize: 13, marginBottom: 4 }}>
        {loading ? 'Suche…' : `${total} Treffer${q ? ` für „${q}"` : ''}`}
      </div>

      <div className="search-layout">
        <aside className="facets">
          <FacetPanel
            label="Typ"
            buckets={typesFacet}
            active={typeFilt}
            onSelect={v => setFilter('type', v)}
          />
          <FacetPanel
            label="Status"
            buckets={statusFacet}
            active={statusFilt}
            onSelect={v => setFilter('status', v)}
          />
          {facetFields.map(field => {
            const buckets = data?.facets?.[`meta_${field}`] ?? []
            return (
              <FacetPanel
                key={field}
                label={field}
                buckets={buckets}
                active={metaFilters[field] ?? ''}
                onSelect={v => setMetaFilter(field, v)}
              />
            )
          })}
          {(!typeFilt || typeFilt === 'object') && (
            <>
              <FacetPanel
                label="Personen/Org."
                buckets={data?.facets?.['related_entities'] ?? []}
                active={relEntity}
                onSelect={v => setRelFilter('rel_entity', v)}
              />
              <FacetPanel
                label="Orte"
                buckets={data?.facets?.['related_places'] ?? []}
                active={relPlace}
                onSelect={v => setRelFilter('rel_place', v)}
              />
              <FacetPanel
                label="Werke/Ereignisse"
                buckets={data?.facets?.['related_occurrences'] ?? []}
                active={relOccurrence}
                onSelect={v => setRelFilter('rel_occurrence', v)}
              />
            </>
          )}
        </aside>

        <div className="result-list">
          {loading && <div style={{ padding: 24, color: 'var(--fg-3)' }}>Lade…</div>}
          {!loading && data?.items.length === 0 && (
            <div style={{ padding: 24, color: 'var(--fg-3)' }}>Keine Ergebnisse.</div>
          )}
          {!loading && data?.items.map(r => {
            const path = r.record_type === 'entity' ? `/entities/${r.id}`
              : r.record_type === 'place' ? `/places/${r.id}`
              : r.record_type === 'occurrence' ? `/occurrences/${r.id}`
              : `/objects/${r.id}`
            return (
              <div key={r.id} className="result-row" onClick={() => { saveLastSearch(window.location.pathname + window.location.search); navigate(path) }}>
                <div className="thumb-sm">
                  {thumbnails[r.id] ? (
                    <img src={thumbnails[r.id]} alt="" loading="lazy" />
                  ) : null}
                </div>
                <div className="body">
                  <div className="title">{r.title || r.id}</div>
                  <div className="desc">
                    {TYPE_LABELS[r.record_type] ?? r.record_type} · {r.status ?? '—'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(n => (
            <button key={n} className={`page-btn${n === page ? ' active' : ''}`} onClick={() => setPage(n)}>{n}</button>
          ))}
        </div>
      )}
    </div>
  )
}
