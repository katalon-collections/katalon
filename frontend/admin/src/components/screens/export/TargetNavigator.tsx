// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { ExportMappingRule, ExportTargetCapability, LidoEventConfig, LocalizedText, MappingDiagnostic } from '../../../types'
import { ConfirmModal } from '../../ui/ConfirmModal'
import { AlertCircle, Check, Plus, Trash, X } from '../../ui/Icons'

const EVENT_PRESETS: { id: string; type: string; label: LocalizedText }[] = [
  { id: 'acquisition', type: 'Erwerb', label: { de: 'Erwerb / Zugang', en: 'Acquisition / Ingestion' } },
  { id: 'discovery', type: 'Fund', label: { de: 'Fund / Ausgrabung', en: 'Discovery / Finding' } },
  { id: 'restoration', type: 'Restaurierung', label: { de: 'Restaurierung / Konservierung', en: 'Restoration / Conservation' } },
  { id: 'usage', type: 'Nutzung', label: { de: 'Nutzung / Verwendung', en: 'Use / Operation' } },
]

function hasConfiguredSource(rule: ExportMappingRule): boolean {
  const config = rule.source_config
  switch (rule.source_kind) {
    case 'field':
      return typeof config.field_name === 'string' && config.field_name.trim() !== ''
    case 'relation':
      return typeof config.relation_type === 'string' && config.relation_type.trim() !== ''
    case 'record':
    case 'media':
      return typeof config.property === 'string' && config.property.trim() !== ''
    case 'constant':
      return config.value !== undefined && String(config.value).trim() !== ''
  }
}

export interface TargetNavigatorProps {
  targets: ExportTargetCapability[]
  rulesByTarget: Record<string, ExportMappingRule[]>
  diagnosticsByTarget: Record<string, MappingDiagnostic[]>
  selected: string | null
  onSelect: (key: string) => void
  isLido?: boolean
  lidoEvents?: LidoEventConfig[]
  onAddLidoEvent?: (event: LidoEventConfig) => void
  onDeleteLidoEvent?: (eventId: string) => void
}

