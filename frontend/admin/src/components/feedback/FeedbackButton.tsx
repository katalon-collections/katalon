import { useState } from 'react'
import { req, getTokenUser } from '../../api/client'
import { Help, X } from '../ui/Icons'

const feedbackEnabled = Boolean(import.meta.env.VITE_ADMIN_FEEDBACK_EMAIL?.trim())

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
      setError(e instanceof Error ? e.message : 'Fehler beim Senden')
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
              ✓ Feedback gesendet. Danke!
            </div>
          ) : (<>
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
            autoFocus
          />
          {error && (
            <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 6 }}>{error}</div>
          )}
          <div style={{ color: 'var(--fg-3)', fontSize: 11.5, marginTop: 8 }}>
            URL, Browser und Fenstergröße werden mitgeschickt.
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => setOpen(false)}>Abbrechen</button>
            <button
              type="button"
              className="btn pri"
              disabled={!message.trim() || sending}
              onClick={send}
            >
              {sending ? 'Senden…' : 'Senden'}
            </button>
          </div>
          </>)}
        </div>
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
