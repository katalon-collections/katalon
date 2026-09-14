// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { workingSets } from '../../api/client'
import type { WorkingSet } from '../../types'
import { Plus, X } from '../ui/Icons'

interface Props {
  recordType: string
  recordIds: string[]
  onClose: () => void
  onSuccess: (setName: string, count: number) => void
}

export function AddToWorkingSetModal({ recordType, recordIds, onClose, onSuccess }: Props) {
  const { t } = useTranslation('screenWorkingSets')

  const [sets, setSets] = useState<WorkingSet[]>([])
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'existing' | 'new'>('existing')

  const [selectedSetId, setSelectedSetId] = useState<string>('')
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newShared, setNewShared] = useState(false)

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    workingSets
      .list({ record_type: recordType })
      .then((res) => {
        setSets(res)
        if (res.length > 0) {
          setSelectedSetId(res[0].id)
          setMode('existing')
        } else {
          setMode('new')
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Fehler beim Laden der Arbeitslisten')
        setMode('new')
      })
      .finally(() => setLoading(false))
  }, [recordType])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      let targetSetId = selectedSetId
      let targetSetName = ''

      if (mode === 'new') {
        if (!newName.trim()) {
          setError('Bitte einen Namen angeben.')
          setSaving(false)
          return
        }
        const created = await workingSets.create({
          name: newName.trim(),
          description: newDesc.trim() || null,
          record_type: recordType,
          is_shared: newShared,
        })
        targetSetId = created.id
        targetSetName = created.name
      } else {
        if (!targetSetId) {
          setError('Bitte eine Arbeitsliste auswählen.')
          setSaving(false)
          return
        }
        const found = sets.find((s) => s.id === targetSetId)
        targetSetName = found ? found.name : 'Arbeitsliste'
      }

      await workingSets.addItems(targetSetId, { record_ids: recordIds })
      onSuccess(targetSetName, recordIds.length)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Fehler beim Hinzufügen')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="batch-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="batch-modal" style={{ width: 480 }} onClick={(e) => e.stopPropagation()}>
        <div className="batch-modal-header">
          <h2>{t('addToSetTitle')}</h2>
          <button
            type="button"
            className="btn ico gh"
            onClick={onClose}
            aria-label={t('cancel')}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div className="batch-modal-body">
            <div className="batch-summary">
              {t('itemsCount', { count: recordIds.length })} ausgewählt.
            </div>

            {error && (
              <div
                style={{
                  marginBottom: 16,
                  padding: 10,
                  background: '#fee2e2',
                  color: '#991b1b',
                  borderRadius: 6,
                  fontSize: 13,
                }}
              >
                {error}
              </div>
            )}

            {loading ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)' }}>Lade…</div>
            ) : (
              <>
                {sets.length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      marginBottom: 16,
                      borderBottom: '1px solid var(--border)',
                      paddingBottom: 12,
                    }}
                  >
                    <button
                      type="button"
                      className={`btn sm ${mode === 'existing' ? 'pri' : 'gh'}`}
                      onClick={() => setMode('existing')}
                    >
                      {t('selectSet')}
                    </button>
                    <button
                      type="button"
                      className={`btn sm ${mode === 'new' ? 'pri' : 'gh'}`}
                      onClick={() => setMode('new')}
                    >
                      <Plus size={12} /> {t('orCreateNew')}
                    </button>
                  </div>
                )}

                {mode === 'existing' && sets.length > 0 ? (
                  <div style={{ marginBottom: 16 }}>
                    <label
                      style={{
                        display: 'block',
                        fontSize: 12,
                        fontWeight: 600,
                        marginBottom: 6,
                        color: 'var(--fg-2)',
                      }}
                    >
                      {t('selectSet')}
                    </label>
                    <select
                      className="fld"
                      style={{ width: '100%', boxSizing: 'border-box' }}
                      value={selectedSetId}
                      onChange={(e) => setSelectedSetId(e.target.value)}
                    >
                      {sets.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({t('itemsCount', { count: s.item_count })})
                          {s.is_shared ? ` [${t('sharedSets')}]` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div>
                    <div style={{ marginBottom: 14 }}>
                      <label
                        style={{
                          display: 'block',
                          fontSize: 12,
                          fontWeight: 600,
                          marginBottom: 4,
                          color: 'var(--fg-2)',
                        }}
                      >
                        {t('name')} *
                      </label>
                      <input
                        type="text"
                        required
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder={t('namePlaceholder')}
                        className="fld"
                        style={{ width: '100%', boxSizing: 'border-box' }}
                        autoFocus
                      />
                    </div>

                    <div style={{ marginBottom: 14 }}>
                      <label
                        style={{
                          display: 'block',
                          fontSize: 12,
                          fontWeight: 600,
                          marginBottom: 4,
                          color: 'var(--fg-2)',
                        }}
                      >
                        {t('description')}
                      </label>
                      <textarea
                        value={newDesc}
                        onChange={(e) => setNewDesc(e.target.value)}
                        placeholder={t('descriptionPlaceholder')}
                        className="fld"
                        style={{
                          width: '100%',
                          boxSizing: 'border-box',
                          minHeight: 60,
                          resize: 'vertical',
                        }}
                      />
                    </div>

                    <div style={{ marginBottom: 12 }}>
                      <label
                        style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                      >
                        <input
                          type="checkbox"
                          checked={newShared}
                          onChange={(e) => setNewShared(e.target.checked)}
                          className="ck"
                        />
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{t('isShared')}</span>
                      </label>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="batch-modal-footer">
            <button type="button" className="btn gh" onClick={onClose} disabled={saving}>
              {t('cancel')}
            </button>
            <button
              type="submit"
              className="btn pri"
              disabled={saving || (mode === 'new' && !newName.trim())}
            >
              {saving ? 'Hinzufügen…' : t('save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
