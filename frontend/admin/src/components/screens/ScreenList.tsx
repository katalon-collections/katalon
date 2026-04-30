import { useState } from 'react'
import { MOCK_OBJECTS } from '../../api/mock-data'
import { StatusBadge } from '../ui/StatusBadge'
import { Edit, Plus, Search, Trash } from '../ui/Icons'

const TABS = [
  { id: 'all',      label: 'Alle' },
  { id: 'draft',    label: 'Entwurf' },
  { id: 'internal', label: 'Intern' },
  { id: 'public',   label: 'Öffentlich' },
]

function count(status: string) {
  if (status === 'all') return MOCK_OBJECTS.length
  return MOCK_OBJECTS.filter(o => o.status === status).length
}

interface Props { onOpen?: (id: string) => void }

export function ScreenList({ onOpen }: Props) {
  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<Set<string>>(new Set())

  const items = MOCK_OBJECTS.filter(o => {
    if (tab !== 'all' && o.status !== tab) return false
    if (!q) return true
    const s = q.toLowerCase()
    const m = o.metadata_ as Record<string, string>
    return (
      (o.idno ?? '').toLowerCase().includes(s) ||
      (m.title ?? '').toLowerCase().includes(s) ||
      (m.creator ?? '').toLowerCase().includes(s)
    )
  })

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
          <div className="sub">{MOCK_OBJECTS.length.toLocaleString('de')} Datensätze · Stadtarchiv Zürich</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={() => onOpen?.('new')}>
            <Plus size={13} /> Neu anlegen
          </button>
        </div>
      </div>

      <div className="tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}<span className="ct">{count(t.id)}</span>
          </button>
        ))}
      </div>

      <div className="toolbar">
        <div className="search">
          <Search className="ic" size={14} />
          <input placeholder="Titel, Inventar-Nr., Urheber…" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <button className="btn gh">Status</button>
        <button className="btn gh">Sammlung</button>
        <button className="btn gh">Jahr</button>
      </div>

      {someSel && (
        <div className="bb">
          <b>{sel.size} ausgewählt</b>
          <div className="grow" />
          <button>Status ändern</button>
          <button style={{ color: '#f87171' }}>Löschen</button>
          <button onClick={() => setSel(new Set())}>Abbrechen</button>
        </div>
      )}

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
            {items.length === 0 && (
              <tr><td colSpan={9} className="empty">Keine Datensätze gefunden.</td></tr>
            )}
            {items.map(obj => {
              const m = obj.metadata_ as Record<string, string>
              return (
                <tr key={obj.id} className={sel.has(obj.id) ? 'sel' : ''}>
                  <td className="col-ck"><input type="checkbox" className="ck" checked={sel.has(obj.id)} onChange={() => toggle(obj.id)} /></td>
                  <td className="col-thumb"><div className="thumb" /></td>
                  <td className="mono" style={{ maxWidth: 140 }}>{obj.idno}</td>
                  <td style={{ maxWidth: 280 }}><span className="tt">{m.title}</span></td>
                  <td style={{ maxWidth: 100 }}><StatusBadge status={obj.status} /></td>
                  <td style={{ maxWidth: 140, color: 'var(--fg-2)' }}>{m.creator}</td>
                  <td style={{ maxWidth: 80, color: 'var(--fg-3)' }} className="mono">{m.year}</td>
                  <td style={{ maxWidth: 120, color: 'var(--fg-3)', fontSize: 12 }}>{fmt(obj.updated_at)}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button className="btn sm ico gh" title="Bearbeiten" onClick={() => onOpen?.(obj.id)}><Edit size={12} /></button>
                      <button className="btn sm ico gh dn" title="Löschen"><Trash size={12} /></button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="pg">
          <span>1–{items.length} von {items.length}</span>
          <div className="nums">
            {[1,2,3].map(n => <button key={n} className={`pg-num${n===1?' active':''}`}>{n}</button>)}
          </div>
          <span>50 pro Seite</span>
        </div>
      </div>
    </div>
  )
}
