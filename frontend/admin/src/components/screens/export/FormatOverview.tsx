// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportMappingSets, exportProfiles } from '../../../api/client'
import type { ExportMappingSet, ExportProfileCapabilities } from '../../../types'
import { StatusBadge } from '../../ui/StatusBadge'
import { ChevR } from '../../ui/Icons'

export interface FormatOverviewProps {
  recordType: string
  onOpen: (profile: ExportProfileCapabilities) => void
}

export function FormatOverview({ recordType, onOpen }: FormatOverviewProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'
  const [profiles, setProfiles] = useState<ExportProfileCapabilities[]>([])
  const [sets, setSets] = useState<ExportMappingSet[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([exportProfiles.list(), exportMappingSets.list({ record_type: recordType })])
      .then(([p, s]) => { setProfiles(p); setSets(s) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [recordType])

  if (loading) return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('mappingLoading')}</div>
  if (profiles.length === 0) return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('overviewNoProfiles')}</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {profiles.map(profile => {
        const published = sets.find(s => s.format_key === profile.format_key && s.status === 'published')
        const draft = sets.find(s => s.format_key === profile.format_key && s.status === 'draft')
        return (
          <button
            key={`${profile.format_key}:${profile.profile_id}`}
            type="button"
            className="settings-card"
            onClick={() => onOpen(profile)}
            style={{ display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left', width: '100%', cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{profile.label[lang]}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                {t('overviewTargetCount', { count: profile.targets.length })}
              </div>
            </div>
            {published && <StatusBadge status="public" />}
            {draft && <StatusBadge status="draft" />}
            {!published && !draft && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('overviewNotConfigured')}</span>}
            <ChevR size={14} style={{ color: 'var(--fg-3)' }} />
          </button>
        )
      })}
    </div>
  )
}
