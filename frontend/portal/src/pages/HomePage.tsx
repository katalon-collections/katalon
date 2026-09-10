// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, mediaThumbnailUrl, type ObjectSummary, type PortalConfig, type MediaFile } from '../api/client'
import { recordTitle } from '../utils/renderFieldValue'
import { useI18n } from '../i18n'

const DEFAULT_CONFIG: PortalConfig = {
  site_title: 'Sammlung',
  site_subtitle: '',
  hero_text: 'Fotografien, Dokumente, Objekte und Personen aus dem Archiv',
  featured_object_ids: [],
  facet_fields: {},
  subtitle_fields: {},
  browse_enabled_types: ['object', 'entity', 'place', 'occurrence'],
  accent_color: '#1e3a8a',
  logo_url: '',
  placeholder_image_url: '',
  color_tokens: {},
  supported_languages: ['de', 'en'],
  detail_sidebar_position: 'right',
  facet_sort: 'count',
  facet_initial_count: 10,
}

export function HomePage() {
  const [q, setQ] = useState('')
  const [config, setConfig] = useState<PortalConfig>(DEFAULT_CONFIG)
  const [featured, setFeatured] = useState<ObjectSummary[]>([])
  const [recent, setRecent] = useState<ObjectSummary[]>([])
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { t, locale } = useI18n()

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
        const allObjects = d.items.filter(o => !featuredIds.includes(o.id))
        setRecent(allObjects)
        // Load thumbnails for all visible objects
        const thumbMap: Record<string, string> = {}
        await Promise.all(
          [...featuredItems, ...allObjects].map(obj =>
            api.objects.media(obj.id)
              .then(media => {
                const ready = media.filter((m: MediaFile) => m.status === 'ready')
                const primary = ready.find((m: MediaFile) => m.is_primary) ?? ready[0]
                if (primary) {
                  thumbMap[obj.id] = mediaThumbnailUrl(obj.id, primary.id)
                }
              })
              .catch(() => {})
          )
        )
        setThumbnails(thumbMap)
        setLoading(false)
      })
  }, [])

  function search(e: React.FormEvent) {
    e.preventDefault()
    navigate(`/search?q=${encodeURIComponent(q.trim())}`)
  }

  function objTitle(obj: ObjectSummary) {
    const m = obj.metadata_ as Record<string, unknown>
    return recordTitle(m, locale, obj.idno ?? obj.id)
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
              placeholder={t('home.searchPlaceholder')}
              value={q}
              onChange={e => setQ(e.target.value)}
              autoFocus
            />
            <button type="submit">{t('home.searchButton')}</button>
          </form>
        </div>
      </div>

      <div className="container page">
        {featured.length > 0 && (
          <>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 0, color: 'var(--fg-2)' }}>
              {t('home.highlights')}
            </h2>
            <div className="obj-grid">
              {featured.map(obj => (
                <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
                  <div className="thumb">
                    {thumbnails[obj.id] ? (
                      <img src={thumbnails[obj.id]} alt="" loading="lazy" />
                    ) : null}
                  </div>
                  <div className="info">
                    <div className="title">{objTitle(obj)}</div>
                    {objSub(obj) && <div className="meta">{objSub(obj)}</div>}
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}

        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 0, marginTop: featured.length > 0 ? 32 : 0, color: 'var(--fg-2)' }}>
          {t('home.recent')}
        </h2>

        {loading && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>{t('common.loading')}</div>
        )}

        {!loading && recent.length === 0 && featured.length === 0 && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>
            {t('home.noObjects')}
          </div>
        )}

        {!loading && recent.length > 0 && (
          <div className="obj-grid">
            {recent.map(obj => (
              <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
                <div className="thumb">
                  {thumbnails[obj.id] ? (
                    <img src={thumbnails[obj.id]} alt="" loading="lazy" />
                  ) : null}
                </div>
                <div className="info">
                  <div className="title">{objTitle(obj)}</div>
                  {objSub(obj) && <div className="meta">{objSub(obj)}</div>}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
