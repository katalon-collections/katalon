// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, mediaThumbnailUrl, type ObjectSummary, type CollectionSummary, type PortalConfig, type HomepageBlock, type MediaFile } from '../api/client'
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
  homepage_blocks: [],
  terminology: {},
}

function objTitle(obj: ObjectSummary, locale: string) {
  const m = obj.metadata_ as Record<string, unknown>
  return recordTitle(m, locale, obj.idno ?? obj.id)
}
function objSub(obj: ObjectSummary) {
  const m = obj.metadata_ as Record<string, unknown>
  return [String(m.creator ?? m.photographer ?? ''), String(m.year ?? m.date ?? '')].filter(Boolean).join(' · ')
}

function BlockHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{ fontSize: 16, fontWeight: 600, margin: '32px 0 0', color: 'var(--fg-2)' }}>{children}</h2>
  )
}

function ObjectGrid({ objects, thumbnails, locale }: { objects: ObjectSummary[]; thumbnails: Record<string, string>; locale: string }) {
  return (
    <div className="obj-grid">
      {objects.map(obj => (
        <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
          <div className="thumb">
            {thumbnails[obj.id] ? <img src={thumbnails[obj.id]} alt="" loading="lazy" /> : null}
          </div>
          <div className="info">
            <div className="title">{objTitle(obj, locale)}</div>
            {objSub(obj) && <div className="meta">{objSub(obj)}</div>}
          </div>
        </Link>
      ))}
    </div>
  )
}

function CollectionGrid({ collections, locale }: { collections: CollectionSummary[]; locale: string }) {
  const { t } = useI18n()
  return (
    <div className="obj-grid">
      {collections.map(col => {
        const m = col.metadata_ as Record<string, unknown>
        return (
          <Link key={col.id} className="obj-card" to={`/collections/${col.id}`}>
            <div className="info">
              <div className="title">{recordTitle(m, locale, col.idno ?? col.id)}</div>
              <div className="meta">{col.collection_type || t('type.collection')}</div>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

function TextBlock({ block, locale }: { block: HomepageBlock; locale: string }) {
  const content = block.content ?? {}
  const text = content[locale] ?? Object.values(content)[0] ?? ''
  if (!text) return null
  return <p style={{ whiteSpace: 'pre-wrap', color: 'var(--fg-2)', lineHeight: 1.6 }}>{text}</p>
}

function blockTitle(block: HomepageBlock, locale: string, fallback: string): string {
  return block.title?.[locale] ?? Object.values(block.title ?? {})[0] ?? fallback
}

export function HomePage() {
  const [q, setQ] = useState('')
  const [config, setConfig] = useState<PortalConfig>(DEFAULT_CONFIG)
  const [curated, setCurated] = useState<ObjectSummary[]>([])
  const [recent, setRecent] = useState<ObjectSummary[]>([])
  const [collectionsByBlock, setCollectionsByBlock] = useState<Record<string, CollectionSummary[]>>({})
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
        const blocks = c.homepage_blocks.filter(b => b.enabled)
        const curatedBlock = blocks.find(b => b.type === 'curated')
        const objectsBlock = blocks.find(b => b.type === 'objects')
        const collectionBlocks = blocks.filter(b => b.type === 'collections')

        const curatedIds = curatedBlock ? (c.featured_object_ids ?? []).slice(0, curatedBlock.limit ?? 100) : []
        const curatedItems: ObjectSummary[] = []
        await Promise.all(
          curatedIds.map(id => api.objects.get(id).then(o => curatedItems.push(o)).catch(() => {}))
        )
        setCurated(curatedItems)

        let recentItems: ObjectSummary[] = []
        if (objectsBlock) {
          const d = await api.objects.list({ page_size: objectsBlock.limit ?? 12 }).catch(() => ({ items: [] as ObjectSummary[] }))
          recentItems = d.items.filter(o => !curatedIds.includes(o.id))
          setRecent(recentItems)
        }

        await Promise.all(
          collectionBlocks.map(async block => {
            const mode = block.collections_mode ?? 'top'
            const limit = block.limit ?? 12
            try {
              if (mode === 'selected' && block.collection_ids?.length) {
                const items: CollectionSummary[] = []
                await Promise.all(
                  block.collection_ids.slice(0, limit).map(id =>
                    api.collections.get(id).then(c2 => items.push(c2)).catch(() => {})
                  )
                )
                setCollectionsByBlock(prev => ({ ...prev, [block.id]: items }))
              } else {
                const res = await api.collections.list({ page_size: limit, top_level: mode !== 'all' })
                setCollectionsByBlock(prev => ({ ...prev, [block.id]: res.items }))
              }
            } catch {
              setCollectionsByBlock(prev => ({ ...prev, [block.id]: [] }))
            }
          })
        )

        // Load thumbnails for all visible objects
        const thumbMap: Record<string, string> = {}
        await Promise.all(
          [...curatedItems, ...recentItems].map(obj =>
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

  const blocks = config.homepage_blocks.filter(b => b.enabled)
  const nothingToShow = !loading && blocks.length > 0 &&
    blocks.every(b => {
      if (b.type === 'curated') return curated.length === 0
      if (b.type === 'objects') return recent.length === 0
      if (b.type === 'collections') return (collectionsByBlock[b.id] ?? []).length === 0
      return !(b.content && Object.values(b.content).some(Boolean))
    })

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
        {loading && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>{t('common.loading')}</div>
        )}

        {!loading && blocks.length === 0 && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>{t('home.noObjects')}</div>
        )}

        {!loading && nothingToShow && (
          <div style={{ marginTop: 32, color: 'var(--fg-3)', fontSize: 14 }}>{t('home.noObjects')}</div>
        )}

        {!loading && blocks.map(block => {
          if (block.type === 'text') {
            const text = block.content?.[locale] ?? Object.values(block.content ?? {})[0]
            if (!text) return null
            return (
              <div key={block.id}>
                {block.title && Object.values(block.title).some(Boolean) && (
                  <BlockHeading>{blockTitle(block, locale, '')}</BlockHeading>
                )}
                <TextBlock block={block} locale={locale} />
              </div>
            )
          }
          if (block.type === 'curated' && curated.length > 0) {
            return (
              <div key={block.id}>
                <BlockHeading>{blockTitle(block, locale, t('home.highlights'))}</BlockHeading>
                <ObjectGrid objects={curated} thumbnails={thumbnails} locale={locale} />
              </div>
            )
          }
          if (block.type === 'objects' && recent.length > 0) {
            return (
              <div key={block.id}>
                <BlockHeading>{blockTitle(block, locale, t('home.recent'))}</BlockHeading>
                <ObjectGrid objects={recent} thumbnails={thumbnails} locale={locale} />
              </div>
            )
          }
          if (block.type === 'collections') {
            const items = collectionsByBlock[block.id] ?? []
            if (items.length === 0) return null
            return (
              <div key={block.id}>
                <BlockHeading>{blockTitle(block, locale, t('nav.collections'))}</BlockHeading>
                <CollectionGrid collections={items} locale={locale} />
              </div>
            )
          }
          return null
        })}
      </div>
    </>
  )
}
