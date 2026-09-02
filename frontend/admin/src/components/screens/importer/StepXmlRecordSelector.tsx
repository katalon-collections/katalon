// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { XmlElementLevel, XmlElementTag } from '../../../api/client'

interface Props {
  elementLevels: XmlElementLevel[]
  loading: boolean
  onSelect: (clarkTag: string) => void
}

export function StepXmlRecordSelector({ elementLevels, loading, onSelect }: Props) {
  const { t } = useTranslation('stepXmlRecordSelector')
  const [selected, setSelected] = useState<XmlElementTag | null>(null)

  if (loading) {
    return (
      <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>
        {t('loadingSelectors')}
      </div>
    )
  }

  // Flatten to all tags with depth info for display
  const allTags = elementLevels.flatMap(lvl =>
    lvl.tags.map(tag => ({ ...tag, depth: lvl.depth }))
  )

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>{t('heading')}</h3>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
          {t('description')}
        </p>
      </div>

      <div className="card">
        <div className="bd" style={{ padding: 0 }}>
          {allTags.map((tag, i) => {
            const isSelected = selected?.clark_tag === tag.clark_tag
            return (
              <button
                key={`${tag.clark_tag}-${i}`}
                onClick={() => setSelected(tag)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '10px 16px',
                  paddingLeft: 16 + tag.depth * 20,
                  background: isSelected ? 'var(--accent-soft, rgba(99,102,241,.08))' : 'transparent',
                  border: 'none',
                  borderBottom: i < allTags.length - 1 ? '1px solid var(--border-soft)' : 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 13,
                  color: isSelected ? 'var(--accent)' : 'var(--fg-1)',
                  fontWeight: isSelected ? 600 : 400,
                }}>
                  {'  '.repeat(tag.depth)}{'<'}{tag.label}{'>'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{t('depth', { depth: tag.depth })}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        {!selected && (
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('selectElementHint')}</span>
        )}
        <button
          className="btn pri"
          disabled={!selected}
          onClick={() => selected && onSelect(selected.clark_tag)}
        >
          {t('continueToMapping')}
        </button>
      </div>
    </>
  )
}
