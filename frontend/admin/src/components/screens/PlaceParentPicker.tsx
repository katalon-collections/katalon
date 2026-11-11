// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { places } from '../../api/client'
import type { Place } from '../../types'
import { X } from '../ui/Icons'

export interface PlaceParentPickerProps {
  value: string | null
  /** The place being edited; it can not be its own parent. */
  excludeId?: string | null
  disabled?: boolean
  /** Wraps the selected parent's title, e.g. in a link that opens that place. */
  renderSelected?: (id: string, title: string) => ReactNode
  onChange: (id: string | null) => void
}

function placeTitle(place: Place): string {
  const raw = place.metadata_.label
  const label = typeof raw === 'string' ? raw : ''
  if (!label) return place.idno || place.id.slice(0, 8) + '…'
  return place.idno ? `${label} · ${place.idno}` : label
}

export function PlaceParentPicker({ value, excludeId, disabled, renderSelected, onChange }: PlaceParentPickerProps) {
  const { t } = useTranslation('screenForm')
  const [selected, setSelected] = useState<Place | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!value) { setSelected(null); return }
    let cancelled = false
    places.get(value).then(p => { if (!cancelled) setSelected(p) }).catch(() => { if (!cancelled) setSelected(null) })
    return () => { cancelled = true }
  }, [value])

  useEffect(() => {
    if (!open) return
    const handle = setTimeout(() => {
      places.list({ q: query.trim() || undefined, page_size: 50, sort_by: 'idno', sort_dir: 'asc' })
        .then(r => setResults(r.items.filter(p => p.id !== excludeId)))
        .catch(() => setResults([]))
    }, query ? 250 : 0)
    return () => clearTimeout(handle)
  }, [open, query, excludeId])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  if (value) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="chip">
          {(() => {
            const title = selected ? placeTitle(selected) : value.slice(0, 8) + '…'
            return renderSelected ? renderSelected(value, title) : title
          })()}
        </span>
        <button
          type="button" className="btn sm ico gh" disabled={disabled}
          aria-label={t('placeParentClear')} title={t('placeParentClear')}
          onClick={() => onChange(null)}
        >
          <X size={12} />
        </button>
      </div>
    )
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', maxWidth: 360 }}>
      <input
        className="fld"
        type="search"
        value={query}
        disabled={disabled}
        placeholder={t('placeParentPlaceholder')}
        aria-label={t('placeParentLabel')}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }}
      />
      {open && (
        <ul role="listbox" style={{
          position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0, marginTop: 4,
          background: 'var(--panel, #fff)', border: '1px solid var(--border)', borderRadius: 8,
          boxShadow: '0 4px 16px rgba(0,0,0,.08)', listStyle: 'none', padding: 4, maxHeight: 240, overflowY: 'auto',
        }}>
          {results.length === 0 && <li style={{ padding: '6px 10px', color: 'var(--fg-3)' }}>{t('placeParentEmpty')}</li>}
          {results.map(p => (
            <li key={p.id}>
              <button
                type="button" role="option" aria-selected={false} className="btn sm gh"
                style={{ width: '100%', textAlign: 'left', justifyContent: 'flex-start' }}
                onClick={() => { onChange(p.id); setQuery(''); setOpen(false) }}
              >
                {placeTitle(p)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
