import { useState, useEffect, useRef } from 'react'
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
  const [logoUploading, setLogoUploading] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)

  const [siteTitle, setSiteTitle] = useState('')
  const [siteSubtitle, setSiteSubtitle] = useState('')
  const [heroText, setHeroText] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [featuredIds, setFeaturedIds] = useState('')
  const [facetFields, setFacetFields] = useState('')
  const [accentColor, setAccentColor] = useState('')
  const [headerBg, setHeaderBg] = useState('')
  const [headerFg, setHeaderFg] = useState('')
  const [pageBg, setPageBg] = useState('')
  const [panelBg, setPanelBg] = useState('')

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
        setHeroText(c.hero_text)
        setLogoUrl(c.logo_url)
        setFeaturedIds((c.featured_object_ids ?? []).join('\n'))
        setFacetFields((c.facet_fields ?? []).join('\n'))
        setAccentColor(c.accent_color)
        const ct = c.color_tokens ?? {}
        setHeaderBg(ct['--header-bg'] ?? '')
        setHeaderFg(ct['--header-fg'] ?? '')
        setPageBg(ct['--bg'] ?? '')
        setPanelBg(ct['--panel'] ?? '')
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
          hero_text: heroText,
          logo_url: logoUrl,
          featured_object_ids: featuredIds.split('\n').map(s => s.trim()).filter(Boolean),
          facet_fields: facetFields.split('\n').map(s => s.trim()).filter(Boolean),
          accent_color: accentColor,
          color_tokens: Object.fromEntries(
            [['--header-bg', headerBg], ['--header-fg', headerFg], ['--bg', pageBg], ['--panel', panelBg]]
              .filter(([, v]) => v.trim())
          ),
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

  async function handleLogoUpload(file: File) {
    setLogoUploading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const token = localStorage.getItem('katalon_token')
      const res = await fetch(`${BASE}/v1/portal/logo`, {
        method: 'POST',
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? `Fehler ${res.status}`)
      }
      const c: PortalConfigRead = await res.json()
      setLogoUrl(c.logo_url)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLogoUploading(false)
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
                <div className="lbl">Willkommenstext (Hero)</div>
                <textarea className="fld" rows={3} value={heroText} onChange={e => setHeroText(e.target.value)}
                  style={{ resize: 'vertical', fontFamily: 'inherit' }} />
              </div>
              <div className="field">
                <div className="lbl">Logo <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  {logoUrl && (
                    <img src={logoUrl} alt="Logo-Vorschau"
                      style={{ height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />
                  )}
                  <button className="btn gh sm" onClick={() => logoInputRef.current?.click()} disabled={logoUploading}>
                    {logoUploading ? 'Lädt hoch…' : 'Logo hochladen'}
                  </button>
                  {logoUrl && (
                    <button className="btn sm gh" onClick={() => setLogoUrl('')} title="Logo entfernen">✕</button>
                  )}
                  <input ref={logoInputRef} type="file" accept="image/*" style={{ display: 'none' }}
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleLogoUpload(f); e.target.value = '' }} />
                </div>
                <input className="fld mono" value={logoUrl} onChange={e => setLogoUrl(e.target.value)}
                  placeholder="oder URL eingeben" style={{ marginTop: 6, fontSize: 12 }} />
              </div>
              <div className="field">
                <div className="lbl">Highlight-Objekte <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(eine UUID pro Zeile, max. 6)</span></div>
                <textarea className="fld mono" rows={4} value={featuredIds} onChange={e => setFeaturedIds(e.target.value)}
                  style={{ resize: 'vertical', fontSize: 12 }} placeholder={'uuid-1\nuuid-2\nuuid-3'} />
              </div>
              <div className="field">
                <div className="lbl">Facetten-Felder <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(ein Feldname pro Zeile — erscheinen als Filter in der Portal-Suche)</span></div>
                <textarea className="fld mono" rows={4} value={facetFields} onChange={e => setFacetFields(e.target.value)}
                  style={{ resize: 'vertical', fontSize: 12 }} placeholder={'creator\nmaterial\nlocation'} />
              </div>
              {[
                { lbl: 'Akzentfarbe', val: accentColor, set: setAccentColor },
                { lbl: 'Kopfzeile — Hintergrund', val: headerBg, set: setHeaderBg, ph: '#0b1a33' },
                { lbl: 'Kopfzeile — Schrift', val: headerFg, set: setHeaderFg, ph: '#ffffff' },
                { lbl: 'Seitenhintergrund', val: pageBg, set: setPageBg, ph: '#f4f5f7' },
                { lbl: 'Panel-/Kartenfarbe', val: panelBg, set: setPanelBg, ph: '#ffffff' },
              ].map(({ lbl, val, set, ph }) => (
                <div className="field" key={lbl}>
                  <div className="lbl">{lbl}</div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input type="color" value={val || (ph ?? '#000000')} onChange={e => set(e.target.value)}
                      style={{ width: 40, height: 32, padding: 2, border: '1px solid var(--border-s)', borderRadius: 4 }} />
                    <input className="fld mono" value={val} onChange={e => set(e.target.value)}
                      placeholder={ph ?? ''} style={{ flex: 1 }} />
                    {val && <button className="btn sm gh" onClick={() => set('')} title="Zurücksetzen">✕</button>}
                  </div>
                </div>
              ))}
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

        </div>
      )}
    </div>
  )
}
