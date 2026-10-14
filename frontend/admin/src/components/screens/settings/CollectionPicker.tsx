// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { collections } from '../../../api/client'
import type { KatalonCollection } from '../../../types'

function titleOf(collection: Pick<KatalonCollection, 'metadata_' | 'idno' | 'id'>): string {
  const label = collection.metadata_?.label
  if (typeof label === 'string' && label.trim()) return label
  if (label && typeof label === 'object') {
    const text = Object.values(label as Record<string, unknown>).find(v => typeof v === 'string' && v.trim())
    if (typeof text === 'string') return text
  }
  return collection.idno || collection.id
}

/** Ordered selection of collections for the homepage "selected" block:
 *  search by title/ID, add, reorder, remove — instead of typing UUIDs. */
export function CollectionPicker({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const { t } = useTranslation('screenSettings')
  const [titles, setTitles] = useState<Record<string, string>>({})
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<KatalonCollection[]>([])

  const missingKey = value.filter(id => !(id in titles)).join(',')
  useEffect(() => {
    const missing = missingKey ? missingKey.split(',') : []
    if (missing.length === 0) return
    Promise.all(missing.map(id => collections.get(id).then(c => [id, titleOf(c)] as const).catch(() => [id, id] as const)))
      .then(entries => setTitles(prev => ({ ...prev, ...Object.fromEntries(entries) })))
  }, [missingKey])

  useEffect(() => {
    const term = query.trim()
    if (term.length < 2) { setResults([]); return }
    const timer = setTimeout(() => {
      collections.list({ q: term, page_size: 10 })
        .then(page => setResults(page.items))
        .catch(() => setResults([]))
    }, 250)
    return () => clearTimeout(timer)
  }, [query])

  function move(index: number, delta: number) {
    const next = [...value]
    const [moved] = next.splice(index, 1)
    next.splice(index + delta, 0, moved)
    onChange(next)
  }

  return (
    <div>
      {value.length === 0 && <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '4px 0' }}>{t('startseite.collectionNoneSelected')}</div>}
      <ol style={{ listStyle: 'none', margin: '0 0 10px', padding: 0 }}>
        {value.map((id, index) => (
          <li key={id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0', fontSize: 13 }}>
            <span style={{ flex: 1, minWidth: 0 }}>{titles[id] ?? id}</span>
            <button type="button" className="btn sm ico gh" disabled={index === 0} onClick={() => move(index, -1)} aria-label={`${t('startseite.collectionMoveUp')}: ${titles[id] ?? id}`}>↑</button>
            <button type="button" className="btn sm ico gh" disabled={index === value.length - 1} onClick={() => move(index, 1)} aria-label={`${t('startseite.collectionMoveDown')}: ${titles[id] ?? id}`}>↓</button>
            <button type="button" className="btn sm gh" onClick={() => onChange(value.filter(v => v !== id))}>{t('startseite.collectionRemove')}</button>
          </li>
        ))}
      </ol>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
        {t('startseite.collectionSearch')}
        <input className="fld" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t('startseite.collectionSearchPlaceholder')} />
      </label>
      {results.length > 0 && (
        <ul style={{ listStyle: 'none', margin: '6px 0 0', padding: 0, border: '1px solid var(--border-s)', borderRadius: 6 }}>
          {results.filter(c => !value.includes(c.id)).map(c => (
            <li key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', fontSize: 13, borderBottom: '1px solid var(--border-s)' }}>
              <span style={{ flex: 1, minWidth: 0 }}>{titleOf(c)}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{c.idno}</span>
              <button
                type="button"
                className="btn sm"
                onClick={() => {
                  setTitles(prev => ({ ...prev, [c.id]: titleOf(c) }))
                  onChange([...value, c.id])
                }}
              >
                {t('startseite.collectionAdd')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
