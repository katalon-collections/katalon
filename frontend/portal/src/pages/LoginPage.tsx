// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, setToken } from '../api/client'
import { useI18n } from '../i18n'

interface Props { onLogin: () => void }

export function LoginPage({ onLogin }: Props) {
  const navigate = useNavigate()
  const { t } = useI18n()
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
    <h1>{t('login.title')}</h1>
    <p>{t('login.intro')}</p>
    <label>{t('login.email')}<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus /></label>
    <label>{t('login.password')}<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
    {error && <p className="login-error" role="alert">{error}</p>}
    <button type="submit" disabled={loading}>{loading ? t('login.submitting') : t('login.title')}</button>
    <div className="login-register">
      <span>{t('login.noAccount')}</span>
      <button type="button" disabled>{t('login.register')}</button>
    </div>
  </form></section>
}
