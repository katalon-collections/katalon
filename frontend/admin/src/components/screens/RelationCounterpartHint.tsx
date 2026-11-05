// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { RelationCounterpart } from '../../api/client'
import { Alert } from '../ui/Icons'

/** Non-blocking hint: the same relation is already modelled in the opposite direction. */
export function RelationCounterpartHint({ counterparts, targetTypeLabel }: { counterparts: RelationCounterpart[]; targetTypeLabel: string }) {
  const { t, i18n } = useTranslation('screenSchema')
  if (counterparts.length === 0) return null
  return (
    <div className="batch-warning" role="status" style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'stretch' }}>
      {counterparts.map(c => {
        const label = c.label[i18n.language] || c.label.de || c.label.en || c.name
        const where = c.target_subtype
          ? t('fieldDetail.counterpartWhereSubtype', { type: targetTypeLabel, subtype: c.target_subtype })
          : t('fieldDetail.counterpartWhereAll', { type: targetTypeLabel })
        return (
          <div key={c.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <Alert size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <p style={{ margin: 0, fontSize: 13 }}>{t('fieldDetail.counterpartWarning', { label, where })}</p>
          </div>
        )
      })}
    </div>
  )
}
