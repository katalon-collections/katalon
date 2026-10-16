// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { FieldDefinition } from '../../../types'
import { HelpPopover } from '../../ui/HelpPopover'
import { Plus, X } from '../../ui/Icons'
import { FieldSearch, withGroupPaths } from './SourcePicker'

/** institution_config keys this section owns (kept out of the free key/value rows). */
export const LIDO_DELIVERY_KEYS = [
  'require_media_license',
  'allowed_license_uris',
  'resource_sets',
  'resource_iiif_manifest',
  'record_rights_holder',
  'rights_work_holder',
  'resource_rights_fallback',
  'resource_rights_default_uri',
  'actor_id_fields',
  'place_id_fields',
  'actor_types',
  'location_place_ids',
  'work_ids',
] as const

const AUTHORITY_SOURCES = ['gnd', 'wikidata', 'viaf', 'ulan', 'geonames', 'tgn', 'aat', 'iconclass']

type Row = Record<string, string>

interface Column {
  key: string
  label: string
  options?: { value: string; label: string }[]
  placeholder?: string
}

const lbl: React.CSSProperties = { display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }
const hint: React.CSSProperties = { fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }

function rowsOf(value: unknown): Row[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map(item => Object.fromEntries(Object.entries(item).map(([k, v]) => [k, String(v ?? '')])))
}

function RowList({ label, help, columns, rows, onChange }: {
  label: string
  help: string
  columns: Column[]
  rows: Row[]
  onChange: (rows: Row[]) => void
}) {
  const { t } = useTranslation('screenExport')
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
        <span style={{ ...lbl, marginBottom: 0 }}>{label}</span>
        <HelpPopover title={label} content={<div style={{ fontSize: 12 }}>{help}</div>} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rows.map((row, i) => (
          <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {columns.map(col => col.options ? (
              <select
                key={col.key}
                className="fld sm"
                style={{ flex: 1, minWidth: 0 }}
                aria-label={col.label}
                value={row[col.key] ?? ''}
                onChange={e => onChange(rows.map((r, idx) => idx === i ? { ...r, [col.key]: e.target.value } : r))}
              >
                <option value="">{col.label}</option>
                {col.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : (
              <input
                key={col.key}
                className="fld sm"
                style={{ flex: 1, minWidth: 0 }}
                aria-label={col.label}
                placeholder={col.placeholder ?? col.label}
                value={row[col.key] ?? ''}
                onChange={e => onChange(rows.map((r, idx) => idx === i ? { ...r, [col.key]: e.target.value } : r))}
              />
            ))}
            <button
              type="button"
              className="btn sm ico gh"
              aria-label={t('ruleDeleteLabel')}
              title={t('ruleDeleteLabel')}
              onClick={() => onChange(rows.filter((_, idx) => idx !== i))}
            >
              <X size={12} />
            </button>
          </div>
        ))}
        <div>
          <button
            type="button"
            className="btn sm gh"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}
            onClick={() => onChange([...rows, {}])}
          >
            <Plus size={12} /> {t('deliveryRowAdd')}
          </button>
        </div>
      </div>
    </div>
  )
}

function Check({ label, help, checked, disabled, onChange }: {
  label: string
  help: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: 'var(--fg-1)' }}>
        <input type="checkbox" checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} />
        {label}
      </label>
      <div style={hint}>{help}</div>
    </div>
  )
}

/** Drop incomplete rows; only rows with a value in ``required`` are saved. */
function cleanRows(rows: Row[], required: string): Row[] {
  return rows
    .map(row => Object.fromEntries(Object.entries(row).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()])))
    .filter(row => row[required])
}

