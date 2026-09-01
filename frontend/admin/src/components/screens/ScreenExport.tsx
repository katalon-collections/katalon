// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { schema, subtypes, exportApi, metadataMappings } from '../../api/client'
import type { ExportFormatInfo, MetadataFormatInfo } from '../../api/client'
import type { FieldDefinition, RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { Download } from '../ui/Icons'

const MAPPABLE_FIELD_TYPES = new Set(['text', 'richtext', 'date', 'number', 'boolean', 'vocab', 'vocab_free', 'relation', 'geo', 'pid', 'authority'])

const lbl: React.CSSProperties = { display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }

export function ScreenExport() {
  const { t } = useTranslation('screenExport')
  const [tab, setTab] = useState<'dumps' | 'mapping'>('dumps')
  const [recordType, setRecordType] = useState('object')
  const RECORD_TYPES = [
    { id: 'object', label: t('recordTypeObject') },
    { id: 'entity', label: t('recordTypeEntity') },
    { id: 'place', label: t('recordTypePlace') },
    { id: 'occurrence', label: t('recordTypeOccurrence') },
    { id: 'procedure', label: t('recordTypeProcedure') },
  ]

  return (
    <div className="settings-page">
      <div className="settings-head" style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t('headline')}</h1>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        <button type="button" className={`btn sm ${tab === 'dumps' ? 'pri' : 'gh'}`} onClick={() => setTab('dumps')}>{t('tabDumps')}</button>
        <button type="button" className={`btn sm ${tab === 'mapping' ? 'pri' : 'gh'}`} onClick={() => setTab('mapping')}>{t('tabMapping')}</button>
      </div>

      <div style={{ marginBottom: 20, maxWidth: 260 }}>
        <label style={lbl}>{t('typeLabel')}</label>
        <select className="fld" value={recordType} onChange={e => setRecordType(e.target.value)}>
          {RECORD_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
      </div>

      {tab === 'dumps' ? <DumpsTab recordType={recordType} /> : <MappingTab recordType={recordType} />}
    </div>
  )
}

function DumpsTab({ recordType }: { recordType: string }) {
  const { t } = useTranslation('screenExport')
  const [formats, setFormats] = useState<ExportFormatInfo[]>([])
  const [format, setFormat] = useState('')
  const [subtypeOptions, setSubtypeOptions] = useState<RecordSubtype[]>([])
  const [subtype, setSubtype] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSubtype('')
    setError(null)
    exportApi.listFormats(recordType).then(fs => { setFormats(fs); setFormat(fs[0]?.key ?? '') }).catch(() => {})
    subtypes.list(recordType).then(setSubtypeOptions).catch(() => {})
  }, [recordType])

  async function download() {
    setDownloading(true)
    setError(null)
    try {
      await exportApi.download(recordType, format, subtype || undefined)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('exportFailed'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="settings-card" style={{ maxWidth: 480 }}>
      <div style={{ marginBottom: 14 }}>
        <label style={lbl}>{t('formatLabel')}</label>
        <select className="fld" value={format} onChange={e => setFormat(e.target.value)}>
          {formats.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
      </div>

      {subtypeOptions.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <label style={lbl}>{t('subtypeLabel')}</label>
          <select className="fld" value={subtype} onChange={e => setSubtype(e.target.value)}>
            <option value="">{t('subtypeAll')}</option>
            {subtypeOptions.map(s => <option key={s.id} value={s.name}>{getLabel(s)}</option>)}
          </select>
        </div>
      )}

      {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      <button
        type="button"
        className="btn pri"
        onClick={download}
        disabled={downloading || !format}
        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
      >
        <Download size={14} /> {downloading ? t('exportDownloading') : t('exportButton')}
      </button>
    </div>
  )
}

function MappingTab({ recordType }: { recordType: string }) {
  const { t } = useTranslation('screenExport')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formats, setFormats] = useState<MetadataFormatInfo[]>([])
  const [mappings, setMappings] = useState<Record<string, Record<string, string>>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      schema.list(recordType),
      metadataMappings.listFormats(),
      metadataMappings.list(),
    ]).then(([fieldList, formatList, allMappings]) => {
      const mappableFields = fieldList.filter(f => MAPPABLE_FIELD_TYPES.has(f.field_type))
      setFields(mappableFields)
      setFormats(formatList)
      const byField: Record<string, Record<string, string>> = {}
      for (const m of allMappings) {
        if (!mappableFields.some(f => f.id === m.field_definition_id)) continue
        byField[m.field_definition_id] ??= {}
        byField[m.field_definition_id][m.format_key] = m.target_path
      }
      setMappings(byField)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [recordType])

  useEffect(() => { load() }, [load])

  async function setTarget(fieldId: string, formatKey: string, targetPath: string) {
    setSaving(`${fieldId}:${formatKey}`)
    try {
      await metadataMappings.setFieldFormat(fieldId, formatKey, { target_path: targetPath || null })
      setMappings(m => ({ ...m, [fieldId]: { ...m[fieldId], [formatKey]: targetPath } }))
    } catch {
      load()
    } finally {
      setSaving(null)
    }
  }

  if (loading) return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('mappingLoading')}</div>
  if (fields.length === 0) return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('mappingNoFields')}</div>

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>{t('mappingFieldHeader')}</th>
            {formats.map(f => (
              <th key={f.key} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>{f.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fields.map(field => (
            <tr key={field.id}>
              <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>{getLabel(field) || field.name}</td>
              {formats.map(fmt => (
                <td key={fmt.key} style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>
                  <select
                    className="fld"
                    style={{ minWidth: 200 }}
                    value={mappings[field.id]?.[fmt.key] ?? ''}
                    disabled={saving === `${field.id}:${fmt.key}`}
                    onChange={e => setTarget(field.id, fmt.key, e.target.value)}
                  >
                    <option value="">{t('mappingNoMapping')}</option>
                    {fmt.targets.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
