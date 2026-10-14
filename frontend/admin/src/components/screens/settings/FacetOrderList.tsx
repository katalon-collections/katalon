// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface FacetOrderItem {
  name: string
  label: string
  kind: 'field' | 'date' | 'tree' | 'relation' | 'related' | 'inherited'
}

/** Orders the active facets of one record type. Native drag & drop plus
 *  up/down buttons, so the order can also be changed with keyboard and
 *  screen readers. */
export function FacetOrderList({ items, onChange }: {
  items: FacetOrderItem[]
  onChange: (names: string[]) => void
}) {
  const { t } = useTranslation('facetSettings')
  const [dragging, setDragging] = useState<string | null>(null)
  const [over, setOver] = useState<string | null>(null)
  const names = items.map(item => item.name)

  function move(from: number, to: number) {
    if (to < 0 || to >= names.length || from === to) return
    const next = [...names]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    onChange(next)
  }

  if (items.length === 0) {
    return <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>{t('order.empty')}</div>
  }

  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {items.map((item, index) => (
        <li
          key={item.name}
          draggable
          onDragStart={e => { setDragging(item.name); e.dataTransfer.effectAllowed = 'move' }}
          onDragOver={e => { e.preventDefault(); setOver(item.name) }}
          onDragLeave={() => setOver(current => (current === item.name ? null : current))}
          onDrop={e => {
            e.preventDefault()
            if (dragging) move(names.indexOf(dragging), index)
            setDragging(null)
            setOver(null)
          }}
          onDragEnd={() => { setDragging(null); setOver(null) }}
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px', fontSize: 13,
            borderTop: over === item.name && dragging !== item.name ? '2px solid var(--accent)' : '2px solid transparent',
            opacity: dragging === item.name ? 0.5 : 1,
            background: 'var(--bg, transparent)',
          }}
        >
          <span aria-label={t('order.dragHandle', { name: item.label })} title={t('order.dragHandle', { name: item.label })} style={{ cursor: 'grab', color: 'var(--fg-4)', userSelect: 'none' }}>⠿</span>
          <span style={{ flex: 1, minWidth: 0 }}>{item.label}</span>
          <span style={{ fontSize: 10, color: 'var(--fg-3)', border: '1px solid var(--border-s)', borderRadius: 4, padding: '0 5px' }}>{t(`order.kind.${item.kind}`)}</span>
          <button type="button" className="btn sm ico gh" disabled={index === 0} onClick={() => move(index, index - 1)} aria-label={t('order.moveUp', { name: item.label })}>↑</button>
          <button type="button" className="btn sm ico gh" disabled={index === items.length - 1} onClick={() => move(index, index + 1)} aria-label={t('order.moveDown', { name: item.label })}>↓</button>
        </li>
      ))}
    </ol>
  )
}
