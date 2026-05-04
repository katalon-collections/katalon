import { useState, useEffect } from 'react'
import { req, BASE } from '../../api/client'
import type { PortalConfigRead } from '../../types'

interface Props {
  onNavigate?: (route: string) => void
}

export function ScreenSettings({ onNavigate }: Props) {
  const [config, setConfig] = useState<PortalConfigRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [siteTitle, setSiteTitle] = useState('')
  const [siteSubtitle, setSiteSubtitle] = useState('')
  const [accentColor, setAccentColor] = useState('')

  const [lang, setLang] = useState(localStorage.getItem('katalon_lang') ?? 'de')

  const [pwdCurrent, setPwdCurrent] = useState('')
  const [pwdNew, setPwdNew] = useState('')
  const [pwdConfirm, setPwdConfirm] = useState('')
  const [pwdError, setPwdError] = useState<string | null>(null)
  const [pwdSuccess, setPwdSuccess] = useState(false)

  useEffect(() => {
    setLoading(true)
    req<PortalConfigRead>(`${BASE}/v1/portal/config`)
      .then((c: PortalConfigRead) => {
        setConfig(c)
        setSiteTitle(c.site_title)
        setSiteSubtitle(c.site_subtitle)
        setAccentColor(c.accent_color)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleSaveConfig() {
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({
          site_title: siteTitle,
          site_subtitle: siteSubtitle,
          accent_color: accentColor,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  function handleLangChange(next: string) {
    setLang(next)
    localStorage.setItem('katalon_lang', next)
  }

  async function handleChangePassword() {
    setPwdError(null)
    setPwdSuccess(false)
    if (pwdNew !== pwdConfirm) {
      setPwdError('Die neuen Passwörter stimmen nicht überein.')
      return
    }
    if (pwdNew.length < 6) {
      setPwdError('Das neue Passwort muss mindestens 6 Zeichen haben.')
      return
    }
    try {
      await req(`${BASE}/v1/users/me/password`, {
        method: 'PUT',
        body: JSON.stringify({ current_password: pwdCurrent, new_password: pwdNew }),
      })
      setPwdSuccess(true)
      setPwdCurrent('')
      setPwdNew('')
      setPwdConfirm('')
      setTimeout(() => setPwdSuccess(false), 3000)
    } catch (e) {
      setPwdError((e as Error).message)
    }
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Einstellungen</h1><div className="sub">System- und Account-Einstellungen</div></div>
      </div>

      {loading && <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div style={{ maxWidth: 640, padding: '0 24px' }}>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="hd">Portal & Institution</div>
            <div className="bd">
              <div className="field">
                <div className="lbl">Institutionsname / Seitentitel</div>
                <input className="fld" value={siteTitle} onChange={e => setSiteTitle(e.target.value)} />
              </div>
              <div className="field">
                <div className="lbl">Untertitel</div>
                <input className="fld" value={siteSubtitle} onChange={e => setSiteSubtitle(e.target.value)} />
              </div>
              <div className="field">
                <div className="lbl">Akzentfarbe</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="color" value={accentColor} onChange={e => setAccentColor(e.target.value)} style={{ width: 40, height: 32, padding: 2, border: '1px solid var(--border-s)', borderRadius: 4 }} />
                  <input className="fld mono" value={accentColor} onChange={e => setAccentColor(e.target.value)} style={{ flex: 1 }} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="btn pri" onClick={handleSaveConfig} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
                {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>Gespeichert.</span>}
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="hd">Oberfläche</div>
            <div className="bd">
              <div className="field">
                <div className="lbl">Sprache</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className={`btn${lang === 'de' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('de')}>Deutsch</button>
                  <button className={`btn${lang === 'en' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('en')}>English</button>
                </div>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="hd">Passwort ändern</div>
            <div className="bd">
              <div className="field">
                <div className="lbl">Aktuelles Passwort</div>
                <input className="fld" type="password" value={pwdCurrent} onChange={e => setPwdCurrent(e.target.value)} />
              </div>
              <div className="field">
                <div className="lbl">Neues Passwort</div>
                <input className="fld" type="password" value={pwdNew} onChange={e => setPwdNew(e.target.value)} />
              </div>
              <div className="field">
                <div className="lbl">Neues Passwort wiederholen</div>
                <input className="fld" type="password" value={pwdConfirm} onChange={e => setPwdConfirm(e.target.value)} />
              </div>
              {pwdError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{pwdError}</div>}
              {pwdSuccess && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>Passwort geändert.</div>}
              <button className="btn pri" onClick={handleChangePassword}>Passwort ändern</button>
            </div>
          </div>

          <div className="card">
            <div className="hd">Portal-Konfiguration</div>
            <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
              Für erweiterte Portal-Einstellungen (Startseite, Facetten, Statische Seiten) siehe Phase 8.1.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
