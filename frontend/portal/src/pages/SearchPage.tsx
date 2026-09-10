// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, BASE, mediaThumbnailUrl, PORTAL_API, type FacetBucket, type SearchResponse } from '../api/client'
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
  const inherited = field.match(/^inherited_(object|entity|place|occurrence|collection|procedure)_(.+)$/)
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
// Relation-derived facets — see configuredMetadataFacets: included in the
// request field list, but rendered as dedicated panels below, not generic ones.
const RELATED_FACET_NAMES = ['related_entities', 'related_places', 'related_occurrences', 'related_collections']

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

function isBooleanFacet(
  field: string,
  labels: Record<string, Record<string, { field_type: string }>>,
  config: Record<string, string[]>,
  recordType: string,
): boolean {
  const owners = recordType
    ? [recordType]
    : Object.entries(config).filter(([type, fields]) => type !== '_system' && fields.includes(field)).map(([type]) => type)
  return owners.length > 0 && owners.every(owner => labels[owner]?.[field]?.field_type === 'boolean')
}

function NumericFacetPanel({ label, bounds, from, to, onChange }: {
  label: string
  bounds: { min: number; max: number } | undefined
  from: string
  to: string
  onChange: (from: string, to: string) => void
}) {
  const { t } = useI18n()
  const defaultFrom = bounds ? String(bounds.min) : ''
  const defaultTo = bounds ? String(bounds.max) : ''
  const [sliderRange, setSliderRange] = useState({ from: from || defaultFrom, to: to || defaultTo })
  const committedRange = useRef({ from, to })

  useEffect(() => {
    setSliderRange({ from: from || defaultFrom, to: to || defaultTo })
    committedRange.current = { from, to }
  }, [from, to, defaultFrom, defaultTo])

  if (!bounds) return null
  const sliderStep = Number.isInteger(bounds.min) && Number.isInteger(bounds.max) ? 1 : 'any'
  const lower = Number(sliderRange.from || bounds.min)
  const upper = Number(sliderRange.to || bounds.max)
  const normalizeRange = (range: { from: string; to: string }) => ({
    from: range.from === defaultFrom ? '' : range.from,
    to: range.to === defaultTo ? '' : range.to,
  })
  const commitSliderRange = () => {
    const nextRange = normalizeRange(sliderRange)
    if (nextRange.from === committedRange.current.from && nextRange.to === committedRange.current.to) return
    committedRange.current = nextRange
    onChange(nextRange.from, nextRange.to)
  }
  return (
    <div className="numeric-facet">
      <h3>{label}</h3>
      <div className="numeric-facet-inputs">
        <input aria-label={`${label}: ${t('advanced.from')}`} type="number" value={from || defaultFrom} onChange={event => onChange(event.target.value === defaultFrom ? '' : event.target.value, to)} />
        <input aria-label={`${label}: ${t('advanced.to')}`} type="number" value={to || defaultTo} onChange={event => onChange(from, event.target.value === defaultTo ? '' : event.target.value)} />
      </div>
      <div className="numeric-facet-slider">
        <input aria-label={`${label}: ${t('advanced.from')} slider`} className="numeric-facet-slider-lower" type="range" min={bounds.min} max={bounds.max} step={sliderStep} value={Math.min(lower, upper)} onChange={event => setSliderRange(range => ({ from: event.target.value, to: Number(event.target.value) > Number(range.to) ? event.target.value : range.to }))} onPointerUp={commitSliderRange} onBlur={commitSliderRange} />
        <input aria-label={`${label}: ${t('advanced.to')} slider`} className="numeric-facet-slider-upper" type="range" min={bounds.min} max={bounds.max} step={sliderStep} value={Math.max(lower, upper)} onChange={event => setSliderRange(range => ({ from: Number(event.target.value) < Number(range.from) ? event.target.value : range.from, to: event.target.value }))} onPointerUp={commitSliderRange} onBlur={commitSliderRange} />
      </div>
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

function FacetPanel({ label, buckets, active, onSelect, initialCount, translateBooleanValues = false }: {
  label: string
  buckets: FacetBucket[]
  active: string[]
  onSelect: (v: string) => void
  initialCount: number
  translateBooleanValues?: boolean
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  if (!buckets.length) return null
  const activeOnly = buckets.filter(b => active.includes(b.value) && !buckets.slice(0, initialCount).includes(b))
  const visible = expanded ? buckets : [...buckets.slice(0, initialCount), ...activeOnly]
  const hiddenCount = buckets.length - visible.length
  return (
    <div style={{ marginBottom: 20 }}>
      <h3>{label}</h3>
      {visible.map(b => (
        <button
          type="button"
          key={b.value}
          className="facet-item"
          onClick={() => onSelect(b.value)}
          aria-pressed={active.includes(b.value)}
          style={{ fontWeight: active.includes(b.value) ? 600 : undefined }}
        >
          <span>{translateBooleanValues && ['true', 'false'].includes(b.value.toLowerCase()) ? t(b.value.toLowerCase() === 'true' ? 'advanced.yes' : 'advanced.no') : typeLabel(b.value)}</span>
          <span className="ct">{b.count}</span>
        </button>
      ))}
      {hiddenCount > 0 && (
        <button type="button" className="facet-more" onClick={() => setExpanded(true)}>
          {t('search.showMore', { count: hiddenCount })}
        </button>
      )}
      {expanded && buckets.length > initialCount && (
        <button type="button" className="facet-more" onClick={() => setExpanded(false)}>
          {t('search.showLess')}
        </button>
      )}
      {active.length > 0 && (
        <button type="button" className="facet-reset" onClick={() => onSelect('')}>
          {t('search.all')}
        </button>
      )}
    </div>
  )
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const typeFilt = params.get('type') ?? ''
  const statusFilt = params.getAll('status')
  const encodedAdvancedQuery = params.get('aq') ?? ''
  const advancedQuery = decodeAdvancedQuery(encodedAdvancedQuery)
  const effectiveType = advancedQuery?.record_type ?? typeFilt
  const page = parseInt(params.get('page') ?? '1', 10)
  const sort = params.get('sort') ?? ''
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [allItems, setAllItems] = useState<SearchResponse['items']>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [facetConfig, setFacetConfig] = useState<Record<string, string[]>>({ _system: DEFAULT_SYSTEM_FACETS })
  const [subtitleConfig, setSubtitleConfig] = useState<Record<string, string[]>>({})
  const [facetInitialCount, setFacetInitialCount] = useState(10)
  const { locale, t } = useI18n()
  const [viewMode, setViewMode] = useState<'list' | 'masonry' | 'grid'>(() => {
    const stored = localStorage.getItem('katalon_search_view')
    if (stored === 'masonry' || stored === 'grid') return stored
    return 'list'
  })
  const [infinite, setInfinite] = useState(() => localStorage.getItem('katalon_search_infinite') === '1')
  const PAGE_SIZE = 20
  const nextPageRef = useRef(1)
  const loadingMoreRef = useRef(false)
  const pageKeyRef = useRef('')
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const [showScrollTop, setShowScrollTop] = useState(false)

  useEffect(() => {
    const onScroll = () => setShowScrollTop(window.scrollY > 600)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  const facetTypesKey = [...new Set(
    Object.entries(facetConfig)
      .filter(([type]) => type !== '_system')
      .flatMap(([type, fields]) => [
        type,
        ...fields.flatMap(field => {
          const inherited = field.match(/^inherited_(object|entity|place|occurrence|collection|procedure)_/)
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
        setFacetInitialCount(c.facet_initial_count || 10)
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
  const relEntity = params.getAll('rel_entity')
  const relPlace = params.getAll('rel_place')
  const relOccurrence = params.getAll('rel_occurrence')
  const relCollection = params.getAll('rel_collection')
  const filterKey = JSON.stringify({ q, typeFilt, statusFilt, encodedAdvancedQuery, metaFilters, numericFilters, relEntity, relPlace, relOccurrence, relCollection, sort })

  async function loadPage(pageNum: number): Promise<SearchResponse> {
    const systemFacets = facetConfig._system ?? DEFAULT_SYSTEM_FACETS
    const searchParams: Record<string, string | number | undefined> = {
      q: q || undefined,
      type: systemFacets.includes('record_type') ? (typeFilt || undefined) : undefined,
      page: pageNum,
      page_size: PAGE_SIZE,
      facets: (() => {
        const fields = configuredMetadataFacets(facetConfig, effectiveType)
        return fields.length > 0 ? fields.join(',') : undefined
      })(),
      sort: sort || undefined,
    }
    const qs = new URLSearchParams(
      Object.entries(searchParams)
        .filter(([, value]) => value != null)
        .map(([key, value]) => [key, String(value)])
    )
    if (systemFacets.includes('status')) statusFilt.forEach(value => qs.append('status', value))
    relEntity.forEach(value => qs.append('rel_entity', value))
    relPlace.forEach(value => qs.append('rel_place', value))
    relOccurrence.forEach(value => qs.append('rel_occurrence', value))
    relCollection.forEach(value => qs.append('rel_collection', value))
    Object.entries(metaFilters).forEach(([field, values]) => {
      values.forEach(value => qs.append(`meta_${field}`, value))
    })
    Object.entries(numericFilters).forEach(([field, range]) => {
      if (range.from) qs.set(`range_${field}_from`, range.from)
      if (range.to) qs.set(`range_${field}_to`, range.to)
    })
    if (encodedAdvancedQuery) {
      if (!advancedQuery) throw new Error(t('advanced.invalidLink'))
      return api.search.advanced({
        query: advancedQuery,
        q: q || undefined,
        page: pageNum,
        page_size: PAGE_SIZE,
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
          related_collections: relCollection,
        },
        status: statusFilt,
        sort: sort || undefined,
      })
    }
    const res = await fetch(`${BASE}${PORTAL_API}/search?${qs.toString()}`)
    if (!res.ok) throw new Error(res.statusText)
    return res.json()
  }

  // Fetch on filter/page/view changes
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    if (infinite) nextPageRef.current = 1
    pageKeyRef.current = filterKey
    const fetchPage = infinite ? 1 : page
    loadPage(fetchPage)
      .then(result => {
        if (cancelled) return
        setData(result)
        setAllItems(result.items)
        if (infinite) nextPageRef.current = 2
      })
      .catch(reason => {
        if (!cancelled) {
          setData(null)
          setAllItems([])
          setError(reason instanceof Error ? reason.message : t('advanced.searchFailed'))
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filterKey, JSON.stringify(facetConfig), page, infinite])

  async function loadMore() {
    if (!infinite || loadingMoreRef.current) return
    if (!data || nextPageRef.current * PAGE_SIZE >= data.total) return
    loadingMoreRef.current = true
    const pageNum = nextPageRef.current
    try {
      const result = await loadPage(pageNum)
      setAllItems(prev => [...prev, ...result.items])
      nextPageRef.current = pageNum + 1
    } catch {
      // silent — next scroll attempt will retry
    } finally {
      loadingMoreRef.current = false
    }
  }

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !infinite) return
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting) loadMore()
      },
      { rootMargin: '300px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [data, infinite])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const next = new URLSearchParams(params)
    const term = localQ.trim()
    if (term) next.set('q', term)
    else next.delete('q')
    setParams(next)
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  function toggleParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    const selected = next.getAll(key)
    next.delete(key)
    selected.filter(current => current !== value).forEach(current => next.append(key, current))
    if (!selected.includes(value)) next.append(key, value)
    setParams(next)
  }

  function toggleMetaFilter(field: string, value: string) {
    toggleParam(`meta_${field}`, value)
  }

  function setNumericFilter(field: string, from: string, to: string) {
    const next = new URLSearchParams(params)
    const fromKey = `range_${field}_from`
    const toKey = `range_${field}_to`
    if (from) next.set(fromKey, from)
    else next.delete(fromKey)
    if (to) next.set(toKey, to)
    else next.delete(toKey)
    setParams(next)
  }

  function setPage(n: number) {
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  const total = data?.total ?? 0
  const hasMore = data ? allItems.length < data.total : false
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1
  const typesFacet: FacetBucket[] = data?.facets?.['by_type'] ?? []
  const statusFacet: FacetBucket[] = data?.facets?.['by_status'] ?? []
  const systemFacets = facetConfig._system ?? DEFAULT_SYSTEM_FACETS

  return (
    <div className="container page">
      <div className="search-header">
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, marginBottom: 4, flexWrap: 'wrap' }}>
          <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>
            {loading
              ? t('search.searching')
              : <>
                  {t('search.results', { count: total })}
                  {q ? t('search.resultsFor', { q }) : ''}
                </>}
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--fg-3)' }}>
            {t('search.sortLabel')}
            <select value={sort} onChange={e => setFilter('sort', e.target.value)}>
              <option value="">{t('search.sortRelevance')}</option>
              <option value="idno_asc">{t('search.sortIdno')}</option>
              <option value="title_asc">{t('search.sortTitle')}</option>
              <option value="newest">{t('search.sortNewest')}</option>
              <option value="oldest">{t('search.sortOldest')}</option>
            </select>
          </label>
        </div>
      </div>

      <div className="search-layout">
        <div className="facets-wrap"><aside className="facets">
          {!advancedQuery && systemFacets.includes('record_type') && (
            <FacetPanel
              label={t('search.typeFacet')}
              buckets={typesFacet}
              active={typeFilt ? [typeFilt] : []}
              onSelect={v => setFilter('type', v)}
              initialCount={facetInitialCount}
            />
          )}
          {systemFacets.includes('status') && (
            <FacetPanel
              label={t('search.statusFacet')}
              buckets={statusFacet}
              active={statusFilt}
              onSelect={v => v ? toggleParam('status', v) : setFilter('status', '')}
              initialCount={facetInitialCount}
            />
          )}
          {configuredMetadataFacets(facetConfig, effectiveType).filter(field => !RELATED_FACET_NAMES.includes(field)).map(field => {
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
                initialCount={facetInitialCount}
                translateBooleanValues={isBooleanFacet(field, fieldLabels, facetConfig, effectiveType)}
              />
            )
          })}
          {(() => {
            const activeRelated = configuredMetadataFacets(facetConfig, effectiveType)
            return (
              <>
                {activeRelated.includes('related_entities') && (
                  <FacetPanel
                    label={t('search.relatedEntities')}
                    buckets={data?.facets?.['related_entities'] ?? []}
                    active={relEntity}
                    onSelect={v => v ? toggleParam('rel_entity', v) : setFilter('rel_entity', '')}
                    initialCount={facetInitialCount}
                  />
                )}
                {activeRelated.includes('related_places') && (
                  <FacetPanel
                    label={t('search.relatedPlaces')}
                    buckets={data?.facets?.['related_places'] ?? []}
                    active={relPlace}
                    onSelect={v => v ? toggleParam('rel_place', v) : setFilter('rel_place', '')}
                    initialCount={facetInitialCount}
                  />
                )}
                {activeRelated.includes('related_occurrences') && (
                  <FacetPanel
                    label={t('search.relatedOccurrences')}
                    buckets={data?.facets?.['related_occurrences'] ?? []}
                    active={relOccurrence}
                    onSelect={v => v ? toggleParam('rel_occurrence', v) : setFilter('rel_occurrence', '')}
                    initialCount={facetInitialCount}
                  />
                )}
                {activeRelated.includes('related_collections') && (
                  <FacetPanel
                    label={t('search.relatedCollections')}
                    buckets={data?.facets?.['related_collections'] ?? []}
                    active={relCollection}
                    onSelect={v => v ? toggleParam('rel_collection', v) : setFilter('rel_collection', '')}
                    initialCount={facetInitialCount}
                  />
                )}
              </>
            )
          })()}
        </aside></div>

        <div className="result-list">
          {error && <div className="advanced-error" role="alert">{error}</div>}
          {loading && <div style={{ padding: 24, color: 'var(--fg-3)' }}>{t('common.loading')}</div>}
          {!loading && allItems.length === 0 && (
            <div style={{ padding: 24, color: 'var(--fg-3)' }}>{t('search.noResultsShort')}</div>
          )}
          {!loading && data && allItems.length > 0 && (
            <>
              {effectiveType === 'object' && (
                <div className="view-toggle-bar">
                  <div className="view-toggle">
                    <button type="button" className={`view-toggle__btn${viewMode === 'list' ? ' active' : ''}`} onClick={() => { setViewMode('list'); localStorage.setItem('katalon_search_view', 'list') }} aria-label={t('search.viewList')} title={t('search.viewList')}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="4" rx="1"/><rect x="9" y="1" width="6" height="4" rx="1"/><rect x="1" y="6" width="6" height="4" rx="1"/><rect x="9" y="6" width="6" height="4" rx="1"/><rect x="1" y="11" width="6" height="4" rx="1"/><rect x="9" y="11" width="6" height="4" rx="1"/></svg>
                    </button>
                    <button type="button" className={`view-toggle__btn${viewMode === 'masonry' ? ' active' : ''}`} onClick={() => { setViewMode('masonry'); localStorage.setItem('katalon_search_view', 'masonry') }} aria-label={t('search.viewMasonry')} title={t('search.viewMasonry')}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="7" rx="1"/><rect x="9" y="1" width="6" height="4" rx="1"/><rect x="1" y="10" width="6" height="5" rx="1"/><rect x="9" y="7" width="6" height="8" rx="1"/></svg>
                    </button>
                    <button type="button" className={`view-toggle__btn${viewMode === 'grid' ? ' active' : ''}`} onClick={() => { setViewMode('grid'); localStorage.setItem('katalon_search_view', 'grid') }} aria-label={t('search.viewGrid')} title={t('search.viewGrid')}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
                    </button>
                  </div>
                  <div className="view-toggle">
                    <button type="button" className={`view-toggle__btn${!infinite ? ' active' : ''}`} onClick={() => { setInfinite(false); localStorage.setItem('katalon_search_infinite', '0') }} aria-label={t('search.modePaged')} title={t('search.modePaged')}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="4" rx="1"/><rect x="9" y="1" width="6" height="4" rx="1"/><rect x="1" y="6" width="6" height="4" rx="1"/><rect x="9" y="6" width="6" height="4" rx="1"/><rect x="1" y="11" width="6" height="4" rx="1"/><rect x="9" y="11" width="6" height="4" rx="1"/></svg>
                    </button>
                    <button type="button" className={`view-toggle__btn${infinite ? ' active' : ''}`} onClick={() => { setInfinite(true); localStorage.setItem('katalon_search_infinite', '1') }} aria-label={t('search.modeInfinite')} title={t('search.modeInfinite')}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 2v12M4 5l4-3 4 3M4 11l4 3 4-3" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    </button>
                  </div>
                </div>
              )}
              <div className={`result-list__items result-list__items--${viewMode}`}>
                {allItems.map(r => {
                  const path = r.record_type === 'entity' ? `/entities/${r.id}`
                    : r.record_type === 'place' ? `/places/${r.id}`
                    : r.record_type === 'occurrence' ? `/occurrences/${r.id}`
                    : r.record_type === 'collection' ? `/collections/${r.id}`
                    : `/objects/${r.id}`
                  const thumbUrl = r.primary_media_id ? mediaThumbnailUrl(r.id, r.primary_media_id) : null
                  const isPortrait = r.media_width != null && r.media_height != null && r.media_height > r.media_width

                  if (viewMode === 'list') {
                    return (
                      <Link key={r.id} className="result-row" to={path} onClick={() => saveLastSearch(window.location.pathname + window.location.search)}>
                        {r.record_type === 'object' && (
                          <div className="thumb-sm">
                            {thumbUrl ? <img src={thumbUrl} alt="" loading="lazy" /> : null}
                          </div>
                        )}
                        <div className="body">
                          <div className="title">
                            <span className="result-type-badge">{typeLabel(r.record_type)}</span>
                            {r.title || r.id}
                          </div>
                          <div className="desc">{resultSubtitle(r, subtitleConfig)}</div>
                        </div>
                      </Link>
                    )
                  }

                  const aspectRatio = r.media_width != null && r.media_height != null
                    ? r.media_width / r.media_height
                    : undefined
                  const gridClass = r.record_type !== 'object' ? 'result-card result-card--nonobject'
                    : isPortrait ? 'result-card result-card--portrait'
                    : aspectRatio != null && aspectRatio > 1.3 ? 'result-card result-card--landscape'
                    : 'result-card'

                  return (
                    <Link key={r.id} className={gridClass} to={path} onClick={() => saveLastSearch(window.location.pathname + window.location.search)}>
                      {r.record_type === 'object' && thumbUrl ? (
                        <div className="result-card__thumb" style={aspectRatio ? { aspectRatio: String(aspectRatio) } : undefined}>
                          <img src={thumbUrl} alt="" loading="lazy" />
                        </div>
                      ) : (
                        <div className="result-card__thumb result-card__thumb--empty">
                          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
                        </div>
                      )}
                      <div className="result-card__info">
                        <div className="result-card__title">{r.title || r.id}</div>
                        <div className="result-card__meta">{resultSubtitle(r, subtitleConfig)}</div>
                      </div>
                    </Link>
                  )
                })}
              </div>
              {infinite && hasMore && <div ref={sentinelRef} style={{ height: 1 }} />}
            </>
          )}
        </div>
      </div>

      {!infinite && totalPages > 1 && (
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
      {showScrollTop && (
        <button type="button" className="scroll-top-btn" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label={t('search.scrollTop')}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3l-7 7h4v7h6v-7h4z"/></svg>
        </button>
      )}
    </div>
  )
}
