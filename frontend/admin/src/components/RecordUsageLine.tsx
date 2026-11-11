// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, Eye } from './ui/Icons'
import { usageApi, type RecordUsage } from '../api/client'

const COUNTED_TYPES = new Set(['object', 'entity', 'place', 'occurrence', 'collection'])

/** Compact anonymous portal view/download counts for the record toolbar. */
export function RecordUsageLine({ recordType, recordId }: { recordType: string; recordId: string }) {
  const { t, i18n } = useTranslation('screenForm')
  const [usage, setUsage] = useState<RecordUsage | null>(null)

  useEffect(() => {
    if (!COUNTED_TYPES.has(recordType)) return
    let active = true
    usageApi.get(recordType, recordId)
      .then(result => { if (active) setUsage(result) })
      .catch(() => { if (active) setUsage(null) })
    return () => { active = false }
  }, [recordType, recordId])

  if (!usage?.enabled) return null
  const n = (value: number) => value.toLocaleString(i18n.language)
  const views = t('usage.views', { count: usage.views, total: n(usage.views), recent: n(usage.views_30d) })
  const downloads = t('usage.downloads', { count: usage.downloads, total: n(usage.downloads), recent: n(usage.downloads_30d) })
  return (
    <div className="record-usage" style={{ display: 'inline-flex', gap: 12, fontSize: 12, color: 'var(--fg-3)' }}>
      <span title={views} aria-label={views} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <Eye size={13} aria-hidden="true" />{n(usage.views)}
      </span>
      {usage.downloads > 0 && (
        <span title={downloads} aria-label={downloads} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Download size={13} aria-hidden="true" />{n(usage.downloads)}
        </span>
      )}
    </div>
  )
}
