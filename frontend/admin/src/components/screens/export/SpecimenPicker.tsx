// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { search } from '../../../api/client'
import type { SearchResult } from '../../../types'
import { X } from '../../ui/Icons'

export interface Specimen {
  id: string
  idno: string | null
  title: string
}

export interface SpecimenPickerProps {
  recordType: string
  value: Specimen | null
  onChange: (specimen: Specimen | null) => void
}

export function SpecimenPicker({ recordType, value, onChange }: SpecimenPickerProps) {
  const { t } = useTranslation('screenExport')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return }
    const handle = setTimeout(() => {
      search.query(query, recordType, 8).then(r => { setResults(r.items); setOpen(true) }).catch(() => setResults([]))
    }, 250)
    return () => clearTimeout(handle)
  }, [query, recordType])

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
          {value.idno ? `${value.idno} · ` : ''}{value.title}
        </span>
        <button type="button" className="btn sm ico gh" aria-label={t('specimenClear')} title={t('specimenClear')} onClick={() => onChange(null)}>
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
        placeholder={t('specimenSearchPlaceholder')}
        aria-label={t('specimenSearchPlaceholder')}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {open && results.length > 0 && (
        <ul role="listbox" style={{
          position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0, marginTop: 4,
          background: '#fff', border: '1px solid var(--border)', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,.08)',
          listStyle: 'none', padding: 4, maxHeight: 240, overflowY: 'auto',
        }}>
          {results.map(r => (
            <li key={r.id}>
              <button
                type="button"
                className="btn sm gh"
                style={{ width: '100%', textAlign: 'left', justifyContent: 'flex-start' }}
                onClick={() => {
                  onChange({ id: r.id, idno: r.idno ?? null, title: r.title })
                  setQuery('')
                  setOpen(false)
                }}
              >
                {r.idno ? `${r.idno} · ` : ''}{r.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
