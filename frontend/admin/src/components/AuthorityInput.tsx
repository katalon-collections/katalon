import { useState, useEffect, useRef } from 'react'
import { authority as authorityApi } from '../api/client'
import type { AuthorityHit } from '../api/client'
import { X } from './ui/Icons'

export type AuthorityEntry = { source: string; external_id: string; label: string }

export function AuthorityInput({ source, value, onChange, disabled }: {
  source: string
  value: AuthorityEntry | null
  onChange: (v: AuthorityEntry | null) => void
  disabled?: boolean
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<AuthorityHit[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const t = e.target as Node
      if (inputRef.current?.contains(t) || dropRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    if (open && inputRef.current) {
      const r = inputRef.current.getBoundingClientRect()
      const spaceBelow = window.innerHeight - r.bottom - 8
      const spaceAbove = r.top - 8
      const showBelow = spaceBelow >= 120 || spaceBelow >= spaceAbove
      setDropPos({
        top: showBelow ? r.bottom + 2 : r.top - Math.min(280, spaceAbove) - 2,
        left: r.left,
        width: r.width,
        maxHeight: showBelow ? Math.min(280, spaceBelow) : Math.min(280, spaceAbove),
      })
    }
  }, [open])

  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults([]); setOpen(false); return }
    timer.current = setTimeout(() => {
      setBusy(true)
      authorityApi.search(source, q.trim())
        .then(r => { setResults(r); setOpen(r.length > 0) })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, source])

  function pick(hit: AuthorityHit) {
    onChange({ source: hit.source, external_id: hit.external_id, label: hit.label })
    setQ(''); setResults([]); setOpen(false)
  }

  if (value) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 8px', borderRadius: 4,
          background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
        }}>
          {value.label || value.external_id}
          <span style={{ fontSize: 10, opacity: 0.6, fontFamily: 'var(--mono)' }}>
            {value.source}:{value.external_id}
          </span>
        </span>
        {!disabled && (
          <button className="btn sm ico gh" onClick={() => onChange(null)} title="Entfernen">
            <X size={12} />
          </button>
        )}
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        className="fld"
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder={`${source.toUpperCase()} durchsuchen…`}
        disabled={disabled}
      />
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {open && results.length > 0 && dropPos && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          {results.map(hit => (
            <button
              key={hit.external_id}
              onMouseDown={e => { e.preventDefault(); pick(hit) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{hit.label}</div>
              {hit.description && (
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{hit.description}</div>
              )}
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                {hit.source} · {hit.external_id}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
