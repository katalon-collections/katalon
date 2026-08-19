import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, BASE, PORTAL_API, fetchRecord, type MediaFile, type ObjectSummary, type Relation } from '../api/client'
import { useFieldDefinitions } from '../hooks/useFieldDefinitions'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { IIIFViewer } from '../components/IIIFViewer'
import { RelationsList } from '../components/RelationsList'
import { MediaViewer, MediaThumb } from '../components/MediaViewer'
import { useBackToSearch } from '../hooks/useBackToSearch'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { authorityUrl, pidUrl, renderFieldValue } from '../utils/renderFieldValue'
import { RelationFieldRow } from '../components/RelationFieldRow'
import { useI18n } from '../i18n'

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

function ViewerFallback({ objectId, mediaFiles }: { objectId: string; mediaFiles: MediaFile[] }) {
  if (mediaFiles.length === 1) {
    return (
      <img
        src={`${BASE}${PORTAL_API}/objects/${objectId}/media/${mediaFiles[0].id}/file`}
        alt=""
        style={{ width: '100%', borderRadius: 10, display: 'block', background: '#0f172a' }}
        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
      />
    )
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
      {mediaFiles.map(f => (
        <img
          key={f.id}
          src={`${BASE}${PORTAL_API}/objects/${objectId}/media/${f.id}/file`}
          alt=""
          style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', borderRadius: 8, display: 'block', background: '#0f172a' }}
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      ))}
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

  const [relations, setRelations] = useState<Relation[]>([])
  const [relationTitles, setRelationTitles] = useState<Record<string, string>>({})
  const [relationMeta, setRelationMeta] = useState<Record<string, Record<string, unknown>>>({})
  const [viewerError, setViewerError] = useState(false)
  const [selectedMediaId, setSelectedMediaId] = useState<string | null>(null)
  const fieldDefs = useFieldDefinitions('object')
  const { t, locale } = useI18n()
  const resolveRelationType = useRelationTypeLabels(locale)
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
        Promise.all(pairs.map(p => fetchRecord(p.type, p.id).then(r => ({ key: `${p.type}/${p.id}`, ...r }))))
          .then(entries => {
            const titleMap: Record<string, string> = {}
            const metaMap: Record<string, Record<string, unknown>> = {}
            for (const e of entries) {
              if (e.title) titleMap[e.key] = e.title
              metaMap[e.key] = e.metadata
            }
            setRelationTitles(titleMap)
            setRelationMeta(metaMap)
          })
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return <div className="container page" style={{ color: 'var(--fg-3)' }}>{t('common.loading')}</div>
  }

  if (error || !obj) {
    return (
      <div className="container page">
        <div style={{ color: '#dc2626' }}>{error ?? t('error.objectNotFound')}</div>
      </div>
    )
  }

  const m = obj.metadata_ as Record<string, unknown>
  const title = String(m.title ?? m.name ?? obj.idno ?? obj.id)
  const readyMedia = mediaFiles.filter(f => f.status === 'ready')
  const primaryMedia = readyMedia.find(f => f.is_primary) ?? readyMedia[0]
  const selectedMedia = readyMedia.find(f => f.id === selectedMediaId) ?? primaryMedia
  const category = selectedMedia?.category ?? 'image'
  const imageMedia = readyMedia.filter(f => (f.category ?? 'image') === 'image')

  const manifestUrl = `${BASE || window.location.origin}${PORTAL_API}/objects/${obj.id}/iiif/manifest`
  const showViewer = readyMedia.length > 0 && !viewerError

  const description = renderFieldValue(m.description, locale) ?? ''
  const primaryImage = readyMedia.find(f => f.is_primary && (f.category ?? 'image') === 'image')
    ?? readyMedia.find(f => (f.category ?? 'image') === 'image')
  const ogImage = primaryImage ? `${BASE}${PORTAL_API}/objects/${obj.id}/media/${primaryImage.id}/file` : ''

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
        {imageMedia.length > 0 && (
          <link rel="alternate" type="application/ld+json" href={manifestUrl} />
        )}
      </Helmet>
      <div className="bc">
        {backSearch ? (
          <a href="#" onClick={e => { e.preventDefault(); navigate(backSearch) }}>{t('common.backToSearch')}</a>
        ) : (
          <>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>{t('common.home')}</a>
            <span className="sep">/</span>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=') }}>{t('common.search')}</a>
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
          {category !== 'image' && selectedMedia ? (
            <MediaViewer objectId={obj.id} media={selectedMedia} />
          ) : showViewer ? (
            <IIIFViewer manifestUrl={manifestUrl} onError={() => setViewerError(true)} />
          ) : readyMedia.length > 0 ? (
            <ViewerFallback objectId={obj.id} mediaFiles={readyMedia} />
          ) : portalConfig.placeholder_image_url ? (
            <img
              src={portalConfig.placeholder_image_url}
              alt=""
              style={{ width: '100%', borderRadius: 10, display: 'block', background: '#0f172a' }}
            />
          ) : (
            <div className="detail-viewer" style={{ display: 'grid', placeItems: 'center', minHeight: 200, color: 'var(--fg-3)', fontSize: 14 }}>
              {t('object.noImage')}
            </div>
          )}

          {readyMedia.length > 1 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))', gap: 8, marginTop: 16 }}>
              {readyMedia.map(m => (
                <MediaThumb
                  key={m.id}
                  objectId={obj.id}
                  media={m}
                  active={m.id === selectedMedia?.id}
                  onSelect={() => setSelectedMediaId(m.id)}
                />
              ))}
            </div>
          )}

          {m.description != null && (
            <div style={{ marginTop: 20, fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>
              {renderFieldValue(m.description, locale)}
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
            metadata={relationMeta}
            fieldDefs={fieldDefs}
          />
        </div>

        <aside className="detail-meta">
          {obj.idno && <MetaRow label={t('common.inventoryNo')} value={obj.idno} />}
          {visibleFields.map(f => {
            const rawValue = m[f.name]
            if (f.field_type === 'relation') {
              return <RelationFieldRow key={f.name} label={f.label?.[locale] ?? f.label?.de ?? f.label?.en ?? f.name} value={rawValue} targetType={f.settings?.target_type as string | undefined} />
            }
            const rendered = renderFieldValue(rawValue, locale, f.field_type)
            const href = f.field_type === 'authority'
              ? authorityUrl(rawValue)
              : f.field_type === 'pid'
                ? pidUrl(rawValue)
                : undefined
            return rendered ? <MetaRow key={f.name} label={f.label?.[locale] ?? f.label?.de ?? f.label?.en ?? f.name} value={rendered} href={href} /> : null
          })}
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {imageMedia.length > 0 && (
              <>
                <a href={manifestUrl} target="_blank" rel="noreferrer"
                   style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {t('object.iiifManifest')} ({imageMedia.length} {imageMedia.length === 1 ? t('object.imageSingular') : t('object.imagePlural')}) ↗
                </a>
                <button
                  onClick={() => navigator.clipboard.writeText(manifestUrl)}
                  style={{
                    fontSize: 11, color: 'var(--fg-3)', background: 'none', border: 'none',
                    padding: 0, cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  📋 {t('object.copyManifest')}
                </button>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
