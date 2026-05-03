import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, BASE, type MediaFile, type ObjectSummary } from '../api/client'
import { useFieldLabels } from '../hooks/useFieldLabels'
import { IIIFViewer } from '../components/IIIFViewer'



function MetaRow({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val">{value}</span>
    </div>
  )
}

function ViewerFallback({ objectId, media }: { objectId: string; media: MediaFile }) {
  return (
    <img
      src={`${BASE}/v1/objects/${objectId}/media/${media.id}/file`}
      alt=""
      style={{ width: '100%', borderRadius: 10, display: 'block', background: '#0f172a' }}
      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
    />
  )
}

export function ObjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [obj, setObj] = useState<ObjectSummary | null>(null)
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Hook must be called BEFORE any conditional returns
  const fieldLabels = useFieldLabels('object')

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
    return <div className="container page" style={{ color: 'var(--fg-3)' }}>Lade…</div>
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

  const readyMedia = mediaFiles.filter(f => f.status === 'ready')
  const primaryMedia = readyMedia.find(f => f.is_primary) ?? readyMedia[0]

  const manifestUrl = `${BASE}/v1/objects/${obj.id}/iiif/manifest`
  const excludedKeys = new Set(['description', 'keywords'])
  const [viewerError, setViewerError] = useState(false)
  const showViewer = readyMedia.length > 0 && !viewerError

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
          {showViewer ? (
            <IIIFViewer manifestUrl={manifestUrl} onError={() => setViewerError(true)} />
          ) : primaryMedia ? (
            <ViewerFallback objectId={obj.id} media={primaryMedia} />
          ) : (
            <div className="detail-viewer" style={{ display: 'grid', placeItems: 'center', minHeight: 200, color: 'var(--fg-3)', fontSize: 14 }}>
              Kein Bild verfügbar
            </div>
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
          {Object.entries(m).map(([k, v]) =>
            !excludedKeys.has(k) && v && typeof v !== 'object'
              ? <MetaRow key={k} label={fieldLabels[k] ?? k} value={String(v)} />
              : null
          )}
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {readyMedia.length > 0 && (
              <>
                <a href={manifestUrl} target="_blank" rel="noreferrer"
                   style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  IIIF Manifest ({readyMedia.length} {readyMedia.length === 1 ? 'Bild' : 'Bilder'}) ↗
                </a>
                <button
                  onClick={() => navigator.clipboard.writeText(manifestUrl)}
                  style={{
                    fontSize: 11, color: 'var(--fg-3)', background: 'none', border: 'none',
                    padding: 0, cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  📋 Manifest-URL kopieren
                </button>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
