// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, type CollectionSummary, type Page } from '../api/client'
import { recordTitle, renderFieldValue } from '../utils/renderFieldValue'
import { useI18n } from '../i18n'

export function CollectionsPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { t, locale } = useI18n()

  const q = params.get('q') ?? ''
  const page = parseInt(params.get('page') ?? '1', 10)

  const [collectionsPage, setCollectionsPage] = useState<Page<CollectionSummary> | null>(null)
  const [loading, setLoading] = useState(true)
  const [localQ, setLocalQ] = useState(q)

  useEffect(() => {
    setLoading(true)
    api.collections
      .list({
        page,
        page_size: 24,
        q: q || undefined,
      })
      .then(res => {
        setCollectionsPage(res)
      })
      .catch(() => {
        setCollectionsPage(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [q, page])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const next = new URLSearchParams(params)
    if (localQ.trim()) {
      next.set('q', localQ.trim())
    } else {
      next.delete('q')
    }
    next.set('page', '1')
    setParams(next)
  }

  const items = collectionsPage?.items ?? []
  const total = collectionsPage?.total ?? 0
  const totalPages = Math.ceil(total / 24)

  // Group top-level vs sub-collections
  const topLevel = items.filter(c => !c.parent_id)
  const subCollections = items.filter(c => Boolean(c.parent_id))

  return (
    <>
      <Helmet>
        <title>{t('nav.collectionsLong')}</title>
      </Helmet>

      <div className="container page collections-overview-page">
        {/* Header & Suchleiste */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 6 }}>
            {t('nav.collectionsLong')}
          </div>
          <h1 style={{ fontSize: 32, fontWeight: 700, margin: '0 0 12px', color: 'var(--fg-1)' }}>
            {t('nav.collections')}
          </h1>
          <p style={{ fontSize: 16, color: 'var(--fg-2)', maxWidth: 700, margin: '0 0 24px', lineHeight: 1.5 }}>
            Bestände, Nachlässe und kuratierte Sammlungspräsentationen der Institution durchstöbern.
          </p>

          <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, maxWidth: 500 }}>
            <input
              type="text"
              className="search-input"
              style={{ flex: 1, padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)' }}
              placeholder={t('search.placeholder')}
              value={localQ}
              onChange={e => setLocalQ(e.target.value)}
            />
            <button type="submit" className="button" style={{ padding: '10px 20px', borderRadius: 8 }}>
              {t('search.button')}
            </button>
          </form>
        </div>

        {/* Listen / Raster der Sammlungen */}
        {loading ? (
          <div style={{ color: 'var(--fg-3)', padding: '32px 0' }}>{t('common.loading')}</div>
        ) : items.length === 0 ? (
          <div
            style={{
              padding: 48,
              textAlign: 'center',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 12,
              color: 'var(--fg-3)',
            }}
          >
            {t('search.noResultsShort')}
          </div>
        ) : (
          <div>
            {/* Wenn keine Suche aktiv ist, gruppieren wir nach Hauptbeständen und Teilbeständen */}
            {!q && topLevel.length > 0 && (
              <section style={{ marginBottom: 40 }}>
                <h2 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 16px', color: 'var(--fg-1)' }}>
                  Hauptbestände ({topLevel.length})
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
                  {topLevel.map(col => {
                    const m = col.metadata_ as Record<string, unknown>
                    const title = recordTitle(m, locale, col.idno ?? col.id)
                    const desc = renderFieldValue(m.description || m.kurzbeschreibung, locale)
                    const scope = renderFieldValue(m.scope_and_content || m.bestandsumfang, locale)

                    return (
                      <Link
                        key={col.id}
                        to={`/collections/${col.id}`}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          padding: '24px 20px',
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border)',
                          borderRadius: 12,
                          textDecoration: 'none',
                          color: 'inherit',
                          transition: 'transform 0.15s, box-shadow 0.15s, border-color 0.15s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.transform = 'translateY(-2px)'
                          e.currentTarget.style.borderColor = 'var(--accent)'
                          e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.06)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.transform = 'none'
                          e.currentTarget.style.borderColor = 'var(--border)'
                          e.currentTarget.style.boxShadow = 'none'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--accent)' }}>
                              📁 {col.collection_type || t('type.collection')}
                            </span>
                            {col.idno && (
                              <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--fg-3)' }}>
                                {col.idno}
                              </span>
                            )}
                          </div>
                          <h3 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 10px', color: 'var(--fg-1)', lineHeight: 1.3 }}>
                            {title}
                          </h3>
                          {desc && (
                            <p style={{ fontSize: 14, color: 'var(--fg-2)', lineHeight: 1.5, margin: '0 0 12px', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                              {desc}
                            </p>
                          )}
                          {scope && (
                            <div style={{ fontSize: 12, color: 'var(--fg-3)', fontStyle: 'italic', marginBottom: 12 }}>
                              {scope}
                            </div>
                          )}
                        </div>

                        <div style={{ paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 13, color: 'var(--accent)', fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span>Sammlung ansehen →</span>
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </section>
            )}

            {/* Teilbestände & Serien */}
            {(!q ? subCollections : items).length > 0 && (
              <section>
                {!q && topLevel.length > 0 && (
                  <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 16px', color: 'var(--fg-1)' }}>
                    Teilbestände & Unterserien ({subCollections.length})
                  </h2>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                  {(!q ? subCollections : items).map(col => {
                    const m = col.metadata_ as Record<string, unknown>
                    const title = recordTitle(m, locale, col.idno ?? col.id)
                    const desc = renderFieldValue(m.description || m.kurzbeschreibung, locale)

                    return (
                      <Link
                        key={col.id}
                        to={`/collections/${col.id}`}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          padding: 16,
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          textDecoration: 'none',
                          color: 'inherit',
                          transition: 'border-color 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)' }}>
                              📂 {col.collection_type || t('type.collection')}
                            </span>
                            {col.idno && (
                              <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'monospace' }}>
                                {col.idno}
                              </span>
                            )}
                          </div>
                          <h4 style={{ fontSize: 15, fontWeight: 600, margin: '4px 0 8px', color: 'var(--fg-1)' }}>
                            {title}
                          </h4>
                          {desc && (
                            <p style={{ fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.4, margin: '0 0 8px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                              {desc}
                            </p>
                          )}
                        </div>
                        <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, marginTop: 8 }}>
                          Details ansehen →
                        </span>
                      </Link>
                    )
                  })}
                </div>
              </section>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 32 }}>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    type="button"
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--border)',
                      background: p === page ? 'var(--accent)' : 'var(--bg-card)',
                      color: p === page ? '#fff' : 'var(--fg-2)',
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      const next = new URLSearchParams(params)
                      next.set('page', String(p))
                      setParams(next)
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
