// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { importer, type ImportMapping } from '../../api/client'
import { Trash } from '../ui/Icons'

interface LoadMappingModalProps {
  isOpen: boolean
  onClose: () => void
  recordType: string
  onSelect: (mapping: ImportMapping) => void
}

export function LoadMappingModal({
  isOpen,
  onClose,
  recordType,
  onSelect,
}: LoadMappingModalProps) {
  const { t } = useTranslation('screenImporter')
  const [mappings, setMappings] = useState<ImportMapping[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadMappings()
    }
  }, [isOpen, recordType])

  async function loadMappings() {
    setLoading(true)
    setError(null)
    try {
      const list = await importer.listMappings(recordType)
      setMappings(list)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!window.confirm(t('confirmDeleteTemplate', 'Möchten Sie die Vorlage „{{name}}“ wirklich löschen?', { name }))) {
      return
    }
    setDeletingId(id)
    try {
      await importer.deleteMapping(id)
      setMappings(prev => prev.filter(m => m.id !== id))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
    } finally {
      setDeletingId(null)
    }
  }

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,.35)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={e => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          background: 'var(--panel)',
          borderRadius: 10,
          padding: 24,
          width: 580,
          maxWidth: '92vw',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 30px rgba(0,0,0,.15)',
        }}
      >
        <h3 style={{ margin: '0 0 8px' }}>
          {t('loadTemplateModalTitle', 'Mapping-Vorlage laden')}
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--fg-3)' }}>
          {t('loadTemplateModalDesc', 'Wählen Sie eine gespeicherte Vorlage für Datensatz-Typ „{{type}}“ aus.', { type: recordType })}
        </p>

        {error && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: '#fef2f2',
              border: '1px solid #fca5a5',
              color: '#991b1b',
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ flex: 1, overflow: 'auto', minHeight: 140, marginBottom: 16 }}>
          {loading ? (
            <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>
              {t('loadingTemplates', 'Lade Vorlagen…')}
            </div>
          ) : mappings.length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>
              {t('noSavedTemplates', 'Keine gespeicherten Vorlagen für diesen Datensatz-Typ vorhanden.')}
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--fg-3)' }}>
                  <th style={{ padding: '8px 6px', fontWeight: 500 }}>{t('templateNameCol', 'Name')}</th>
                  <th style={{ padding: '8px 6px', fontWeight: 500 }}>{t('templateSubtypeCol', 'Subtyp')}</th>
                  <th style={{ padding: '8px 6px', fontWeight: 500 }}>{t('templateRulesCol', 'Zuordnungen')}</th>
                  <th style={{ padding: '8px 6px', fontWeight: 500 }}>{t('templateDateCol', 'Aktualisiert')}</th>
                  <th style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 500 }}>{t('actionsCol', 'Aktionen')}</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map(m => {
                  const ruleCount = m.mapping ? Object.keys(m.mapping).length : 0
                  const dateStr = m.updated_at ? new Date(m.updated_at).toLocaleDateString() : '—'
                  return (
                    <tr key={m.id} style={{ borderBottom: '1px solid var(--border-subtle, #eee)' }}>
                      <td style={{ padding: '10px 6px', fontWeight: 500 }}>{m.name}</td>
                      <td style={{ padding: '10px 6px', color: 'var(--fg-3)' }}>
                        {m.subtype ? (
                          <span style={{ background: 'var(--panel-2)', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
                            {m.subtype}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td style={{ padding: '10px 6px', color: 'var(--fg-3)' }}>{ruleCount}</td>
                      <td style={{ padding: '10px 6px', color: 'var(--fg-3)', fontSize: 12 }}>{dateStr}</td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                          <button
                            className="btn pri sm"
                            onClick={() => {
                              onSelect(m)
                              onClose()
                            }}
                          >
                            {t('applyTemplateButton', 'Laden')}
                          </button>
                          <button
                            className="btn gh sm"
                            style={{ color: '#b91c1c', padding: '4px 6px' }}
                            onClick={() => handleDelete(m.id, m.name)}
                            disabled={deletingId === m.id}
                            title={t('deleteTemplate', 'Vorlage löschen')}
                          >
                            <Trash size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn gh" onClick={onClose}>
            {t('close', 'Schließen')}
          </button>
        </div>
      </div>
    </div>
  )
}
