import { useState, useEffect, useRef, useCallback } from 'react'
import { objects, entities, places, occurrences, procedures, schema, subtypes, ConflictError } from '../../api/client'
import type { AnyRecord, FieldDefinition, Page, RecordSubtype, RecordType } from '../../types'
import { getLabel } from '../../types'
import { StatusBadge } from '../ui/StatusBadge'
import { Edit, Plus, Search, Trash } from '../ui/Icons'

const TABS = [
  { id: 'all',      label: 'Alle' },
  { id: 'draft',    label: 'Entwurf' },
  { id: 'internal', label: 'Intern' },
  { id: 'public',   label: 'Öffentlich' },
]
const PROCEDURE_TABS = [
  { id: 'all',       label: 'Alle' },
  { id: 'draft',     label: 'Entwurf' },
  { id: 'active',    label: 'Aktiv' },
  { id: 'completed', label: 'Abgeschlossen' },
  { id: 'cancelled', label: 'Abgebrochen' },
]
const PAGE_SIZE = 50

const TYPE_LABELS: Record<RecordType, string> = {
  object: 'Objekte',
  entity: 'Entitäten',
  place: 'Orte',
  occurrence: 'Occurrences',
  procedure: 'Vorgänge',
}

const TYPE_SINGULAR_LABELS: Record<RecordType, string> = {
  object: 'Objekt',
  entity: 'Entität',
  place: 'Ort',
  occurrence: 'Occurrence',
  procedure: 'Vorgang',
}

const SUBTYPE_KEYS: Record<RecordType, string | undefined> = {
  object: 'object_type',
  entity: 'entity_type',
  place: 'place_type',
  occurrence: 'occurrence_type',
  procedure: 'procedure_type',
}

function getApi(recordType: RecordType) {
  switch (recordType) {
    case 'object':     return objects
    case 'entity':     return entities
    case 'place':      return places
    case 'occurrence': return occurrences
    case 'procedure':  return procedures
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
    if ('label' in val) return String((val as { label?: unknown }).label ?? '')
    if ('value' in val) return String((val as { value?: unknown }).value ?? '')
    return ''
  }
  return String(val)
}

interface Props {
  recordType: RecordType
  onOpen?: (id: string) => void
}

