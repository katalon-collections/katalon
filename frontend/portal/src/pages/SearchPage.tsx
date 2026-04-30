import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const RESULTS = [
  { id: 'OBJ-2026-00412', title: 'Bahnhofstraße bei Nacht', creator: 'Henri Cartier', year: '1958', medium: 'Silbergelatine', tags: ['Architektur', 'Nacht', 'Stadt'] },
  { id: 'OBJ-2026-00409', title: 'Markttag in der Altstadt', creator: 'G. Albrecht', year: '1965', medium: 'Silbergelatine', tags: ['Markt', 'Alltag', 'Stadt'] },
  { id: 'OBJ-2026-00406', title: 'Tramhaltestelle Paradeplatz', creator: 'Henri Cartier', year: '1960', medium: 'Silbergelatine', tags: ['Verkehr', 'Stadt'] },
]

const FACETS = [
  { label: 'Sammlung', values: [{ v: 'Stadtarchiv Zürich', n: 8 }, { v: 'Sammlung Maier', n: 3 }] },
  { label: 'Material', values: [{ v: 'Silbergelatine', n: 7 }, { v: 'Chromogen-Druck', n: 3 }, { v: 'Negativ, Glas', n: 2 }] },
  { label: 'Jahrzehnt', values: [{ v: '1950er', n: 2 }, { v: '1960er', n: 4 }, { v: '1970er', n: 3 }] },
]

export function SearchPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const [localQ, setLocalQ] = useState(q)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (localQ.trim()) navigate(`/search?q=${encodeURIComponent(localQ.trim())}`)
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
        {RESULTS.length} Treffer für „{q}"
      </div>

      <div className="search-layout">
        <aside className="facets">
          {FACETS.map(f => (
            <div key={f.label} style={{ marginBottom: 20 }}>
              <h3>{f.label}</h3>
              {f.values.map(v => (
                <div key={v.v} className="facet-item">
                  <span>{v.v}</span>
                  <span className="ct">{v.n}</span>
                </div>
              ))}
            </div>
          ))}
        </aside>

        <div className="result-list">
          {RESULTS.map(r => (
            <div key={r.id} className="result-row" onClick={() => navigate(`/objects/${r.id}`)}>
              <div className="thumb-sm" />
              <div className="body">
                <div className="title">{r.title}</div>
                <div className="desc">{r.creator} · {r.year} · {r.medium}</div>
                <div className="tags">
                  {r.tags.map(t => <span key={t} className="tag">{t}</span>)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="pagination">
        {[1, 2, 3].map(n => (
          <button key={n} className={`page-btn${n === 1 ? ' active' : ''}`}>{n}</button>
        ))}
      </div>
    </div>
  )
}
