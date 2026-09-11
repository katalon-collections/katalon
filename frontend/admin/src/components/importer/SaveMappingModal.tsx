// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { importer, type ImportMapping, type MappingEntry } from '../../api/client'

interface SaveMappingModalProps {
  isOpen: boolean
  onClose: () => void
  recordType: string
  subtype: string | null
  mediaSelector: string | null
  mapping: Record<string, MappingEntry>
  savedMappingId: string | null
  savedMappingName: string | null
  onSaved: (saved: ImportMapping) => void
}

export function SaveMappingModal({
  isOpen,
  onClose,
  recordType,
  subtype,
  mediaSelector,
  mapping,
  savedMappingId,
  savedMappingName,
  onSaved,
}: SaveMappingModalProps) {
  const { t } = useTranslation('screenImporter')
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'update' | 'new'>('new')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      setError(null)
      if (savedMappingId && savedMappingName) {
        setName(savedMappingName)
        setMode('update')
      } else {
        setName('')
        setMode('new')
      }
    }
  }, [isOpen, savedMappingId, savedMappingName])

  if (!isOpen) return null

  const mappedCount = Object.keys(mapping).length

  async function handleSave() {
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError(t('templateNameRequired', 'Bitte einen Namen eingeben.'))
      return
    }

    setSaving(true)
    setError(null)
    try {
      let result: ImportMapping
      if (mode === 'update' && savedMappingId) {
        result = await importer.updateMapping(savedMappingId, {
          name: trimmedName,
          subtype: subtype ?? null,
          media_selector: mediaSelector ?? null,
          mapping,
        })
      } else {
        result = await importer.createMapping({
          name: trimmedName,
          record_type: recordType,
          subtype: subtype ?? null,
          media_selector: mediaSelector ?? null,
          mapping,
        })
      }
      onSaved(result)
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

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
          width: 480,
          maxWidth: '90vw',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 30px rgba(0,0,0,.15)',
        }}
      >
        <h3 style={{ margin: '0 0 8px' }}>
          {t('saveTemplateModalTitle', 'Mapping-Vorlage speichern')}
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--fg-3)' }}>
          {t('saveTemplateModalDesc', 'Speichern Sie das aktuelle Mapping in der Datenbank, um es später in der UI oder über die API wiederzuverwenden.')}
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

        {savedMappingId && savedMappingName && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input
                type="radio"
                name="saveMode"
                checked={mode === 'update'}
                onChange={() => setMode('update')}
              />
              <span>{t('updateExistingTemplate', 'Bestehende Vorlage „{{name}}“ aktualisieren', { name: savedMappingName })}</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input
                type="radio"
                name="saveMode"
                checked={mode === 'new'}
                onChange={() => setMode('new')}
              />
              <span>{t('saveAsNewTemplate', 'Als neue Vorlage speichern')}</span>
            </label>
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
            {t('templateNameLabel', 'Name der Vorlage')} *
          </label>
          <input
            className="fld"
            style={{ width: '100%', height: 32, fontSize: 13 }}
            placeholder={t('templateNamePlaceholder', 'z. B. LIDO 1.0 Standard')}
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleSave()
            }}
            autoFocus
          />
        </div>

        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-3)',
            background: 'var(--panel-2, #f8fafc)',
            padding: '10px 12px',
            borderRadius: 6,
            marginBottom: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div><strong>{t('typeLabel', 'Typ:')}</strong> {recordType}</div>
          {subtype && <div><strong>{t('subtypeLabel', 'Subtyp:')}</strong> {subtype}</div>}
          <div><strong>{t('mappingsCount', 'Zuordnungen:')}</strong> {mappedCount}</div>
          {mediaSelector && <div><strong>{t('mediaSelectorLabel', 'Medienfeld:')}</strong> {mediaSelector}</div>}
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn gh" onClick={onClose} disabled={saving}>
            {t('cancel', 'Abbrechen')}
          </button>
          <button className="btn pri" onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? t('saving', 'Speichere…') : t('save', 'Speichern')}
          </button>
        </div>
      </div>
    </div>
  )
}
