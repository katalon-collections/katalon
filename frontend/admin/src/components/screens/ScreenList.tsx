// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { objects, entities, places, occurrences, procedures, collections, schema, subtypes, ConflictError, getTokenUser } from '../../api/client'
import type { AnyRecord, FieldDefinition, ListableRecordType, Page, RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { StatusBadge } from '../ui/StatusBadge'
import { Edit, Eye, Folder, Layers, Plus, Search, Trash } from '../ui/Icons'
import { ActionMenu } from '../ui/ActionMenu'
import { BatchEditModal } from './BatchEditModal'
import { AddToWorkingSetModal } from './AddToWorkingSetModal'

const PAGE_SIZE = 50

const SUBTYPE_KEYS: Record<ListableRecordType, string | undefined> = {
  object: 'object_type',
  entity: 'entity_type',
  place: 'place_type',
  occurrence: 'occurrence_type',
  procedure: 'procedure_type',
  collection: 'collection_type',
}

function getApi(recordType: ListableRecordType) {
  switch (recordType) {
    case 'object':     return objects
    case 'entity':     return entities
    case 'place':      return places
    case 'occurrence': return occurrences
    case 'procedure':  return procedures
    case 'collection': return collections
  }
}

/** Extract a display value from metadata for a field name.
 *  Handles both plain strings and repeatable-field lists. */
function getFieldValue(metadata: Record<string, unknown>, fieldName: string): string {
  const val = metadata[fieldName]
  if (val == null) return ''
  if (typeof val === 'string') return val
  if (Array.isArray(val) && val.length > 0) {
    const first = val[0]
    if (typeof first === 'string') return first
    if (first && typeof first === 'object') {
      if ('value' in first) return String((first as { value?: unknown }).value ?? '')
      if ('label' in first) return String((first as { label?: unknown }).label ?? '')
    }
    return ''
  }
  if (val && typeof val === 'object') {
    const obj = val as { label?: unknown; value?: unknown }
    const labelText = 'label' in obj ? String(obj.label ?? '') : ''
    if (labelText) return labelText
    if ('value' in obj) return String(obj.value ?? '')
    return ''
  }
  return String(val)
}

/** Order collection records as a depth-first hierarchy (parent → children),
 *  sorted alphabetically by title within each level. Records whose parent
 *  isn't part of the loaded set (e.g. filtered out) are treated as roots. */
function buildCollectionTree(records: AnyRecord[], titleKey: string): { list: AnyRecord[]; depth: Map<string, number> } {
  const byParent = new Map<string, AnyRecord[]>()
  for (const r of records) {
    const pid = (r as { parent_id?: string | null }).parent_id ?? ''
    if (!byParent.has(pid)) byParent.set(pid, [])
    byParent.get(pid)!.push(r)
  }
  const titleOf = (r: AnyRecord) => getFieldValue(r.metadata_ as Record<string, unknown>, titleKey) || (r as { idno?: string | null }).idno || ''
  for (const arr of byParent.values()) arr.sort((a, b) => titleOf(a).localeCompare(titleOf(b)))
  const seen = new Set<string>()
  const depth = new Map<string, number>()
  const list: AnyRecord[] = []
  function visit(pid: string, d: number) {
    for (const c of byParent.get(pid) ?? []) {
      if (seen.has(c.id)) continue
      seen.add(c.id)
      depth.set(c.id, d)
      list.push(c)
      visit(c.id, d + 1)
    }
  }
  visit('', 0)
  for (const r of records) {
    if (!seen.has(r.id)) { seen.add(r.id); depth.set(r.id, 0); list.push(r) }
  }
  return { list, depth }
}

interface Props {
  recordType: ListableRecordType
  onOpen?: (id: string) => void
  initialTab?: string | null
  onTabChange?: (tab: string) => void
}

export function ScreenList({ recordType, onOpen, initialTab, onTabChange }: Props) {
  const { t } = useTranslation('screenList')
  const api = getApi(recordType)
  const subtypeKey = SUBTYPE_KEYS[recordType]

  const tabs = recordType === 'procedure'
    ? [
        { id: 'all',       label: t('tabAll') },
        { id: 'draft',     label: t('tabDraft') },
        { id: 'active',    label: t('tabActive') },
        { id: 'completed', label: t('tabCompleted') },
        { id: 'cancelled', label: t('tabCancelled') },
      ]
    : [
        { id: 'all',      label: t('tabAll') },
        { id: 'draft',    label: t('tabDraft') },
        { id: 'internal', label: t('tabInternal') },
        { id: 'public',   label: t('tabPublic') },
      ]
  const tabIds = tabs.map(t => t.id)

  const typeLabels: Record<ListableRecordType, string> = {
    object: t('typeObject'),
    entity: t('typeEntity'),
    place: t('typePlace'),
    occurrence: t('typeOccurrence'),
    procedure: t('typeProcedure'),
    collection: t('typeCollection'),
  }
  const typeSingularLabels: Record<ListableRecordType, string> = {
    object: t('typeSingularObject'),
    entity: t('typeSingularEntity'),
    place: t('typeSingularPlace'),
    occurrence: t('typeSingularOccurrence'),
    procedure: t('typeSingularProcedure'),
    collection: t('typeSingularCollection'),
  }

  const [tab, setTab] = useState(initialTab && tabIds.includes(initialTab) ? initialTab : 'all')
  const skipResetRef = useRef(true)
  const [q, setQ] = useState('')
  const [subtypeFilter, setSubtypeFilter] = useState('')
  const [availableSubtypes, setAvailableSubtypes] = useState<RecordSubtype[]>([])
  const [dueBefore, setDueBefore] = useState('')
  const [referenceNumber, setReferenceNumber] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Page<AnyRecord>>({ total: 0, page: 1, page_size: PAGE_SIZE, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestSeqRef = useRef(0)
  const selectAllRef = useRef<HTMLInputElement>(null)
  const user = getTokenUser()
  const canEdit = user?.role !== 'viewer'
  const canDelete = user?.role !== 'viewer'

  const [debouncedQ, setDebouncedQ] = useState('')
  const [listFields, setListFields] = useState<FieldDefinition[]>([])
  const [sortBy, setSortBy] = useState<'idno' | 'status' | 'updated_at' | ''>('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [selectionMode, setSelectionMode] = useState<'page' | 'all'>('page')
  const [batchOpen, setBatchOpen] = useState(false)
  const [addToSetOpen, setAddToSetOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [treeItems, setTreeItems] = useState<AnyRecord[] | null>(null)

  // Hierarchical browse: only when unfiltered/unsorted, so parent/child relations stay complete.
  const isCollectionTree = recordType === 'collection' && tab === 'all' && !debouncedQ && !subtypeFilter && !sortBy

  useEffect(() => {
    if (!isCollectionTree) { setTreeItems(null); return }
    let cancelled = false
    collections.list({ page_size: 200 }).then(res => {
      if (!cancelled) setTreeItems(res.items)
    }).catch(() => { if (!cancelled) setTreeItems(null) })
    return () => { cancelled = true }
  }, [isCollectionTree])

  const currentFilters = useMemo<Record<string, unknown>>(() => {
    const f: Record<string, unknown> = {}
    if (tab !== 'all') f.status = tab
    if (debouncedQ) f.q = debouncedQ
    if (subtypeKey && subtypeFilter) f[subtypeKey] = subtypeFilter
    if (recordType === 'procedure') {
      if (dueBefore) f.due_before = dueBefore
      if (referenceNumber) f.reference_number = referenceNumber
    }
    return f
  }, [tab, debouncedQ, subtypeFilter, subtypeKey, dueBefore, referenceNumber, recordType])

  function resetSelection() {
    setSel(new Set())
    setSelectionMode('page')
  }

  // List columns include subtype-specific fields when a subtype is selected.
  useEffect(() => {
    schema.list(recordType, subtypeFilter || undefined)
      .then(fields => {
        const visible = fields
          .filter(f => f.show_in_list)
          .sort((a, b) => a.sort_order - b.sort_order)
        setListFields(visible)
      })
      .catch(() => setListFields([]))
  }, [recordType, subtypeFilter])

  useEffect(() => {
    if (!subtypeKey) {
      setAvailableSubtypes([])
      return
    }
    subtypes.list(recordType).then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
  }, [recordType, subtypeKey])

  useEffect(() => {
    if (skipResetRef.current) { skipResetRef.current = false; return }
    setTab('all')
    setQ('')
    setSubtypeFilter('')
    setDueBefore('')
    setReferenceNumber('')
    setPage(1)
    setDebouncedQ('')
    resetSelection()
  }, [recordType])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(q), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q])

  const load = useCallback(() => {
    const requestSeq = ++requestSeqRef.current
    setLoading(true)
    setError(null)
    const params: Record<string, unknown> = {
      page,
      page_size: PAGE_SIZE,
      status: tab === 'all' ? undefined : tab,
    }
    if (debouncedQ) params.q = debouncedQ
    if (subtypeKey && subtypeFilter) params[subtypeKey] = subtypeFilter
    if (recordType === 'procedure') {
      if (dueBefore) params.due_before = dueBefore
      if (referenceNumber) params.reference_number = referenceNumber
    }
    if (sortBy) { params.sort_by = sortBy; params.sort_dir = sortDir }
    ;(api.list as (p: typeof params) => Promise<Page<AnyRecord>>)(params)
      .then(d => {
        if (requestSeq !== requestSeqRef.current) return
        const lastPage = Math.max(1, Math.ceil(d.total / PAGE_SIZE))
        if (page > lastPage) {
          setPage(lastPage)
          return
        }
        setData(d)
      })
      .catch(e => {
        if (requestSeq === requestSeqRef.current) setError(e.message)
      })
      .finally(() => {
        if (requestSeq === requestSeqRef.current) setLoading(false)
      })
  }, [page, tab, debouncedQ, subtypeFilter, subtypeKey, dueBefore, referenceNumber, sortBy, sortDir, api, recordType])

  useEffect(() => { load() }, [load])

  function handleTabChange(id: string) { resetSelection(); setTab(id); setPage(1); onTabChange?.(id) }
  function handleSort(col: 'idno' | 'status' | 'updated_at') {
    if (sortBy === col) { setSortDir(d => d === 'asc' ? 'desc' : 'asc') }
    else { setSortBy(col); setSortDir('asc') }
    setPage(1)
  }
  function handleSearch(v: string) { resetSelection(); setQ(v); setPage(1) }
  function handleOverdue() {
    resetSelection()
    setTab('active')
    setDueBefore(new Date().toISOString().slice(0, 10))
    setPage(1)
    onTabChange?.('active')
  }

  function removeLocally(id: string) {
    setData(prev => ({ ...prev, items: prev.items.filter(item => item.id !== id), total: Math.max(0, prev.total - 1) }))
    setSel(prev => { if (!prev.has(id)) return prev; const next = new Set(prev); next.delete(id); return next })
  }

  async function handleDelete(id: string) {
    if (!window.confirm(t('deleteConfirm', { type: typeSingularLabels[recordType] }))) return
    try {
      await api.delete(id)
      removeLocally(id)
      load()
    } catch (e) {
      if (e instanceof ConflictError) {
        const confirmed = window.confirm(t('deleteConfirmWithConflicts', { message: e.message }))
        if (!confirmed) return
        try {
          await api.delete(id, true)
          removeLocally(id)
          load()
        } catch (e2) {
          alert((e2 as Error).message)
        }
      } else {
        alert((e as Error).message)
      }
    }
  }

  // Primary label field: first list field, or fallback to label
  const primaryField = listFields[0]
  const primaryKey = primaryField?.name || 'label'
  const collectionTree = useMemo(
    () => (isCollectionTree && treeItems ? buildCollectionTree(treeItems, primaryKey) : null),
    [isCollectionTree, treeItems, primaryKey],
  )
  const items = collectionTree ? collectionTree.list : data.items
  const showingTree = isCollectionTree && !collectionTree
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const visiblePageCount = Math.min(totalPages, 5)
  const firstVisiblePage = Math.min(
    Math.max(1, page - Math.floor(visiblePageCount / 2)),
    totalPages - visiblePageCount + 1,
  )
  const visiblePages = Array.from({ length: visiblePageCount }, (_, i) => firstVisiblePage + i)
  const allSel = selectionMode === 'all' || (items.length > 0 && items.every(o => sel.has(o.id)))
  const someSel = selectionMode === 'all' || items.some(o => sel.has(o.id))
  const canSelectAll = selectionMode === 'page' && someSel && data.total > items.length

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someSel && !allSel
  }, [allSel, someSel])

  function toggle(id: string) {
    if (selectionMode === 'all') {
      setSel(new Set([id]))
      setSelectionMode('page')
      return
    }
    setSel(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  function toggleAll() {
    if (selectionMode === 'all') {
      resetSelection()
      return
    }
    if (allSel) setSel(new Set()); else setSel(new Set(items.map(o => o.id)))
  }
  function selectAllMatching() {
    setSelectionMode('all')
    setSel(new Set(items.map(o => o.id)))
  }
  function selectionSummary() {
    if (selectionMode === 'all') return t('selectionAllMatching', { count: data.total })
    return t('selectionSomeSelected', { count: sel.size })
  }
  function fmt(iso: string) {
    return new Date(iso).toLocaleDateString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  // Build column configuration dynamically
  // Always: Checkbox, ID-Nr., [Subtype], [listFields...], Status, Geändert, Actions
  const showIdno = true
  const showSubtype = Boolean(subtypeKey)
  const primaryLabel = primaryField?.label?.de || primaryField?.label?.en || primaryField?.name || 'Titel'

  // Additional list fields (after primary)
  const extraFields = listFields.slice(1)

  const colCount = 4 + (showIdno ? 1 : 0) + (showSubtype ? 1 : 0) + extraFields.length

  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>{typeLabels[recordType]}</h1>
          <div className="sub">{t('recordsCount', { count: data.total })}</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={() => onOpen?.('new')} data-tour="new-record-button">
            <Plus size={13} /> {t('addButton')}
          </button>
        </div>
      </div>

      <div className="tabs">
            {tabs.map(tp => (
          <button key={tp.id} className={`tab${tab === tp.id ? ' active' : ''}`} onClick={() => handleTabChange(tp.id)}>
            {tp.label}
            {tp.id === 'all' && <span className="ct">{data.total}</span>}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <div className="search">
          <Search className="ic" size={14} />
          <input
            aria-label={t('searchAriaLabel', { type: typeLabels[recordType] })}
            placeholder={t('searchPlaceholder')}
            value={q}
            onChange={e => handleSearch(e.target.value)}
          />
        </div>
        {availableSubtypes.length > 0 && (
          <select
            aria-label={t('subtypeFilterAriaLabel')}
            className="fld"
            style={{ maxWidth: 210 }}
            value={subtypeFilter}
            onChange={e => { resetSelection(); setSubtypeFilter(e.target.value); setPage(1) }}
          >
            <option value="">{t('subtypeFilterAll')}</option>
            {availableSubtypes.map(subtype => (
              <option key={subtype.id} value={subtype.name}>{getLabel(subtype, subtype.name)}</option>
            ))}
          </select>
        )}
        {recordType === 'procedure' && (
          <>
            <input aria-label={t('dueDateAriaLabel')} className="fld mono" type="date" style={{ maxWidth: 150 }} value={dueBefore} onChange={e => { resetSelection(); setDueBefore(e.target.value); setPage(1) }} title={t('dueDateTitle')} />
            <input aria-label={t('referenceNumberAriaLabel')} className="fld mono" style={{ maxWidth: 180 }} placeholder={t('referenceNumberPlaceholder')} value={referenceNumber} onChange={e => { resetSelection(); setReferenceNumber(e.target.value); setPage(1) }} />
            <button className="btn gh" onClick={handleOverdue}>{t('overdueButton')}</button>
          </>
        )}
      </div>

      {someSel && (
        <div className="bb">
          <b>{selectionSummary()}</b>
          <div className="grow" />
          {canSelectAll && (
            <button onClick={selectAllMatching}>{t('selectAllMatching', { count: data.total })}</button>
          )}
          {selectionMode === 'all' && (
            <button onClick={resetSelection}>{t('selectThisPage')}</button>
          )}
          <button onClick={() => setBatchOpen(true)}><Layers size={13} /> {t('batchEdit')}</button>
          <button onClick={() => setAddToSetOpen(true)}><Folder size={13} /> {t('addToWorkingSet')}</button>
          <button onClick={resetSelection}>{t('selectionCancel')}</button>
        </div>
      )}

      {toast && (
        <div style={{ margin: '14px 24px 0 24px', padding: '10px 16px', background: '#dcfce7', color: '#166534', borderRadius: 6, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>{toast}</span>
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 'bold' }}>×</button>
        </div>
      )}

      {error && <div className="empty" style={{ color: '#f87171', padding: '16px 24px' }}>{error}</div>}

      <div className="tw">
        <table className="tbl">
          <thead>
            <tr>
              <th className="col-ck">
                <label className="ck-hit">
                  <input
                    aria-label={t('selectAllAriaLabel')}
                    ref={selectAllRef}
                    type="checkbox"
                    className={`ck${someSel && !allSel ? ' ind' : ''}`}
                    checked={allSel}
                    onChange={toggleAll}
                  />
                </label>
              </th>
              {showIdno && (
                <th className="sortable" style={{ width: 140 }} onClick={() => handleSort('idno')}>
                  {t('tableIdno')}{sortBy === 'idno' && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                </th>
              )}
              {showSubtype && <th style={{ width: 120 }}>{t('tableType')}</th>}
              <th>{primaryLabel}</th>
              {extraFields.map(f => (
                <th key={f.name} style={{ width: 140 }}>{f.label?.de || f.label?.en || f.name}</th>
              ))}
              <th className="sortable" style={{ width: 100 }} onClick={() => handleSort('status')}>
                {t('tableStatus')}{sortBy === 'status' && (sortDir === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th className="sortable" style={{ width: 120 }} onClick={() => handleSort('updated_at')}>
                {t('tableChanged')}{sortBy === 'updated_at' && (sortDir === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th className="col-act" />
            </tr>
          </thead>
          <tbody>
            {(loading || showingTree) && (
              <tr><td colSpan={colCount} className="empty">{t('loading')}</td></tr>
            )}
            {!loading && !showingTree && items.length === 0 && (
              <tr><td colSpan={colCount} className="empty">{t('empty')}</td></tr>
            )}
            {!loading && !showingTree && items.map(rec => {
              const m = rec.metadata_ as Record<string, unknown>
              const subtypeVal = subtypeKey ? String((rec as unknown as Record<string, unknown>)[subtypeKey] ?? '') : ''
              const idno = (rec as { idno?: string | null }).idno
              const title = getFieldValue(m, primaryKey)
              const discriminator = idno || rec.id
              const recordLabel = title ? `${title} (${discriminator})` : discriminator
              const depth = collectionTree?.depth.get(rec.id) ?? 0
              return (
                <tr key={rec.id} className={sel.has(rec.id) ? 'sel' : ''}>
                  <td className="col-ck">
                    <label className="ck-hit">
                      <input aria-label={t('selectRowAriaLabel', { label: recordLabel })} type="checkbox" className="ck" checked={sel.has(rec.id)} onChange={() => toggle(rec.id)} />
                    </label>
                  </td>
                  {showIdno && <td className="mono">{idno}</td>}
                  {showSubtype && <td style={{ color: 'var(--fg-2)', fontSize: 12 }}>{subtypeVal}</td>}
                  <td>
                    {depth > 0 && <span style={{ display: 'inline-block', width: depth * 16 }} aria-hidden="true" />}
                    {depth > 0 && <span style={{ color: 'var(--fg-4)', marginRight: 4 }} aria-hidden="true">&#8627;</span>}
                    <span className="tt">{getFieldValue(m, primaryKey)}</span>
                  </td>
                  {extraFields.map(f => (
                    <td key={f.name} style={{ color: 'var(--fg-2)' }}>
                      {getFieldValue(m, f.name)}
                    </td>
                  ))}
                  <td><StatusBadge status={(rec as { status?: string }).status ?? 'draft'} /></td>
                  <td style={{ color: 'var(--fg-3)', fontSize: 12 }}>{fmt(rec.updated_at)}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <ActionMenu
                        ariaLabel={t('editRowAriaLabel', { label: recordLabel })}
                        items={[
                          {
                            key: canEdit ? 'edit' : 'view',
                            label: canEdit ? t('editRowTitle') : t('viewRowTitle'),
                            icon: canEdit ? <Edit size={13} /> : <Eye size={13} />,
                            onClick: () => onOpen?.(rec.id),
                          },
                          ...(canDelete ? [{
                            key: 'delete',
                            label: t('deleteRowTitle'),
                            icon: <Trash size={13} />,
                            danger: true,
                            onClick: () => handleDelete(rec.id),
                          }] : []),
                        ]}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {!isCollectionTree && totalPages > 1 && (
          <nav className="pg" aria-label={t('paginationNavAriaLabel')}>
            <span className="pg-range">{t('paginationRange', { start: (page - 1) * PAGE_SIZE + 1, end: Math.min(page * PAGE_SIZE, data.total), total: data.total })}</span>
            <div className="pg-controls">
              <button className="pg-nav" disabled={page === 1} onClick={() => setPage(page - 1)}>{t('paginationPrev')}</button>
              <div className="nums">
                {visiblePages.map(n => (
                  <button
                    key={n}
                    aria-label={t('paginationPageAriaLabel', { number: n })}
                    aria-current={n === page ? 'page' : undefined}
                    className={`pg-num${n === page ? ' active' : ''}`}
                    onClick={() => setPage(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <button className="pg-nav" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>{t('paginationNext')}</button>
            </div>
            <span className="pg-summary">{t('paginationSummary', { page, totalPages })}</span>
            <span className="pg-size">{t('paginationPageSize', { size: PAGE_SIZE })}</span>
          </nav>
        )}
      </div>

      {batchOpen && (
        <BatchEditModal
          recordType={recordType}
          fields={listFields}
          selection={
            selectionMode === 'all'
              ? { mode: 'filters', ids: [], filters: currentFilters, count: data.total }
              : { mode: 'ids', ids: Array.from(sel), filters: {}, count: sel.size }
          }
          onClose={() => setBatchOpen(false)}
          onSuccess={() => {
            setBatchOpen(false)
            resetSelection()
            load()
          }}
        />
      )}

      {addToSetOpen && (
        <AddToWorkingSetModal
          recordType={recordType}
          recordIds={items.filter((it) => sel.has(it.id)).map((it) => it.id)}
          onClose={() => setAddToSetOpen(false)}
          onSuccess={(setName, count) => {
            setAddToSetOpen(false)
            resetSelection()
            setToast(count === 1 ? t('addSuccess_one', { name: setName }) : t('addSuccess', { count, name: setName }))
            setTimeout(() => setToast(null), 5000)
          }}
        />
      )}
    </div>
  )
}