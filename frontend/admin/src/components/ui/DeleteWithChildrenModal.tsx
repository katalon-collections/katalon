// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { Alert, X } from './Icons'

interface DeleteWithChildrenModalProps {
  title: string
  description: string
  warningTitle: string
  warningText: string
  chooseActionLabel: string
  reparentLabel: string
  reparentDesc: string
  cascadeLabel: string
  cascadeDesc: string
  cancelLabel: string
  confirmLabel: string
  deletingLabel: string
  onConfirm: (action: 'cascade' | 'reparent') => void | Promise<void>
  onCancel: () => void
}

/**
 * Decision dialog for deleting a node in a self-referential parent_id hierarchy
 * (collections, storage locations, vocabulary terms) that still has direct
 * children. Forces an explicit choice between deleting the whole subtree and
 * promoting the direct children to the deleted node's own parent — the backend
 * blocks the delete (409) until one of the two is chosen, never silently
 * orphaning children via the FK's ondelete=SET NULL fallback.
 */
export function DeleteWithChildrenModal({
  title,
  description,
  warningTitle,
  warningText,
  chooseActionLabel,
  reparentLabel,
  reparentDesc,
  cascadeLabel,
  cascadeDesc,
  cancelLabel,
  confirmLabel,
  deletingLabel,
  onConfirm,
  onCancel,
}: DeleteWithChildrenModalProps) {
  const [action, setAction] = useState<'cascade' | 'reparent'>('reparent')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm(action)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="batch-modal-backdrop" onClick={busy ? undefined : onCancel} role="dialog" aria-modal="true">
      <div className="batch-modal batch-modal--compact" style={{ width: 480 }} onClick={e => e.stopPropagation()}>
        <div className="batch-modal-header">
          <h2>{title}</h2>
          <button type="button" className="btn sm ico gh" onClick={onCancel} disabled={busy} aria-label={cancelLabel}>
            <X size={16} />
          </button>
        </div>
        <div className="batch-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p style={{ margin: 0, fontSize: 14 }}>{description}</p>

          <div className="batch-warning" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <Alert size={18} style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ flex: 1 }}>
                <strong style={{ display: 'block', marginBottom: 4 }}>{warningTitle}</strong>
                <p style={{ margin: 0, fontSize: 13, color: '#92400e' }}>{warningText}</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 500 }}>{chooseActionLabel}</p>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  background: action === 'reparent' ? 'var(--panel-active, rgba(0,0,0,0.03))' : 'var(--bg-1, #fff)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="hierarchyDeleteAction"
                  value="reparent"
                  checked={action === 'reparent'}
                  onChange={() => setAction('reparent')}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{reparentLabel}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 2 }}>{reparentDesc}</div>
                </div>
              </label>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  background: action === 'cascade' ? 'var(--panel-active, rgba(0,0,0,0.03))' : 'var(--bg-1, #fff)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="hierarchyDeleteAction"
                  value="cascade"
                  checked={action === 'cascade'}
                  onChange={() => setAction('cascade')}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: '#b91c1c' }}>{cascadeLabel}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 2 }}>{cascadeDesc}</div>
                </div>
              </label>
            </div>
          </div>

          {error && (
            <div className="error-banner" style={{ fontSize: 13, padding: '8px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, color: '#991b1b' }}>
              {error}
            </div>
          )}
        </div>
        <div className="batch-modal-footer">
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button type="button" className={action === 'cascade' ? 'btn danger' : 'btn pri'} onClick={handleConfirm} disabled={busy}>
            {busy ? deletingLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
