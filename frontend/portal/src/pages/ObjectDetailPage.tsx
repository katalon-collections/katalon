import { useNavigate, useParams } from 'react-router-dom'

const MOCK: Record<string, { title: string; creator: string; year: string; medium: string; rights: string; description: string; tags: string[] }> = {
  'OBJ-2026-00412': {
    title: 'Bahnhofstraße bei Nacht',
    creator: 'Henri Cartier',
    year: '1957–1959',
    medium: 'Silbergelatine',
    rights: 'CC BY 4.0',
    description: 'Nachtaufnahme der Zürcher Bahnhofstraße. Lichtreflexe auf dem nassen Pflaster, vereinzelte Passanten.',
    tags: ['Architektur', 'Nacht', 'Stadt', 'Zürich'],
  },
}

const FALLBACK = {
  title: 'Unbekanntes Objekt', creator: '—', year: '—', medium: '—',
  rights: '—', description: '', tags: [],
}

export function ObjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const obj = MOCK[id ?? ''] ?? FALLBACK

  return (
    <div className="container page">
      <div className="bc">
        <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>Startseite</a>
        <span className="sep">/</span>
        <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=') }}>Suche</a>
        <span className="sep">/</span>
        <span>{obj.title}</span>
      </div>

      <h1 style={{ margin: '0 0 6px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em' }}>{obj.title}</h1>
      <div style={{ color: 'var(--fg-3)', fontSize: 13, marginBottom: 28 }}>
        {obj.creator} · {obj.year} · {id}
      </div>

      <div className="detail-layout">
        <div>
          <div className="detail-viewer">IIIF-Viewer (Cantaloupe)</div>
          {obj.description && (
            <div style={{ marginTop: 20, fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>
              {obj.description}
            </div>
          )}
          {obj.tags.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {obj.tags.map(t => <span key={t} className="tag">{t}</span>)}
            </div>
          )}
        </div>

        <aside className="detail-meta">
          {[
            ['Inventar-Nr.', id],
            ['Urheber:in', obj.creator],
            ['Datierung', obj.year],
            ['Material/Technik', obj.medium],
            ['Rechte', obj.rights],
          ].map(([k, v]) => (
            <div key={k} className="meta-row">
              <span className="key">{k}</span>
              <span className="val">{v}</span>
            </div>
          ))}
          <div style={{ marginTop: 16 }}>
            <a href={`/v1/objects/${id}/iiif/manifest`} target="_blank" rel="noreferrer"
               style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              IIIF Manifest ↗
            </a>
          </div>
        </aside>
      </div>
    </div>
  )
}
