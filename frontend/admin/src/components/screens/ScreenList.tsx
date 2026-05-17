import { useState, useEffect, useRef, useCallback } from 'react'
import { objects, entities, places, occurrences, ConflictError } from '../../api/client'
import type { AnyRecord, Page, RecordType } from '../../types'
import { StatusBadge } from '../ui/StatusBadge'
import { Edit, Plus, Search, Trash } from '../ui/Icons'

const TABS = [
  { id: 'all',      label: 'Alle' },
  { id: 'draft',    label: 'Entwurf' },
  { id: 'internal', label: 'Intern' },
  { id: 'public',   label: 'Öffentlich' },
]

const PAGE_SIZE = 50

type TypeConfig = {
  label: string
  schemaType: string
  subtypeKey?: string
  subtypeLabel?: string
  primaryLabel: string
  primaryKey: string
  secondaryLabel?: string
  secondaryKey?: string
}

const TYPE_CONFIG: Record<RecordType, TypeConfig> = {
  object:     { label: 'Objekte',     schemaType: 'object',     subtypeKey: 'object_type',     subtypeLabel: 'Typ', primaryLabel: 'Titel',       primaryKey: 'title',    secondaryLabel: 'Urheber:in', secondaryKey: 'creator' },
  entity:     { label: 'Entitäten',   schemaType: 'entity',     subtypeKey: 'entity_type',     subtypeLabel: 'Typ', primaryLabel: 'Name',        primaryKey: 'name' },
  place:      { label: 'Orte',        schemaType: 'place',      subtypeKey: 'place_type',      subtypeLabel: 'Typ', primaryLabel: 'Name',        primaryKey: 'name' },
  occurrence: { label: 'Occurrences', schemaType: 'occurrence', subtypeKey: 'occurrence_type', subtypeLabel: 'Typ', primaryLabel: 'Titel',       primaryKey: 'title' },
}

function getApi(recordType: RecordType) {
  switch (recordType) {
    case 'object':     return objects
    case 'entity':     return entities
    case 'place':      return places
    case 'occurrence': return occurrences
  }
}

interface Props {
  recordType: RecordType
  onOpen?: (id: string) => void
}

export function ScreenList({ recordType, onOpen }: Props) {
  const cfg = TYPE_CONFIG[recordType]
  const api = getApi(recordType)

  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Page<AnyRecord>>({ total: 0, page: 1, page_size: PAGE_SIZE, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedQ, setDebouncedQ] = useState('')

  useEffect(() => {
    setTab('all')
    setQ('')
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
    setLoading(true)
    setError(null)
    const params: Record<string, unknown> = {
      page,
      page_size: PAGE_SIZE,
      status: tab === 'all' ? undefined : tab,
    }
    if (debouncedQ) params.q = debouncedQ
    ;(api.list as (p: typeof params) => Promise<Page<AnyRecord>>)(params)
      .then(d => { setData(d); setSel(new Set()) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, tab, debouncedQ, api, recordType])

  useEffect(() => { load() }, [load])

  function handleTabChange(id: string) { setTab(id); setPage(1) }
  function handleSearch(v: string) { setQ(v); setPage(1) }

  async function handleDelete(id: string) {
    if (!window.confirm(`${cfg.label.slice(0, -1)} wirklich löschen?`)) return
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
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const allSel = items.length > 0 && items.every(o => sel.has(o.id))
  const someSel = items.some(o => sel.has(o.id))

  function toggle(id: string) {
    setSel(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }
  function toggleAll() {
    if (allSel) setSel(new Set()); else setSel(new Set(items.map(o => o.id)))
  }
  function fmt(iso: string) {
    return new Date(iso).toLocaleDateString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  const showIdno = true
  const showSubtype = Boolean(cfg.subtypeKey)
  const showSecondary = Boolean(cfg.secondaryKey)
  const colCount = 5 + (showIdno ? 1 : 0) + (showSubtype ? 1 : 0) + (showSecondary ? 1 : 0)

  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>{cfg.label}</h1>
          <div className="sub">{data.total.toLocaleString('de')} Datensätze</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={() => onOpen?.('new')}>
            <Plus size={13} /> Neu anlegen
          </button>
        </div>
      </div>

      <div className="tabs">
        {TABS.map(t => (
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
            placeholder="Suchen…"
            value={q}
            onChange={e => handleSearch(e.target.value)}
          />
        </div>
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
                <input type="checkbox" className={`ck${someSel && !allSel ? ' ind' : ''}`} checked={allSel} onChange={toggleAll} />
              </th>
              {showIdno    && <th>ID-Nr.</th>}
              {showSubtype && <th>{cfg.subtypeLabel}</th>}
              <th>{cfg.primaryLabel}</th>
              <th>Status</th>
              {showSecondary && <th>{cfg.secondaryLabel}</th>}
              {recordType === 'object' && <th>Jahr</th>}
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
              const subtypeVal = cfg.subtypeKey ? String((rec as unknown as Record<string, unknown>)[cfg.subtypeKey] ?? '') : ''
              const primaryVal = String(m[cfg.primaryKey] ?? '')
              const secondaryVal = cfg.secondaryKey ? String(m[cfg.secondaryKey] ?? '') : ''
              return (
                <tr key={rec.id} className={sel.has(rec.id) ? 'sel' : ''}>
                  <td className="col-ck"><input type="checkbox" className="ck" checked={sel.has(rec.id)} onChange={() => toggle(rec.id)} /></td>
                  {showIdno    && <td className="mono" style={{ maxWidth: 140 }}>{(rec as { idno?: string | null }).idno}</td>}
                  {showSubtype && <td style={{ maxWidth: 120, color: 'var(--fg-2)', fontSize: 12 }}>{subtypeVal}</td>}
                  <td style={{ maxWidth: 280 }}><span className="tt">{primaryVal}</span></td>
                  <td style={{ maxWidth: 100 }}><StatusBadge status={rec.status} /></td>
                  {showSecondary && <td style={{ maxWidth: 140, color: 'var(--fg-2)' }}>{secondaryVal}</td>}
                  {recordType === 'object' && <td style={{ maxWidth: 80, color: 'var(--fg-3)' }} className="mono">{String(m.year ?? '')}</td>}
                  <td style={{ maxWidth: 120, color: 'var(--fg-3)', fontSize: 12 }}>{fmt(rec.updated_at)}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button className="btn sm ico gh" title="Bearbeiten" onClick={() => onOpen?.(rec.id)}><Edit size={12} /></button>
                      <button className="btn sm ico gh dn" title="Löschen" onClick={() => handleDelete(rec.id)}><Trash size={12} /></button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {totalPages > 1 && (
          <div className="pg">
            <span>{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} von {data.total}</span>
            <div className="nums">
              {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map(n => (
                <button key={n} className={`pg-num${n === page ? ' active' : ''}`} onClick={() => setPage(n)}>{n}</button>
              ))}
            </div>
            <span>{PAGE_SIZE} pro Seite</span>
          </div>
        )}
      </div>
    </div>
  )
}
