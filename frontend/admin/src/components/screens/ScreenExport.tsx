// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { ExportFormatInfo } from '../../api/client'
import { exportApi, exportProfiles, subtypes } from '../../api/client'
import type { ExportProfileCapabilities, RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { Download } from '../ui/Icons'
import { FormatOverview } from './export/FormatOverview'
import { MappingWorkspace } from './export/MappingWorkspace'

const lbl: React.CSSProperties = { display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }

const VALID_RECORD_TYPES = ['object', 'entity', 'place', 'occurrence', 'procedure', 'collection', 'storage_location'] as const

function parseExportPath(path?: string | null): { tab: 'dumps' | 'mapping'; recordType: string; formatKey: string | null } {
  if (!path) return { tab: 'dumps', recordType: 'object', formatKey: null }
  const parts = path.split('/')
  const tab: 'dumps' | 'mapping' = parts[0] === 'mapping' ? 'mapping' : 'dumps'
  const recordType = VALID_RECORD_TYPES.includes(parts[1] as typeof VALID_RECORD_TYPES[number]) ? parts[1] : 'object'
  const formatKey = tab === 'mapping' && parts[2] ? parts[2] : null
  return { tab, recordType, formatKey }
}

function buildExportPath(tab: 'dumps' | 'mapping', recordType: string, formatKey: string | null): string {
  if (tab === 'mapping') {
    return formatKey ? `mapping/${recordType}/${formatKey}` : `mapping/${recordType}`
  }
  return `dumps/${recordType}`
}

export interface ScreenExportProps {
  initialPath?: string | null
  onPathChange?: (path: string) => void
}

export function ScreenExport({ initialPath, onPathChange }: ScreenExportProps = {}) {
  const { t } = useTranslation('screenExport')
  const initial = parseExportPath(initialPath)
  const [tab, setTab] = useState<'dumps' | 'mapping'>(initial.tab)
  const [recordType, setRecordType] = useState(initial.recordType)
  const [formatKey, setFormatKey] = useState<string | null>(initial.formatKey)

  const lastEmittedPathRef = useRef<string | null>(initialPath ?? null)

  const RECORD_TYPES = [
    { id: 'object', label: t('recordTypeObject') },
    { id: 'entity', label: t('recordTypeEntity') },
    { id: 'place', label: t('recordTypePlace') },
    { id: 'occurrence', label: t('recordTypeOccurrence') },
    { id: 'procedure', label: t('recordTypeProcedure') },
    { id: 'collection', label: t('recordTypeCollection') },
    { id: 'storage_location', label: t('recordTypeStorageLocation') },
  ]

  function updateState(nextTab: 'dumps' | 'mapping', nextType: string, nextFormatKey: string | null) {
    setTab(nextTab)
    setRecordType(nextType)
    setFormatKey(nextFormatKey)
    const newPath = buildExportPath(nextTab, nextType, nextFormatKey)
    lastEmittedPathRef.current = newPath
    onPathChange?.(newPath)
  }

  useEffect(() => {
    if ((initialPath ?? null) === lastEmittedPathRef.current) return
    const parsed = parseExportPath(initialPath)
    lastEmittedPathRef.current = initialPath ?? null
    setTab(parsed.tab)
    setRecordType(parsed.recordType)
    setFormatKey(parsed.formatKey)
  }, [initialPath])

  return (
    <div className="settings-page">
      <div className="settings-head" style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t('headline')}</h1>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        <button
          type="button"
          className={`btn sm ${tab === 'dumps' ? 'pri' : 'gh'}`}
          onClick={() => updateState('dumps', recordType, null)}
        >
          {t('tabDumps')}
        </button>
        <button
          type="button"
          className={`btn sm ${tab === 'mapping' ? 'pri' : 'gh'}`}
          onClick={() => updateState('mapping', recordType, null)}
        >
          {t('tabMapping')}
        </button>
      </div>

      <div style={{ marginBottom: 20, maxWidth: 260 }}>
        <label style={lbl}>{t('typeLabel')}</label>
        <select
          className="fld"
          value={recordType}
          onChange={e => updateState(tab, e.target.value, tab === 'mapping' ? formatKey : null)}
        >
          {RECORD_TYPES.map(rt => <option key={rt.id} value={rt.id}>{rt.label}</option>)}
        </select>
      </div>

      {tab === 'dumps' ? (
        <DumpsTab recordType={recordType} />
      ) : (
        <MappingTab
          recordType={recordType}
          formatKey={formatKey}
          onSelectFormat={fKey => updateState('mapping', recordType, fKey)}
        />
      )}
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

function MappingTab({
  recordType,
  formatKey,
  onSelectFormat,
}: {
  recordType: string
  formatKey: string | null
  onSelectFormat: (formatKey: string | null) => void
}) {
  const { t } = useTranslation('screenExport')
  const [profiles, setProfiles] = useState<ExportProfileCapabilities[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    exportProfiles.list()
      .then(setProfiles)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const activeProfile = formatKey ? profiles.find(p => p.format_key === formatKey) ?? null : null

  if (loading && formatKey) {
    return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('mappingLoading')}</div>
  }

  if (activeProfile) {
    return (
      <MappingWorkspace
        recordType={recordType}
        profile={activeProfile}
        onBack={() => onSelectFormat(null)}
      />
    )
  }

  return (
    <FormatOverview
      recordType={recordType}
      onOpen={profile => onSelectFormat(profile.format_key)}
    />
  )
}
