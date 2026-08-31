import { useState, useEffect, useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { authority as authorityApi } from '../api/client'
import type { AuthorityHit } from '../api/client'
import { X } from './ui/Icons'

export type AuthorityEntry = {
  source: string
  external_id: string
  label: string
  coordinates?: { lat: number; lng: number }
}

const AUTHORITY_URLS: Record<string, string> = {
  gnd: 'https://d-nb.info/gnd/',
  geonames: 'https://www.geonames.org/',
  viaf: 'https://viaf.org/viaf/',
  wikidata: 'https://www.wikidata.org/wiki/',
  tgn: 'https://vocab.getty.edu/tgn/',
  iconclass: 'https://iconclass.org/',
  aat: 'https://vocab.getty.edu/aat/',
}

function authorityUrl({ source, external_id }: AuthorityEntry): string | null {
  const baseUrl = AUTHORITY_URLS[source]
  return baseUrl ? `${baseUrl}${encodeURIComponent(external_id)}` : null
}

function geonamesCoordinates(value: AuthorityEntry): { lat: number; lng: number } | null {
  if (value.source !== 'geonames' || !value.coordinates) return null
  const { lat, lng } = value.coordinates
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
    ? { lat, lng }
    : null
}

export function GeoNamesMap({ value }: { value: AuthorityEntry }) {
  const coordinates = geonamesCoordinates(value)
  if (!coordinates) return null
  const { lat, lng } = coordinates
  const bbox = `${lng - 0.05},${lat - 0.03},${lng + 0.05},${lat + 0.03}`
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`
  return (
    <details style={{ width: '100%', marginTop: 8 }}>
      <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--accent-ink)' }}>OpenStreetMap</summary>
      <iframe
        src={src}
        title={`OpenStreetMap: ${value.label}`}
        width="100%"
        height="240"
        style={{ border: '1px solid var(--border)', borderRadius: 6, display: 'block', marginTop: 6 }}
        loading="lazy"
      />
    </details>
  )
}

export function AuthorityInput({ source, value, onChange, disabled }: {
  source: string
  value: AuthorityEntry | null
  onChange: (v: AuthorityEntry | null) => void
  disabled?: boolean
}) {
  const { t } = useTranslation('authorityInput')
  const [q, setQ] = useState('')
  const [results, setResults] = useState<AuthorityHit[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const listId = useId()
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
        .then(r => { setResults(r); setOpen(r.length > 0); setActiveIndex(r.length ? 0 : -1) })
        .catch(() => { setResults([]); setActiveIndex(-1) })
        .finally(() => setBusy(false))
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, source])

  function pick(hit: AuthorityHit) {
    const lat = Number(hit.extra.lat)
    const lng = Number(hit.extra.lng)
    const coordinates = hit.source === 'geonames' && Number.isFinite(lat) && Number.isFinite(lng)
      && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
      ? { lat, lng }
      : undefined
    onChange({ source: hit.source, external_id: hit.external_id, label: hit.label, coordinates })
    setQ(''); setResults([]); setOpen(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (!results.length || !['ArrowDown', 'ArrowUp', 'Enter'].includes(e.key)) return
    e.preventDefault()
    if (e.key === 'Enter') {
      if (open && activeIndex >= 0) pick(results[activeIndex])
      return
    }
    setOpen(true)
    setActiveIndex(i => e.key === 'ArrowDown'
      ? Math.min(i + 1, results.length - 1)
      : Math.max(i <= 0 ? results.length - 1 : i - 1, 0))
  }

  if (value) {
    const url = authorityUrl(value)
    const chipStyle = {
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 8px', borderRadius: 4,
      background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
    }
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        {url ? (
          <a href={url} target="_blank" rel="noreferrer" style={chipStyle}>
            {value.label || value.external_id}
            <span style={{ fontSize: 10, opacity: 0.6, fontFamily: 'var(--mono)' }}>
              {value.source}:{value.external_id}
            </span>
          </a>
        ) : (
          <span style={chipStyle}>
            {value.label || value.external_id}
            <span style={{ fontSize: 10, opacity: 0.6, fontFamily: 'var(--mono)' }}>
              {value.source}:{value.external_id}
            </span>
          </span>
        )}
        {!disabled && (
          <button className="btn sm ico gh" onClick={() => onChange(null)} title={t('remove')} aria-label={t('removeAriaLabel', { label: value.label || value.external_id })}>
            <X size={12} />
          </button>
        )}
        <GeoNamesMap value={value} />
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
        onKeyDown={handleKeyDown}
        placeholder={t('searchPlaceholder', { source: source.toUpperCase() })}
        disabled={disabled}
        role="combobox"
        aria-label={t('searchAriaLabel', { source: source.toUpperCase() })}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
        aria-busy={busy}
      />
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          {t('searching')}
        </div>
      )}
      {open && results.length > 0 && dropPos && (
        <div ref={dropRef} id={listId} role="listbox" style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          {results.map((hit, index) => (
            <button
              key={hit.external_id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={e => { e.preventDefault(); pick(hit) }}
              onMouseEnter={() => setActiveIndex(index)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)',
                background: index === activeIndex ? 'var(--accent-50)' : 'none', cursor: 'pointer',
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
