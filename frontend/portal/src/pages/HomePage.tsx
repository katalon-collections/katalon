import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const SAMPLE = [
  { id: 'OBJ-2026-00412', title: 'Bahnhofstraße bei Nacht', creator: 'Henri Cartier', year: '1958' },
  { id: 'OBJ-2026-00409', title: 'Markttag in der Altstadt', creator: 'G. Albrecht', year: '1965' },
  { id: 'OBJ-2026-00408', title: 'Kinder am See', creator: 'G. Albrecht', year: '1962' },
  { id: 'OBJ-2026-00406', title: 'Tramhaltestelle Paradeplatz', creator: 'Henri Cartier', year: '1960' },
  { id: 'OBJ-2026-00403', title: 'Bauarbeiter Limmatquai', creator: 'Hans Brunner', year: '1950' },
  { id: 'OBJ-2026-00401', title: 'Gartenfest auf dem Dach', creator: 'Lina Maier', year: '1971' },
]

export function HomePage() {
  const [q, setQ] = useState('')
  const navigate = useNavigate()

  function search(e: React.FormEvent) {
    e.preventDefault()
    if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`)
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
        <div className="obj-grid">
          {SAMPLE.map(obj => (
            <div key={obj.id} className="obj-card" onClick={() => navigate(`/objects/${obj.id}`)}>
              <div className="thumb">📷</div>
              <div className="info">
                <div className="title">{obj.title}</div>
                <div className="meta">{obj.creator} · {obj.year}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
