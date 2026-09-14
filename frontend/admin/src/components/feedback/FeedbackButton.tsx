// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { req, getTokenUser } from '../../api/client'
import { Help, X } from '../ui/Icons'

const feedbackEnabled = Boolean(import.meta.env.VITE_ADMIN_FEEDBACK_ENABLED?.trim())

const panel = {
  position: 'fixed',
  left: 18,
  bottom: 18,
  zIndex: 40,
  width: 'min(360px, calc(100vw - 32px))',
  background: '#fff',
  border: '1px solid var(--border)',
  borderRadius: 8,
  boxShadow: '0 18px 44px rgba(15, 23, 42, .18)',
  padding: 14,
} as const

export function FeedbackButton() {
  const { t } = useTranslation('feedbackButton')
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const user = getTokenUser()

  if (!feedbackEnabled) return null

  async function send() {
    if (!message.trim()) return
    setSending(true)
    setError(null)
    try {
      await req('/v1/feedback', {
        method: 'POST',
        body: JSON.stringify({
          message: message.trim(),
          url: window.location.href,
          user: user?.email || 'unbekannt',
          viewport: `${window.innerWidth}x${window.innerHeight}`,
          time: new Date().toLocaleString('de-DE'),
        }),
      })
      setSent(true)
      setMessage('')
      setTimeout(() => { setOpen(false); setSent(false) }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('sendError'))
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {open && (
        <div style={panel}>
          {sent ? (
            <div style={{ textAlign: 'center', padding: '18px 0', fontSize: 13 }}>
              {t('sentConfirmation')}
            </div>
          ) : (<>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <strong style={{ fontSize: 13 }}>{t('title')}</strong>
            <button
              type="button"
              className="ib"
              style={{ marginLeft: 'auto' }}
              aria-label={t('close')}
              onClick={() => setOpen(false)}
            >
              <X size={15} />
            </button>
          </div>
          <textarea
            className="fld"
            rows={5}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('placeholder')}
            autoFocus
          />
          {error && (
            <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 6 }}>{error}</div>
          )}
          <div style={{ color: 'var(--fg-3)', fontSize: 11.5, marginTop: 8 }}>
            {t('hint')}
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => setOpen(false)}>{t('cancel')}</button>
            <button
              type="button"
              className="btn pri"
              disabled={!message.trim() || sending}
              onClick={send}
            >
              {sending ? t('sending') : t('send')}
            </button>
          </div>
          </>)}
        </div>
      )}
      <button
        type="button"
        className="sb-it"
        onClick={() => setOpen(true)}
      >
        <Help className="ic" size={15} />
        <span>{t('buttonLabel')}</span>
      </button>
    </>
  )
}
