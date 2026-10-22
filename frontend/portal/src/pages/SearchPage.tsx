// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, BASE, PORTAL_API, type FacetBucket, type FacetKind, type SearchResponse } from '../api/client'
import { thumbnailSrcSet, thumbnailUrl } from '../utils/thumbnails'
import { LazyImage } from '../components/LazyImage'
import { TreeFacetPanel } from '../components/TreeFacetPanel'
import { saveLastSearch, saveSearchContext } from '../hooks/useBackToSearch'
import { useFieldLabels } from '../hooks/useFieldLabels'
import { useRecordSubtypeLabels } from '../hooks/useRecordSubtypeLabels'
import { useSubtypePlaceholder } from '../hooks/useSubtypePlaceholders'
import { t, typeLabel, useI18n } from '../i18n'
import { decodeAdvancedQuery, usesRelations } from '../utils/advancedSearch'
import { dateBucketLabel, facetKind, resolveLabel, splitRelationBucket } from '../utils/facets'
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

const DEFAULT_SUBTITLE_FIELDS: string[] = []
const DEFAULT_SYSTEM_FACETS = ['record_type', 'subtype']
// Results whose thumbnails load eagerly with high priority (first visible rows).
const PRIORITY_IMAGES = 8
// Relation-derived facets — see configuredMetadataFacets: included in the
// request field list, but rendered as dedicated panels below, not generic ones.
const RELATED_FACET_PARAMS: Record<string, string> = {
  related_entities: 'rel_entity',
  related_places: 'rel_place',
  related_occurrences: 'rel_occurrence',
  related_collections: 'rel_collection',
}
const RELATED_FACET_LABELS: Record<string, string> = {
  related_entities: 'search.relatedEntities',
  related_places: 'search.relatedPlaces',
  related_occurrences: 'search.relatedOccurrences',
  related_collections: 'search.relatedCollections',
}

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
      if (field === 'status') return r.status ?? '–'
      const value = r.subtitle_values?.[field]
      return value == null ? null : Array.isArray(value) ? value.join(', ') : value
    })
    .filter((v): v is string => !!v)
    .join(' · ')
}

