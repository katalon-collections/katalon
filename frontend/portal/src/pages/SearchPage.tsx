import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, BASE, PORTAL_API, type FacetBucket, type SearchResponse, type MediaFile } from '../api/client'
import { saveLastSearch } from '../hooks/useBackToSearch'
import { t, typeLabel, useI18n } from '../i18n'

function facetLabel(field: string): string {
  const inherited = field.match(/^inherited_(object|entity|place|occurrence|procedure)_(.+)$/)
  return inherited ? t('search.linkedFacet', { type: typeLabel(inherited[1]), field: inherited[2] }) : field
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const typeFilt = params.get('type') ?? ''
  const statusFilt = params.get('status') ?? ''
  const page = parseInt(params.get('page') ?? '1', 10)
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [facetConfig, setFacetConfig] = useState<Record<string, string[]>>({})
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const { t } = useI18n()

  // Load configurable facet fields from portal config
  useEffect(() => {
    api.portal.config()
      .then(c => setFacetConfig(c.facet_fields ?? {}))
      .catch(() => {})
  }, [])

  // Collect active meta_ filters from URL
  const metaFilters: Record<string, string> = {}
  params.forEach((value, key) => {
    if (key.startsWith('meta_')) metaFilters[key.slice(5)] = value
  })
  const relEntity = params.get('rel_entity') ?? ''
  const relPlace = params.get('rel_place') ?? ''
  const relOccurrence = params.get('rel_occurrence') ?? ''

  useEffect(() => {
    setLoading(true)
    const searchParams: Record<string, string | number | undefined> = {
      q: q || undefined,
      type: typeFilt || undefined,
      status: statusFilt || undefined,
      page,
      page_size: 20,
      facets: (() => {
        const fields = typeFilt ? (facetConfig[typeFilt] ?? []) : Object.values(facetConfig).flat()
        const unique = [...new Set(fields)]
        return unique.length > 0 ? unique.join(',') : undefined
      })(),
      rel_entity: relEntity || undefined,
      rel_place: relPlace || undefined,
      rel_occurrence: relOccurrence || undefined,
    }
    // Pass meta_ filters as extra query params
    const qs = new URLSearchParams(
      Object.entries({ ...searchParams, ...Object.fromEntries(Object.entries(metaFilters).map(([k, v]) => [`meta_${k}`, v])) })
        .filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ).toString()
    fetch(`${BASE}${PORTAL_API}/search?${qs}`)
      .then(r => r.json())
      .then(async (result: SearchResponse) => {
        setData(result)
        // Load thumbnails for object results
        const thumbMap: Record<string, string> = {}
        await Promise.all(
          result.items
            .filter(r => r.record_type === 'object')
            .map(r =>
              api.objects.media(r.id)
                .then(media => {
                  const ready = media.filter((m: MediaFile) => m.status === 'ready')
                  const primary = ready.find((m: MediaFile) => m.is_primary) ?? ready[0]
                  if (primary) {
                    thumbMap[r.id] = `${BASE}${PORTAL_API}/objects/${r.id}/media/${primary.id}/file`
                  }
                })
                .catch(() => {})
            )
        )
        setThumbnails(thumbMap)
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [q, typeFilt, statusFilt, page, JSON.stringify(facetConfig), JSON.stringify(metaFilters), relEntity, relPlace, relOccurrence])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (localQ.trim()) navigate(`/search?q=${encodeURIComponent(localQ.trim())}`)
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.set('page', '1')
    setParams(next)
  }

  function setMetaFilter(field: string, value: string) {
    const key = `meta_${field}`
    setFilter(key, value)
  }

  function setRelFilter(paramKey: string, value: string) {
    setFilter(paramKey, value)
  }

  function setPage(n: number) {
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  const total = data?.total ?? 0
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1
  const typesFacet: FacetBucket[] = data?.facets?.['by_type'] ?? []
  const statusFacet: FacetBucket[] = data?.facets?.['by_status'] ?? []

  function FacetPanel({ label, buckets, active, onSelect }: {
    label: string
    buckets: FacetBucket[]
    active: string
    onSelect: (v: string) => void
  }) {
    if (!buckets.length) return null
    return (
      <div style={{ marginBottom: 20 }}>
        <h3>{label}</h3>
        <button
          type="button"
          className="facet-item"
          onClick={() => onSelect('')}
          aria-pressed={!active}
          style={{ fontWeight: !active ? 600 : undefined }}
        >
          <span>{t('search.all')}</span>
        </button>
        {buckets.map(b => (
          <button
            type="button"
            key={b.value}
            className="facet-item"
            onClick={() => onSelect(b.value)}
            aria-pressed={active === b.value}
            style={{ fontWeight: active === b.value ? 600 : undefined }}
          >
            <span>{typeLabel(b.value)}</span>
            <span className="ct">{b.count}</span>
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="container page">
      <form onSubmit={submit} className="refine-search" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          aria-label={t('search.refine')}
          style={{ flex: 1, width: '100%', boxSizing: 'border-box', background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 14px', fontSize: 14, outline: 'none', color: 'var(--fg)' }}
          value={localQ}
          onChange={e => setLocalQ(e.target.value)}
          placeholder={t('search.refine')}
        />
        <button type="submit" style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '0 18px', fontWeight: 600, fontSize: 13 }}>
          {t('search.button')}
        </button>
      </form>
      <div style={{ color: 'var(--fg-3)', fontSize: 13, marginBottom: 4 }}>
        {loading
          ? t('search.searching')
          : <>
              {t('search.results', { count: total })}
              {q ? t('search.resultsFor', { q }) : ''}
              {typeFilt ? t('search.resultsType', { type: typeLabel(typeFilt) }) : t('search.resultsAllTypes')}
            </>}
      </div>

      <div className="search-layout">
        <aside className="facets">
          <FacetPanel
            label={t('search.typeFacet')}
            buckets={typesFacet}
            active={typeFilt}
            onSelect={v => setFilter('type', v)}
          />
          <FacetPanel
            label={t('search.statusFacet')}
            buckets={statusFacet}
            active={statusFilt}
            onSelect={v => setFilter('status', v)}
          />
          {(typeFilt ? (facetConfig[typeFilt] ?? []) : [...new Set(Object.values(facetConfig).flat())]).map(field => {
            const buckets = data?.facets?.[`meta_${field}`] ?? []
            return (
              <FacetPanel
                key={field}
                label={facetLabel(field)}
                buckets={buckets}
                active={metaFilters[field] ?? ''}
                onSelect={v => setMetaFilter(field, v)}
              />
            )
          })}
          {(!typeFilt || typeFilt === 'object') && (
            <>
              <FacetPanel
                label={t('search.relatedEntities')}
                buckets={data?.facets?.['related_entities'] ?? []}
                active={relEntity}
                onSelect={v => setRelFilter('rel_entity', v)}
              />
              <FacetPanel
                label={t('search.relatedPlaces')}
                buckets={data?.facets?.['related_places'] ?? []}
                active={relPlace}
                onSelect={v => setRelFilter('rel_place', v)}
              />
              <FacetPanel
                label={t('search.relatedOccurrences')}
                buckets={data?.facets?.['related_occurrences'] ?? []}
                active={relOccurrence}
                onSelect={v => setRelFilter('rel_occurrence', v)}
              />
            </>
          )}
        </aside>

        <div className="result-list">
          {loading && <div style={{ padding: 24, color: 'var(--fg-3)' }}>{t('common.loading')}</div>}
          {!loading && data?.items.length === 0 && (
            <div style={{ padding: 24, color: 'var(--fg-3)' }}>{t('search.noResultsShort')}</div>
          )}
          {!loading && data?.items.map(r => {
            const path = r.record_type === 'entity' ? `/entities/${r.id}`
              : r.record_type === 'place' ? `/places/${r.id}`
              : r.record_type === 'occurrence' ? `/occurrences/${r.id}`
              : `/objects/${r.id}`
            return (
              <Link key={r.id} className="result-row" to={path} onClick={() => saveLastSearch(window.location.pathname + window.location.search)}>
                <div className="thumb-sm">
                  {thumbnails[r.id] ? (
                    <img src={thumbnails[r.id]} alt="" loading="lazy" />
                  ) : null}
                </div>
                <div className="body">
                  <div className="title">{r.title || r.id}</div>
                  <div className="desc">
                    {typeLabel(r.record_type)} · {r.status ?? '—'}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {totalPages > 1 && (
        <nav className="pagination" aria-label={t('search.pagination')}>
          {(() => {
            const pages: (number | '...')[] = []
            const add = (n: number) => { if (!pages.includes(n)) pages.push(n) }
            for (let i = 1; i <= Math.min(2, totalPages); i++) add(i)
            for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) add(i)
            for (let i = Math.max(1, totalPages - 1); i <= totalPages; i++) add(i)
            const withEllipsis: (number | '...')[] = []
            pages.sort((a, b) => (a as number) - (b as number)).forEach((n, i) => {
              if (i > 0 && (n as number) - (pages[i - 1] as number) > 1) withEllipsis.push('...')
              withEllipsis.push(n)
            })
            return withEllipsis.map((n, i) =>
              n === '...'
                ? <span key={`e${i}`} className="page-ellipsis">…</span>
                : <button key={n} className={`page-btn${n === page ? ' active' : ''}`} aria-current={n === page ? 'page' : undefined} onClick={() => setPage(n as number)}>{n}</button>
            )
          })()}
        </nav>
      )}
    </div>
  )
}
