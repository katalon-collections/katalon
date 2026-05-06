import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, type OccurrenceSummary, type ObjectSummary, type Relation } from '../api/client'
import { useFieldLabels } from '../hooks/useFieldLabels'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { RelationsList } from '../components/RelationsList'
import { useBackToSearch } from '../hooks/useBackToSearch'

function MetaRow({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val">{value}</span>
    </div>
  )
}

const OCCURRENCE_TYPE_LABELS: Record<string, string> = {
  work: 'Werk', event: 'Ereignis', concept: 'Konzept', other: 'Sonstiges',
}

export function OccurrenceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [occurrence, setOccurrence] = useState<OccurrenceSummary | null>(null)
  const [relations, setRelations] = useState<Relation[]>([])
  const [linkedObjects, setLinkedObjects] = useState<ObjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fieldLabels = useFieldLabels('occurrence')
  const resolveRelationType = useRelationTypeLabels()
  const backSearch = useBackToSearch()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.occurrences.get(id)
      .then(async o => {
        setOccurrence(o)
        const rels = await api.relations.forRecord('occurrence', id).catch(() => [] as Relation[])
        setRelations(rels)
        const objIds = rels
          .filter(r => r.from_type === 'object' || r.to_type === 'object')
          .map(r => r.from_type === 'object' ? r.from_id : r.to_id)
          .slice(0, 12)
        const objs = await Promise.all(
          objIds.map(oid => api.objects.get(oid).catch(() => null))
        )
        setLinkedObjects(objs.filter((o): o is ObjectSummary => o !== null))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="container page" style={{ color: 'var(--fg-3)' }}>Lade…</div>
  if (error || !occurrence) return (
    <div className="container page">
      <div style={{ color: '#dc2626' }}>{error ?? 'Eintrag nicht gefunden.'}</div>
    </div>
  )

  const m = occurrence.metadata_ as Record<string, unknown>
  const title = String(m.title ?? m.name ?? m.label ?? occurrence.id)
  const typeLabel = OCCURRENCE_TYPE_LABELS[occurrence.occurrence_type] ?? occurrence.occurrence_type
  const description = String(m.description ?? '')

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
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=&type=occurrence') }}>Werke &amp; Ereignisse</a>
          </>
        )}
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span className="tag" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{typeLabel}</span>
        <span className="tag">{occurrence.status}</span>
      </div>
      <h1 style={{ margin: '0 0 24px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em' }}>{title}</h1>

      <div className="detail-layout">
        <div>
          {m.description != null && (
            <div style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)', marginBottom: 20 }}>
              {String(m.description)}
            </div>
          )}

          {linkedObjects.length > 0 && (
            <section style={{ marginTop: 8 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Zugehörige Objekte</h2>
              <div className="obj-grid">
                {linkedObjects.map(obj => {
                  const om = obj.metadata_ as Record<string, unknown>
                  const otitle = String(om.title ?? om.name ?? obj.idno ?? obj.id)
                  const rel = relations.find(r =>
                    r.from_id === obj.id || r.to_id === obj.id
                  )
                  return (
                    <div key={obj.id} className="obj-card" onClick={() => navigate(`/objects/${obj.id}`)}>
                      <div className="thumb" />
                      <div className="info">
                        <div className="title">{otitle}</div>
                        {rel && (
                          <div className="meta" style={{ textTransform: 'uppercase', letterSpacing: '.04em', fontSize: 10 }}>
                            {resolveRelationType(rel.relation_type)}
                          </div>
                        )}
                        {obj.idno && <div className="meta">{obj.idno}</div>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          <RelationsList
            relations={relations.filter(r =>
              r.from_type !== 'object' && r.to_type !== 'object'
            )}
            currentId={occurrence.id}
            resolveLabel={resolveRelationType}
          />
        </div>

        <aside className="detail-meta">
          {Object.entries(m).map(([k, v]) =>
            v && typeof v !== 'object' ? (
              <MetaRow key={k} label={fieldLabels[k] ?? k} value={String(v)} />
            ) : null
          )}
          <MetaRow label="Typ" value={typeLabel} />
        </aside>
      </div>
    </div>
  )
}
