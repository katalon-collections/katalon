// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { FieldDefinition, SourceKind } from '../../../types'
import { getLabel } from '../../../types'

const fld: React.CSSProperties = { minWidth: 160 }
const lbl: React.CSSProperties = { display: 'block', fontSize: 11, fontWeight: 600, marginBottom: 3, color: 'var(--fg-3)' }

export interface SourceDraft {
  source_kind: SourceKind
  source_config: Record<string, unknown>
  settings: Record<string, unknown>
}

export interface SourcePickerProps {
  allowedKinds: SourceKind[]
  value: SourceDraft
  fields: FieldDefinition[]
  acceptedFieldTypes: string[]
  disabled?: boolean
  onChange: (next: SourceDraft) => void
}

const RECORD_PROPERTIES = ['idno', 'canonical_url', 'id', 'created_at', 'updated_at']
const MEDIA_PROPERTIES = ['url', 'mime_type', 'license_uri', 'rights_holder']

/** Local text input that commits on blur/Enter instead of on every keystroke. */
function CommitInput({ value, placeholder, ariaLabel, onCommit, disabled }: {
  value: string
  placeholder?: string
  ariaLabel: string
  disabled?: boolean
  onCommit: (v: string) => void
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <input
      className="fld"
      style={fld}
      value={draft}
      placeholder={placeholder}
      aria-label={ariaLabel}
      disabled={disabled}
      onChange={e => setDraft(e.target.value)}
      onBlur={() => { if (draft !== value) onCommit(draft) }}
      onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
    />
  )
}

function FieldSearch({ value, fields, disabled, placeholder, onChange }: {
  value: string
  fields: FieldDefinition[]
  disabled?: boolean
  placeholder: string
  onChange: (value: string) => void
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const selected = fields.find(f => f.name === value)
  const filtered = fields.filter(f => {
    const text = `${getLabel(f) || f.name} ${f.name}`.toLocaleLowerCase()
    return text.includes(query.toLocaleLowerCase())
  }).slice(0, 12)
  return (
    <div style={{ position: 'relative', minWidth: 220 }}>
      <input
        className="fld"
        style={{ width: '100%' }}
        type="search"
        value={open ? query : (selected ? `${getLabel(selected) || selected.name} · ${selected.name}` : '')}
        placeholder={placeholder}
        aria-label={placeholder}
        disabled={disabled}
        onFocus={() => { setQuery(''); setOpen(true) }}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }}
      />
      {open && !disabled && (
        <div role="listbox" style={{
          position: 'absolute', zIndex: 20, top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--panel, #fff)', border: '1px solid var(--border)', borderRadius: 8,
          boxShadow: '0 4px 16px rgba(0,0,0,.08)', padding: 4, maxHeight: 240, overflowY: 'auto',
        }}>
          {filtered.map(field => (
            <button
              key={field.id}
              type="button"
              role="option"
              aria-selected={field.name === value}
              className="btn sm gh"
              style={{ width: '100%', textAlign: 'left', justifyContent: 'flex-start' }}
              onMouseDown={e => e.preventDefault()}
              onClick={() => { onChange(field.name); setOpen(false) }}
            >
              {getLabel(field) || field.name} <span style={{ color: 'var(--fg-3)' }}>· {field.name}</span>
            </button>
          ))}
          {filtered.length === 0 && <div style={{ padding: 8, fontSize: 12, color: 'var(--fg-3)' }}>Keine Treffer</div>}
        </div>
      )}
    </div>
  )
}

