// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import {
  api,
  mediaThumbnailUrl,
  type CollectionDetail,
  type MediaFile,
  type ObjectSummary,
  type Relation,
} from '../api/client'
import { useFieldDefinitions } from '../hooks/useFieldDefinitions'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { useBackToSearch } from '../hooks/useBackToSearch'
import { recordTitle, renderFieldValue } from '../utils/renderFieldValue'
import { MetaRow } from '../components/DetailPageLayout'
import { RelationsList } from '../components/RelationsList'
import { useI18n } from '../i18n'

export function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t, locale } = useI18n()
  const resolveRelationType = useRelationTypeLabels(locale)
  const backSearch = useBackToSearch()

  const [col, setCol] = useState<CollectionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [objects, setObjects] = useState<ObjectSummary[]>([])
  const [objectsLoading, setObjectsLoading] = useState(false)
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [searchQuery, setSearchQuery] = useState('')

  const [relations, setRelations] = useState<Relation[]>([])
  const [fieldDefs] = useFieldDefinitions('collection')

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)

    api.collections
      .get(id)
      .then(async data => {
        setCol(data)
        setLoading(false)

        // Load non-object relations for sidebar (entities, places, etc. - objects are displayed in main column)
        api.relations.forRecord('collection', id)
          .then(allRels => {
            const nonObjRels = allRels.filter(
              r => (r.from_type !== 'object' && r.to_type !== 'object') && r.relation_type !== 'member_of'
            )
            setRelations(nonObjRels)
          })
          .catch(() => {})
        // Load member objects
        setObjectsLoading(true)
        try {
          const rels = await api.relations.forRecord('collection', id, true).catch(() => [] as Relation[])
          const memberObjIds = rels
            .filter(r => (r.to_type === 'collection' && r.from_type === 'object') ||
                         (r.from_type === 'collection' && r.to_type === 'object'))
            .map(r => r.from_type === 'object' ? r.from_id : r.to_id)
          const uniqueIds = [...new Set(memberObjIds)].slice(0, 48)

          if (uniqueIds.length > 0) {
            const fetched = await Promise.all(uniqueIds.map(oid => api.objects.get(oid).catch(() => null)))
            const valid = fetched.filter((o): o is ObjectSummary => o !== null)
            setObjects(valid)

            // Fetch thumbnails
            const thumbMap: Record<string, string> = {}
            await Promise.all(
              valid.map(obj =>
                api.objects
                  .media(obj.id)
                  .then((m: MediaFile[]) => {
                    const ready = m.filter(mf => mf.status === 'ready')
                    const primary = ready.find(mf => mf.is_primary) ?? ready[0]
                    if (primary) {
                      thumbMap[obj.id] = mediaThumbnailUrl(obj.id, primary.id)
                    }
                  })
                  .catch(() => {})
              )
            )
            setThumbnails(thumbMap)
          } else {
            setObjects([])
          }
        } finally {
          setObjectsLoading(false)
        }
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : t('error.collectionNotFound'))
        setLoading(false)
      })
  }, [id, t])

  if (loading) {
    return <div className="container page" style={{ color: 'var(--fg-3)' }}>{t('common.loading')}</div>
  }

  if (error || !col) {
    return (
      <div className="container page">
        <div style={{ color: '#dc2626' }}>{error ?? t('error.collectionNotFound')}</div>
      </div>
    )
  }

  const m = col.metadata_ as Record<string, unknown>
  const title = recordTitle(m, locale, col.idno ?? col.id)
  const description = renderFieldValue(m.description || m.kurzbeschreibung, locale)
  const scopeAndContent = renderFieldValue(m.scope_and_content || m.bestandsumfang, locale)

  // Filter objects by quick local search if entered
  const filteredObjects = searchQuery.trim()
    ? objects.filter(obj => {
        const objTitle = recordTitle(obj.metadata_ as Record<string, unknown>, locale, obj.idno ?? '')
        return objTitle.toLowerCase().includes(searchQuery.toLowerCase()) ||
               (obj.idno && obj.idno.toLowerCase().includes(searchQuery.toLowerCase()))
      })
    : objects

  // Highlight image from first object thumbnail for cover/hero visual
  const heroImage = objects.length > 0 && thumbnails[objects[0].id] ? thumbnails[objects[0].id] : null

  function handleSearchInCollection(e: React.FormEvent) {
    e.preventDefault()
    if (!col) return
    navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}&rel_collection=${encodeURIComponent(title)}`)
  }

  return (
    <>
      <Helmet>
        <title>{title}</title>
        {description && <meta name="description" content={description} />}
      </Helmet>

      <div className="container page collection-detail-page">
        {/* Navigation Breadcrumb Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--fg-3)', flexWrap: 'wrap' }}>
            {backSearch ? (
              <button
                type="button"
                className="back-link"
                onClick={() => navigate(backSearch)}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--accent)', fontSize: 'inherit' }}
              >
                ← {t('common.backToSearch')}
              </button>
            ) : (
              <Link to="/search?type=collection" style={{ color: 'var(--accent)' }}>
                {t('nav.collections')}
              </Link>
            )}

            {col.ancestors.length > 0 && (
              <>
                <span>/</span>
                {col.ancestors.map(anc => (
                  <span key={anc.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <Link to={`/collections/${anc.id}`} style={{ color: 'var(--fg-2)' }}>
                      {anc.title || anc.idno || anc.id.slice(0, 8)}
                    </Link>
                    <span>/</span>
                  </span>
                ))}
              </>
            )}
            <span style={{ color: 'var(--fg-1)', fontWeight: 500 }}>{title}</span>
          </div>

          {col.idno && (
            <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--fg-2)' }}>
              {t('common.signature')}: <strong>{col.idno}</strong>
            </span>
          )}
        </div>

        {/* Hero & Kuratorischer Header */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '32px 28px',
            marginBottom: 32,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {heroImage && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                right: 0,
                bottom: 0,
                width: '40%',
                backgroundImage: `url(${heroImage})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                opacity: 0.12,
                maskImage: 'linear-gradient(to left, black 30%, transparent 100%)',
                WebkitMaskImage: 'linear-gradient(to left, black 30%, transparent 100%)',
                pointerEvents: 'none',
              }}
            />
          )}

          <div style={{ position: 'relative', maxWidth: '800px', zIndex: 1 }}>
            <div style={{ display: 'inline-block', fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 8 }}>
              {col.collection_type ? `${t('type.collection')} · ${col.collection_type}` : t('type.collection')}
            </div>
            <h1 style={{ fontSize: 32, fontWeight: 700, margin: '0 0 16px', lineHeight: 1.2, color: 'var(--fg-1)' }}>
              {title}
            </h1>

            {description && (
              <p style={{ fontSize: 16, lineHeight: 1.6, color: 'var(--fg-2)', margin: '0 0 20px' }}>
                {description}
              </p>
            )}

            {scopeAndContent && (
              <div style={{ fontSize: 14, lineHeight: 1.5, color: 'var(--fg-2)', margin: '0 0 20px', padding: '12px 16px', background: 'var(--bg)', borderRadius: 8, borderLeft: '3px solid var(--accent)' }}>
                <strong>Bestandsumfang & Inhalt: </strong>{scopeAndContent}
              </div>
            )}

            {/* Quick-Search inside collection */}
            <form onSubmit={handleSearchInCollection} style={{ display: 'flex', gap: 8, maxWidth: 500, marginTop: 24 }}>
              <input
                type="text"
                className="search-input"
                style={{ flex: 1, padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)' }}
                placeholder={t('collection.searchInCollection')}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="button" style={{ padding: '8px 16px', borderRadius: 8 }}>
                {t('search.button')}
              </button>
            </form>
          </div>
        </div>

        {/* 2-Spalten-Layout: Links Hierarchie & Metadaten, Rechts Bestands-Objekte */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 320px) 1fr', gap: 32, alignItems: 'start' }}>
          
          {/* Linke Spalte: Hierarchiebaum & Formale Metadaten */}
          <aside style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Hierarchie-Panel */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 14px', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-3)' }}>
                {t('collection.hierarchy')}
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
                {col.ancestors.map((anc, idx) => (
                  <div key={anc.id} style={{ paddingLeft: idx * 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: 'var(--fg-3)' }}>└</span>
                    <Link to={`/collections/${anc.id}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                      {anc.title || anc.idno || anc.id.slice(0, 8)}
                    </Link>
                  </div>
                ))}

                {/* Aktuelle Sammlung */}
                <div
                  style={{
                    paddingLeft: col.ancestors.length * 14,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontWeight: 600,
                    color: 'var(--fg-1)',
                    background: 'var(--bg)',
                    padding: '6px 10px',
                    borderRadius: 6,
                  }}
                >
                  <span>●</span>
                  <span>{title}</span>
                </div>

                {/* Untergeordnete Sammlungen */}
                {col.children.map(child => (
                  <div
                    key={child.id}
                    style={{
                      paddingLeft: (col.ancestors.length + 1) * 14,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 13,
                    }}
                  >
                    <span style={{ color: 'var(--fg-3)' }}>├</span>
                    <Link to={`/collections/${child.id}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                      {child.title || child.idno || child.id.slice(0, 8)}
                    </Link>
                  </div>
                ))}
              </div>

              {col.children.length === 0 && col.ancestors.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }}>
                  Eigenständige Sammlung (keine Hierarchie hinterlegt).
                </div>
              )}
            </div>

            {/* Formale Metadaten */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 14px', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-3)' }}>
                {t('common.relations')} & Details
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                {col.idno && <MetaRow label={t('common.signature')} value={col.idno} />}
                {col.collection_type && <MetaRow label={t('common.type')} value={col.collection_type} />}
                <MetaRow label={t('collection.objectsCount', { count: col.member_objects_count })} value={String(col.member_objects_count)} />

                {/* Dynamische Schema-Felder (außer bereits dargestellter Titel/Beschreibungen) */}
                {fieldDefs
                  .filter(f => !['title', 'name', 'description', 'kurzbeschreibung', 'scope_and_content'].includes(f.name))
                  .map(f => {
                    const val = m[f.name]
                    if (val == null || val === '') return null
                    const rendered = renderFieldValue(val, locale, f.field_type)
                    if (!rendered) return null
                    const label = f.label?.[locale] ?? f.label?.de ?? f.label?.en ?? f.name
                    return <MetaRow key={f.name} label={label} value={rendered} />
                  })}
              </div>

              {relations.length > 0 && (
                <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                  <RelationsList relations={relations} currentId={col.id} resolveLabel={resolveRelationType} />
                </div>
              )}
            </div>
          </aside>

          {/* Rechte Spalte: Unter-Sammlungs-Karten & Zugehörige Objekte */}
          <main style={{ minWidth: 0 }}>
            {/* Wenn Unter-Sammlungen vorhanden sind, als Teilsammlungs-Karten hervorheben */}
            {col.children.length > 0 && (
              <section style={{ marginBottom: 36 }}>
                <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 16px', color: 'var(--fg-1)' }}>
                  {t('collection.subCollections')} ({col.children.length})
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
                  {col.children.map(child => (
                    <Link
                      key={child.id}
                      to={`/collections/${child.id}`}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        padding: 16,
                        borderRadius: 8,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        textDecoration: 'none',
                        color: 'inherit',
                        transition: 'border-color 0.15s, box-shadow 0.15s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'var(--accent)'
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.05)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'var(--border)'
                        e.currentTarget.style.boxShadow = 'none'
                      }}
                    >
                      <div>
                        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--accent)' }}>
                          📁 {child.collection_type || t('type.collection')}
                        </span>
                        <h4 style={{ fontSize: 15, fontWeight: 600, margin: '6px 0 8px', color: 'var(--fg-1)' }}>
                          {child.title || child.idno || child.id.slice(0, 8)}
                        </h4>
                      </div>
                      {child.idno && (
                        <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                          {child.idno}
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Zugehörige Objekte dieser Sammlung */}
            <section>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
                <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: 'var(--fg-1)' }}>
                  {t('common.relatedObjects')}
                  {filteredObjects.length > 0 && <span style={{ fontWeight: 400, color: 'var(--fg-3)', marginLeft: 8 }}>({filteredObjects.length})</span>}
                </h2>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {/* Umschalter Grid / List */}
                  <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
                    <button
                      type="button"
                      style={{
                        padding: '4px 10px',
                        background: viewMode === 'grid' ? 'var(--accent)' : 'var(--bg-card)',
                        color: viewMode === 'grid' ? '#fff' : 'var(--fg-2)',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: 12,
                      }}
                      onClick={() => setViewMode('grid')}
                    >
                      ⊞ {t('collection.viewGrid')}
                    </button>
                    <button
                      type="button"
                      style={{
                        padding: '4px 10px',
                        background: viewMode === 'list' ? 'var(--accent)' : 'var(--bg-card)',
                        color: viewMode === 'list' ? '#fff' : 'var(--fg-2)',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: 12,
                        borderLeft: '1px solid var(--border)',
                      }}
                      onClick={() => setViewMode('list')}
                    >
                      ☰ {t('collection.viewList')}
                    </button>
                  </div>

                  {col.member_objects_count > filteredObjects.length && (
                    <Link
                      to={`/search?rel_collection=${encodeURIComponent(title)}`}
                      style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}
                    >
                      {t('collection.allInCollection', { count: col.member_objects_count })}
                    </Link>
                  )}
                </div>
              </div>

              {objectsLoading ? (
                <div style={{ color: 'var(--fg-3)', padding: '24px 0' }}>{t('common.loading')}</div>
              ) : filteredObjects.length === 0 ? (
                <div
                  style={{
                    padding: 32,
                    textAlign: 'center',
                    background: 'var(--bg-card)',
                    border: '1px dashed var(--border)',
                    borderRadius: 8,
                    color: 'var(--fg-3)',
                    fontSize: 14,
                  }}
                >
                  {t('collection.noObjects')}
                </div>
              ) : viewMode === 'grid' ? (
                /* Raster-Ansicht / Galerie */
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16 }}>
                  {filteredObjects.map(obj => {
                    const objTitle = recordTitle(obj.metadata_ as Record<string, unknown>, locale, obj.idno ?? '')
                    const thumb = thumbnails[obj.id]
                    return (
                      <Link
                        key={obj.id}
                        to={`/objects/${obj.id}`}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          overflow: 'hidden',
                          textDecoration: 'none',
                          color: 'inherit',
                          transition: 'transform 0.15s, box-shadow 0.15s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.transform = 'translateY(-2px)'
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.transform = 'none'
                          e.currentTarget.style.boxShadow = 'none'
                        }}
                      >
                        <div style={{ width: '100%', aspectRatio: '4/3', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                          {thumb ? (
                            <img src={thumb} alt={objTitle} style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
                          ) : (
                            <span style={{ fontSize: 24, color: 'var(--fg-3)' }}>🖼️</span>
                          )}
                        </div>
                        <div style={{ padding: '10px 12px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-1)', lineHeight: 1.3, marginBottom: 4 }}>
                            {objTitle}
                          </span>
                          {obj.idno && (
                            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{obj.idno}</span>
                          )}
                        </div>
                      </Link>
                    )
                  })}
                </div>
              ) : (
                /* Listen-Ansicht / Findbuch-Tabelle */
                <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: 'var(--bg)', borderBottom: '1px solid var(--border)', color: 'var(--fg-3)' }}>
                        <th style={{ padding: '10px 14px', width: 48 }}></th>
                        <th style={{ padding: '10px 14px' }}>{t('common.inventoryNo')}</th>
                        <th style={{ padding: '10px 14px' }}>{t('type.object')}</th>
                        <th style={{ padding: '10px 14px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredObjects.map(obj => {
                        const objTitle = recordTitle(obj.metadata_ as Record<string, unknown>, locale, obj.idno ?? '')
                        const thumb = thumbnails[obj.id]
                        return (
                          <tr
                            key={obj.id}
                            style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                            onClick={() => navigate(`/objects/${obj.id}`)}
                          >
                            <td style={{ padding: '8px 14px' }}>
                              <div style={{ width: 36, height: 36, borderRadius: 4, background: 'var(--bg)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {thumb ? <img src={thumb} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '🖼️'}
                              </div>
                            </td>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', color: 'var(--fg-2)', fontSize: 12 }}>
                              {obj.idno ?? '—'}
                            </td>
                            <td style={{ padding: '8px 14px', fontWeight: 500, color: 'var(--fg-1)' }}>
                              <Link to={`/objects/${obj.id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                                {objTitle}
                              </Link>
                            </td>
                            <td style={{ padding: '8px 14px', color: 'var(--fg-3)', fontSize: 12 }}>
                              {obj.status}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </main>
        </div>
      </div>
    </>
  )
}
