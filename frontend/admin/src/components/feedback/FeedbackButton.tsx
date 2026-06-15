import { FormEvent, useMemo, useState } from 'react'
import { getTokenUser } from '../../api/client'
import { Help, X } from '../ui/Icons'

const feedbackEmail = import.meta.env.VITE_ADMIN_FEEDBACK_EMAIL?.trim()

const panel = {
  position: 'fixed',
  right: 18,
  bottom: 66,
  zIndex: 40,
  width: 'min(360px, calc(100vw - 32px))',
  background: '#fff',
  border: '1px solid var(--border)',
  borderRadius: 8,
  boxShadow: '0 18px 44px rgba(15, 23, 42, .18)',
  padding: 14,
} as const

export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const user = getTokenUser()

  const context = useMemo(() => ({
    url: window.location.href,
    user: user?.email || 'unbekannt',
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    userAgent: navigator.userAgent,
    time: new Date().toISOString(),
  }), [open])

  if (!feedbackEmail) return null

  function send(e: FormEvent) {
    e.preventDefault()
    const body = [
      message.trim(),
      '',
      '--- Kontext ---',
      `URL: ${context.url}`,
      `Benutzer: ${context.user}`,
      `Viewport: ${context.viewport}`,
      `User-Agent: ${context.userAgent}`,
      `Zeitpunkt: ${context.time}`,
    ].join('\n')

    window.location.href = `mailto:${feedbackEmail}?subject=${encodeURIComponent('Katalon Admin Feedback')}&body=${encodeURIComponent(body)}`
    setOpen(false)
    setMessage('')
  }

  return (
    <>
      {open && (
        <form style={panel} onSubmit={send}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <strong style={{ fontSize: 13 }}>Feedback senden</strong>
            <button
              type="button"
              className="ib"
              style={{ marginLeft: 'auto' }}
              aria-label="Feedback schließen"
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
            placeholder="Was ist dir aufgefallen?"
            required
            autoFocus
          />
          <div style={{ color: 'var(--fg-3)', fontSize: 11.5, marginTop: 8 }}>
            URL, Browser und Fenstergröße werden in die E-Mail übernommen.
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => setOpen(false)}>Abbrechen</button>
            <button type="submit" className="btn pri">E-Mail öffnen</button>
          </div>
        </form>
      )}
      <button
        type="button"
        className="btn pri"
        style={{
          position: 'fixed',
          right: 18,
          bottom: 18,
          zIndex: 40,
          height: 36,
          boxShadow: '0 10px 24px rgba(15, 23, 42, .18)',
        }}
        onClick={() => setOpen(true)}
      >
        <Help size={15} />
        Feedback
      </button>
    </>
  )
}