function FacetPanel({ label, buckets, active, onSelect, initialCount, translateBooleanValues = false, valueLabel }: {
  label: string
  buckets: FacetBucket[]
  active: string[]
  onSelect: (v: string) => void
  initialCount: number
  translateBooleanValues?: boolean
  valueLabel?: (raw: string) => string
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
          <span>{translateBooleanValues && ['true', 'false'].includes(b.value.toLowerCase()) ? t(b.value.toLowerCase() === 'true' ? 'advanced.yes' : 'advanced.no') : (valueLabel ?? typeLabel)(b.value)}</span>
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
  const subtypeFilt = params.getAll('subtype')
  const encodedAdvancedQuery = params.get('aq') ?? ''
  const advancedQuery = decodeAdvancedQuery(encodedAdvancedQuery)
  const relationSearch = advancedQuery ? usesRelations(advancedQuery.group) : false
  const effectiveType = advancedQuery?.record_type ?? typeFilt
  const page = parseInt(params.get('page') ?? '1', 10)
  const sort = params.get('sort') ?? ''
  const [localQ, setLocalQ] = useState(q)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [allItems, setAllItems] = useState<SearchResponse['items']>([])
  const [loading, setLoading] = useState(false)
  // Searches over relations resolve their targets first; after a moment, say why it takes longer.
  const [slowSearch, setSlowSearch] = useState(false)
  const [error, setError] = useState('')
  const [jumpPage, setJumpPage] = useState('')
  const [jumpError, setJumpError] = useState('')
  const [facetConfig, setFacetConfig] = useState<Record<string, string[]>>({ _system: DEFAULT_SYSTEM_FACETS })
  const [facetKinds, setFacetKinds] = useState<Record<string, Record<string, FacetKind>>>({})
  // Expanded nodes per tree facet; kept across filter changes so the open
  // branches stay open, sent as expand_<name> so the API counts their children.
  const [treeExpanded, setTreeExpanded] = useState<Record<string, string[]>>({})
  const [subtitleConfig, setSubtitleConfig] = useState<Record<string, string[]>>({})
  const [facetInitialCount, setFacetInitialCount] = useState(10)
  const { locale, t } = useI18n()
  const subtypePlaceholder = useSubtypePlaceholder('object')
  const subtypeLabel = useRecordSubtypeLabels(locale)
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
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  useEffect(() => {
    if (!mobileFiltersOpen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prevOverflow }
  }, [mobileFiltersOpen])

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
        setFacetKinds(c.facet_kinds ?? {})
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
  const filterKey = JSON.stringify({ q, typeFilt, statusFilt, subtypeFilt, encodedAdvancedQuery, metaFilters, numericFilters, relEntity, relPlace, relOccurrence, relCollection, sort })

  async function loadPage(pageNum: number, expandedTrees = treeExpanded): Promise<SearchResponse> {
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
    if (systemFacets.includes('subtype')) subtypeFilt.forEach(value => qs.append('subtype', value))
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
    Object.entries(expandedTrees).forEach(([field, ids]) => {
      ids.forEach(id => qs.append(`expand_${field}`, id))
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
        subtype: subtypeFilt,
        sort: sort || undefined,
        tree_expand: expandedTrees,
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
    setJumpPage('')
    setJumpError('')
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

  useEffect(() => {
    if (!loading || !relationSearch) return
    const timer = window.setTimeout(() => setSlowSearch(true), 1500)
    return () => { window.clearTimeout(timer); setSlowSearch(false) }
  }, [loading, relationSearch])

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

  function toggleTreeNode(field: string, id: string) {
    const current = treeExpanded[field] ?? []
    const isOpen = current.includes(id)
    const next = { ...treeExpanded, [field]: isOpen ? current.filter(v => v !== id) : [...current, id] }
    setTreeExpanded(next)
    if (isOpen || data?.tree_facets?.[field]?.nodes[id]) return
    // Only the counts of the newly opened node are missing: fetch them without
    // replacing the result list.
    loadPage(1, next)
      .then(result => setData(prev => (prev ? { ...prev, tree_facets: result.tree_facets } : prev)))
      .catch(() => {})
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
    if (!data || !Number.isInteger(n) || n < 1 || n > totalPages) {
      setJumpError(t('search.pageInvalid', { total: totalPages }))
      return
    }
    // Match Elasticsearch's 10,000-hit window at either end; relevance with
    // a text query cannot use the reversed tail (search_documents).
    const from = (n - 1) * data.page_size
    const reversible = !q || ['idno_asc', 'title_asc', 'newest', 'oldest'].includes(sort)
    if (from + data.page_size > 10_000 && (!reversible || data.total - from > 10_000)) {
      setJumpError(t('search.pageUnavailable'))
      return
    }
    setJumpError('')
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  const total = data?.total ?? 0
  // Grid/masonry rely on media thumbnails and only object results carry them; the
  // toggle bar below is object-only too, so other types would get stuck in a mode
  // with no way back. Force list there regardless of the stored preference.
  const effectiveViewMode = effectiveType === 'object' ? viewMode : 'list'
  const hasMore = data ? allItems.length < data.total : false
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1
  const typesFacet: FacetBucket[] = data?.facets?.['by_type'] ?? []
  const statusFacet: FacetBucket[] = data?.facets?.['by_status'] ?? []
  const subtypeFacet: FacetBucket[] = data?.facets?.['by_subtype'] ?? []
  const systemFacets = facetConfig._system ?? DEFAULT_SYSTEM_FACETS
  const activeFilters: { keys: string[]; value?: string; label: string }[] = []
  const addFilter = (key: string, value: string, label: string) => {
    activeFilters.push({ keys: [key], value, label })
  }
  if (!advancedQuery && systemFacets.includes('record_type') && typeFilt) {
    addFilter('type', typeFilt, `${t('search.typeFacet')}: ${typeLabel(typeFilt)}`)
  }
  if (systemFacets.includes('status')) statusFilt.forEach(value => addFilter('status', value, `${t('search.statusFacet')}: ${typeLabel(value)}`))
  if (systemFacets.includes('subtype')) subtypeFilt.forEach(value => addFilter('subtype', value, `${t('search.subtypeFacet')}: ${subtypeLabel(value)}`))
  Object.entries(RELATED_FACET_PARAMS).forEach(([field, key]) => {
    params.getAll(key).forEach(value => addFilter(key, value, `${t(RELATED_FACET_LABELS[field])}: ${value}`))
  })
  const metadataLabel = (field: string) => {
    const kind = facetKind(facetKinds, effectiveType, field)
    return kind?.label ? resolveLabel(kind.label, locale, field) : facetLabel(field, fieldLabels, facetConfig, effectiveType)
  }
  Object.entries(metaFilters).forEach(([field, values]) => {
    const kind = facetKind(facetKinds, effectiveType, field)
    values.forEach(value => {
      let label = value
      if (kind?.kind === 'relation') {
        const bucket = data?.facets?.[`meta_${field}`]?.find(b => splitRelationBucket(b.value).id === value)
        label = splitRelationBucket(bucket?.value ?? value).title
      } else if (kind?.kind === 'tree') {
        label = data?.tree_facets?.[field]?.paths[value]?.map(node => resolveLabel(node.label, locale, node.id)).join(' › ') || value
      } else if (kind?.kind === 'date') {
        label = dateBucketLabel(value, kind.granularity, locale)
      } else if ((kind ? kind.kind === 'boolean' : isBooleanFacet(field, fieldLabels, facetConfig, effectiveType)) && ['true', 'false'].includes(value.toLowerCase())) {
        label = t(value.toLowerCase() === 'true' ? 'advanced.yes' : 'advanced.no')
      }
      addFilter(`meta_${field}`, value, `${metadataLabel(field)}: ${label}`)
    })
  })
  Object.entries(numericFilters).forEach(([field, range]) => {
    if (!range.from && !range.to) return
    const value = range.from && range.to ? `${range.from}–${range.to}` : range.from ? `≥ ${range.from}` : `≤ ${range.to}`
    activeFilters.push({ keys: [`range_${field}_from`, `range_${field}_to`], label: `${metadataLabel(field)}: ${value}` })
  })

  function removeFilter(filter: typeof activeFilters[number]) {
    const next = new URLSearchParams(params)
    filter.keys.forEach(key => {
      if (filter.value === undefined) next.delete(key)
      else next.delete(key, filter.value)
    })
    next.delete('page')
    setParams(next)
  }

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
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              type="button"
              className="mobile-filters-toggle"
              onClick={() => setMobileFiltersOpen(true)}
              aria-label={t('search.openFilters')}
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 4h12M4.5 8h7M7 12h2"/></svg>
              {t('search.openFilters')}
            </button>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--fg-3)' }}>
              <span className="sort-label-text">{t('search.sortLabel')}</span>
              <span className="sort-select">
                <select value={sort} onChange={e => setFilter('sort', e.target.value)}>
                  <option value="">{t('search.sortRelevance')}</option>
                  <option value="idno_asc">{t('search.sortIdno')}</option>
                  <option value="title_asc">{t('search.sortTitle')}</option>
                  <option value="newest">{t('search.sortNewest')}</option>
                  <option value="oldest">{t('search.sortOldest')}</option>
                </select>
              </span>
            </label>
          </div>
        </div>
        {activeFilters.length > 0 && (
          <div className="active-filters" role="group" aria-label={t('search.openFilters')}>
            {activeFilters.map(filter => (
              <button
                type="button"
                key={`${filter.keys[0]}:${filter.value ?? ''}`}
                className="active-filter"
                aria-label={`${t('search.removeFilter')}: ${filter.label}`}
                onClick={() => removeFilter(filter)}
              >
                <span>{filter.label}</span><span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="search-layout">
        {mobileFiltersOpen && <div className="facets-backdrop" onClick={() => setMobileFiltersOpen(false)} />}
        <div className={`facets-wrap${mobileFiltersOpen ? ' facets-wrap--open' : ''}`}>
          <button
            type="button"
            className="facets-close"
            onClick={() => setMobileFiltersOpen(false)}
            aria-label={t('search.closeFilters')}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M4 4l10 10M14 4L4 14"/></svg>
          </button>
          <aside className="facets">
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
          {systemFacets.includes('subtype') && (
            <FacetPanel
              label={t('search.subtypeFacet')}
              buckets={subtypeFacet}
              active={subtypeFilt}
              onSelect={v => v ? toggleParam('subtype', v) : setFilter('subtype', '')}
              initialCount={facetInitialCount}
              valueLabel={subtypeLabel}
            />
          )}
          {configuredMetadataFacets(facetConfig, effectiveType).map(field => {
            const kind = facetKind(facetKinds, effectiveType, field)
            const relatedParam = RELATED_FACET_PARAMS[field]
            if (relatedParam) {
              const active = params.getAll(relatedParam)
              return (
                <FacetPanel
                  key={field}
                  label={t(RELATED_FACET_LABELS[field])}
                  buckets={data?.facets?.[field] ?? []}
                  active={active}
                  onSelect={v => v ? toggleParam(relatedParam, v) : setFilter(relatedParam, '')}
                  initialCount={facetInitialCount}
                />
              )
            }
            const baseLabel = kind?.label
              ? resolveLabel(kind.label, locale, field)
              : facetLabel(field, fieldLabels, facetConfig, effectiveType)
            const active = metaFilters[field] ?? []
            const select = (v: string) => v ? toggleMetaFilter(field, v) : setFilter(`meta_${field}`, '')
            if (kind?.kind === 'tree') {
              return (
                <TreeFacetPanel
                  key={field}
                  label={baseLabel}
                  tree={data?.tree_facets?.[field]}
                  active={active}
                  expanded={treeExpanded[field] ?? []}
                  onToggleExpand={id => toggleTreeNode(field, id)}
                  onSelect={select}
                />
              )
            }
            if (kind?.kind === 'numeric' || (!kind && isNumericFacet(field, fieldLabels, facetConfig, effectiveType))) {
              const range = numericFilters[field] ?? { from: '', to: '' }
              return <NumericFacetPanel key={field} label={baseLabel} bounds={data?.numeric_facets?.[field]} from={range.from} to={range.to} onChange={(from, to) => setNumericFilter(field, from, to)} />
            }
            const buckets = data?.facets?.[`meta_${field}`] ?? []
            if (kind?.kind === 'relation') {
              // Buckets are "<id>|<title>"; filter by id, show the title.
              return (
                <FacetPanel
                  key={field}
                  label={baseLabel}
                  buckets={buckets.map(b => ({ ...b, value: splitRelationBucket(b.value).id }))}
                  active={active}
                  onSelect={select}
                  initialCount={facetInitialCount}
                  valueLabel={id => splitRelationBucket(buckets.find(b => splitRelationBucket(b.value).id === id)?.value ?? id).title}
                />
              )
            }
            if (kind?.kind === 'date') {
              return (
                <FacetPanel
                  key={field}
                  label={`${baseLabel} (${t(`search.granularity.${kind.granularity ?? 'decade'}`)})`}
                  buckets={buckets}
                  active={active}
                  onSelect={select}
                  initialCount={facetInitialCount}
                  valueLabel={bucket => dateBucketLabel(bucket, kind.granularity, locale)}
                />
              )
            }
            return (
              <FacetPanel
                key={field}
                label={baseLabel}
                buckets={buckets}
                active={active}
                onSelect={select}
                initialCount={facetInitialCount}
                translateBooleanValues={kind ? kind.kind === 'boolean' : isBooleanFacet(field, fieldLabels, facetConfig, effectiveType)}
              />
            )
          })}
        </aside></div>

        <div className="result-list">
          {error && <div className="advanced-error" role="alert">{error}</div>}
          {loading && (
            <div className="search-loading" role="status" style={{ padding: 24, color: 'var(--fg-3)' }}>
              {relationSearch ? t('advanced.loadingRelations') : t('common.loading')}
              {slowSearch && <div className="search-loading__hint">{t('advanced.loadingRelationsHint')}</div>}
            </div>
          )}
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
              <div className={`result-list__items result-list__items--${effectiveViewMode}`}>
                {allItems.map((r, index) => {
                  const path = r.record_type === 'entity' ? `/entities/${r.id}`
                    : r.record_type === 'place' ? `/places/${r.id}`
                    : r.record_type === 'occurrence' ? `/occurrences/${r.id}`
                    : r.record_type === 'collection' ? `/collections/${r.id}`
                    : `/objects/${r.id}`
                  const thumbUrl = r.primary_media_id ? thumbnailUrl(r.id, r.primary_media_id, r.primary_media_iiif) : null
                  const fallbackUrl = !thumbUrl && r.record_type === 'object' ? subtypePlaceholder(r.object_type) : ''
                  const thumbSrcSet = thumbUrl ? thumbnailSrcSet(r.primary_media_iiif) : undefined
                  // The first results are visible right away: load them first, not lazily.
                  const priorityImage = index < PRIORITY_IMAGES
                  const isPortrait = r.media_width != null && r.media_height != null && r.media_height > r.media_width
                  const saveContext = () => {
                    saveLastSearch(window.location.pathname + window.location.search)
                    saveSearchContext({
                      url: window.location.pathname + window.location.search,
                      items: allItems.map(({ id, record_type }) => ({ id, record_type })),
                      page: data.page,
                      pageSize: data.page_size,
                      total: data.total,
                      index: allItems.findIndex(item => item.id === r.id),
                    })
                  }

                  const subtitle = resultSubtitle(r, subtitleConfig)

                  if (effectiveViewMode === 'list') {
                    return (
                      <Link key={r.id} className="result-row" to={path} onClick={saveContext}>
                        {r.record_type === 'object' && (
                          <div className="thumb-sm">
                            {thumbUrl || fallbackUrl ? (
                              <LazyImage src={thumbUrl ?? fallbackUrl} srcSet={thumbSrcSet} width={r.media_width} height={r.media_height} priority={priorityImage} />
                            ) : (
                              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
                            )}
                          </div>
                        )}
                        <div className="body">
                          <div className="title">
                            <span className="result-type-badge">{r.subtype ? subtypeLabel(r.subtype) : typeLabel(r.record_type)}</span>
                            {r.title || r.id}
                          </div>
                          {subtitle && <div className="desc">{subtitle}</div>}
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
                    <Link key={r.id} className={gridClass} to={path} onClick={saveContext}>
                      {r.record_type === 'object' && (thumbUrl || fallbackUrl) ? (
                        <div className="result-card__thumb" style={aspectRatio ? { aspectRatio: String(aspectRatio) } : undefined}>
                          <LazyImage src={thumbUrl ?? fallbackUrl} srcSet={thumbSrcSet} width={r.media_width} height={r.media_height} priority={priorityImage} />
                        </div>
                      ) : (
                        <div className="result-card__thumb result-card__thumb--empty">
                          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
                        </div>
                      )}
                      <div className="result-card__info">
                        <div className="result-card__title">
                          <span className="result-type-badge">{r.subtype ? subtypeLabel(r.subtype) : typeLabel(r.record_type)}</span>
                          {r.title || r.id}
                        </div>
                        {subtitle && <div className="result-card__meta">{subtitle}</div>}
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
          <div className="pagination-pages">
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
          </div>
          <form className="page-jump" onSubmit={event => { event.preventDefault(); setPage(Number(jumpPage)) }}>
            <label htmlFor="page-jump-input">{t('search.page')}</label>
            <input id="page-jump-input" type="number" min={1} max={totalPages} step={1} required value={jumpPage} placeholder={String(page)} onChange={event => { setJumpPage(event.target.value); setJumpError('') }} aria-invalid={!!jumpError} aria-describedby={jumpError ? 'page-jump-error' : undefined} />
            <span>{t('search.pageOf', { total: totalPages })}</span>
            <button type="submit" disabled={loading}>{t('search.pageGo')}</button>
          </form>
          {jumpError && <p id="page-jump-error" className="page-jump-error" role="alert">{jumpError}</p>}
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
