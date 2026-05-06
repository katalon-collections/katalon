import { useState, useEffect, useRef } from 'react'
import { req, BASE, apiKeys } from '../../api/client'
import type { ApiKey, ApiKeyCreated, PortalConfigRead } from '../../types'

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
  const [placeholderImageUrl, setPlaceholderImageUrl] = useState('')
  const [featuredIds, setFeaturedIds] = useState('')
  const [facetFields, setFacetFields] = useState('')
  const [accentColor, setAccentColor] = useState('')
  const [headerBg, setHeaderBg] = useState('')
  const [headerFg, setHeaderFg] = useState('')
  const [pageBg, setPageBg] = useState('')
  const [panelBg, setPanelBg] = useState('')

  const [lang, setLang] = useState(localStorage.getItem('katalon_lang') ?? 'de')

  const [reindexing, setReindexing] = useState<string | null>(null)
  const [reindexMsg, setReindexMsg] = useState<string | null>(null)

  const [pwdCurrent, setPwdCurrent] = useState('')
  const [pwdNew, setPwdNew] = useState('')
  const [pwdConfirm, setPwdConfirm] = useState('')
  const [pwdError, setPwdError] = useState<string | null>(null)
  const [pwdSuccess, setPwdSuccess] = useState(false)

  const [ownKeys, setOwnKeys] = useState<ApiKey[]>([])
  const [ownKeysLoading, setOwnKeysLoading] = useState(true)
  const [newKeyName, setNewKeyName] = useState('')
  const [keyCreating, setKeyCreating] = useState(false)
  const [keyCreated, setKeyCreated] = useState<ApiKeyCreated | null>(null)
  const [keyError, setKeyError] = useState<string | null>(null)

  useEffect(() => {
    apiKeys.listOwn()
      .then(setOwnKeys)
      .catch(() => {/* silently ignore */})
      .finally(() => setOwnKeysLoading(false))
  }, [])

  async function handleCreateOwnKey() {
    if (!newKeyName.trim()) return
    setKeyCreating(true)
    setKeyError(null)
    setKeyCreated(null)
    try {
      const result = await apiKeys.createOwn(newKeyName.trim())
      setKeyCreated(result)
      setNewKeyName('')
      const updated = await apiKeys.listOwn()
      setOwnKeys(updated)
    } catch (e) {
      setKeyError((e as Error).message)
    } finally {
      setKeyCreating(false)
    }
  }

  async function handleRevokeOwnKey(keyId: string) {
    if (!window.confirm('API-Schlüssel wirklich widerrufen?')) return
    try {
      await apiKeys.revokeOwn(keyId)
      setOwnKeys(prev => prev.filter(k => k.id !== keyId))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  useEffect(() => {
    setLoading(true)
    req<PortalConfigRead>(`${BASE}/v1/portal/config`)
      .then((c: PortalConfigRead) => {
        setConfig(c)
        setSiteTitle(c.site_title)
        setSiteSubtitle(c.site_subtitle)
        setHeroText(c.hero_text)
        setLogoUrl(c.logo_url)
        setPlaceholderImageUrl(c.placeholder_image_url ?? '')
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
          placeholder_image_url: placeholderImageUrl,
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

  async function handleReindex(type?: string) {
    const key = type ?? 'all'
    if (!window.confirm(type ? `Alle ${type}-Datensätze neu indizieren?` : 'Alle Datensätze vollständig neu indizieren?')) return
    setReindexing(key)
    setReindexMsg(null)
    try {
      const url = type ? `${BASE}/v1/search/reindex/${type}` : `${BASE}/v1/search/reindex`
      await req(url, { method: 'POST' })
      setReindexMsg('Reindizierung gestartet — läuft im Hintergrund.')
      setTimeout(() => setReindexMsg(null), 5000)
    } catch (e) {
      setReindexMsg(`Fehler: ${(e as Error).message}`)
    } finally {
      setReindexing(null)
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
                <div className="lbl">Platzhalter-Bild <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(für Objekte ohne Bild)</span></div>
                <input className="fld mono" value={placeholderImageUrl} onChange={e => setPlaceholderImageUrl(e.target.value)}
                  placeholder="https://..." style={{ fontSize: 12 }} />
                {placeholderImageUrl && (
                  <img src={placeholderImageUrl} alt="Platzhalter-Vorschau"
                    style={{ marginTop: 6, height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />
                )}
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

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="hd">API-Schlüssel</div>
            <div className="bd">
              <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
                API-Schlüssel ermöglichen den Zugriff auf die API ohne Passwort. Schicke den Schlüssel im Header <code>X-API-Key</code>.
              </p>

              {keyCreated && (
                <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '10px 12px', marginBottom: 12, fontSize: 12 }}>
                  <div style={{ fontWeight: 600, color: '#166534', marginBottom: 4 }}>✓ Schlüssel erstellt — bitte jetzt kopieren, er wird nicht erneut angezeigt:</div>
                  <code style={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: 11, background: '#dcfce7', padding: '6px 8px', borderRadius: 4, color: '#14532d' }}>
                    {keyCreated.key}
                  </code>
                  <button className="btn sm gh" style={{ marginTop: 6 }} onClick={() => navigator.clipboard.writeText(keyCreated.key)}>
                    Kopieren
                  </button>
                </div>
              )}

              {keyError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{keyError}</div>}

              {!ownKeysLoading && ownKeys.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-s)' }}>
                      <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Name</th>
                      <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Präfix</th>
                      <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Erstellt</th>
                      <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Zuletzt verwendet</th>
                      <th style={{ width: 60 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {ownKeys.map(k => (
                      <tr key={k.id} style={{ borderBottom: '1px solid var(--border-s)' }}>
                        <td style={{ padding: '4px 8px' }}>{k.name}</td>
                        <td style={{ padding: '4px 8px', fontFamily: 'monospace', fontSize: 11 }}>{k.key_prefix}…</td>
                        <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>{new Date(k.created_at).toLocaleDateString('de-DE')}</td>
                        <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>
                          {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('de-DE') : '—'}
                        </td>
                        <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                          <button className="btn sm ico gh dn" onClick={() => handleRevokeOwnKey(k.id)} title="Widerrufen">🗑</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  className="fld"
                  style={{ flex: 1 }}
                  placeholder="Name des neuen Schlüssels"
                  value={newKeyName}
                  onChange={e => setNewKeyName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreateOwnKey()}
                />
                <button className="btn pri" onClick={handleCreateOwnKey} disabled={keyCreating || !newKeyName.trim()}>
                  {keyCreating ? 'Erstelle…' : 'Erstellen'}
                </button>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="hd">Suche &amp; Indexierung</div>
            <div className="bd">
              <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
                Nach Schema-Änderungen oder Datenimporten muss der Suchindex manuell aktualisiert werden.
                Die Reindizierung läuft asynchron im Hintergrund.
              </p>
              {reindexMsg && (
                <div style={{ fontSize: 12, color: reindexMsg.startsWith('Fehler') ? '#dc2626' : '#166534', marginBottom: 10 }}>
                  {reindexMsg}
                </div>
              )}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {(['object', 'entity', 'place', 'occurrence'] as const).map(t => (
                  <button
                    key={t}
                    className="btn sm gh"
                    onClick={() => handleReindex(t)}
                    disabled={reindexing !== null}
                  >
                    {reindexing === t ? 'Läuft…' : `${t} reindizieren`}
                  </button>
                ))}
                <button
                  className="btn sm pri"
                  onClick={() => handleReindex()}
                  disabled={reindexing !== null}
                  style={{ marginLeft: 8 }}
                >
                  {reindexing === 'all' ? 'Läuft…' : 'Alles reindizieren'}
                </button>
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
