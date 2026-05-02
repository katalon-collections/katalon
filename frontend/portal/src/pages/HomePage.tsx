import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type ObjectSummary, type PortalConfig } from '../api/client'

const DEFAULT_CONFIG: PortalConfig = {
  site_title: 'Sammlung',
  site_subtitle: '',
  hero_text: 'Fotografien, Dokumente, Objekte und Personen aus dem Archiv',
  featured_object_ids: [],
  accent_color: '#1e3a8a',
  logo_url: '',
}

export function HomePage() {
  const [q, setQ] = useState('')
  const [config, setConfig] = useState<PortalConfig>(DEFAULT_CONFIG)
  const [featured, setFeatured] = useState<ObjectSummary[]>([])
  const [recent, setRecent] = useState<ObjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.portal.config()
      .then(c => {
        setConfig(c)
        if (c.accent_color) {
          document.documentElement.style.setProperty('--accent', c.accent_color)
        }
        return c
      })
      .catch(() => DEFAULT_CONFIG)
      .then(async (c) => {
        const featuredIds = c.featured_object_ids ?? []
        const featuredItems: ObjectSummary[] = []
        await Promise.all(
          featuredIds.slice(0, 6).map(id =>
            api.objects.get(id).then(o => featuredItems.push(o)).catch(() => {})
          )
        )
        setFeatured(featuredItems)
        const d = await api.objects.list({ page_size: 12 }).catch(() => ({ items: [] as ObjectSummary[] }))
        setRecent(d.items.filter(o => !featuredIds.includes(o.id)))
        setLoading(false)
      })
  }, [])

  function search(e: React.FormEvent) {
    e.preventDefault()
    navigate(`/search?q=${encodeURIComponent(q.trim())}`)
  }

  function objTitle(obj: ObjectSummary) {
    const m = obj.metadata_ as Record<string, unknown>
    return String(m.title ?? m.name ?? obj.idno ?? obj.id)
  }
  function objSub(obj: ObjectSummary) {
    const m = obj.metadata_ as Record<string, unknown>
    return [String(m.creator ?? m.photographer ?? ''), String(m.year ?? m.date ?? '')].filter(Boolean).join(' · ')
  }

  return (
    <>
      <div className="hero">
        <div className="container">
          {config.logo_url && (
            <img src={config.logo_url} alt="Logo" style={{ maxHeight: 64, marginBottom: 16 }} />
          )}
          <h1>{config.site_title}</h1>
          {config.site_subtitle && <p style={{ fontSize: 18, opacity: 0.85 }}>{config.site_subtitle}</p>}
          {config.hero_text && <p>{config.hero_text}</p>}
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
        {featured.length > 0 && (
          <>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 0, color: 'var(--fg-2)' }}>
              Highlights
            </h2>
            <div className="obj-grid">
              {featured.map(obj => (
                <div key={obj.id} className="obj-card" onClick={() => navigate(`/objects/${obj.id}`)}>
                  <div className="thumb" />
                  <div className="info">
                    <div className="title">{objTitle(obj)}</div>
                    {objSub(obj) && <div className="meta">{objSub(obj)}</div>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 0, marginTop: featured.length > 0 ? 32 : 0, color: 'var(--fg-2)' }}>
          Neueste Zugänge
        </h2>

        {loading && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>Lade…</div>
        )}

        {!loading && recent.length === 0 && featured.length === 0 && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>
            Noch keine Objekte vorhanden.
          </div>
        )}

        {!loading && recent.length > 0 && (
          <div className="obj-grid">
            {recent.map(obj => (
              <div key={obj.id} className="obj-card" onClick={() => navigate(`/objects/${obj.id}`)}>
                <div className="thumb" />
                <div className="info">
                  <div className="title">{objTitle(obj)}</div>
                  {objSub(obj) && <div className="meta">{objSub(obj)}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
