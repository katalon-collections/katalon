// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { ExportMappingRule, ExportTargetCapability, MappingDiagnostic } from '../../../types'
import { AlertCircle, Check } from '../../ui/Icons'

export interface TargetNavigatorProps {
  targets: ExportTargetCapability[]
  rulesByTarget: Record<string, ExportMappingRule[]>
  diagnosticsByTarget: Record<string, MappingDiagnostic[]>
  selected: string | null
  onSelect: (key: string) => void
}

export function TargetNavigator({ targets, rulesByTarget, diagnosticsByTarget, selected, onSelect }: TargetNavigatorProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'

  const groups: Record<string, ExportTargetCapability[]> = {}
  for (const target of targets) {
    (groups[target.group] ??= []).push(target)
  }

  return (
    <nav aria-label={t('targetNavigatorLabel')} style={{ width: 260, flexShrink: 0 }}>
      {Object.entries(groups).map(([group, groupTargets]) => (
        <div key={group} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--fg-3)', marginBottom: 6 }}>
            {group}
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {groupTargets.map(target => {
              const rules = (rulesByTarget[target.key] ?? []).filter(r => r.is_enabled)
              const diags = diagnosticsByTarget[target.key] ?? []
              const hasError = diags.some(d => d.level === 'error')
              const missingRequired = target.required && rules.length === 0
              return (
                <li key={target.key}>
                  <button
                    type="button"
                    onClick={() => onSelect(target.key)}
                    aria-current={selected === target.key ? 'true' : undefined}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      width: '100%',
                      textAlign: 'left',
                      padding: '6px 8px',
                      border: 'none',
                      borderRadius: 6,
                      background: selected === target.key ? 'var(--accent-soft, #eef2ff)' : 'transparent',
                      color: selected === target.key ? 'var(--accent)' : 'var(--fg-1)',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    {hasError || missingRequired
                      ? <AlertCircle size={13} style={{ color: '#dc2626', flexShrink: 0 }} />
                      : rules.length > 0
                        ? <Check size={13} style={{ color: '#16a34a', flexShrink: 0 }} />
                        : <span style={{ width: 13, flexShrink: 0 }} />}
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{target.label[lang]}</span>
                    {rules.length > 0 && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{rules.length}</span>}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}