export function SourcePicker({ allowedKinds, value, fields, acceptedFieldTypes, disabled, onChange }: SourcePickerProps) {
  const { t } = useTranslation('screenExport')

  function setKind(kind: SourceKind) {
    onChange({ source_kind: kind, source_config: {}, settings: {} })
  }

  const kindLabels: Record<SourceKind, string> = {
    field: t('sourceKindField'),
    relation: t('sourceKindRelation'),
    record: t('sourceKindRecord'),
    constant: t('sourceKindConstant'),
    media: t('sourceKindMedia'),
  }

  const eligibleFields = fields.filter(f => acceptedFieldTypes.length === 0 || acceptedFieldTypes.includes(f.field_type))


  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
      {allowedKinds.length > 1 && (
        <div>
          <label style={lbl}>{t('sourceKindLabel')}</label>
          <select
            className="fld"
            style={fld}
            value={value.source_kind}
            disabled={disabled}
            onChange={e => setKind(e.target.value as SourceKind)}
          >
            {allowedKinds.map(k => <option key={k} value={k}>{kindLabels[k]}</option>)}
          </select>
        </div>
      )}

      {value.source_kind === 'field' && (
        <>
          <div>
            <label style={lbl}>{t('sourceFieldLabel')}</label>
            <FieldSearch
              value={String(value.source_config.field_name ?? '')}
              fields={eligibleFields}
              disabled={disabled}
              placeholder={t('sourceFieldSearchPlaceholder')}
              onChange={field_name => onChange({ ...value, source_config: { ...value.source_config, field_name } })}
            />
          </div>
          <div>
            <label style={lbl}>{t('sourcePrefixLabel')}</label>
            <CommitInput
              value={String(value.settings.prefix ?? '')}
              ariaLabel={t('sourcePrefixLabel')}
              disabled={disabled}
              onCommit={v => onChange({ ...value, settings: { ...value.settings, prefix: v || undefined } })}
            />
          </div>
        </>
      )}

      {value.source_kind === 'relation' && (
        <>
          <div>
            <label style={lbl}>{t('sourceRelationTypeLabel')}</label>
            <CommitInput
              value={String(value.source_config.relation_type ?? '')}
              placeholder={t('sourceRelationTypePlaceholder')}
              ariaLabel={t('sourceRelationTypeLabel')}
              disabled={disabled}
              onCommit={v => onChange({ ...value, source_config: { ...value.source_config, relation_type: v || undefined } })}
            />
          </div>
          <div>
            <label style={lbl}>{t('sourceDirectionLabel')}</label>
            <select
              className="fld"
              style={fld}
              value={String(value.source_config.direction ?? 'outbound')}
              disabled={disabled}
              onChange={e => onChange({ ...value, source_config: { ...value.source_config, direction: e.target.value } })}
            >
              <option value="outbound">{t('sourceDirectionOutbound')}</option>
              <option value="inbound">{t('sourceDirectionInbound')}</option>
            </select>
          </div>
          <div>
            <label style={lbl}>{t('sourceRoleLabel')}</label>
            <CommitInput
              value={String(value.settings.role ?? '')}
              placeholder={t('sourceRolePlaceholder')}
              ariaLabel={t('sourceRoleLabel')}
              disabled={disabled}
              onCommit={v => onChange({ ...value, settings: { ...value.settings, role: v || undefined } })}
            />
          </div>
        </>
      )}

      {value.source_kind === 'record' && (
        <div>
          <label style={lbl}>{t('sourceRecordPropertyLabel')}</label>
          <select
            className="fld"
            style={fld}
            value={String(value.source_config.property ?? '')}
            disabled={disabled}
            onChange={e => onChange({ ...value, source_config: { ...value.source_config, property: e.target.value } })}
          >
            <option value="">{t('sourceFieldChoose')}</option>
            {RECORD_PROPERTIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      )}

      {value.source_kind === 'constant' && (
        <div>
          <label style={lbl}>{t('sourceConstantValueLabel')}</label>
          <CommitInput
            value={String(value.source_config.value ?? '')}
            ariaLabel={t('sourceConstantValueLabel')}
            disabled={disabled}
            onCommit={v => onChange({ ...value, source_config: { ...value.source_config, value: v || undefined } })}
          />
        </div>
      )}

      {value.source_kind === 'media' && (
        <div>
          <label style={lbl}>{t('sourceMediaPropertyLabel')}</label>
          <select
            className="fld"
            style={fld}
            value={String(value.source_config.property ?? '')}
            disabled={disabled}
            onChange={e => onChange({ ...value, source_config: { ...value.source_config, property: e.target.value } })}
          >
            <option value="">{t('sourceFieldChoose')}</option>
            {MEDIA_PROPERTIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      )}
    </div>
  )
}
