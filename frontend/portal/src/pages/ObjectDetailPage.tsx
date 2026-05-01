import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type MediaFile, type ObjectSummary } from '../api/client'

const TYPE_LABEL_MAP: Record<string, string> = {
  title: 'Titel', name: 'Name', creator: 'Urheber:in', photographer: 'Fotograf:in',
  year: 'Jahr', date: 'Datierung', medium: 'Material/Technik', technique: 'Technik',
  rights: 'Rechte', license: 'Lizenz', description: 'Beschreibung',
  keywords: 'Schlagwörter', location: 'Aufnahmeort', format: 'Format', dimensions: 'Maße',
}

function MetaRow({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val">{value}</span>
    </div>
  )
}

export function ObjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [obj, setObj] = useState<ObjectSummary | null>(null)
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.objects.get(id),
      api.objects.media(id).catch(() => [] as MediaFile[]),
    ])
      .then(([o, m]) => { setObj(o); setMediaFiles(m) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="container page" style={{ color: 'var(--fg-3)' }}>Lade…</div>
    )
  }

  if (error || !obj) {
    return (
      <div className="container page">
        <div style={{ color: '#dc2626' }}>{error ?? 'Objekt nicht gefunden.'}</div>
      </div>
    )
  }

  const m = obj.metadata_ as Record<string, unknown>
  const title = String(m.title ?? m.name ?? obj.idno ?? obj.id)

  const primaryMedia = mediaFiles.find(f => f.is_primary && f.status === 'ready')
    ?? mediaFiles.find(f => f.status === 'ready')

  const knownKeys = new Set(Object.keys(TYPE_LABEL_MAP))
  const extraMeta = Object.entries(m).filter(([k]) => !knownKeys.has(k))

  return (
    <div className="container page">
      <div className="bc">
        <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>Startseite</a>
        <span className="sep">/</span>
        <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=') }}>Suche</a>
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <h1 style={{ margin: '0 0 6px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em' }}>{title}</h1>
      <div style={{ color: 'var(--fg-3)', fontSize: 13, marginBottom: 28 }}>
        {[String(m.creator ?? m.photographer ?? ''), String(m.year ?? m.date ?? ''), obj.idno].filter(Boolean).join(' · ')}
      </div>

      <div className="detail-layout">
        <div>
          {primaryMedia ? (
            <img
              src={`/v1/objects/${obj.id}/media/${primaryMedia.id}/file`}
              alt={title}
              style={{ width: '100%', borderRadius: 10, display: 'block', background: '#0f172a' }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <div className="detail-viewer">Kein Bild verfügbar</div>
          )}

          {m.description != null && (
            <div style={{ marginTop: 20, fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>
              {String(m.description)}
            </div>
          )}

          {Array.isArray(m.keywords) && (m.keywords as string[]).length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(m.keywords as string[]).map((t, i) => <span key={i} className="tag">{t}</span>)}
            </div>
          )}
        </div>

        <aside className="detail-meta">
          {obj.idno && <MetaRow label="Inventar-Nr." value={obj.idno} />}
          {Object.entries(TYPE_LABEL_MAP).map(([k, label]) =>
            m[k] ? <MetaRow key={k} label={label} value={String(m[k])} /> : null
          )}
          {extraMeta.map(([k, v]) =>
            v && typeof v !== 'object' ? (
              <MetaRow key={k} label={k} value={String(v)} />
            ) : null
          )}
          <div style={{ marginTop: 16 }}>
            <a href={`/v1/objects/${obj.id}/iiif/manifest`} target="_blank" rel="noreferrer"
               style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              IIIF Manifest ↗
            </a>
          </div>
        </aside>
      </div>

      {mediaFiles.length > 1 && (
        <div style={{ marginTop: 32 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Weitere Medien</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {mediaFiles.map(f => (
              <div key={f.id} style={{
                width: 100, height: 100, borderRadius: 8, overflow: 'hidden',
                background: '#e4e6eb', border: f.is_primary ? '2px solid var(--accent)' : '1px solid var(--border)',
              }}>
                <img
                  src={`/v1/objects/${obj.id}/media/${f.id}/file`}
                  alt={f.filename}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={e => { (e.target as HTMLImageElement).style.opacity = '0' }}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
