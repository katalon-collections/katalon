import { useState } from 'react'

const feedbackEnabled = Boolean(import.meta.env.VITE_PORTAL_FEEDBACK_EMAIL?.trim())

const BASE = import.meta.env.VITE_API_URL ?? ''

const panelStyle: React.CSSProperties = {
  position: 'fixed',
  right: 18,
  bottom: 66,
  zIndex: 9999,
  width: 'min(360px, calc(100vw - 32px))',
  background: '#fff',
  border: '1px solid #e4e6eb',
  borderRadius: 8,
  boxShadow: '0 18px 44px rgba(15,23,42,.18)',
  padding: 14,
}

const btnBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '0 14px',
  height: 36,
  border: 'none',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 500,
  fontFamily: 'inherit',
}

export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!feedbackEnabled) return null

  async function send() {
    if (!message.trim()) return
    setSending(true)
    setError(null)
    try {
      const res = await fetch(`${BASE}/v1/feedback/public`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message.trim(),
          url: window.location.href,
          user: 'anonym (Portal)',
          viewport: `${window.innerWidth}x${window.innerHeight}`,
          time: new Date().toLocaleString('de-DE'),
        }),
      })
      if (!res.ok) throw new Error(res.statusText)
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
        <div style={panelStyle}>
          {sent ? (
            <div style={{ textAlign: 'center', padding: '18px 0', fontSize: 13 }}>
              ✓ Feedback gesendet. Danke!
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <strong style={{ fontSize: 13 }}>Feedback senden</strong>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Schließen"
                  style={{ ...btnBase, marginLeft: 'auto', padding: '0 8px', background: 'transparent', color: '#64748b' }}
                >
                  <svg viewBox="0 0 24 24" width={15} height={15} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <textarea
                rows={5}
                value={message}
                onChange={e => setMessage(e.target.value)}
                placeholder="Was ist dir aufgefallen?"
                autoFocus
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid #e4e6eb', borderRadius: 6, fontSize: 13, fontFamily: 'inherit', resize: 'vertical' }}
              />
              {error && (
                <div style={{ color: '#dc2626', fontSize: 12, marginTop: 6 }}>{error}</div>
              )}
              <div style={{ color: '#94a3b8', fontSize: 11.5, marginTop: 8 }}>
                URL, Browser und Fenstergröße werden mitgeschickt.
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  style={{ ...btnBase, background: '#f1f5f9', color: '#374151' }}
                >
                  Abbrechen
                </button>
                <button
                  type="button"
                  disabled={!message.trim() || sending}
                  onClick={send}
                  style={{ ...btnBase, background: 'var(--accent, #1e3a8a)', color: '#fff', opacity: (!message.trim() || sending) ? 0.6 : 1 }}
                >
                  {sending ? 'Senden…' : 'Senden'}
                </button>
              </div>
            </>
          )}
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          ...btnBase,
          position: 'fixed',
          right: 18,
          bottom: 18,
          zIndex: 9999,
          background: 'var(--accent, #1e3a8a)',
          color: '#fff',
          boxShadow: '0 10px 24px rgba(15,23,42,.18)',
        }}
      >
        <svg viewBox="0 0 24 24" width={15} height={15} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <path d="M12 17h.01" />
        </svg>
        Feedback
      </button>
    </>
  )
}
