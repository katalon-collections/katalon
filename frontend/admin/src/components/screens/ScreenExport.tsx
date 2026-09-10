// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { subtypes, exportApi } from '../../api/client'
import type { ExportFormatInfo } from '../../api/client'
import type { ExportProfileCapabilities, RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { Download } from '../ui/Icons'
import { FormatOverview } from './export/FormatOverview'
import { MappingWorkspace } from './export/MappingWorkspace'

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
    { id: 'collection', label: t('recordTypeCollection') },
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
  const [activeProfile, setActiveProfile] = useState<ExportProfileCapabilities | null>(null)

  useEffect(() => { setActiveProfile(null) }, [recordType])

  if (activeProfile) {
    return (
      <MappingWorkspace
        recordType={recordType}
        profile={activeProfile}
        onBack={() => setActiveProfile(null)}
      />
    )
  }

  return <FormatOverview recordType={recordType} onOpen={setActiveProfile} />
}
