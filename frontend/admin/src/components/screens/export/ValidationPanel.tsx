// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { MappingDiagnostic } from '../../../types'
import { AlertCircle, Check, Info, Refresh } from '../../ui/Icons'

const LEVEL_COLOR: Record<MappingDiagnostic['level'], string> = {
  error: '#dc2626',
  warning: '#b45309',
  info: 'var(--fg-2)',
}

export interface ValidationPanelProps {
  diagnostics: MappingDiagnostic[]
  validated: boolean
  validating: boolean
  onValidate: () => void
  onJump: (targetKey: string) => void
}

export function ValidationPanel({ diagnostics, validated, validating, onValidate, onJump }: ValidationPanelProps) {
  const { t } = useTranslation('screenExport')
  const errorCount = diagnostics.filter(d => d.level === 'error').length

  return (
    <div className="settings-card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, flex: 1 }}>{t('validationHeadline')}</h3>
        <button type="button" className="btn sm gh" disabled={validating} onClick={onValidate} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Refresh size={13} /> {validating ? t('validating') : t('validateButton')}
        </button>
      </div>

      {!validated && <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('validationNotRun')}</div>}

      {validated && diagnostics.length === 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#16a34a' }}>
          <Check size={14} /> {t('validationClean')}
        </div>
      )}

      {validated && diagnostics.length > 0 && (
        <ul role="list" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {diagnostics.map((d, i) => (
            <li key={i}>
              <button
                type="button"
                className="btn sm gh"
                disabled={!d.target_key}
                onClick={() => d.target_key && onJump(d.target_key)}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 6, textAlign: 'left', width: '100%', color: LEVEL_COLOR[d.level] }}
              >
                {d.level === 'info' ? <Info size={13} style={{ flexShrink: 0, marginTop: 2 }} /> : <AlertCircle size={13} style={{ flexShrink: 0, marginTop: 2 }} />}
                <span>{d.message}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {validated && errorCount > 0 && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#dc2626' }}>{t('validationErrorsBlockPublish', { count: errorCount })}</div>
      )}
    </div>
  )
}
