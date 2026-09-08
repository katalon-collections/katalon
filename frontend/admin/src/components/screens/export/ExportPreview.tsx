// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportMappingSets } from '../../../api/client'
import type { MappingDiagnostic } from '../../../types'
import { AlertCircle, Eye } from '../../ui/Icons'
import { SpecimenPicker, type Specimen } from './SpecimenPicker'

export function ExportPreview({ recordType, mappingSetId }: { recordType: string; mappingSetId: string }) {
  const { t } = useTranslation('screenExport')
  const [specimen, setSpecimen] = useState<Specimen | null>(null)
  const [xml, setXml] = useState<string | null>(null)
  const [diagnostics, setDiagnostics] = useState<MappingDiagnostic[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runPreview() {
    if (!specimen) return
    setLoading(true)
    setError(null)
    try {
      const result = await exportMappingSets.preview(mappingSetId, specimen.id)
      setXml(result.xml)
      setDiagnostics(result.diagnostics)
    } catch (e) {
      setXml(null)
      setError(e instanceof Error ? e.message : t('previewFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="settings-card" style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, marginTop: 0, marginBottom: 10 }}>{t('previewHeadline')}</h3>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <SpecimenPicker recordType={recordType} value={specimen} onChange={s => { setSpecimen(s); setXml(null); setDiagnostics([]) }} />
        <button
          type="button"
          className="btn sm pri"
          disabled={!specimen || loading}
          onClick={runPreview}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Eye size={13} /> {loading ? t('previewLoading') : t('previewButton')}
        </button>
      </div>

      {error && (
        <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#dc2626', fontSize: 13, marginBottom: 10 }}>
          <AlertCircle size={13} /> {error}
        </div>
      )}

      {diagnostics.length > 0 && (
        <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {diagnostics.map((d, i) => (
            <div key={i} style={{ fontSize: 12, color: d.level === 'error' ? '#dc2626' : d.level === 'warning' ? '#b45309' : 'var(--fg-2)' }}>
              {d.message}
            </div>
          ))}
        </div>
      )}

      {xml && (
        <pre style={{
          background: 'var(--panel-2, #f8fafc)', border: '1px solid var(--border)', borderRadius: 8,
          padding: 12, fontSize: 11.5, lineHeight: 1.5, maxHeight: 420, overflow: 'auto', fontFamily: 'var(--mono)',
        }}>
          {xml}
        </pre>
      )}

      {!xml && !error && (
        <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('previewEmpty')}</div>
      )}
    </div>
  )
}
