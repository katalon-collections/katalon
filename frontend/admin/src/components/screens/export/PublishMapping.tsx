// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { ExportMappingSet } from '../../../types'
import { StatusBadge } from '../../ui/StatusBadge'
import { Check, Edit, Trash } from '../../ui/Icons'

export interface PublishMappingProps {
  publishedSet: ExportMappingSet | null
  draftSet: ExportMappingSet | null
  busy: boolean
  canPublish: boolean
  onCreateDraft: () => void
  onPublish: () => void
  onDiscardDraft: () => void
}

function badgeStatus(status: ExportMappingSet['status']): 'draft' | 'internal' | 'public' {
  if (status === 'published') return 'public'
  if (status === 'archived') return 'internal'
  return 'draft'
}

export function PublishMapping({ publishedSet, draftSet, busy, canPublish, onCreateDraft, onPublish, onDiscardDraft }: PublishMappingProps) {
  const { t } = useTranslation('screenExport')

  return (
    <div className="settings-card" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('publishedStateLabel')}</span>
        {publishedSet
          ? <StatusBadge status={badgeStatus(publishedSet.status)} />
          : <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('publishNoneYet')}</span>}
      </div>

      {draftSet && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('draftStateLabel')}</span>
          <StatusBadge status={badgeStatus(draftSet.status)} />
        </div>
      )}

      <div style={{ flex: 1 }} />

      {!draftSet && (
        <button type="button" className="btn sm gh" disabled={busy} onClick={onCreateDraft} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Edit size={13} /> {publishedSet ? t('editPublished') : t('createDraft')}
        </button>
      )}

      {draftSet && (
        <>
          <button type="button" className="btn sm gh" disabled={busy} onClick={onDiscardDraft} style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#dc2626' }}>
            <Trash size={13} /> {t('discardDraft')}
          </button>
          <button type="button" className="btn sm pri" disabled={busy || !canPublish} onClick={onPublish} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Check size={13} /> {t('publishDraft')}
          </button>
        </>
      )}
    </div>
  )
}
