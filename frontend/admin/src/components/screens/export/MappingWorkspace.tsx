// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportMappingSets, schema } from '../../../api/client'
import type { ExportMappingRule, ExportMappingSet, ExportProfileCapabilities, FieldDefinition, MappingDiagnostic, SourceKind } from '../../../types'
import { ChevL, Plus, Trash, X } from '../../ui/Icons'
import { ExportPreview } from './ExportPreview'
import { PublishMapping } from './PublishMapping'
import { RuleEditor } from './RuleEditor'
import { SourcePicker, type SourceDraft } from './SourcePicker'
import { TargetNavigator } from './TargetNavigator'
import { ValidationPanel } from './ValidationPanel'

export interface MappingWorkspaceProps {
  recordType: string
  profile: ExportProfileCapabilities
  onBack: () => void
}

function InstitutionConfigEditor({ config, busy, onSave }: {
  config: Record<string, unknown>
  busy: boolean
  onSave: (config: Record<string, string>) => void
}) {
  const { t } = useTranslation('screenExport')
  const [rows, setRows] = useState<{ key: string; value: string }[]>(
    () => Object.entries(config).map(([key, value]) => ({ key, value: String(value ?? '') })),
  )
  const [dirty, setDirty] = useState(false)

  function updateRow(i: number, patch: Partial<{ key: string; value: string }>) {
    setRows(r => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)))
    setDirty(true)
  }
  function addRow() {
    setRows(r => [...r, { key: '', value: '' }])
    setDirty(true)
  }
  function removeRow(i: number) {
    setRows(r => r.filter((_, idx) => idx !== i))
    setDirty(true)
  }
  function save() {
    const next: Record<string, string> = {}
    for (const row of rows) if (row.key.trim()) next[row.key.trim()] = row.value
    onSave(next)
    setDirty(false)
  }

  return (
    <div className="settings-card" style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, marginTop: 0, marginBottom: 4 }}>{t('institutionConfigHeadline')}</h3>
      <p style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 0 }}>{t('institutionConfigHelp')}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
        {rows.map((row, i) => (
          <div key={i} style={{ display: 'flex', gap: 8 }}>
            <input className="fld" style={{ width: 220 }} placeholder={t('institutionConfigKey')} aria-label={t('institutionConfigKey')} value={row.key} onChange={e => updateRow(i, { key: e.target.value })} />
            <input className="fld" style={{ flex: 1 }} placeholder={t('institutionConfigValue')} aria-label={t('institutionConfigValue')} value={row.value} onChange={e => updateRow(i, { value: e.target.value })} />
            <button type="button" className="btn sm ico gh" aria-label={t('ruleDeleteLabel')} title={t('ruleDeleteLabel')} onClick={() => removeRow(i)}>
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="btn sm gh" onClick={addRow} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Plus size={13} /> {t('institutionConfigAddRow')}
        </button>
        <button type="button" className="btn sm pri" disabled={!dirty || busy} onClick={save}>{t('institutionConfigSave')}</button>
      </div>
    </div>
  )
}

export function MappingWorkspace({ recordType, profile, onBack }: MappingWorkspaceProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'
  const compact = profile.format_key === 'oai_dc'

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [publishedSet, setPublishedSet] = useState<ExportMappingSet | null>(null)
  const [draftSet, setDraftSet] = useState<ExportMappingSet | null>(null)
  const [selectedTargetKey, setSelectedTargetKey] = useState<string | null>(null)
  const [diagnostics, setDiagnostics] = useState<MappingDiagnostic[]>([])
  const [validated, setValidated] = useState(false)
  const [busy, setBusy] = useState(false)
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    return Promise.all([
      schema.list(recordType),
      exportMappingSets.list({ record_type: recordType, format_key: profile.format_key }),
    ]).then(([fieldList, sets]) => {
      setFields(fieldList)
      setPublishedSet(sets.find(s => s.status === 'published') ?? null)
      setDraftSet(sets.find(s => s.status === 'draft') ?? null)
    })
  }, [recordType, profile.format_key])

  useEffect(() => {
    setSelectedTargetKey(compact ? null : (profile.targets[0]?.key ?? null))
    setDiagnostics([])
    setValidated(false)
    load().catch(() => setError(t('loadFailed')))
  }, [load])

  async function refreshDraft(id: string) {
    const full = await exportMappingSets.get(id)
    setDraftSet(full)
    setValidated(false)
    setDiagnostics([])
    return full
  }

  async function createDraft() {
    setBusy(true)
    setError(null)
    try {
      const created = await exportMappingSets.create({
        format_key: profile.format_key,
        profile_id: profile.profile_id,
        profile_version: profile.profile_version,
        record_type: recordType,
        name: `${profile.label[lang]} (${recordType})`,
        based_on_id: publishedSet?.id ?? null,
        institution_config: publishedSet?.institution_config ?? {},
      })
      await refreshDraft(created.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function discardDraft() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      await exportMappingSets.delete(draftSet.id)
      setDraftSet(null)
      setDiagnostics([])
      setValidated(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function runValidate() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const result = await exportMappingSets.validate(draftSet.id)
      setDiagnostics(result)
      setValidated(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function publish() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const result = await exportMappingSets.validate(draftSet.id)
      setDiagnostics(result)
      setValidated(true)
      if (result.some(d => d.level === 'error')) return
      await exportMappingSets.publish(draftSet.id, draftSet.version)
      setDraftSet(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function updateInstitutionConfig(config: Record<string, string>) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      await exportMappingSets.update(draftSet.id, { institution_config: config }, draftSet.version)
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function addRule(targetKey: string, sourceKind: SourceKind) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const rules = draftSet.rules ?? []
      await exportMappingSets.createRule(draftSet.id, {
        source_kind: sourceKind,
        target_key: targetKey,
        sort_order: rules.length,
      })
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function updateRule(ruleId: string, patch: SourceDraft) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.updateRule(draftSet.id, ruleId, patch)
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  async function toggleRule(ruleId: string, enabled: boolean) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.updateRule(draftSet.id, ruleId, { is_enabled: enabled })
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  async function deleteRule(ruleId: string) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.deleteRule(draftSet.id, ruleId)
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  const rulesByTarget: Record<string, ExportMappingRule[]> = {}
  for (const rule of draftSet?.rules ?? []) {
    (rulesByTarget[rule.target_key] ??= []).push(rule)
  }
  const diagnosticsByTarget: Record<string, MappingDiagnostic[]> = {}
  for (const d of diagnostics) {
    if (d.target_key) (diagnosticsByTarget[d.target_key] ??= []).push(d)
  }

  const selectedTarget = profile.targets.find(target => target.key === selectedTargetKey) ?? null

  return (
    <div>
      <button type="button" className="btn sm gh" onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16 }}>
        <ChevL size={13} /> {t('backToOverview')}
      </button>

      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 0 }}>{profile.label[lang]}</h2>

      {error && <div role="alert" style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      <PublishMapping
        publishedSet={publishedSet}
        draftSet={draftSet}
        busy={busy}
        canPublish={!validated || diagnostics.every(d => d.level !== 'error')}
        onCreateDraft={createDraft}
        onPublish={publish}
        onDiscardDraft={discardDraft}
      />

      {draftSet && (
        <>
          {!compact && (
            <InstitutionConfigEditor key={draftSet.id} config={draftSet.institution_config} busy={busy} onSave={updateInstitutionConfig} />
          )}

          {compact ? (
            <div className="settings-card" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginTop: 0 }}>{t('compactFieldsHeadline')}</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {profile.targets.map(target => {
                  const rules = rulesByTarget[target.key] ?? []
                  return (
                    <div key={target.key} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-s)' }}>
                      <div style={{ width: 200, fontSize: 13, flexShrink: 0 }}>{target.label[lang]}</div>
                      <div style={{ flex: 1 }}>
                        {rules.length === 0 ? (
                          <button type="button" className="btn sm gh" disabled={busy} onClick={() => addRule(target.key, 'field')}>
                            {t('ruleAddLabel')}
                          </button>
                        ) : (
                          <SourcePicker
                            allowedKinds={target.source_kinds}
                            fields={fields}
                            acceptedFieldTypes={target.accepted_field_types}
                            disabled={busyRuleId === rules[0].id}
                            value={{ source_kind: rules[0].source_kind, source_config: rules[0].source_config, settings: rules[0].settings }}
                            onChange={draft => updateRule(rules[0].id, draft)}
                          />
                        )}
                      </div>
                      {rules.length > 0 && (
                        <button type="button" className="btn sm ico gh" aria-label={t('ruleDeleteLabel')} title={t('ruleDeleteLabel')} disabled={busyRuleId === rules[0].id} onClick={() => deleteRule(rules[0].id)}>
                          <Trash size={13} />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <TargetNavigator
                targets={profile.targets}
                rulesByTarget={rulesByTarget}
                diagnosticsByTarget={diagnosticsByTarget}
                selected={selectedTargetKey}
                onSelect={setSelectedTargetKey}
              />
              <div style={{ flex: 1, minWidth: 280 }}>
                {selectedTarget && (
                  <RuleEditor
                    target={selectedTarget}
                    rules={rulesByTarget[selectedTarget.key] ?? []}
                    fields={fields}
                    diagnostics={diagnosticsByTarget[selectedTarget.key] ?? []}
                    busyRuleId={busyRuleId}
                    onAdd={() => addRule(selectedTarget.key, selectedTarget.source_kinds[0])}
                    onUpdate={updateRule}
                    onToggle={toggleRule}
                    onDelete={deleteRule}
                  />
                )}
              </div>
            </div>
          )}

          <ValidationPanel
            diagnostics={diagnostics}
            validated={validated}
            validating={busy}
            onValidate={runValidate}
            onJump={key => setSelectedTargetKey(key)}
          />

          <ExportPreview recordType={recordType} mappingSetId={draftSet.id} />
        </>
      )}
    </div>
  )
}
