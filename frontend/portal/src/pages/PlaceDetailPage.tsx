import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, type ObjectSummary, type PlaceSummary, type Relation } from '../api/client'
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

function StaticMap({ lat, lon, name }: { lat: number; lon: number; name: string }) {
  // OpenStreetMap embed via iframe (no extra dependency needed)
  const bbox = `${lon - 0.05},${lat - 0.03},${lon + 0.05},${lat + 0.03}`
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`
  return (
    <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 16 }}>
      <iframe
        src={src}
        title={`Karte: ${name}`}
        width="100%"
        height="300"
        style={{ border: 0, display: 'block' }}
        loading="lazy"
      />
      <div style={{ padding: '6px 10px', fontSize: 12, color: 'var(--fg-3)', background: 'var(--panel)' }}>
        {lat.toFixed(5)}, {lon.toFixed(5)} ·{' '}
        <a
          href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=13/${lat}/${lon}`}
          target="_blank" rel="noreferrer"
          style={{ color: 'var(--fg-3)' }}
        >
          OpenStreetMap ↗
        </a>
      </div>
    </div>
  )
}

export function PlaceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [place, setPlace] = useState<PlaceSummary | null>(null)
  const [relations, setRelations] = useState<Relation[]>([])
  const [linkedObjects, setLinkedObjects] = useState<ObjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fieldLabels = useFieldLabels('place')
  const resolveRelationType = useRelationTypeLabels()
  const backSearch = useBackToSearch()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.places.get(id)
      .then(async p => {
        setPlace(p)
        const rels = await api.relations.forRecord('place', id).catch(() => [] as Relation[])
        setRelations(rels)
        const objIds = rels
          .filter(r => r.from_type === 'object' || r.to_type === 'object')
          .map(r => r.from_type === 'object' ? r.from_id : r.to_id)
          .slice(0, 12)
        const objs = await Promise.all(objIds.map(oid => api.objects.get(oid).catch(() => null)))
        setLinkedObjects(objs.filter((o): o is ObjectSummary => o !== null))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="container page" style={{ color: 'var(--fg-3)' }}>Lade…</div>
  if (error || !place) return (
    <div className="container page">
      <div style={{ color: '#dc2626' }}>{error ?? 'Ort nicht gefunden.'}</div>
    </div>
  )

  const m = place.metadata_ as Record<string, unknown>
  const title = String(m.name ?? m.title ?? m.label ?? place.id)
  const hasCoords = place.lat != null && place.lon != null
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
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=&type=place') }}>Orte</a>
          </>
        )}
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <div style={{ marginBottom: 6 }}>
        <span className="tag">{place.status}</span>
      </div>
      <h1 style={{ margin: '0 0 24px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em' }}>{title}</h1>

      <div className="detail-layout">
        <div>
          {hasCoords && (
            <StaticMap lat={place.lat!} lon={place.lon!} name={title} />
          )}

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
            currentId={place.id}
            resolveLabel={resolveRelationType}
          />
        </div>

        <aside className="detail-meta">
          {Object.entries(m).map(([k, v]) =>
            v && typeof v !== 'object' ? <MetaRow key={k} label={fieldLabels[k] ?? k} value={String(v)} /> : null
          )}
          {hasCoords && (
            <MetaRow label="Koordinaten" value={`${place.lat!.toFixed(5)}, ${place.lon!.toFixed(5)}`} />
          )}
        </aside>
      </div>
    </div>
  )
}
