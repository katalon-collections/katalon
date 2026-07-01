import { useState } from 'react'
import { auth, setToken } from '../../api/client'

interface Props {
  onLogin: () => void
}

export function ScreenLogin({ onLogin }: Props) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const token = await auth.login(email, password)
      setToken(token.access_token, token.refresh_token)
      onLogin()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{ width: 360 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10, margin: '0 auto 16px',
            background: 'linear-gradient(135deg,#3556a8,#1e3a8a)',
            color: '#fff', display: 'grid', placeItems: 'center',
            fontFamily: "'IBM Plex Mono',monospace", fontWeight: 700, fontSize: 20,
          }}>K</div>
          <div style={{ fontWeight: 700, fontSize: 20, letterSpacing: '-.01em' }}>Katalon</div>
          <div style={{ color: 'var(--fg-3)', fontSize: 13, marginTop: 4 }}>Digital Collection Management System</div>
        </div>

        <div className="card">
          <div className="hd">Anmelden</div>
          <div className="bd">
            <form onSubmit={handleSubmit}>
              <div className="field">
                <div className="lbl">E-Mail</div>
                <input
                  className="fld"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="admin@katalon.dev"
                  autoFocus
                  required
                />
              </div>
              <div className="field">
                <div className="lbl">Passwort</div>
                <input
                  className="fld"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </div>

              {error && (
                <div style={{
                  background: '#fef2f2', border: '1px solid #fecaca',
                  borderRadius: 6, padding: '8px 12px', marginBottom: 12,
                  fontSize: 13, color: '#b91c1c',
                }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="btn pri"
                style={{ width: '100%', justifyContent: 'center', padding: '9px 0', fontSize: 14 }}
                disabled={loading}
              >
                {loading ? 'Anmelden…' : 'Anmelden'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