export function TargetNavigator({
  targets,
  rulesByTarget,
  diagnosticsByTarget,
  selected,
  onSelect,
  isLido = false,
  lidoEvents = [],
  onAddLidoEvent,
  onDeleteLidoEvent,
}: TargetNavigatorProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'

  const [eventToDelete, setEventToDelete] = useState<LidoEventConfig | null>(null)
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [customName, setCustomName] = useState('')

  function handleAddCustom() {
    const trimmed = customName.trim()
    if (!trimmed || !onAddLidoEvent) return
    const id = `custom_${Date.now().toString(36)}`
    onAddLidoEvent({
      id,
      type: trimmed,
      label: { de: trimmed, en: trimmed },
    })
    setCustomName('')
    setShowCustomInput(false)
  }

  const groupOrder = ['identification', 'classification', 'events', 'relations', 'rights', 'media']
  const groups: Record<string, ExportTargetCapability[]> = {}
  for (const target of targets) {
    (groups[target.group] ??= []).push(target)
  }

  const allGroupKeys = new Set(Object.keys(groups))
  if (isLido && lidoEvents.length > 0) {
    allGroupKeys.add('events')
  }

  const sortedGroupKeys = Array.from(allGroupKeys).sort((a, b) => {
    const ia = groupOrder.indexOf(a)
    const ib = groupOrder.indexOf(b)
    if (ia !== -1 && ib !== -1) return ia - ib
    if (ia !== -1) return -1
    if (ib !== -1) return 1
    return a.localeCompare(b)
  })

  return (
    <nav aria-label={t('targetNavigatorLabel')} style={{ width: 280, flexShrink: 0 }}>
      {sortedGroupKeys.map(group => {
        if (isLido && group === 'events') {
          return (
            <div key="events" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--fg-3)', marginBottom: 8 }}>
                {t('groupEvents')}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {lidoEvents.map(event => {
                  const eventTargets = targets.filter(trg => trg.key.startsWith(`lido:events/${event.id}/`))
                  return (
                    <div
                      key={event.id}
                      style={{
                        background: 'var(--bg-card, #f8fafc)',
                        border: '1px solid var(--border-s, #e2e8f0)',
                        borderRadius: 8,
                        padding: '8px 8px 6px 8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {event.label[lang] || event.type}
                          </span>
                          <span
                            style={{
                              fontSize: 10,
                              padding: '1px 5px',
                              borderRadius: 4,
                              background: 'var(--border-s, #e2e8f0)',
                              color: 'var(--fg-2)',
                              flexShrink: 0,
                            }}
                          >
                            {t('eventTypeLabel')}: {event.type}
                          </span>
                        </div>
                        {!event.is_preset && event.id !== 'production' && onDeleteLidoEvent && (
                          <button
                            type="button"
                            className="btn sm ico gh"
                            title={t('deleteLidoEvent')}
                            aria-label={t('deleteLidoEvent')}
                            style={{ padding: 2, height: 20, width: 20, flexShrink: 0 }}
                            onClick={() => setEventToDelete(event)}
                          >
                            <Trash size={12} />
                          </button>
                        )}
                      </div>

                      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                        {eventTargets.map(target => {
                          const rules = (rulesByTarget[target.key] ?? []).filter(
                            rule => rule.is_enabled && hasConfiguredSource(rule)
                          )
                          const diags = diagnosticsByTarget[target.key] ?? []
                          const hasError = diags.some(d => d.level === 'error')
                          const missingRequired = target.required && rules.length === 0
                          const subfieldLabel = target.label[lang].includes(': ')
                            ? target.label[lang].split(': ').slice(1).join(': ')
                            : target.label[lang]

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
                                  padding: '4px 6px',
                                  border: 'none',
                                  borderRadius: 4,
                                  background: selected === target.key ? 'var(--accent-soft, #eef2ff)' : 'transparent',
                                  color: selected === target.key ? 'var(--accent)' : 'var(--fg-1)',
                                  fontSize: 12,
                                  cursor: 'pointer',
                                }}
                              >
                                {hasError || missingRequired
                                  ? <AlertCircle size={12} style={{ color: '#dc2626', flexShrink: 0 }} />
                                  : rules.length > 0
                                    ? <Check size={12} style={{ color: '#16a34a', flexShrink: 0 }} />
                                    : <span style={{ width: 12, flexShrink: 0 }} />}
                                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {subfieldLabel}
                                </span>
                                {rules.length > 0 && <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>{rules.length}</span>}
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  )
                })}

                {onAddLidoEvent && (
                  <div style={{ position: 'relative', marginTop: 4 }}>
                    {!showAddMenu && !showCustomInput ? (
                      <button
                        type="button"
                        className="btn sm gh"
                        style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 12, padding: '6px 8px' }}
                        onClick={() => setShowAddMenu(true)}
                      >
                        <Plus size={13} /> {t('addLidoEvent')}
                      </button>
                    ) : showCustomInput ? (
                      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-s)', borderRadius: 6, padding: 8 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 4 }}>{t('customEventPrompt')}</div>
                        <input
                          className="fld sm"
                          style={{ width: '100%', marginBottom: 6 }}
                          placeholder={t('customEventPlaceholder')}
                          value={customName}
                          onChange={e => setCustomName(e.target.value)}
                          autoFocus
                          onKeyDown={e => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              handleAddCustom()
                            } else if (e.key === 'Escape') {
                              setShowCustomInput(false)
                              setCustomName('')
                            }
                          }}
                        />
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="btn sm gh"
                            onClick={() => {
                              setShowCustomInput(false)
                              setCustomName('')
                            }}
                          >
                            {t('cancelBtn')}
                          </button>
                          <button
                            type="button"
                            className="btn sm pri"
                            disabled={!customName.trim()}
                            onClick={handleAddCustom}
                          >
                            {t('customEventAdd')}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          background: 'var(--bg-card, #fff)',
                          border: '1px solid var(--border-s, #cbd5e1)',
                          borderRadius: 6,
                          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                          padding: 6,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 4,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '2px 4px', marginBottom: 2 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--fg-3)' }}>{t('addLidoEventTitle')}</span>
                          <button
                            type="button"
                            className="btn sm ico gh"
                            style={{ padding: 2, height: 18, width: 18 }}
                            onClick={() => setShowAddMenu(false)}
                          >
                            <X size={12} />
                          </button>
                        </div>
                        {EVENT_PRESETS.map(preset => (
                          <button
                            key={preset.id}
                            type="button"
                            className="btn sm gh"
                            style={{ textAlign: 'left', justifyContent: 'flex-start', fontSize: 12, padding: '4px 8px' }}
                            onClick={() => {
                              setShowAddMenu(false)
                              onAddLidoEvent({
                                id: `${preset.id}_${Date.now().toString(36)}`,
                                type: preset.type,
                                label: preset.label,
                              })
                            }}
                          >
                            {preset.label[lang]}
                          </button>
                        ))}
                        <button
                          type="button"
                          className="btn sm gh"
                          style={{ textAlign: 'left', justifyContent: 'flex-start', fontSize: 12, padding: '4px 8px', borderTop: '1px solid var(--border-s)' }}
                          onClick={() => {
                            setShowAddMenu(false)
                            setShowCustomInput(true)
                          }}
                        >
                          {t('presetCustom')}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        }

        const groupTargets = groups[group] ?? []
        return (
          <div key={group} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--fg-3)', marginBottom: 6 }}>
              {group}
            </div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {groupTargets.map(target => {
                const rules = (rulesByTarget[target.key] ?? []).filter(
                  rule => rule.is_enabled && hasConfiguredSource(rule)
                )
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
        )
      })}

      {eventToDelete && (
        <ConfirmModal
          title={t('deleteLidoEventConfirmTitle')}
          message={t('deleteLidoEventConfirmMessage', { name: eventToDelete.label[lang] || eventToDelete.type })}
          confirmLabel={t('deleteLidoEventConfirmBtn')}
          cancelLabel={t('cancelBtn')}
          danger
          onConfirm={() => {
            onDeleteLidoEvent?.(eventToDelete.id)
            setEventToDelete(null)
          }}
          onCancel={() => setEventToDelete(null)}
        />
      )}
    </nav>
  )
}