/** Convert the section's form state back into institution_config values (empty = key removed). */
export function lidoDeliveryConfig(value: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const key of ['resource_rights_fallback', 'resource_rights_default_uri']) {
    const v = String(value[key] ?? '').trim()
    if (v && v !== 'none') out[key] = v
  }
  for (const key of ['require_media_license', 'resource_sets', 'resource_iiif_manifest', 'record_rights_holder', 'rights_work_holder']) {
    if (value[key] === true) out[key] = true
  }
  const allowed = licenseLines(value.allowed_license_uris)
  if (allowed.length) out.allowed_license_uris = allowed
  const lists: [string, string][] = [
    ['actor_id_fields', 'field'],
    ['place_id_fields', 'field'],
    ['location_place_ids', 'id'],
    ['work_ids', 'field_name'],
  ]
  for (const [key, required] of lists) {
    const rows = cleanRows(rowsOf(value[key]), required)
    if (rows.length) out[key] = rows
  }
  const actorTypes = cleanRows(rowsOf(value.actor_types), 'subtype')
    .filter(row => row.kind)
    .map(row => [row.subtype, row.kind] as const)
  if (actorTypes.length) out.actor_types = Object.fromEntries(actorTypes)
  return out
}

/** allowed_license_uris as list (stored as list; edited as one URI per line). */
function licenseLines(value: unknown): string[] {
  const lines = Array.isArray(value) ? value.map(String) : String(value ?? '').split('\n')
  return lines.map(line => line.trim()).filter(Boolean)
}

/** Form state from institution_config (actor_types: object -> rows). */
export function lidoDeliveryState(config: Record<string, unknown>): Record<string, unknown> {
  const state: Record<string, unknown> = {}
  for (const key of LIDO_DELIVERY_KEYS) if (key in config) state[key] = config[key]
  const types = config.actor_types
  state.actor_types = types && typeof types === 'object' && !Array.isArray(types)
    ? Object.entries(types as Record<string, unknown>).map(([subtype, kind]) => ({ subtype, kind: String(kind) }))
    : []
  return state
}

