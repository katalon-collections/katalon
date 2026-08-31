import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, BASE, mediaThumbnailUrl, PORTAL_API, type FacetBucket, type SearchResponse, type MediaFile } from '../api/client'
import { saveLastSearch } from '../hooks/useBackToSearch'
import { useFieldLabels } from '../hooks/useFieldLabels'
import { t, typeLabel, useI18n } from '../i18n'
import { decodeAdvancedQuery } from '../utils/advancedSearch'
import { QuerySummary } from './AdvancedSearchPage'

function facetLabel(
  field: string,
  labels: Record<string, Record<string, { label: string }>>,
  config: Record<string, string[]>,
  recordType: string,
): string {
  const inherited = field.match(/^inherited_(object|entity|place|occurrence|procedure)_(.+)$/)
  if (inherited) {
    return t('search.linkedFacet', {
      type: typeLabel(inherited[1]),
      field: labels[inherited[1]]?.[inherited[2]]?.label ?? inherited[2],
    })
  }
  const owner = recordType || Object.entries(config)
    .find(([type, fields]) => type !== '_system' && fields.includes(field))?.[0]
  return (owner ? labels[owner]?.[field]?.label : undefined) ?? field
}

const DEFAULT_SUBTITLE_FIELDS = ['record_type', 'status']
const DEFAULT_SYSTEM_FACETS = ['record_type', 'status']

function configuredMetadataFacets(config: Record<string, string[]>, recordType: string): string[] {
  const fields = recordType
    ? (config[recordType] ?? [])
    : Object.entries(config).filter(([key]) => key !== '_system').flatMap(([, values]) => values)
  return [...new Set(fields)]
}

function isNumericFacet(
  field: string,
  labels: Record<string, Record<string, { field_type: string }>>,
  config: Record<string, string[]>,
  recordType: string,
): boolean {
  const owners = recordType
    ? [recordType]
    : Object.entries(config).filter(([type, fields]) => type !== '_system' && fields.includes(field)).map(([type]) => type)
  return owners.length > 0 && owners.every(owner => labels[owner]?.[field]?.field_type === 'number')
}

function NumericFacetPanel({ label, bounds, from, to, onChange }: {
  label: string
  bounds: { min: number; max: number } | undefined
  from: string
  to: string
  onChange: (from: string, to: string) => void
}) {
  const { t } = useI18n()
  if (!bounds) return null
  const lower = Number(from || bounds.min)
  const upper = Number(to || bounds.max)
  return (
    <div className="numeric-facet">
      <h3>{label}</h3>
      <div className="numeric-facet-inputs">
        <input aria-label={`${label}: ${t('advanced.from')}`} type="number" value={from} placeholder={t('advanced.from')} onChange={event => onChange(event.target.value, to)} />
        <input aria-label={`${label}: ${t('advanced.to')}`} type="number" value={to} placeholder={t('advanced.to')} onChange={event => onChange(from, event.target.value)} />
      </div>
      <input aria-label={`${label}: ${t('advanced.from')} slider`} type="range" min={bounds.min} max={bounds.max} step="any" value={Math.min(lower, upper)} onChange={event => onChange(event.target.value, to && Number(event.target.value) > Number(to) ? event.target.value : to)} />
      <input aria-label={`${label}: ${t('advanced.to')} slider`} type="range" min={bounds.min} max={bounds.max} step="any" value={Math.max(lower, upper)} onChange={event => onChange(from && Number(event.target.value) < Number(from) ? event.target.value : from, event.target.value)} />
      {(from || to) && <button type="button" className="facet-reset" onClick={() => onChange('', '')}>{t('search.all')}</button>}
    </div>
  )
}

