import { useState, useEffect, useRef, useCallback } from 'react'
import { objects } from '../../api/client'
import type { KatalonObject, Page } from '../../types'
import { StatusBadge } from '../ui/StatusBadge'
import { Edit, Plus, Search, Trash } from '../ui/Icons'

const TABS = [
  { id: 'all',      label: 'Alle' },
  { id: 'draft',    label: 'Entwurf' },
  { id: 'internal', label: 'Intern' },
  { id: 'public',   label: 'Öffentlich' },
]

const PAGE_SIZE = 50

interface Props { onOpen?: (id: string) => void }

export function ScreenList({ onOpen }: Props) {
  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Page<KatalonObject>>({ total: 0, page: 1, page_size: PAGE_SIZE, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedQ, setDebouncedQ] = useState('')

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(q), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q])

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    objects.list({
      page,
      page_size: PAGE_SIZE,
      status: tab === 'all' ? undefined : tab,
      q: debouncedQ || undefined,
    })
      .then(d => { setData(d); setSel(new Set()) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, tab, debouncedQ])

  useEffect(() => { load() }, [load])

  function handleTabChange(id: string) { setTab(id); setPage(1) }
  function handleSearch(v: string) { setQ(v); setPage(1) }

  async function handleDelete(id: string) {
    if (!window.confirm('Objekt wirklich löschen?')) return
    try {
      await objects.delete(id)
      load()
    } catch (e) {
      alert((e as Error).message)
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

  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>Objekte</h1>
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
            placeholder="Titel, Inventar-Nr., Urheber…"
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
              <th className="col-thumb" />
              <th>Inventar-Nr.</th>
              <th>Titel</th>
              <th>Status</th>
              <th>Urheber:in</th>
              <th>Jahr</th>
              <th>Geändert</th>
              <th className="col-act" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={9} className="empty">Lade…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={9} className="empty">Keine Datensätze gefunden.</td></tr>
            )}
            {!loading && items.map(obj => {
              const m = obj.metadata_ as Record<string, unknown>
              return (
                <tr key={obj.id} className={sel.has(obj.id) ? 'sel' : ''}>
                  <td className="col-ck"><input type="checkbox" className="ck" checked={sel.has(obj.id)} onChange={() => toggle(obj.id)} /></td>
                  <td className="col-thumb"><div className="thumb" /></td>
                  <td className="mono" style={{ maxWidth: 140 }}>{obj.idno}</td>
                  <td style={{ maxWidth: 280 }}><span className="tt">{String(m.title ?? '')}</span></td>
                  <td style={{ maxWidth: 100 }}><StatusBadge status={obj.status} /></td>
                  <td style={{ maxWidth: 140, color: 'var(--fg-2)' }}>{String(m.creator ?? '')}</td>
                  <td style={{ maxWidth: 80, color: 'var(--fg-3)' }} className="mono">{String(m.year ?? '')}</td>
                  <td style={{ maxWidth: 120, color: 'var(--fg-3)', fontSize: 12 }}>{fmt(obj.updated_at)}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button className="btn sm ico gh" title="Bearbeiten" onClick={() => onOpen?.(obj.id)}><Edit size={12} /></button>
                      <button className="btn sm ico gh dn" title="Löschen" onClick={() => handleDelete(obj.id)}><Trash size={12} /></button>
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