export function LidoDeliverySettings({ value, fields, onChange }: {
  value: Record<string, unknown>
  fields: FieldDefinition[]
  onChange: (next: Record<string, unknown>) => void
}) {
  const { t } = useTranslation('screenExport')
  const set = (key: string, next: unknown) => onChange({ ...value, [key]: next })
  const fallback = String(value.resource_rights_fallback ?? 'none')
  const fallbackMode = fallback.startsWith('object_field:') ? 'object_field' : fallback
  const sourceOptions = AUTHORITY_SOURCES.map(s => ({ value: s, label: t(`authoritySource_${s}`) }))

  return (
    <div style={{ borderTop: '1px solid var(--border-s)', paddingTop: 12, marginBottom: 16 }}>
      <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 4px' }}>{t('deliverySectionHeadline')}</h4>
      <p style={{ fontSize: 12, color: 'var(--fg-3)', margin: '0 0 12px' }}>{t('deliverySectionHelp')}</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16 }}>
        <Check
          label={t('deliveryRequireLicenseLabel')}
          help={t('deliveryRequireLicenseHelp')}
          checked={value.require_media_license === true}
          onChange={checked => set('require_media_license', checked)}
        />
        <Check
          label={t('deliveryResourceSetsLabel')}
          help={t('deliveryResourceSetsHelp')}
          checked={value.resource_sets === true}
          onChange={checked => set('resource_sets', checked)}
        />
        <Check
          label={t('deliveryManifestLabel')}
          help={t('deliveryManifestHelp')}
          checked={value.resource_iiif_manifest === true}
          onChange={checked => set('resource_iiif_manifest', checked)}
        />
        <Check
          label={t('deliveryRecordRightsHolderLabel')}
          help={t('deliveryRecordRightsHolderHelp')}
          checked={value.record_rights_holder === true}
          onChange={checked => set('record_rights_holder', checked)}
        />
        <Check
          label={t('deliveryRightsWorkHolderLabel')}
          help={t('deliveryRightsWorkHolderHelp')}
          checked={value.rights_work_holder === true}
          onChange={checked => set('rights_work_holder', checked)}
        />
        <div>
          <label style={lbl} htmlFor="delivery-fallback">{t('deliveryFallbackLabel')}</label>
          <select
            id="delivery-fallback"
            className="fld"
            style={{ width: '100%' }}
            value={fallbackMode}
            onChange={e => set('resource_rights_fallback', e.target.value === 'object_field' ? 'object_field:' : e.target.value)}
          >
            <option value="none">{t('deliveryFallbackNone')}</option>
            <option value="object_field">{t('deliveryFallbackObjectField')}</option>
            <option value="default">{t('deliveryFallbackDefault')}</option>
          </select>
          {fallbackMode === 'object_field' && (
            <div style={{ marginTop: 6 }}>
              <FieldSearch
                value={fallback.slice('object_field:'.length)}
                fields={withGroupPaths(fields).filter(f => f.field_type !== 'group')}
                placeholder={t('sourceFieldSearchPlaceholder')}
                onChange={name => set('resource_rights_fallback', `object_field:${name}`)}
              />
            </div>
          )}
          {fallbackMode === 'default' && (
            <input
              className="fld"
              style={{ width: '100%', marginTop: 6 }}
              aria-label={t('deliveryFallbackDefaultUriLabel')}
              placeholder={t('deliveryFallbackDefaultUriLabel')}
              value={String(value.resource_rights_default_uri ?? '')}
              onChange={e => set('resource_rights_default_uri', e.target.value)}
            />
          )}
          <div style={hint}>{t('deliveryFallbackHelp')}</div>
        </div>
        <div>
          <label style={lbl} htmlFor="delivery-allowed-licenses">{t('deliveryAllowedLicensesLabel')}</label>
          <textarea
            id="delivery-allowed-licenses"
            className="fld mono"
            rows={4}
            style={{ width: '100%', fontSize: 12, resize: 'vertical' }}
            placeholder="https://creativecommons.org/publicdomain/zero/1.0/"
            value={Array.isArray(value.allowed_license_uris) ? value.allowed_license_uris.join('\n') : String(value.allowed_license_uris ?? '')}
            onChange={e => set('allowed_license_uris', e.target.value)}
          />
          <div style={hint}>{t('deliveryAllowedLicensesHelp')}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <RowList
          label={t('deliveryActorIdFieldsLabel')}
          help={t('deliveryActorIdFieldsHelp')}
          columns={[
            { key: 'field', label: t('deliveryColFieldName'), placeholder: 'gnd' },
            { key: 'source', label: t('deliveryColSource'), options: sourceOptions },
          ]}
          rows={rowsOf(value.actor_id_fields)}
          onChange={rows => set('actor_id_fields', rows)}
        />
        <RowList
          label={t('deliveryActorTypesLabel')}
          help={t('deliveryActorTypesHelp')}
          columns={[
            { key: 'subtype', label: t('deliveryColEntitySubtype'), placeholder: 'person' },
            {
              key: 'kind',
              label: t('deliveryColActorKind'),
              options: [
                { value: 'person', label: t('deliveryActorKindPerson') },
                { value: 'corporation', label: t('deliveryActorKindCorporation') },
              ],
            },
          ]}
          rows={rowsOf(value.actor_types)}
          onChange={rows => set('actor_types', rows)}
        />
        <RowList
          label={t('deliveryPlaceIdFieldsLabel')}
          help={t('deliveryPlaceIdFieldsHelp')}
          columns={[
            { key: 'field', label: t('deliveryColFieldName'), placeholder: 'geonames' },
            { key: 'source', label: t('deliveryColSource'), options: sourceOptions },
          ]}
          rows={rowsOf(value.place_id_fields)}
          onChange={rows => set('place_id_fields', rows)}
        />
        <RowList
          label={t('deliveryLocationIdsLabel')}
          help={t('deliveryLocationIdsHelp')}
          columns={[
            { key: 'source', label: t('deliveryColSource'), options: sourceOptions },
            { key: 'id', label: t('deliveryColAuthorityId'), placeholder: '2856883' },
          ]}
          rows={rowsOf(value.location_place_ids)}
          onChange={rows => set('location_place_ids', rows)}
        />
        <RowList
          label={t('deliveryWorkIdsLabel')}
          help={t('deliveryWorkIdsHelp')}
          columns={[
            { key: 'field_name', label: t('deliveryColObjectField'), placeholder: 'signatur' },
            { key: 'type', label: t('deliveryColWorkIdType'), placeholder: t('deliveryWorkIdTypePlaceholder') },
          ]}
          rows={rowsOf(value.work_ids)}
          onChange={rows => set('work_ids', rows)}
        />
      </div>
    </div>
  )
}
