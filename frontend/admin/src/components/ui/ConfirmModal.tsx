// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { X } from './Icons'

interface ConfirmModalProps {
  /** Optional header title. Omit for a plain message dialog (parity with window.confirm). */
  title?: string
  /** Body text. `\n` renders as a line break. */
  message: string
  confirmLabel: string
  cancelLabel: string
  /** Styles the confirm button as destructive (red). */
  danger?: boolean
  onConfirm: () => void | Promise<void>
  onCancel: () => void
}

/**
 * Native-dialog replacement for window.confirm(). Reuses the batch-modal-* styles
 * shared with the other in-app modals (see AddToWorkingSetModal, DeleteFieldModal).
 */
export function ConfirmModal({ title, message, confirmLabel, cancelLabel, danger, onConfirm, onCancel }: ConfirmModalProps) {
  const [busy, setBusy] = useState(false)

  async function handleConfirm() {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="batch-modal-backdrop" onClick={busy ? undefined : onCancel} role="dialog" aria-modal="true">
      <div className="batch-modal batch-modal--compact" style={{ width: 440 }} onClick={e => e.stopPropagation()}>
        {title && (
          <div className="batch-modal-header">
            <h2>{title}</h2>
            <button className="btn sm ico gh" onClick={onCancel} disabled={busy} aria-label={cancelLabel}>
              <X size={16} />
            </button>
          </div>
        )}
        <div className="batch-modal-body">
          <p style={{ margin: 0, fontSize: 14, whiteSpace: 'pre-line' }}>{message}</p>
        </div>
        <div className="batch-modal-footer">
          <button className="btn" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button className={danger ? 'btn dn' : 'btn pri'} onClick={handleConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
