import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, BASE, fetchRecordTitle, type MediaFile, type ObjectSummary, type Relation } from '../api/client'
import { useFieldDefinitions } from '../hooks/useFieldDefinitions'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { IIIFViewer } from '../components/IIIFViewer'
import { RelationsList } from '../components/RelationsList'
import { useBackToSearch } from '../hooks/useBackToSearch'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { authorityUrl, pidUrl, renderFieldValue } from '../utils/renderFieldValue'

function MetaRow({ label, value, href }: { label: string; value: string; href?: string }) {
  if (!value) return null
  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val">
        {href ? <a href={href} target="_blank" rel="noreferrer">{value}</a> : value}
      </span>
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
  const [viewerError, setViewerError] = useState(false)
  const [relations, setRelations] = useState<Relation[]>([])
  const [relationTitles, setRelationTitles] = useState<Record<string, string>>({})
  const fieldDefs = useFieldDefinitions('object')
  const resolveRelationType = useRelationTypeLabels()
  const backSearch = useBackToSearch()
  const portalConfig = usePortalConfig()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.objects.get(id),
      api.objects.media(id).catch(() => [] as MediaFile[]),
      api.relations.forRecord('object', id).catch(() => [] as Relation[]),
    ])
      .then(([o, m, r]) => {
        setObj(o)
        setMediaFiles(m)
        setRelations(r)
        const pairs = r.map(rel => {
          const isFrom = rel.from_id === o.id
          return { type: isFrom ? rel.to_type : rel.from_type, id: isFrom ? rel.to_id : rel.from_id }
        })
        Promise.all(pairs.map(p => fetchRecordTitle(p.type, p.id).then(t => ({ key: `${p.type}/${p.id}`, title: t }))))
          .then(entries => {
            const map: Record<string, string> = {}
            for (const e of entries) if (e.title) map[e.key] = e.title
            setRelationTitles(map)
          })
      })
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
  const showViewer = readyMedia.length > 0 && !viewerError

  const description = String(m.description ?? '')
  const ogImage = primaryMedia ? `${BASE}/v1/objects/${obj.id}/media/${primaryMedia.id}/file` : ''

  const visibleFields = fieldDefs.filter(f => f.show_in_detail && f.name !== 'description' && f.name !== 'keywords' && f.name !== 'title' && f.name !== 'name')

  return (
    <div className="container page">
      <Helmet>
        <title>{title}</title>
        {description && <meta name="description" content={description} />}
        <meta property="og:title" content={title} />
        {description && <meta property="og:description" content={description} />}
        <meta property="og:url" content={window.location.href} />
        <meta property="og:type" content="article" />
        {ogImage && <meta property="og:image" content={ogImage} />}
        {readyMedia.length > 0 && (
          <link rel="alternate" type="application/ld+json" href={manifestUrl} />
        )}
      </Helmet>
      <div className="bc">
        {backSearch ? (
          <a href="#" onClick={e => { e.preventDefault(); navigate(backSearch) }}>Zurück zur Suche</a>
        ) : (
          <>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>Startseite</a>
            <span className="sep">/</span>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=') }}>Suche</a>
          </>
        )}
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
          ) : portalConfig.placeholder_image_url ? (
            <img
              src={portalConfig.placeholder_image_url}
              alt=""
              style={{ width: '100%', borderRadius: 10, display: 'block', background: '#0f172a' }}
            />
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

          <RelationsList
            relations={relations}
            currentId={obj.id}
            resolveLabel={resolveRelationType}
            titles={relationTitles}
          />
        </div>

        <aside className="detail-meta">
          {obj.idno && <MetaRow label="Inventar-Nr." value={obj.idno} />}
          {visibleFields.map(f => {
            const rawValue = m[f.name]
            const rendered = renderFieldValue(rawValue)
            const href = f.field_type === 'authority'
              ? authorityUrl(rawValue)
              : f.field_type === 'pid'
                ? pidUrl(rawValue)
                : undefined
            return rendered ? <MetaRow key={f.name} label={f.label?.de ?? f.label?.en ?? f.name} value={rendered} href={href} /> : null
          })}
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
