import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { auth, setToken } from '../../api/client'

interface Props {
  onLogin: () => void
}

export function ScreenLogin({ onLogin }: Props) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'login' | 'request' | 'reset'>(() =>
    window.location.hash.startsWith('#reset-password') ? 'reset' : 'login')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [resetToken] = useState(() => new URLSearchParams(window.location.hash.split('?')[1]).get('token') ?? '')
  const [error, setError]       = useState<string | null>(null)
  const [notice, setNotice]     = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  function goTo(nextMode: 'login' | 'request' | 'reset') {
    if (nextMode === 'login') window.location.hash = ''
    setError(null)
    setNotice(null)
    setMode(nextMode)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setLoading(true)
    try {
      if (mode === 'login') {
        const token = await auth.login(email, password)
        setToken(token.access_token)
        onLogin()
      } else if (mode === 'request') {
        const result = await auth.requestPasswordReset(email)
        setNotice(result.detail)
      } else {
        if (password !== passwordConfirm) throw new Error(t('login.passwordMismatch'))
        await auth.confirmPasswordReset(resetToken, password)
        goTo('login')
        setNotice(t('login.passwordResetComplete'))
      }
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
          <div style={{ color: 'var(--fg-3)', fontSize: 13, marginTop: 4 }}>{t('login.tagline')}</div>
        </div>

        <div className="card">
          <div className="hd">{t(`login.${mode === 'login' ? 'cardTitle' : mode === 'request' ? 'resetTitle' : 'newPasswordTitle'}`)}</div>
          <div className="bd">
            <form onSubmit={handleSubmit}>
              {mode !== 'reset' && <div className="field">
                <label className="lbl" htmlFor="login-email">{t('login.email')}</label>
                <input
                  id="login-email"
                  className="fld"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="admin@katalon.dev"
                  autoFocus
                  required
                />
              </div>}
              {mode === 'request' && <p style={{ color: 'var(--fg-3)', fontSize: 13, marginTop: 0 }}>{t('login.resetHint')}</p>}
              {mode !== 'request' && <div className="field">
                <label className="lbl" htmlFor="login-password">{mode === 'reset' ? t('login.newPassword') : t('login.password')}</label>
                <input
                  id="login-password"
                  className="fld"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoFocus={mode === 'reset'}
                  required
                />
              </div>}
              {mode === 'reset' && <div className="field">
                <label className="lbl" htmlFor="login-password-confirm">{t('login.confirmPassword')}</label>
                <input id="login-password-confirm" className="fld" type="password" value={passwordConfirm} onChange={e => setPasswordConfirm(e.target.value)} required />
              </div>}

              {error && (
                <div role="alert" aria-live="assertive" style={{
                  background: '#fef2f2', border: '1px solid #fecaca',
                  borderRadius: 6, padding: '8px 12px', marginBottom: 12,
                  fontSize: 13, color: '#b91c1c',
                }}>
                  {error}
                </div>
              )}
              {notice && <div role="status" aria-live="polite" style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 6, padding: '8px 12px', marginBottom: 12, fontSize: 13, color: '#047857' }}>{notice}</div>}

              <button
                type="submit"
                className="btn pri"
                style={{ width: '100%', justifyContent: 'center', padding: '9px 0', fontSize: 14 }}
                disabled={loading}
              >
                {loading ? t('login.submitting') : t(`login.${mode === 'login' ? 'submit' : mode === 'request' ? 'resetSubmit' : 'newPasswordSubmit'}`)}
              </button>
              {mode === 'login' && <button type="button" className="btn" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }} onClick={() => goTo('request')}>{t('login.forgotPassword')}</button>}
              {mode !== 'login' && <button type="button" className="btn" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }} onClick={() => goTo('login')}>{t('login.backToLogin')}</button>}
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