export function ScreenList({ recordType, onOpen }: Props) {
  const api = getApi(recordType)
  const subtypeKey = SUBTYPE_KEYS[recordType]

  const [tab, setTab] = useState('all')
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
  const [debouncedQ, setDebouncedQ] = useState('')
  const [listFields, setListFields] = useState<FieldDefinition[]>([])

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
    setTab('all')
    setQ('')
    setSubtypeFilter('')
    setDueBefore('')
    setReferenceNumber('')
    setPage(1)
    setDebouncedQ('')
    setSel(new Set())
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
    ;(api.list as (p: typeof params) => Promise<Page<AnyRecord>>)(params)
      .then(d => {
        if (requestSeq !== requestSeqRef.current) return
        const lastPage = Math.max(1, Math.ceil(d.total / PAGE_SIZE))
        setSel(new Set())
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
  }, [page, tab, debouncedQ, subtypeFilter, subtypeKey, dueBefore, referenceNumber, api, recordType])

  useEffect(() => { load() }, [load])

  function handleTabChange(id: string) { setTab(id); setPage(1) }
  function handleSearch(v: string) { setQ(v); setPage(1) }
  function handleOverdue() {
    setTab('active')
    setDueBefore(new Date().toISOString().slice(0, 10))
    setPage(1)
  }

  async function handleDelete(id: string) {
    if (!window.confirm(`${TYPE_SINGULAR_LABELS[recordType]} wirklich löschen?`)) return
    try {
      await api.delete(id)
      load()
    } catch (e) {
      if (e instanceof ConflictError) {
        const confirmed = window.confirm(
          `${e.message}\n\nAlle Verknüpfungen werden beim Löschen entfernt. Fortfahren?`
        )
        if (!confirmed) return
        try {
          await api.delete(id, true)
          load()
        } catch (e2) {
          alert((e2 as Error).message)
        }
      } else {
        alert((e as Error).message)
      }
    }
  }

  const items = data.items
  const tabs = recordType === 'procedure' ? PROCEDURE_TABS : TABS
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const visiblePageCount = Math.min(totalPages, 5)
  const firstVisiblePage = Math.min(
    Math.max(1, page - Math.floor(visiblePageCount / 2)),
    totalPages - visiblePageCount + 1,
  )
  const visiblePages = Array.from({ length: visiblePageCount }, (_, i) => firstVisiblePage + i)
  const allSel = items.length > 0 && items.every(o => sel.has(o.id))
  const someSel = items.some(o => sel.has(o.id))

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someSel && !allSel
  }, [allSel, someSel])

  function toggle(id: string) {
    setSel(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  function toggleAll() {
    if (allSel) setSel(new Set()); else setSel(new Set(items.map(o => o.id)))
  }
  function fmt(iso: string) {
    return new Date(iso).toLocaleDateString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  // Build column configuration dynamically
  // Always: Checkbox, ID-Nr., [Subtype], [listFields...], Status, Geändert, Actions
  const showIdno = true
  const showSubtype = Boolean(subtypeKey)
  // Primary label field: first list field, or fallback to label
  const primaryField = listFields[0]
  const primaryLabel = primaryField?.label?.de || primaryField?.label?.en || primaryField?.name || 'Titel'
  const primaryKey = primaryField?.name || 'label'

  // Additional list fields (after primary)
  const extraFields = listFields.slice(1)

  const colCount = 4 + (showIdno ? 1 : 0) + (showSubtype ? 1 : 0) + extraFields.length

  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>{TYPE_LABELS[recordType]}</h1>
          <div className="sub">{data.total.toLocaleString('de')} Datensätze</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={() => onOpen?.('new')} data-tour="new-record-button">
            <Plus size={13} /> Neu anlegen
          </button>
        </div>
      </div>

      <div className="tabs">
            {tabs.map(t => (
          <button key={t.id} className={`tab${tab === t.id ? ' active' : ''}`} onClick={() => handleTabChange(t.id)}>
            {t.label}
            {t.id === 'all' && <span className="ct">{data.total}</span>}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <div className="search">
          <Search className="ic" size={14} />
          <input
            aria-label={`${TYPE_LABELS[recordType]} durchsuchen`}
            placeholder="Suchen…"
            value={q}
            onChange={e => handleSearch(e.target.value)}
          />
        </div>
        {availableSubtypes.length > 0 && (
          <select
            aria-label="Subtyp filtern"
            className="fld"
            style={{ maxWidth: 210 }}
            value={subtypeFilter}
            onChange={e => { setSubtypeFilter(e.target.value); setPage(1) }}
          >
            <option value="">Alle Typen</option>
            {availableSubtypes.map(subtype => (
              <option key={subtype.id} value={subtype.name}>{getLabel(subtype, subtype.name)}</option>
            ))}
          </select>
        )}
        {recordType === 'procedure' && (
          <>
            <input aria-label="Fällig bis" className="fld mono" type="date" style={{ maxWidth: 150 }} value={dueBefore} onChange={e => { setDueBefore(e.target.value); setPage(1) }} title="Fällig bis" />
            <input aria-label="Referenznummer" className="fld mono" style={{ maxWidth: 180 }} placeholder="Referenznr." value={referenceNumber} onChange={e => { setReferenceNumber(e.target.value); setPage(1) }} />
            <button className="btn gh" onClick={handleOverdue}>Überfällig</button>
          </>
        )}
      </div>

      {someSel && (
        <div className="bb">
          <b>{sel.size} ausgewählt</b>
          <div className="grow" />
          <button onClick={() => setSel(new Set())}>Abbrechen</button>
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
                    aria-label="Alle Datensätze auf dieser Seite auswählen"
                    ref={selectAllRef}
                    type="checkbox"
                    className={`ck${someSel && !allSel ? ' ind' : ''}`}
                    checked={allSel}
                    onChange={toggleAll}
                  />
                </label>
              </th>
              {showIdno && <th>ID-Nr.</th>}
              {showSubtype && <th>Typ</th>}
              <th>{primaryLabel}</th>
              {extraFields.map(f => (
                <th key={f.name}>{f.label?.de || f.label?.en || f.name}</th>
              ))}
              <th>Status</th>
              <th>Geändert</th>
              <th className="col-act" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={colCount} className="empty">Lade…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={colCount} className="empty">Keine Datensätze gefunden.</td></tr>
            )}
            {!loading && items.map(rec => {
              const m = rec.metadata_ as Record<string, unknown>
              const subtypeVal = subtypeKey ? String((rec as unknown as Record<string, unknown>)[subtypeKey] ?? '') : ''
              const idno = (rec as { idno?: string | null }).idno
              const title = getFieldValue(m, primaryKey)
              const discriminator = idno || rec.id
              const recordLabel = title ? `${title} (${discriminator})` : discriminator
              return (
                <tr key={rec.id} className={sel.has(rec.id) ? 'sel' : ''}>
                  <td className="col-ck">
                    <label className="ck-hit">
                      <input aria-label={`${recordLabel} auswählen`} type="checkbox" className="ck" checked={sel.has(rec.id)} onChange={() => toggle(rec.id)} />
                    </label>
                  </td>
                  {showIdno && <td className="mono" style={{ maxWidth: 140 }}>{idno}</td>}
                  {showSubtype && <td style={{ maxWidth: 120, color: 'var(--fg-2)', fontSize: 12 }}>{subtypeVal}</td>}
                  <td style={{ maxWidth: 280 }}><span className="tt">{getFieldValue(m, primaryKey)}</span></td>
                  {extraFields.map(f => (
                    <td key={f.name} style={{ maxWidth: 140, color: 'var(--fg-2)' }}>
                      {getFieldValue(m, f.name)}
                    </td>
                  ))}
                  <td style={{ maxWidth: 100 }}><StatusBadge status={rec.status} /></td>
                  <td style={{ maxWidth: 120, color: 'var(--fg-3)', fontSize: 12 }}>{fmt(rec.updated_at)}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button aria-label={`${recordLabel} bearbeiten`} className="btn sm ico gh" title="Bearbeiten" onClick={() => onOpen?.(rec.id)}><Edit size={12} /></button>
                      <button aria-label={`${recordLabel} löschen`} className="btn sm ico gh dn" title="Löschen" onClick={() => handleDelete(rec.id)}><Trash size={12} /></button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {totalPages > 1 && (
          <nav className="pg" aria-label="Seitennavigation">
            <span className="pg-range">{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} von {data.total}</span>
            <div className="pg-controls">
              <button className="pg-nav" disabled={page === 1} onClick={() => setPage(page - 1)}>Zurück</button>
              <div className="nums">
                {visiblePages.map(n => (
                  <button
                    key={n}
                    aria-label={`Seite ${n}`}
                    aria-current={n === page ? 'page' : undefined}
                    className={`pg-num${n === page ? ' active' : ''}`}
                    onClick={() => setPage(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <button className="pg-nav" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Weiter</button>
            </div>
            <span className="pg-summary">Seite {page} von {totalPages}</span>
            <span className="pg-size">{PAGE_SIZE} pro Seite</span>
          </nav>
        )}
      </div>
    </div>
  )
}
