import { useState, useEffect, useRef } from 'react'
import { Bell, Help, Search } from '../ui/Icons'
import { search } from '../../api/client'
import type { SearchResult } from '../../types'

const TYPE_LABELS: Record<string, string> = {
  object: 'Obj', entity: 'Ent', place: 'Ort', occurrence: 'Occ',
}

interface Props {
  crumbs: Array<{ label: string; route?: string }>
  onNavigate?: (route: string, id?: string) => void
}

export function Topbar({ crumbs, onNavigate }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!q.trim()) { setResults([]); setOpen(false); return }
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      search.query(q.trim())
        .then(r => { setResults(r.items); setOpen(true) })
        .catch(() => { setResults([]) })
        .finally(() => setLoading(false))
    }, 250)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q])

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  function handleSelect(r: SearchResult) {
    setQ('')
    setOpen(false)
    if (r.record_type === 'object') {
      onNavigate?.('form', r.id)
    } else {
      onNavigate?.(r.record_type + 's')
    }
  }

  return (
    <div className="tb">
      <div className="cr">
        {crumbs.map((c, i) =>
          i === crumbs.length - 1 ? (
            <b key={i}>{c.label}</b>
          ) : c.route ? (
            <span key={i}>
              <button onClick={() => onNavigate?.(c.route!)}>{c.label}</button>
              <span className="sep"> / </span>
            </span>
          ) : (
            <span key={i}>{c.label}<span className="sep"> / </span></span>
          )
        )}
      </div>
      <div className="sp" />
      <div className="gs" ref={wrapRef} style={{ position: 'relative' }}>
        <Search size={14} />
        <input
          placeholder="Global suchen — Objekte, Entitäten, Vokabeln…"
          value={q}
          onChange={e => setQ(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true) }}
        />
        {loading && <span style={{ fontSize: 11, color: 'var(--fg-4)', marginRight: 4 }}>…</span>}
        <span className="kbd">⌘K</span>

        {open && results.length > 0 && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
            background: '#fff', border: '1px solid var(--border)', borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)', zIndex: 200, overflow: 'hidden',
          }}>
            {results.map(r => (
              <div key={r.id}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', cursor: 'pointer', fontSize: 13 }}
                onMouseDown={() => handleSelect(r)}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg)')}
                onMouseLeave={e => (e.currentTarget.style.background = '')}
              >
                <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--accent-50)', color: 'var(--accent-ink)', padding: '1px 5px', borderRadius: 4, flexShrink: 0 }}>
                  {TYPE_LABELS[r.record_type] ?? r.record_type}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</span>
                {r.status && <span style={{ fontSize: 11, color: 'var(--fg-3)', flexShrink: 0 }}>{r.status}</span>}
              </div>
            ))}
          </div>
        )}

        {open && results.length === 0 && q.trim() && !loading && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
            background: '#fff', border: '1px solid var(--border)', borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)', zIndex: 200,
            padding: '12px', fontSize: 13, color: 'var(--fg-3)', textAlign: 'center',
          }}>
            Keine Treffer für „{q}"
          </div>
        )}
      </div>
      <button className="ib" title="Hilfe"><Help size={15} /></button>
      <button className="ib" title="Benachrichtigungen"><Bell size={15} /></button>
    </div>
  )
}
