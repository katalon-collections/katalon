import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type ObjectSummary } from '../api/client'

export function HomePage() {
  const [q, setQ] = useState('')
  const [recent, setRecent] = useState<ObjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.objects.list({ page_size: 12 })
      .then(d => setRecent(d.items))
      .catch(() => setRecent([]))
      .finally(() => setLoading(false))
  }, [])

  function search(e: React.FormEvent) {
    e.preventDefault()
    navigate(`/search?q=${encodeURIComponent(q.trim())}`)
  }

  return (
    <>
      <div className="hero">
        <div className="container">
          <h1>Sammlung durchsuchen</h1>
          <p>Fotografien, Dokumente, Objekte und Personen aus dem Archiv</p>
          <form className="hero-search" onSubmit={search}>
            <input
              placeholder="Suchbegriff eingeben…"
              value={q}
              onChange={e => setQ(e.target.value)}
              autoFocus
            />
            <button type="submit">Suchen</button>
          </form>
        </div>
      </div>

      <div className="container page">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 0, color: 'var(--fg-2)' }}>
          Neueste Zugänge
        </h2>

        {loading && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>Lade…</div>
        )}

        {!loading && recent.length === 0 && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>
            Noch keine Objekte vorhanden.
          </div>
        )}

        {!loading && recent.length > 0 && (
          <div className="obj-grid">
            {recent.map(obj => {
              const m = obj.metadata_ as Record<string, unknown>
              const title = String(m.title ?? m.name ?? obj.idno ?? obj.id)
              const creator = String(m.creator ?? m.photographer ?? '')
              const year = String(m.year ?? m.date ?? '')
              const sub = [creator, year].filter(Boolean).join(' · ')
              return (
                <div key={obj.id} className="obj-card" onClick={() => navigate(`/objects/${obj.id}`)}>
                  <div className="thumb" />
                  <div className="info">
                    <div className="title">{title}</div>
                    {sub && <div className="meta">{sub}</div>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