function resultSubtitle(
  r: { record_type: string; status: string | null; subtitle_values?: Record<string, string | string[]> | null },
  subtitleConfig: Record<string, string[]>
): string {
  const fields = subtitleConfig[r.record_type]?.length ? subtitleConfig[r.record_type] : DEFAULT_SUBTITLE_FIELDS
  return fields
    .map(field => {
      if (field === 'record_type') return typeLabel(r.record_type)
      if (field === 'status') return r.status ?? '—'
      const value = r.subtitle_values?.[field]
      return value == null ? null : Array.isArray(value) ? value.join(', ') : value
    })
    .filter((v): v is string => !!v)
    .join(' · ')
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const typeFilt = params.get('type') ?? ''
  const statusFilt = params.get('status') ?? ''
  const encodedAdvancedQuery = params.get('aq') ?? ''
  const advancedQuery = decodeAdvancedQuery(encodedAdvancedQuery)
  const effectiveType = advancedQuery?.record_type ?? typeFilt
  const page = parseInt(params.get('page') ?? '1', 10)
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [facetConfig, setFacetConfig] = useState<Record<string, string[]>>({ _system: DEFAULT_SYSTEM_FACETS })
  const [subtitleConfig, setSubtitleConfig] = useState<Record<string, string[]>>({})
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const { locale, t } = useI18n()
  const facetTypesKey = [...new Set(
    Object.entries(facetConfig)
      .filter(([type]) => type !== '_system')
      .flatMap(([type, fields]) => [
        type,
        ...fields.flatMap(field => {
          const inherited = field.match(/^inherited_(object|entity|place|occurrence|procedure)_/)
          return inherited ? [inherited[1]] : []
        }),
      ])
  )].sort().join(',')
  const fieldLabels = useFieldLabels(facetTypesKey, locale)

  // Load configurable facet + result-subtitle fields from portal config
  useEffect(() => {
    api.portal.config()
      .then(c => {
        setFacetConfig(c.facet_fields ?? {})
        setSubtitleConfig(c.subtitle_fields ?? {})
      })
      .catch(() => {})
  }, [])

  // Collect active meta_ filters from URL
  const metaFilters: Record<string, string[]> = {}
  const numericFilters: Record<string, { from: string; to: string }> = {}
  params.forEach((value, key) => {
    if (key.startsWith('meta_')) {
      const field = key.slice(5)
      if (!metaFilters[field]?.includes(value)) metaFilters[field] = [...(metaFilters[field] ?? []), value]
    }
    if (key.startsWith('range_') && key.endsWith('_from')) {
      numericFilters[key.slice(6, -5)] = { ...(numericFilters[key.slice(6, -5)] ?? { from: '', to: '' }), from: value }
    }
    if (key.startsWith('range_') && key.endsWith('_to')) {
      numericFilters[key.slice(6, -3)] = { ...(numericFilters[key.slice(6, -3)] ?? { from: '', to: '' }), to: value }
    }
  })
  const relEntity = params.get('rel_entity') ?? ''
  const relPlace = params.get('rel_place') ?? ''
  const relOccurrence = params.get('rel_occurrence') ?? ''

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    const systemFacets = facetConfig._system ?? DEFAULT_SYSTEM_FACETS
    const searchParams: Record<string, string | number | undefined> = {
      q: q || undefined,
      type: systemFacets.includes('record_type') ? (typeFilt || undefined) : undefined,
      status: systemFacets.includes('status') ? (statusFilt || undefined) : undefined,
      page,
      page_size: 20,
      facets: (() => {
        const fields = configuredMetadataFacets(facetConfig, effectiveType)
        return fields.length > 0 ? fields.join(',') : undefined
      })(),
      rel_entity: relEntity || undefined,
      rel_place: relPlace || undefined,
      rel_occurrence: relOccurrence || undefined,
    }
    // Pass meta_ filters as extra query params
    const qs = new URLSearchParams(
      Object.entries(searchParams)
        .filter(([, value]) => value != null)
        .map(([key, value]) => [key, String(value)])
    )
    Object.entries(metaFilters).forEach(([field, values]) => {
      values.forEach(value => qs.append(`meta_${field}`, value))
    })
    Object.entries(numericFilters).forEach(([field, range]) => {
      if (range.from) qs.set(`range_${field}_from`, range.from)
      if (range.to) qs.set(`range_${field}_to`, range.to)
    })
    const request = encodedAdvancedQuery
      ? advancedQuery
        ? api.search.advanced({
            query: advancedQuery,
            q: q || undefined,
            page,
            page_size: 20,
            facet_fields: configuredMetadataFacets(facetConfig, advancedQuery.record_type),
            metadata_filters: metaFilters,
            numeric_filters: Object.fromEntries(Object.entries(numericFilters).map(([field, range]) => [field, {
              ...(range.from ? { from: Number(range.from) } : {}),
              ...(range.to ? { to: Number(range.to) } : {}),
            }])),
            relation_filters: {
              related_entities: relEntity,
              related_places: relPlace,
              related_occurrences: relOccurrence,
            },
          })
        : Promise.reject(new Error(t('advanced.invalidLink')))
      : fetch(`${BASE}${PORTAL_API}/search?${qs.toString()}`).then(r => {
          if (!r.ok) throw new Error(r.statusText)
          return r.json() as Promise<SearchResponse>
        })
    request
      .then(async (result: SearchResponse) => {
        if (cancelled) return
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
                    thumbMap[r.id] = mediaThumbnailUrl(r.id, primary.id)
                  }
                })
                .catch(() => {})
            )
        )
        if (!cancelled) setThumbnails(thumbMap)
      })
      .catch(reason => {
        if (!cancelled) {
          setData(null)
          setError(reason instanceof Error ? reason.message : t('advanced.searchFailed'))
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [q, typeFilt, statusFilt, encodedAdvancedQuery, page, JSON.stringify(facetConfig), JSON.stringify(metaFilters), JSON.stringify(numericFilters), relEntity, relPlace, relOccurrence])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const next = new URLSearchParams(params)
    const term = localQ.trim()
    if (term) next.set('q', term)
    else next.delete('q')
    next.set('page', '1')
    setParams(next)
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.set('page', '1')
    setParams(next)
  }

  function toggleMetaFilter(field: string, value: string) {
    const key = `meta_${field}`
    const next = new URLSearchParams(params)
    const selected = next.getAll(key)
    next.delete(key)
    selected.filter(current => current !== value).forEach(current => next.append(key, current))
    if (!selected.includes(value)) next.append(key, value)
    next.set('page', '1')
    setParams(next)
  }

  function setNumericFilter(field: string, from: string, to: string) {
    const next = new URLSearchParams(params)
    const fromKey = `range_${field}_from`
    const toKey = `range_${field}_to`
    if (from) next.set(fromKey, from)
    else next.delete(fromKey)
    if (to) next.set(toKey, to)
    else next.delete(toKey)
    next.set('page', '1')
    setParams(next)
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
  const systemFacets = facetConfig._system ?? DEFAULT_SYSTEM_FACETS

  function FacetPanel({ label, buckets, active, onSelect }: {
    label: string
    buckets: FacetBucket[]
    active: string[]
    onSelect: (v: string) => void
  }) {
    if (!buckets.length) return null
    return (
      <div style={{ marginBottom: 20 }}>
        <h3>{label}</h3>
        {buckets.map(b => (
          <button
            type="button"
            key={b.value}
            className="facet-item"
            onClick={() => onSelect(b.value)}
            aria-pressed={active.includes(b.value)}
            style={{ fontWeight: active.includes(b.value) ? 600 : undefined }}
          >
            <span>{typeLabel(b.value)}</span>
            <span className="ct">{b.count}</span>
          </button>
        ))}
        {active.length > 0 && (
          <button type="button" className="facet-reset" onClick={() => onSelect('')}>
            {t('search.all')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="container page">
      {advancedQuery && (
        <div className="advanced-summary">
          <div className="advanced-summary-head">
            <span>{t('advanced.active', { type: typeLabel(advancedQuery.record_type) })}</span>
            <Link to={`/advanced-search?aq=${encodeURIComponent(encodedAdvancedQuery)}`}>{t('advanced.edit')}</Link>
          </div>
          <QuerySummary query={advancedQuery} />
        </div>
      )}
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
            </>}
      </div>

      <div className="search-layout">
        <aside className="facets">
          {!advancedQuery && systemFacets.includes('record_type') && (
            <FacetPanel
              label={t('search.typeFacet')}
              buckets={typesFacet}
              active={typeFilt ? [typeFilt] : []}
              onSelect={v => setFilter('type', v)}
            />
          )}
          {systemFacets.includes('status') && (
            <FacetPanel
              label={t('search.statusFacet')}
              buckets={statusFacet}
              active={statusFilt ? [statusFilt] : []}
              onSelect={v => setFilter('status', v)}
            />
          )}
          {configuredMetadataFacets(facetConfig, effectiveType).map(field => {
            const buckets = data?.facets?.[`meta_${field}`] ?? []
            const range = numericFilters[field] ?? { from: '', to: '' }
            if (isNumericFacet(field, fieldLabels, facetConfig, effectiveType)) {
              return <NumericFacetPanel key={field} label={facetLabel(field, fieldLabels, facetConfig, effectiveType)} bounds={data?.numeric_facets?.[field]} from={range.from} to={range.to} onChange={(from, to) => setNumericFilter(field, from, to)} />
            }
            return (
              <FacetPanel
                key={field}
                label={facetLabel(field, fieldLabels, facetConfig, effectiveType)}
                buckets={buckets}
                active={metaFilters[field] ?? []}
                onSelect={v => v ? toggleMetaFilter(field, v) : setFilter(`meta_${field}`, '')}
              />
            )
          })}
          {(!effectiveType || effectiveType === 'object') && (
            <>
              <FacetPanel
                label={t('search.relatedEntities')}
                buckets={data?.facets?.['related_entities'] ?? []}
                active={relEntity ? [relEntity] : []}
                onSelect={v => setRelFilter('rel_entity', v)}
              />
              <FacetPanel
                label={t('search.relatedPlaces')}
                buckets={data?.facets?.['related_places'] ?? []}
                active={relPlace ? [relPlace] : []}
                onSelect={v => setRelFilter('rel_place', v)}
              />
              <FacetPanel
                label={t('search.relatedOccurrences')}
                buckets={data?.facets?.['related_occurrences'] ?? []}
                active={relOccurrence ? [relOccurrence] : []}
                onSelect={v => setRelFilter('rel_occurrence', v)}
              />
            </>
          )}
        </aside>

        <div className="result-list">
          {error && <div className="advanced-error" role="alert">{error}</div>}
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
                {r.record_type === 'object' && (
                  <div className="thumb-sm">
                    {thumbnails[r.id] ? (
                      <img src={thumbnails[r.id]} alt="" loading="lazy" />
                    ) : null}
                  </div>
                )}
                <div className="body">
                  <div className="title">{r.title || r.id}</div>
                  <div className="desc">{resultSubtitle(r, subtitleConfig)}</div>
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
