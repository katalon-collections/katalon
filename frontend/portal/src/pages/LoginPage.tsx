import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, setToken } from '../api/client'

interface Props { onLogin: () => void }

export function LoginPage({ onLogin }: Props) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const token = await login(email, password)
      setToken(token.access_token)
      onLogin()
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return <section className="login-page"><form className="login-card" onSubmit={submit}>
    <h1>Anmelden</h1>
    <p>Mit deinem Katalon-Konto anmelden.</p>
    <label>E-Mail<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus /></label>
    <label>Passwort<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
    {error && <p className="login-error" role="alert">{error}</p>}
    <button type="submit" disabled={loading}>{loading ? 'Anmeldung läuft …' : 'Anmelden'}</button>
    <div className="login-register">
      <span>Noch kein Konto?</span>
      <button type="button" disabled>Registrieren (demnächst)</button>
    </div>
  </form></section>
}
