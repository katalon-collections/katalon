import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type FacetBucket, type SearchResponse } from '../api/client'

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const typeFilt = params.get('type') ?? ''
  const page = parseInt(params.get('page') ?? '1', 10)
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.search
      .query({ q: q || undefined, type: typeFilt || undefined, page, page_size: 20 })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [q, typeFilt, page])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (localQ.trim()) navigate(`/search?q=${encodeURIComponent(localQ.trim())}`)
  }

  function setType(t: string) {
    const next = new URLSearchParams(params)
    if (t) next.set('type', t)
    else next.delete('type')
    next.set('page', '1')
    setParams(next)
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
          {typesFacet.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h3>Typ</h3>
              <div className="facet-item" onClick={() => setType('')} style={{ cursor: 'pointer', fontWeight: !typeFilt ? 600 : undefined }}>
                <span>Alle</span>
              </div>
              {typesFacet.map(b => (
                <div key={b.value} className="facet-item" onClick={() => setType(b.value)} style={{ cursor: 'pointer', fontWeight: typeFilt === b.value ? 600 : undefined }}>
                  <span>{b.value}</span>
                  <span className="ct">{b.count}</span>
                </div>
              ))}
            </div>
          )}
          {statusFacet.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h3>Status</h3>
              {statusFacet.map(b => (
                <div key={b.value} className="facet-item">
                  <span>{b.value}</span>
                  <span className="ct">{b.count}</span>
                </div>
              ))}
            </div>
          )}
        </aside>

        <div className="result-list">
          {loading && <div style={{ padding: 24, color: 'var(--fg-3)' }}>Lade…</div>}
          {!loading && data?.items.length === 0 && (
            <div style={{ padding: 24, color: 'var(--fg-3)' }}>Keine Ergebnisse.</div>
          )}
          {!loading && data?.items.map(r => (
            <div key={r.id} className="result-row" onClick={() => navigate(`/objects/${r.id}`)}>
              <div className="thumb-sm" />
              <div className="body">
                <div className="title">{r.title || r.id}</div>
                <div className="desc">{r.record_type} · {r.status ?? '—'}</div>
              </div>
            </div>
          ))}
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
