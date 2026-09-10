// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { ExportMappingRule, ExportTargetCapability, FieldDefinition, MappingDiagnostic } from '../../../types'
import { Plus, Trash } from '../../ui/Icons'
import { MappingHelp } from './MappingHelp'
import { SourcePicker, type SourceDraft } from './SourcePicker'

export interface RuleEditorProps {
  target: ExportTargetCapability
  rules: ExportMappingRule[]
  fields: FieldDefinition[]
  diagnostics: MappingDiagnostic[]
  busyRuleId: string | null
  onAdd: () => void
  onUpdate: (ruleId: string, patch: SourceDraft) => void
  onToggle: (ruleId: string, enabled: boolean) => void
  onDelete: (ruleId: string) => void
}

export function RuleEditor({ target, rules, fields, diagnostics, busyRuleId, onAdd, onUpdate, onToggle, onDelete }: RuleEditorProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'
  const canAddMore = target.cardinality === 'many' || rules.length === 0

  return (
    <div className="settings-card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{target.label[lang]}</h3>
        <MappingHelp target={target} />
        {target.required && <span style={{ fontSize: 11, color: '#dc2626', fontWeight: 600 }}>{t('requiredMarker')}</span>}
      </div>
      <p style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 0, marginBottom: 12 }}>{target.help[lang]}</p>

      {diagnostics.length > 0 && (
        <div role="alert" style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {diagnostics.map((d, i) => (
            <div key={i} style={{ fontSize: 12, color: d.level === 'error' ? '#dc2626' : d.level === 'warning' ? '#b45309' : 'var(--fg-2)' }}>
              {d.message}
            </div>
          ))}
        </div>
      )}

      {rules.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>{t('ruleEditorEmpty')}</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {rules.map(rule => (
          <div key={rule.id} style={{ display: 'flex', alignItems: 'flex-end', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border-s)' }}>
            <div style={{ flex: 1 }}>
              <SourcePicker
                allowedKinds={target.source_kinds}
                fields={fields}
                acceptedFieldTypes={target.accepted_field_types}
                disabled={busyRuleId === rule.id}
                value={{ source_kind: rule.source_kind, source_config: rule.source_config, settings: rule.settings }}
                onChange={draft => onUpdate(rule.id, draft)}
              />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--fg-2)', whiteSpace: 'nowrap' }}>
              <input
                type="checkbox"
                checked={rule.is_enabled}
                disabled={busyRuleId === rule.id}
                onChange={e => onToggle(rule.id, e.target.checked)}
              />
              {t('ruleEnabledLabel')}
            </label>
            <button
              type="button"
              className="btn sm ico gh"
              aria-label={t('ruleDeleteLabel')}
              title={t('ruleDeleteLabel')}
              disabled={busyRuleId === rule.id}
              onClick={() => onDelete(rule.id)}
            >
              <Trash size={13} />
            </button>
          </div>
        ))}
      </div>

      {canAddMore && (
        <button type="button" className="btn sm gh" style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6 }} onClick={onAdd}>
          <Plus size={13} /> {t('ruleAddLabel')}
        </button>
      )}
    </div>
  )
}
