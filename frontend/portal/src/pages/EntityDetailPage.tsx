import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, BASE, fetchRecord, type EntitySummary, type MediaFile, type ObjectSummary, type Relation } from '../api/client'
import { useFieldDefinitions } from '../hooks/useFieldDefinitions'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { RelationsList } from '../components/RelationsList'
import { useBackToSearch } from '../hooks/useBackToSearch'
import { authorityUrl, pidUrl, renderFieldValue } from '../utils/renderFieldValue'
import { RelationFieldRow } from '../components/RelationFieldRow'

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

const ENTITY_TYPE_LABELS: Record<string, string> = {
  person: 'Person', organisation: 'Organisation', group: 'Gruppe', other: 'Sonstige',
}

export function EntityDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [entity, setEntity] = useState<EntitySummary | null>(null)
  const [relations, setRelations] = useState<Relation[]>([])
  const [linkedObjects, setLinkedObjects] = useState<ObjectSummary[]>([])
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const [relationTitles, setRelationTitles] = useState<Record<string, string>>({})
  const [relationMeta, setRelationMeta] = useState<Record<string, Record<string, unknown>>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fieldDefs = useFieldDefinitions('entity')
  const resolveRelationType = useRelationTypeLabels()
  const backSearch = useBackToSearch()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.entities.get(id)
      .then(async e => {
        setEntity(e)
        const rels = await api.relations.forRecord('entity', id).catch(() => [] as Relation[])
        setRelations(rels)

        const objIds = rels
          .filter(r => r.from_type === 'object' || r.to_type === 'object')
          .map(r => r.from_type === 'object' ? r.from_id : r.to_id)
          .slice(0, 12)
        const objs = await Promise.all(objIds.map(oid => api.objects.get(oid).catch(() => null)))
        const validObjs = objs.filter((o): o is ObjectSummary => o !== null)
        setLinkedObjects(validObjs)

        const thumbMap: Record<string, string> = {}
        await Promise.all(validObjs.map(obj =>
          api.objects.media(obj.id)
            .then((media: MediaFile[]) => {
              const ready = media.filter(mf => mf.status === 'ready')
              const primary = ready.find(mf => mf.is_primary) ?? ready[0]
              if (primary) thumbMap[obj.id] = `${BASE}/v1/objects/${obj.id}/media/${primary.id}/file`
            })
            .catch(() => {})
        ))
        setThumbnails(thumbMap)

        const nonObjRels = rels.filter(r => r.from_type !== 'object' && r.to_type !== 'object')
        const pairs = nonObjRels.map(rel => {
          const isFrom = rel.from_id === e.id
          return { type: isFrom ? rel.to_type : rel.from_type, id: isFrom ? rel.to_id : rel.from_id }
        })
        const entries = await Promise.all(pairs.map(p => fetchRecord(p.type, p.id).then(r => ({ key: `${p.type}/${p.id}`, ...r }))))
        const titleMap: Record<string, string> = {}
        const metaMap: Record<string, Record<string, unknown>> = {}
        for (const entry of entries) {
          if (entry.title) titleMap[entry.key] = entry.title
          metaMap[entry.key] = entry.metadata
        }
        setRelationTitles(titleMap)
        setRelationMeta(metaMap)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="container page" style={{ color: 'var(--fg-3)' }}>Lade…</div>
  if (error || !entity) return (
    <div className="container page">
      <div style={{ color: '#dc2626' }}>{error ?? 'Entität nicht gefunden.'}</div>
    </div>
  )

  const m = entity.metadata_ as Record<string, unknown>
  const title = String(m.name ?? m.title ?? m.label ?? m.display_name ?? entity.id)
  const typeLabel = ENTITY_TYPE_LABELS[entity.entity_type] ?? entity.entity_type
  const description = String(m.description ?? '')

  const allVisibleFields = fieldDefs.filter(f => f.show_in_detail && f.name !== 'description' && f.name !== 'name' && f.name !== 'title')
  const bodyFields = allVisibleFields.filter(f => {
    if (f.field_type === 'relation' || f.field_type === 'authority' || f.field_type === 'pid') return false
    const rendered = renderFieldValue(m[f.name])
    return rendered !== null && rendered.length > 100
  })
  const sidebarFields = allVisibleFields.filter(f => !bodyFields.includes(f))

  return (
    <div className="container page">
      <Helmet>
        <title>{title}</title>
        {description && <meta name="description" content={description} />}
        <meta property="og:title" content={title} />
        {description && <meta property="og:description" content={description} />}
        <meta property="og:url" content={window.location.href} />
        <meta property="og:type" content="article" />
      </Helmet>
      <div className="bc">
        {backSearch ? (
          <a href="#" onClick={e => { e.preventDefault(); navigate(backSearch) }}>Zurück zur Suche</a>
        ) : (
          <>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>Startseite</a>
            <span className="sep">/</span>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=&type=entity') }}>Personen &amp; Organisationen</a>
          </>
        )}
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span className="tag" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{typeLabel}</span>
        <span className="tag">{entity.status}</span>
      </div>
      <h1 style={{ margin: '0 0 24px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em' }}>{title}</h1>

      <div className="detail-layout">
        <div>
          {m.description != null && (
            <div
              className="prose"
              style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)', marginBottom: 20 }}
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(String(m.description)) as string) }}
            />
          )}

          {bodyFields.map(f => {
            const rendered = renderFieldValue(m[f.name])
            if (!rendered) return null
            return (
              <div key={f.name} style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)', marginBottom: 6 }}>
                  {f.label?.de ?? f.label?.en ?? f.name}
                </div>
                <div
                  className="prose"
                  style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(rendered) as string) }}
                />
              </div>
            )
          })}

          {linkedObjects.length > 0 && (
            <section style={{ marginTop: 8 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Zugehörige Objekte</h2>
              <div className="obj-grid">
                {linkedObjects.map(obj => {
                  const om = obj.metadata_ as Record<string, unknown>
                  const otitle = String(om.title ?? om.name ?? obj.idno ?? obj.id)
                  const rel = relations.find(r => r.from_id === obj.id || r.to_id === obj.id)
                  const isFrom = rel ? rel.from_id === entity.id : true
                  return (
                    <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
                      <div className="thumb">
                        {thumbnails[obj.id] && <img src={thumbnails[obj.id]} alt="" loading="lazy" />}
                      </div>
                      <div className="info">
                        <div className="title">{otitle}</div>
                        {rel && (
                          <div className="meta" style={{ textTransform: 'uppercase', letterSpacing: '.04em', fontSize: 10 }}>
                            {resolveRelationType(rel.relation_type, isFrom)}
                          </div>
                        )}
                        {obj.idno && <div className="meta">{obj.idno}</div>}
                      </div>
                    </Link>
                  )
                })}
              </div>
            </section>
          )}

          <RelationsList
            relations={relations.filter(r => r.from_type !== 'object' && r.to_type !== 'object')}
            currentId={entity.id}
            resolveLabel={resolveRelationType}
            titles={relationTitles}
            metadata={relationMeta}
            fieldDefs={fieldDefs}
          />
        </div>

        <aside className="detail-meta">
          {sidebarFields.map(f => {
            const rawValue = m[f.name]
            if (f.field_type === 'relation') {
              return <RelationFieldRow key={f.name} label={f.label?.de ?? f.label?.en ?? f.name} value={rawValue} targetType={f.settings?.target_type as string | undefined} />
            }
            const rendered = renderFieldValue(rawValue)
            const href = f.field_type === 'authority'
              ? authorityUrl(rawValue)
              : f.field_type === 'pid'
                ? pidUrl(rawValue)
                : undefined
            return rendered ? <MetaRow key={f.name} label={f.label?.de ?? f.label?.en ?? f.name} value={rendered} href={href} /> : null
          })}
          <MetaRow label="Typ" value={typeLabel} />
        </aside>
      </div>
    </div>
  )
}
