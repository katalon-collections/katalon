// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { req, BASE, apiKeys, users, schema, subtypes, adminConfig, authority, authorizedFetch, sparql } from '../../api/client'
import type { AdminConfigRead, AuthoritySource, SparqlStatus } from '../../api/client'
import type { ApiKey, ApiKeyCreated, FieldDefinition, PortalConfigRead, RecordSubtype } from '../../types'
import type { TourVariant } from '../tour/Tour'

interface Props {
  onNavigate?: (route: string) => void
  isAdmin: boolean
  features: string[]
  onStartTour?: (variant: TourVariant) => void
}

type Section = 'profil' | 'portal' | 'facetten' | 'sprachen' | 'suche' | 'sparql' | 'idno' | 'ki' | 'medien' | 'authorities' | 'sperren' | 'changelog' | 'gefahrenbereich' | 'ueber'

const RECORD_TYPES = [
  { key: 'object',     label: 'Objekte',     labelKey: 'recordTypes.object' },
  { key: 'entity',     label: 'Entitäten',   labelKey: 'recordTypes.entity' },
  { key: 'place',      label: 'Orte',        labelKey: 'recordTypes.place' },
  { key: 'occurrence', label: 'Occurrences', labelKey: 'recordTypes.occurrence' },
  { key: 'procedure',  label: 'Vorgänge',    labelKey: 'recordTypes.procedure' },
  { key: 'collection', label: 'Sammlungen',  labelKey: 'recordTypes.collection' },
] as const

const AUTHORITY_TESTS: Record<string, { query: string, href: string }> = {
  gnd: { query: 'Beethoven', href: 'https://lobid.org/gnd/search?q=Beethoven' },
  'gnd-person': { query: 'Beethoven', href: 'https://lobid.org/gnd/search?q=Beethoven&filter=type%3APerson' },
  'gnd-subject': { query: 'Fotografie', href: 'https://lobid.org/gnd/search?q=Fotografie&filter=type%3ASubjectHeading' },
  geonames: { query: 'Berlin', href: 'https://www.geonames.org/search.html?q=Berlin' },
  viaf: { query: 'Beethoven', href: 'https://viaf.org/viaf/search?query=local.names+all+%22Beethoven%22' },
  wikidata: { query: 'Berlin', href: 'https://www.wikidata.org/w/index.php?search=Berlin' },
  tgn: { query: 'Berlin', href: 'https://vocab.getty.edu/sparql' },
  iconclass: { query: 'Leier', href: 'https://iconclass.org/search?lang=de&q=leier' },
  aat: { query: 'photograph', href: 'https://vocab.getty.edu/sparql' },
}

// ---------------------------------------------------------------------------
// Profil section
// ---------------------------------------------------------------------------

function SectionProfil({ onStartTour }: { onStartTour?: (variant: TourVariant) => void }) {
  const { t } = useTranslation('screenSettings')
  const [pwdCurrent, setPwdCurrent] = useState('')
  const [pwdNew, setPwdNew] = useState('')
  const [pwdConfirm, setPwdConfirm] = useState('')
  const [pwdError, setPwdError] = useState<string | null>(null)
  const [pwdSuccess, setPwdSuccess] = useState(false)
  const [emailNew, setEmailNew] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [emailSuccess, setEmailSuccess] = useState(false)
  const [ownKeys, setOwnKeys] = useState<ApiKey[]>([])
  const [ownKeysLoading, setOwnKeysLoading] = useState(true)
  const [newKeyName, setNewKeyName] = useState('')
  const [keyCreating, setKeyCreating] = useState(false)
  const [keyCreated, setKeyCreated] = useState<ApiKeyCreated | null>(null)
  const [keyError, setKeyError] = useState<string | null>(null)

  useEffect(() => {
    apiKeys.listOwn()
      .then(setOwnKeys)
      .catch(() => {})
      .finally(() => setOwnKeysLoading(false))
  }, [])

  async function handleCreateOwnKey() {
    if (!newKeyName.trim()) return
    setKeyCreating(true); setKeyError(null); setKeyCreated(null)
    try {
      const result = await apiKeys.createOwn(newKeyName.trim())
      setKeyCreated(result); setNewKeyName('')
      setOwnKeys(await apiKeys.listOwn())
    } catch (e) { setKeyError((e as Error).message) }
    finally { setKeyCreating(false) }
  }

  async function handleRevokeOwnKey(keyId: string) {
    if (!window.confirm(t('profil.apiKeys.revokeConfirm'))) return
    try {
      await apiKeys.revokeOwn(keyId)
      setOwnKeys(prev => prev.filter(k => k.id !== keyId))
    } catch (e) { alert((e as Error).message) }
  }

  async function handleChangePassword() {
    setPwdError(null); setPwdSuccess(false)
    if (pwdNew !== pwdConfirm) { setPwdError(t('profil.password.errors.mismatch')); return }
    if (pwdNew.length < 8 || !/[A-Za-z]/.test(pwdNew) || !/[0-9]/.test(pwdNew)) {
      setPwdError(t('profil.password.errors.weak')); return
    }
    try {
      await users.changeOwnPassword(pwdCurrent, pwdNew)
      setPwdSuccess(true); setPwdCurrent(''); setPwdNew(''); setPwdConfirm('')
      setTimeout(() => setPwdSuccess(false), 3000)
    } catch (e) { setPwdError((e as Error).message) }
  }

  async function handleChangeEmail() {
    setEmailError(null); setEmailSuccess(false)
    if (!emailNew.trim()) { setEmailError(t('profil.email.errors.newRequired')); return }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailNew.trim())) { setEmailError(t('profil.email.errors.invalid')); return }
    if (!emailPassword) { setEmailError(t('profil.email.errors.passwordRequired')); return }
    try {
      await users.changeOwnEmail(emailNew.trim(), emailPassword)
      setEmailSuccess(true); setEmailNew(''); setEmailPassword('')
      setTimeout(() => setEmailSuccess(false), 3000)
    } catch (e) { setEmailError((e as Error).message) }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('profil.email.title')}</div>
        <div className="bd">
          <div className="field">
            <div className="lbl">{t('profil.email.newLabel')}</div>
            <input className="fld" type="email" value={emailNew} onChange={e => setEmailNew(e.target.value)} />
          </div>
          <div className="field">
            <div className="lbl">{t('profil.email.currentPasswordLabel')}</div>
            <input className="fld" type="password" value={emailPassword} onChange={e => setEmailPassword(e.target.value)} />
          </div>
          {emailError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{emailError}</div>}
          {emailSuccess && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{t('profil.email.success')}</div>}
          <button className="btn pri" onClick={handleChangeEmail}>{t('profil.email.submit')}</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('profil.password.title')}</div>
        <div className="bd">
          <div className="field">
            <div className="lbl">{t('profil.password.currentLabel')}</div>
            <input className="fld" type="password" value={pwdCurrent} onChange={e => setPwdCurrent(e.target.value)} />
          </div>
          <div className="field">
            <div className="lbl">{t('profil.password.newLabel')}</div>
            <input className="fld" type="password" value={pwdNew} onChange={e => setPwdNew(e.target.value)} />
          </div>
          <div className="field">
            <div className="lbl">{t('profil.password.confirmLabel')}</div>
            <input className="fld" type="password" value={pwdConfirm} onChange={e => setPwdConfirm(e.target.value)} />
          </div>
          {pwdError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{pwdError}</div>}
          {pwdSuccess && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{t('profil.password.success')}</div>}
          <button className="btn pri" onClick={handleChangePassword}>{t('profil.password.submit')}</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('profil.apiKeys.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
            {t('profil.apiKeys.intro')} <code>X-API-Key</code>.
          </p>
          {keyCreated && (
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '10px 12px', marginBottom: 12, fontSize: 12 }}>
              <div style={{ fontWeight: 600, color: '#166534', marginBottom: 4 }}>{t('profil.apiKeys.created')}</div>
              <code style={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: 11, background: '#dcfce7', padding: '6px 8px', borderRadius: 4, color: '#14532d' }}>
                {keyCreated.key}
              </code>
              <button className="btn sm gh" style={{ marginTop: 6 }} onClick={() => navigator.clipboard.writeText(keyCreated!.key)}>{t('profil.apiKeys.copy')}</button>
            </div>
          )}
          {keyError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{keyError}</div>}
          {!ownKeysLoading && ownKeys.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-s)' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('profil.apiKeys.columns.name')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('profil.apiKeys.columns.prefix')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('profil.apiKeys.columns.created')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('profil.apiKeys.columns.lastUsed')}</th>
                  <th style={{ width: 60 }} />
                </tr>
              </thead>
              <tbody>
                {ownKeys.map(k => (
                  <tr key={k.id} style={{ borderBottom: '1px solid var(--border-s)' }}>
                    <td style={{ padding: '4px 8px' }}>{k.name}</td>
                    <td style={{ padding: '4px 8px', fontFamily: 'monospace', fontSize: 11 }}>{k.key_prefix}…</td>
                    <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>{new Date(k.created_at).toLocaleDateString('de-DE')}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('de-DE') : '—'}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                      <button className="btn sm ico gh dn" onClick={() => handleRevokeOwnKey(k.id)} title={t('profil.apiKeys.revoke')}>🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="fld" style={{ flex: 1 }} placeholder={t('profil.apiKeys.namePlaceholder')}
              value={newKeyName} onChange={e => setNewKeyName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreateOwnKey()}
            />
            <button className="btn pri" onClick={handleCreateOwnKey} disabled={keyCreating || !newKeyName.trim()}>
              {keyCreating ? t('profil.apiKeys.creating') : t('profil.apiKeys.create')}
            </button>
          </div>
        </div>
      </div>

      {onStartTour && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hd">{t('profil.tour.title')}</div>
          <div className="bd">
            <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
              {t('profil.tour.intro')}
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn gh" onClick={() => onStartTour('basic')}>{t('profil.tour.startBasic')}</button>
              <button className="btn gh" onClick={() => onStartTour('advanced')}>{t('profil.tour.startAdvanced')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Portal section
// ---------------------------------------------------------------------------

function SectionPortal({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [logoUploading, setLogoUploading] = useState(false)

  const [siteTitle, setSiteTitle] = useState(config.site_title)
  const [siteSubtitle, setSiteSubtitle] = useState(config.site_subtitle)
  const [heroText, setHeroText] = useState(config.hero_text)
  const [logoUrl, setLogoUrl] = useState(config.logo_url)
  const [placeholderImageUrl, setPlaceholderImageUrl] = useState(config.placeholder_image_url ?? '')
  const [featuredIds, setFeaturedIds] = useState((config.featured_object_ids ?? []).join('\n'))
  const [browseTypes, setBrowseTypes] = useState(config.browse_enabled_types ?? ['object', 'entity', 'place', 'occurrence'])
  const [accentColor, setAccentColor] = useState(config.accent_color)
  const [detailSidebarPosition, setDetailSidebarPosition] = useState(config.detail_sidebar_position ?? 'right')
  const [lang, setLang] = useState(localStorage.getItem('katalon_lang') ?? 'de')

  const ct = config.color_tokens ?? {}
  const [headerBg, setHeaderBg] = useState(ct['--header-bg'] ?? '')
  const [headerFg, setHeaderFg] = useState(ct['--header-fg'] ?? '')
  const [pageBg, setPageBg] = useState(ct['--bg'] ?? '')
  const [panelBg, setPanelBg] = useState(ct['--panel'] ?? '')

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      const c = await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({
          site_title: siteTitle, site_subtitle: siteSubtitle, hero_text: heroText,
          logo_url: logoUrl, placeholder_image_url: placeholderImageUrl,
          featured_object_ids: featuredIds.split('\n').map(s => s.trim()).filter(Boolean),
          browse_enabled_types: browseTypes,
          accent_color: accentColor,
          detail_sidebar_position: detailSidebarPosition,
          color_tokens: Object.fromEntries(
            [['--header-bg', headerBg], ['--header-fg', headerFg], ['--bg', pageBg], ['--panel', panelBg]]
              .filter(([, v]) => v.trim())
          ),
        }),
      })
      onSaved(c)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  async function handleLogoUpload(file: File) {
    setLogoUploading(true); setError(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await authorizedFetch(`${BASE}/v1/portal/logo`, { method: 'POST', body: fd })
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? `Fehler ${res.status}`) }
      const c: PortalConfigRead = await res.json()
      setLogoUrl(c.logo_url); onSaved(c)
    } catch (e) { setError((e as Error).message) }
    finally { setLogoUploading(false) }
  }

  function handleLangChange(next: string) { setLang(next); localStorage.setItem('katalon_lang', next) }

  const colorFields = [
    { lbl: 'Akzentfarbe', val: accentColor, set: setAccentColor },
    { lbl: 'Kopfzeile — Hintergrund', val: headerBg, set: setHeaderBg, ph: '#0b1a33' },
    { lbl: 'Kopfzeile — Schrift', val: headerFg, set: setHeaderFg, ph: '#ffffff' },
    { lbl: 'Seitenhintergrund', val: pageBg, set: setPageBg, ph: '#f4f5f7' },
    { lbl: 'Panel-/Kartenfarbe', val: panelBg, set: setPanelBg, ph: '#ffffff' },
  ]

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Institution</div>
        <div className="bd">
          <div className="field"><div className="lbl">Institutionsname / Seitentitel</div>
            <input className="fld" value={siteTitle} onChange={e => setSiteTitle(e.target.value)} /></div>
          <div className="field"><div className="lbl">Untertitel</div>
            <input className="fld" value={siteSubtitle} onChange={e => setSiteSubtitle(e.target.value)} /></div>
          <div className="field"><div className="lbl">Willkommenstext (Hero)</div>
            <textarea className="fld" rows={3} value={heroText} onChange={e => setHeroText(e.target.value)}
              style={{ resize: 'vertical', fontFamily: 'inherit' }} /></div>
          <div className="field">
            <div className="lbl">Logo <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {logoUrl && <img src={logoUrl} alt="Logo" style={{ height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />}
              <button className="btn gh sm" onClick={() => logoInputRef.current?.click()} disabled={logoUploading}>{logoUploading ? 'Lädt hoch…' : 'Logo hochladen'}</button>
              {logoUrl && <button className="btn sm gh" onClick={() => setLogoUrl('')} title="Logo entfernen">✕</button>}
              <input ref={logoInputRef} type="file" accept="image/*" style={{ display: 'none' }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleLogoUpload(f); e.target.value = '' }} />
            </div>
            <input className="fld mono" value={logoUrl} onChange={e => setLogoUrl(e.target.value)} placeholder="oder URL eingeben" style={{ marginTop: 6, fontSize: 12 }} />
          </div>
          <div className="field">
            <div className="lbl">Platzhalter-Bild <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(für Objekte ohne Bild)</span></div>
            <input className="fld mono" value={placeholderImageUrl} onChange={e => setPlaceholderImageUrl(e.target.value)} placeholder="https://..." style={{ fontSize: 12 }} />
            {placeholderImageUrl && <img src={placeholderImageUrl} alt="Platzhalter" style={{ marginTop: 6, height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />}
          </div>
          <div className="field">
            <div className="lbl">Highlight-Objekte <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(eine UUID pro Zeile, max. 6)</span></div>
            <textarea className="fld mono" rows={4} value={featuredIds} onChange={e => setFeaturedIds(e.target.value)} style={{ resize: 'vertical', fontSize: 12 }} placeholder={'uuid-1\nuuid-2'} />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Öffentliche Navigation</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
            Nur aktivierte Typen erscheinen als eigener Menüpunkt im Portal. Direkte Links bleiben erreichbar.
          </p>
          {RECORD_TYPES.filter(({ key }) => key !== 'procedure').map(({ key, label }) => (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={browseTypes.includes(key)}
                onChange={e => setBrowseTypes(types => e.target.checked ? [...types, key] : types.filter(type => type !== key))}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Detailseiten-Layout</div>
        <div className="bd">
          <div className="field">
            <div className="lbl">Seitenspalte (Metadaten)</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`btn${detailSidebarPosition === 'right' ? ' pri' : ' gh'}`} onClick={() => setDetailSidebarPosition('right')}>Rechts</button>
              <button className={`btn${detailSidebarPosition === 'left' ? ' pri' : ' gh'}`} onClick={() => setDetailSidebarPosition('left')}>Links</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              Gilt einheitlich für alle Detailseiten (Objekte, Entitäten, Orte, Occurrences). Auf kleinen Bildschirmen stehen Medien/Hauptinhalt immer zuerst.
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Design & Farben</div>
        <div className="bd">
          {colorFields.map(({ lbl, val, set, ph }) => (
            <div className="field" key={lbl}>
              <div className="lbl">{lbl}</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="color" value={val || (ph ?? '#000000')} onChange={e => set(e.target.value)}
                  style={{ width: 40, height: 32, padding: 2, border: '1px solid var(--border-s)', borderRadius: 4 }} />
                <input className="fld mono" value={val} onChange={e => set(e.target.value)} placeholder={ph ?? ''} style={{ flex: 1 }} />
                {val && <button className="btn sm gh" onClick={() => set('')} title="Zurücksetzen">✕</button>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Oberfläche</div>
        <div className="bd">
          <div className="field"><div className="lbl">Sprache</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`btn${lang === 'de' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('de')}>Deutsch</button>
              <button className={`btn${lang === 'en' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('en')}>English</button>
            </div>
          </div>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>Gespeichert.</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Danger zone section
// ---------------------------------------------------------------------------

function SectionDangerZone() {
  const [activeType, setActiveType] = useState<(typeof RECORD_TYPES)[number]['key']>('object')
  const [subtypesList, setSubtypesList] = useState<RecordSubtype[]>([])
  const [activeSubtype, setActiveSubtype] = useState('')
  const [summary, setSummary] = useState<number | null>(null)
  const [confirmation, setConfirmation] = useState('')
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const active = RECORD_TYPES.find(type => type.key === activeType)!
  const selectedSubtype = subtypesList.find(subtype => subtype.name === activeSubtype)
  const expectedConfirmation = (selectedSubtype?.label?.de || active.label).toUpperCase()

  useEffect(() => {
    setActiveSubtype('')
    subtypes.list(activeType).then(setSubtypesList).catch(() => setSubtypesList([]))
  }, [activeType])

  useEffect(() => {
    setSummary(null); setConfirmation(''); setError(null); setSuccess(null)
    schema.resetSummary(activeType, activeSubtype || undefined)
      .then(result => setSummary(result.deletable_fields))
      .catch((e: Error) => setError(e.message))
  }, [activeType, activeSubtype])

  async function handleReset() {
    if (confirmation !== expectedConfirmation) return
    setResetting(true); setError(null); setSuccess(null)
    try {
      const result = await schema.reset(activeType, activeSubtype || undefined)
      setSummary(0); setConfirmation('')
      setSuccess(`${result.deleted_fields} Felddefinitionen wurden ausgeblendet.`)
    } catch (e) { setError((e as Error).message) }
    finally { setResetting(false) }
  }

  return (
    <div>
      <div className="card" style={{ borderColor: '#fca5a5' }}>
        <div className="hd" style={{ color: '#b91c1c' }}>Gefahrenbereich</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
            Blendet Felddefinitionen aus, löscht aber keine Datensätze oder Metadaten. Für eine spätere Bearbeitung das Feld im Schema-Editor mit demselben technischen Namen wieder anlegen; die gespeicherten Werte werden dann wieder angezeigt. Das Systemfeld <code>label</code> bleibt erhalten.
          </p>
          <div className="field">
            <div className="lbl">Bestandstyp</div>
            <select className="fld" value={activeType} onChange={e => setActiveType(e.target.value as typeof activeType)}>
              {RECORD_TYPES.map(type => <option key={type.key} value={type.key}>{type.label}</option>)}
            </select>
          </div>
          {subtypesList.length > 0 && <div className="field">
            <div className="lbl">Geltungsbereich</div>
            <select className="fld" value={activeSubtype} onChange={e => setActiveSubtype(e.target.value)}>
              <option value="">Gesamtes {active.label}-Schema</option>
              {subtypesList.map(subtype => <option key={subtype.id} value={subtype.name}>Nur Subtyp: {subtype.label?.de || subtype.name}</option>)}
            </select>
          </div>}
          <p style={{ fontSize: 13, marginBottom: 16 }}>
            {summary === null ? 'Prüfe Felddefinitionen…' : `${summary} Felddefinitionen werden ausgeblendet.`}
          </p>
          <div className="field">
            <div className="lbl">Zur Bestätigung <code>{expectedConfirmation}</code> eingeben</div>
            <input className="fld" value={confirmation} onChange={e => setConfirmation(e.target.value)} autoComplete="off" />
          </div>
          {error && <div style={{ fontSize: 12, color: '#b91c1c', marginBottom: 8 }}>{error}</div>}
          {success && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{success}</div>}
          <button className="btn dn" onClick={handleReset} disabled={resetting || summary === 0 || confirmation !== expectedConfirmation}>
            {resetting ? 'Setze zurück…' : `${selectedSubtype ? `${selectedSubtype.label?.de || selectedSubtype.name}-Subschema` : `${active.label}-Schema`} zurücksetzen`}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Facetten section
// ---------------------------------------------------------------------------

// Relation-derived facets, computed for every record type from `relations`
// rows (not backed by a FieldDefinition). Toggled per type, same storage
// mechanism as inherited_* facets: portal_config.facet_fields[type].
const RELATED_FACET_DEFS = [
  { name: 'related_entities', label: 'Personen/Organisationen' },
  { name: 'related_places', label: 'Orte' },
  { name: 'related_occurrences', label: 'Werke/Ereignisse (Occurrences)' },
  { name: 'related_collections', label: 'Sammlungen' },
] as const
const RELATED_FACET_NAMES: readonly string[] = RELATED_FACET_DEFS.map(f => f.name)

function SectionFacetten({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const [activeType, setActiveType] = useState<string>('object')
  const [fieldsByType, setFieldsByType] = useState<Record<string, FieldDefinition[]>>({})
  const [loadingFields, setLoadingFields] = useState(true)
  const [systemFacets, setSystemFacets] = useState<string[]>(
    () => config.facet_fields?._system ?? ['record_type', 'status']
  )
  const [facetSort, setFacetSort] = useState<'count' | 'alpha'>(config.facet_sort ?? 'count')
  const [facetInitialCount, setFacetInitialCount] = useState(config.facet_initial_count ?? 10)
  const [facetFields, setFacetFields] = useState<Record<string, string[]>>(
    () => {
      const base = config.facet_fields ?? {}
      return Object.fromEntries(RECORD_TYPES.map(({ key }) => [key, base[key] ?? []]))
    }
  )
  const [subtitleFields, setSubtitleFields] = useState<Record<string, string[]>>(
    () => {
      const base = config.subtitle_fields ?? {}
      return Object.fromEntries(RECORD_TYPES.map(({ key }) => [key, base[key] ?? ['record_type', 'status']]))
    }
  )
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoadingFields(true)
    Promise.all(
      RECORD_TYPES.map(({ key }) =>
        schema.list(key).then(fields => [key, fields] as [string, FieldDefinition[]])
      )
    ).then(entries => {
      const byType = Object.fromEntries(entries)
      setFieldsByType(byType)
      setFacetFields(() => {
        const base = config.facet_fields ?? {}
        return Object.fromEntries(RECORD_TYPES.map(({ key }) => {
          const direct = (byType[key] ?? []).filter(f => f.is_facet && f.show_in_detail).map(f => f.name)
          const inherited = (base[key] ?? []).filter(name => name.startsWith('inherited_') || RELATED_FACET_NAMES.includes(name))
          return [key, [...direct, ...inherited]]
        }))
      })
    }).catch(e => setError((e as Error).message))
      .finally(() => setLoadingFields(false))
  }, [])

  function toggle(type: string, name: string) {
    setFacetFields(prev => {
      const cur = prev[type] ?? []
      return { ...prev, [type]: cur.includes(name) ? cur.filter(f => f !== name) : [...cur, name] }
    })
  }

  function toggleSystemFacet(name: string) {
    setSystemFacets(prev => prev.includes(name) ? prev.filter(f => f !== name) : [...prev, name])
  }

  function toggleSubtitle(type: string, name: string) {
    setSubtitleFields(prev => {
      const cur = prev[type] ?? []
      return { ...prev, [type]: cur.includes(name) ? cur.filter(f => f !== name) : [...cur, name] }
    })
  }

  function inheritedFacetFieldsFor(type: string) {
    return (fieldsByType[type] ?? [])
      .filter(f => f.field_type === 'relation')
      .flatMap(relation => {
        const targetType = relation.settings?.target_type as string | undefined
        const inherited = relation.settings?.inherited_fields as string[] | undefined
        if (!targetType || !inherited?.length) return []
        const targetLabel = RECORD_TYPES.find(t => t.key === targetType)?.label ?? targetType
        return inherited.map(name => {
          const targetField = (fieldsByType[targetType] ?? []).find(field => field.name === name)
          const label = targetField?.label?.de || targetField?.label?.en || name
          return { name: `inherited_${targetType}_${name}`, label: `${targetLabel}: ${label}` }
        })
      })
  }

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      // Direct facets are driven by FieldDefinition.is_facet (the schema is the
      // source of truth). Index docs carry facet_all_* for every public field,
      // so toggling is_facet takes effect immediately — no reindex needed.
      // Inherited facets (from relation settings) have no FieldDefinition row,
      // so they are still stored in portal_config.facet_fields.
      const schemaUpdates: Promise<unknown>[] = []
      const inheritedToSave: Record<string, string[]> = { _system: systemFacets }
      const subtitleToSave: Record<string, string[]> = {}

      for (const { key } of RECORD_TYPES) {
        const selected = facetFields[key] ?? []
        inheritedToSave[key] = selected.filter(name => name.startsWith('inherited_') || RELATED_FACET_NAMES.includes(name))

        for (const f of fieldsByType[key] ?? []) {
          const shouldBeFacet = selected.includes(f.name)
          if (f.is_facet !== shouldBeFacet) {
            const { id, ...payload } = f
            delete payload.children
            schemaUpdates.push(schema.update(id, { ...payload, is_facet: shouldBeFacet }))
          }
        }

        // Subtitle fields may only reference the system pseudo-fields (record_type,
        // status, idno — always resolvable, idno has no FieldDefinition/facet) or a
        // field that is (about to be) enabled as a facet — those are the only other
        // ones with a resolvable display value in the search index. Fixed canonical
        // order regardless of selection order in the UI.
        const chosen = new Set(subtitleFields[key] ?? [])
        const availableNames = [
          ...(fieldsByType[key] ?? []).filter(f => selected.includes(f.name)).map(f => f.name),
          ...inheritedFacetFieldsFor(key).filter(f => selected.includes(f.name)).map(f => f.name),
        ]
        subtitleToSave[key] = [
          ...(chosen.has('record_type') ? ['record_type'] : []),
          ...(chosen.has('status') ? ['status'] : []),
          ...(chosen.has('idno') ? ['idno'] : []),
          ...availableNames.filter(name => chosen.has(name)),
        ]
      }

      if (schemaUpdates.length > 0) {
        await Promise.all(schemaUpdates)
        setFieldsByType(prev => {
          const next = { ...prev }
          for (const { key } of RECORD_TYPES) {
            const selected = facetFields[key] ?? []
            next[key] = (prev[key] ?? []).map(f => ({
              ...f,
              is_facet: selected.includes(f.name),
            }))
          }
          return next
        })
      }

      const portalConfig = await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({
          facet_fields: inheritedToSave,
          subtitle_fields: subtitleToSave,
          facet_sort: facetSort,
          facet_initial_count: facetInitialCount,
        }),
      })

      onSaved(portalConfig)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  const fields = (fieldsByType[activeType] ?? []).filter(f => f.show_in_detail)
  const selected = facetFields[activeType] ?? []
  const inheritedFacetFields = inheritedFacetFieldsFor(activeType)
  const subtitleSelected = subtitleFields[activeType] ?? []

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        Lege globale Standardfacetten und zusätzliche Filter pro Datensatztyp fest.
      </p>

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>Standardfacetten</h4>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="bd">
          {[
            { name: 'record_type', label: 'Typ' },
            { name: 'status', label: 'Status' },
          ].map(f => (
            <label key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                className="ck"
                checked={systemFacets.includes(f.name)}
                onChange={() => toggleSystemFacet(f.name)}
              />
              <span style={{ flex: 1 }}>{f.label}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
            </label>
          ))}
        </div>
      </div>

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>Anzeige</h4>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="bd" style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
            Sortierung der Facettenwerte
            <select className="fld" value={facetSort} onChange={e => setFacetSort(e.target.value as 'count' | 'alpha')}>
              <option value="count">Nach Trefferanzahl</option>
              <option value="alpha">Alphabetisch</option>
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
            Anfangs sichtbare Werte
            <input
              className="fld mono"
              type="number"
              min={1}
              max={100}
              value={facetInitialCount}
              onChange={e => setFacetInitialCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
              style={{ width: 80 }}
            />
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid var(--border-s)' }}>
        {RECORD_TYPES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveType(key)}
            style={{
              padding: '7px 14px', fontSize: 13, border: 'none', background: 'none', cursor: 'pointer',
              borderBottom: activeType === key ? '2px solid var(--accent)' : '2px solid transparent',
              color: activeType === key ? 'var(--accent)' : 'var(--fg-2)',
              fontWeight: activeType === key ? 600 : 400,
              marginBottom: -1,
            }}
          >
            {label}
            {(facetFields[key]?.length ?? 0) > 0 && (
              <span style={{ marginLeft: 6, fontSize: 10, background: 'var(--accent)', color: '#fff', borderRadius: 10, padding: '1px 5px' }}>
                {facetFields[key].length}
              </span>
            )}
          </button>
        ))}
      </div>

      {loadingFields ? (
        <div className="empty">Lade Felder…</div>
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="bd">
            {fields.length === 0 && inheritedFacetFields.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>Keine Felder für diesen Typ definiert.</div>
            )}
            {fields.map(f => (
              <label key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
                <input
                  type="checkbox"
                  className="ck"
                  checked={selected.includes(f.name)}
                  onChange={() => toggle(activeType, f.name)}
                />
                <span style={{ flex: 1 }}>{f.label?.de || f.label?.en || f.name}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
              </label>
            ))}
            {inheritedFacetFields.length > 0 && (
              <>
                <div style={{ borderTop: '1px solid var(--border-s)', margin: '10px 0 4px', paddingTop: 10, fontSize: 12, color: 'var(--fg-3)' }}>
                  Felder verknüpfter Datensätze
                </div>
                {inheritedFacetFields.map(f => (
                  <label key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
                    <input
                      type="checkbox"
                      className="ck"
                      checked={selected.includes(f.name)}
                      onChange={() => toggle(activeType, f.name)}
                    />
                    <span style={{ flex: 1 }}>{f.label}</span>
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
                  </label>
                ))}
              </>
            )}
            <div style={{ borderTop: '1px solid var(--border-s)', margin: '10px 0 4px', paddingTop: 10, fontSize: 12, color: 'var(--fg-3)' }}>
              Verknüpfte Datensätze (automatische Relations-Facetten)
            </div>
            {RELATED_FACET_DEFS.map(f => (
              <label key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
                <input
                  type="checkbox"
                  className="ck"
                  checked={selected.includes(f.name)}
                  onChange={() => toggle(activeType, f.name)}
                />
                <span style={{ flex: 1 }}>{f.label}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '20px 0 6px' }}>Ergebnis-Untertitel</h4>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
        Wähle, was in der Trefferliste des Portals unter dem Titel angezeigt wird (z. B. „Objekt · public“).
        Nur Felder, die oben auch als Filter aktiviert sind, stehen hier zur Auswahl.
      </p>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="bd">
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
            <input
              type="checkbox"
              className="ck"
              checked={subtitleSelected.includes('record_type')}
              onChange={() => toggleSubtitle(activeType, 'record_type')}
            />
            <span style={{ flex: 1 }}>Typ</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>record_type</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
            <input
              type="checkbox"
              className="ck"
              checked={subtitleSelected.includes('status')}
              onChange={() => toggleSubtitle(activeType, 'status')}
            />
            <span style={{ flex: 1 }}>Status</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>status</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
            <input
              type="checkbox"
              className="ck"
              checked={subtitleSelected.includes('idno')}
              onChange={() => toggleSubtitle(activeType, 'idno')}
            />
            <span style={{ flex: 1 }}>ID-Nummer</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>idno</span>
          </label>
          {(() => {
            const options = [
              ...fields.filter(f => selected.includes(f.name)).map(f => ({ name: f.name, label: f.label?.de || f.label?.en || f.name })),
              ...inheritedFacetFields.filter(f => selected.includes(f.name)),
            ]
            return options.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>
                Keine weiteren Felder — aktiviere oben zusätzliche Felder als Filter, um sie hier auswählen zu können.
              </div>
            ) : options.map(f => (
              <label key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
                <input
                  type="checkbox"
                  className="ck"
                  checked={subtitleSelected.includes(f.name)}
                  onChange={() => toggleSubtitle(activeType, f.name)}
                />
                <span style={{ flex: 1 }}>{f.label}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
              </label>
            ))
          })()}
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>Gespeichert.</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Suche section
// ---------------------------------------------------------------------------

type IndexHealthEntry = { db: number; es: number; delta: number }
type IndexHealth = { types: Record<string, IndexHealthEntry> }

function IndexHealthWidget() {
  const [health, setHealth] = useState<IndexHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [cfg, setCfg] = useState<Pick<AdminConfigRead, 'reconciliation_enabled' | 'reconciliation_threshold' | 'reconciliation_id_diff_enabled'> | null>(null)
  const [cfgSaving, setCfgSaving] = useState(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      const data = await req<IndexHealth>(`${BASE}/v1/admin/index-health`)
      setHealth(data)
    } catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  async function loadCfg() {
    try {
      const c = await adminConfig.get()
      setCfg({
        reconciliation_enabled: c.reconciliation_enabled,
        reconciliation_threshold: c.reconciliation_threshold,
        reconciliation_id_diff_enabled: c.reconciliation_id_diff_enabled,
      })
    } catch { /* ignore — widget still shows counts without config controls */ }
  }

  useEffect(() => { load(); loadCfg() }, [])

  async function saveCfg(patch: Partial<AdminConfigRead>) {
    if (!cfg) return
    const next = { ...cfg, ...patch }
    setCfg(next)
    setCfgSaving(true)
    try {
      await adminConfig.update(patch)
    } catch (e) { setMsg(`Fehler beim Speichern: ${(e as Error).message}`) }
    finally { setCfgSaving(false) }
  }

  async function handleReconcile(mode: 'count' | 'id_diff') {
    setRunning(mode); setMsg(null)
    try {
      await req(`${BASE}/v1/admin/index-health/reconcile?mode=${mode}`, { method: 'POST' })
      setMsg('Abgleich gestartet — läuft im Hintergrund. Aktualisieren Sie die Seite in Kürze, um das Ergebnis zu sehen.')
      setTimeout(() => setMsg(null), 8000)
    } catch (e) { setMsg(`Fehler: ${(e as Error).message}`) }
    finally { setRunning(null) }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="hd">Index-Status</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          Vergleich der Datensatzanzahl zwischen Datenbank und Suchindex (#214). Abweichungen werden
          täglich automatisch geprüft und ab dem konfigurierten Schwellenwert nachindiziert.
        </p>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 10 }}>{error}</div>}
        {msg && (
          <div style={{ fontSize: 12, color: msg.startsWith('Fehler') ? '#dc2626' : '#166534', marginBottom: 10 }}>
            {msg}
          </div>
        )}
        {loading && <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>Lädt…</p>}
        {!loading && health && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginBottom: 12 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '4px 8px' }}>Typ</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>DB</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>ES</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Abweichung</th>
              </tr>
            </thead>
            <tbody>
              {RECORD_TYPES.map(({ key, label }) => {
                const entry = health.types[key]
                if (!entry) return null
                const ok = entry.delta === 0
                return (
                  <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '4px 8px' }}>{label}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', fontFamily: 'monospace' }}>{entry.db}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', fontFamily: 'monospace' }}>{entry.es}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', fontFamily: 'monospace', color: ok ? '#166534' : '#dc2626' }}>
                      {ok ? '✓ OK' : `⚠ ${entry.delta > 0 ? '+' : ''}${entry.delta}`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        <div style={{ display: 'flex', gap: 8, marginBottom: cfg ? 16 : 0 }}>
          <button className="btn sm gh" onClick={load} disabled={loading}>Aktualisieren</button>
          <button className="btn sm gh" onClick={() => handleReconcile('count')} disabled={running !== null}>
            {running === 'count' ? 'Läuft…' : 'Zählung prüfen'}
          </button>
          <button className="btn sm pri" onClick={() => handleReconcile('id_diff')} disabled={running !== null}>
            {running === 'id_diff' ? 'Läuft…' : 'ID-Diff ausführen'}
          </button>
        </div>
        {cfg && (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <div className="lbl" style={{ marginBottom: 8 }}>Automatischer Abgleich (Celery Beat)</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={cfg.reconciliation_enabled}
                disabled={cfgSaving}
                onChange={e => saveCfg({ reconciliation_enabled: e.target.checked })}
              />
              Tägliche Zählungs-Prüfung aktiv (3 Uhr)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={cfg.reconciliation_id_diff_enabled}
                disabled={cfgSaving}
                onChange={e => saveCfg({ reconciliation_id_diff_enabled: e.target.checked })}
              />
              Wöchentlicher ID-Diff aktiv (sonntags, 4 Uhr)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              Schwellenwert für automatischen ID-Diff (Abweichung)
              <input
                type="number"
                min={0}
                className="fld mono"
                style={{ width: 80 }}
                value={cfg.reconciliation_threshold}
                disabled={cfgSaving}
                onChange={e => saveCfg({ reconciliation_threshold: Number(e.target.value) })}
              />
            </label>
          </div>
        )}
      </div>
    </div>
  )
}

function SectionSuche() {
  const [reindexing, setReindexing] = useState<string | null>(null)
  const [reindexMsg, setReindexMsg] = useState<string | null>(null)

  async function handleReindex(type?: string) {
    const key = type ?? 'all'
    if (!window.confirm(type ? `Alle ${type}-Datensätze neu indizieren?` : 'Alle Datensätze vollständig neu indizieren?')) return
    setReindexing(key); setReindexMsg(null)
    try {
      const url = type ? `${BASE}/v1/search/reindex/${type}` : `${BASE}/v1/search/reindex`
      await req(url, { method: 'POST' })
      setReindexMsg('Reindizierung gestartet — läuft im Hintergrund.')
      setTimeout(() => setReindexMsg(null), 5000)
    } catch (e) { setReindexMsg(`Fehler: ${(e as Error).message}`) }
    finally { setReindexing(null) }
  }

  return (
    <>
    <IndexHealthWidget />
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
            <button key={t} className="btn sm gh" onClick={() => handleReindex(t)} disabled={reindexing !== null}>
              {reindexing === t ? 'Läuft…' : `${t} reindizieren`}
            </button>
          ))}
          <button className="btn sm pri" onClick={() => handleReindex()} disabled={reindexing !== null} style={{ marginLeft: 8 }}>
            {reindexing === 'all' ? 'Läuft…' : 'Alles reindizieren'}
          </button>
        </div>
      </div>
    </div>
    </>
  )
}

function SectionSparql({
  status,
  onRefresh,
  onNavigate,
}: {
  status: SparqlStatus
  onRefresh: () => void
  onNavigate?: (route: string) => void
}) {
  const { t } = useTranslation('screenSettings')
  const [rebuilding, setRebuilding] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const fullEndpoint = `${origin}${status.endpoint_url}`

  async function handleRebuild() {
    if (!window.confirm(t('sparql.rebuildConfirm'))) return
    setRebuilding(true)
    setMsg(null)
    try {
      await sparql.rebuild()
      setMsg({ type: 'ok', text: t('sparql.rebuildSuccess') })
      setTimeout(() => {
        onRefresh()
      }, 3000)
    } catch (e) {
      setMsg({ type: 'err', text: `${t('sparql.rebuildError')}: ${(e as Error).message}` })
    } finally {
      setRebuilding(false)
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(fullEndpoint).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="hd" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>{t('sparql.title')}</span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            padding: '2px 8px',
            borderRadius: 12,
            fontWeight: 500,
            background: status.reachable ? '#f0fdf4' : '#fef2f2',
            color: status.reachable ? '#166534' : '#991b1b',
            border: `1px solid ${status.reachable ? '#bbf7d0' : '#fecaca'}`,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: status.reachable ? '#16a34a' : '#dc2626',
            }}
          />
          {status.reachable ? t('sparql.connected') : t('sparql.unreachable')}
        </span>
      </div>

      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
          {t('sparql.description')}
        </p>

        {!status.reachable && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 6,
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#991b1b',
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {t('sparql.unreachableHelp')}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 20 }}>
          <div style={{ padding: '10px 12px', background: 'var(--bg-2, #f9fafb)', borderRadius: 6, border: '1px solid var(--border-subtle, #e5e7eb)' }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {t('sparql.triplesCount')}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>
              {status.triples_count != null ? status.triples_count.toLocaleString() : '—'}
            </div>
          </div>

          <div style={{ padding: '10px 12px', background: 'var(--bg-2, #f9fafb)', borderRadius: 6, border: '1px solid var(--border-subtle, #e5e7eb)' }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {t('sparql.authModel')}
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6 }}>
              {status.require_auth ? t('sparql.authProtected') : t('sparql.authPublic')}
            </div>
          </div>

          <div style={{ padding: '10px 12px', background: 'var(--bg-2, #f9fafb)', borderRadius: 6, border: '1px solid var(--border-subtle, #e5e7eb)' }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {t('sparql.queryTimeout')}
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6 }}>
              {status.query_timeout}s
            </div>
          </div>
        </div>

        <div className="field" style={{ marginBottom: 20 }}>
          <div className="lbl">{t('sparql.endpointUrl')}</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="text"
              readOnly
              className="fld mono"
              value={fullEndpoint}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn sm gh"
              onClick={handleCopy}
              style={{ minWidth: 80 }}
            >
              {copied ? t('sparql.copied') : t('sparql.copy')}
            </button>
          </div>
          {onNavigate && (
            <div style={{ marginTop: 10 }}>
              <button
                type="button"
                className="btn sm"
                onClick={() => onNavigate('sparql')}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <span>{t('sparql.openBuilder')}</span>
              </button>
            </div>
          )}
        </div>

        <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle, #e5e7eb)', margin: '20px 0' }} />

        <div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{t('sparql.rebuildTitle')}</div>
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
            {t('sparql.rebuildDescription')}
          </p>

          {msg && (
            <div
              style={{
                fontSize: 12,
                color: msg.type === 'err' ? '#dc2626' : '#166534',
                marginBottom: 10,
              }}
            >
              {msg.text}
            </div>
          )}

          <button
            type="button"
            className="btn sm pri"
            onClick={handleRebuild}
            disabled={rebuilding || !status.reachable}
          >
            {rebuilding ? t('sparql.rebuilding') : t('sparql.rebuildBtn')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ID-Schemas section
// ---------------------------------------------------------------------------

function SectionIdnoSchemas() {
  const [schemas, setSchemas] = useState<Record<string, string>>({})
  const [patterns, setPatterns] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    adminConfig.get()
      .then(cfg => {
        setSchemas(cfg.idno_schemas ?? {})
        setPatterns(cfg.idno_patterns ?? {})
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      await adminConfig.update({ idno_schemas: schemas, idno_patterns: patterns })
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  function setSchema(type: string, value: string) {
    setSchemas(prev => ({ ...prev, [type]: value }))
  }

  function setPattern(type: string, value: string) {
    setPatterns(prev => ({ ...prev, [type]: value }))
  }

  if (loading) return <div className="empty">Lade…</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        Pro Primärtyp kann ein ID-Schema mit Platzhaltern definiert werden.
        Beim Anlegen eines neuen Datensatzes wird die nächste ID automatisch vorgeschlagen.
      </p>

      {RECORD_TYPES.map(({ key, label }) => (
        <div className="card" key={key} style={{ marginBottom: 16 }}>
          <div className="hd">{label}</div>
          <div className="bd">
            <div className="field">
              <div className="lbl">Schema <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
              <input
                className="fld mono"
                value={schemas[key] ?? ''}
                onChange={e => setSchema(key, e.target.value)}
                placeholder="z.B. ulb_x_{counter:05d}"
              />
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                Platzhalter: {'{counter}'} — laufende Nummer | {'{counter:05d}'} — mit Nullen aufgefüllt | {'{year}'} — aktuelles Jahr | {'{type}'} — Typ-Kürzel (obj/ent/pla/occ/pro)
              </div>
            </div>
            <div className="field">
              <div className="lbl">Validierungs-Muster (Regex) <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
              <input
                className="fld mono"
                value={patterns[key] ?? ''}
                onChange={e => setPattern(key, e.target.value)}
                placeholder="z.B. ^ulb_x_\\d{5}$"
              />
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                Wenn gesetzt, werden manuell eingegebene IDs gegen dieses Muster geprüft.
              </div>
            </div>
          </div>
        </div>
      ))}

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>Gespeichert.</span>}
      </div>
    </div>
  )
}

function SectionAI() {
  const [cfg, setCfg] = useState<AdminConfigRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [secretBusy, setSecretBusy] = useState(false)
  const [checkBusy, setCheckBusy] = useState(false)
  const [checkResult, setCheckResult] = useState<{ ok: boolean; message: string } | null>(null)

  useEffect(() => {
    setLoading(true)
    adminConfig.get()
      .then(setCfg)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function set<K extends keyof AdminConfigRead>(key: K, value: AdminConfigRead[K]) {
    if (!cfg) return
    setCfg({ ...cfg, [key]: value })
  }

  async function handleSave() {
    if (!cfg) return
    setSaving(true); setSaved(false); setError(null)
    try {
      const updated = await adminConfig.update({
        ai_enabled: cfg.ai_enabled,
        ai_base_url: cfg.ai_base_url,
        ai_model: cfg.ai_model,
        ai_max_input_tokens: cfg.ai_max_input_tokens,
        ai_max_output_tokens: cfg.ai_max_output_tokens,
        ai_daily_user_token_limit: cfg.ai_daily_user_token_limit,
        ai_monthly_global_token_limit: cfg.ai_monthly_global_token_limit,
      })
      setCfg(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  async function checkAi() {
    setCheckBusy(true); setCheckResult(null); setError(null)
    try {
      const res = await adminConfig.checkAi()
      setCheckResult(res)
    } catch (e) {
      setCheckResult({ ok: false, message: (e as Error).message })
    } finally { setCheckBusy(false) }
  }

  async function saveSecret() {
    if (!apiKey.trim() || !cfg) return
    setSecretBusy(true); setError(null)
    try {
      const secret = await adminConfig.setAiSecret(apiKey.trim())
      setCfg({ ...cfg, ai_secret: secret })
      setApiKey('')
    } catch (e) { setError((e as Error).message) }
    finally { setSecretBusy(false) }
  }

  async function deleteSecret() {
    if (!cfg || !window.confirm('API-Key wirklich löschen?')) return
    setSecretBusy(true); setError(null)
    try {
      const secret = await adminConfig.deleteAiSecret()
      setCfg({ ...cfg, ai_secret: secret })
    } catch (e) { setError((e as Error).message) }
    finally { setSecretBusy(false) }
  }

  if (loading) return <div className="empty">Lade…</div>
  if (!cfg) return <div className="empty">Keine Konfiguration geladen.</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        Globale KI-Anbindung für feldbezogene Vorschläge. API-Key wird verschlüsselt in Datenbank gespeichert und nie im Klartext zurückgegeben.
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">LLM-Anbindung</div>
        <div className="bd">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 12 }}>
            <input type="checkbox" className="ck" checked={cfg.ai_enabled} onChange={e => set('ai_enabled', e.target.checked)} />
            KI-Unterstützung aktiv
          </label>
          <div className="field">
            <div className="lbl">Base URL</div>
            <input className="fld mono" value={cfg.ai_base_url ?? ''} onChange={e => set('ai_base_url', e.target.value)} placeholder="https://api.openai.com/v1" />
            <div className="sub">Ohne <code>/chat/completions</code> am Ende — wird automatisch angehängt. Für OpenRouter z.B. <code>https://openrouter.ai/api/v1</code>.</div>
          </div>
          <div className="field">
            <div className="lbl">Modell</div>
            <input className="fld mono" value={cfg.ai_model ?? ''} onChange={e => set('ai_model', e.target.value)} placeholder="gpt-4.1-mini" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn gh" onClick={checkAi} disabled={checkBusy}>
              {checkBusy ? 'Prüft…' : 'Verbindung testen'}
            </button>
            {checkResult && (
              <span style={{ fontSize: 12, color: checkResult.ok ? '#166534' : '#b91c1c' }}>
                {checkResult.ok ? `✓ Antwort: ${checkResult.message}` : `✗ ${checkResult.message}`}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">API-Key</div>
        <div className="bd">
          <div style={{ fontSize: 12, color: cfg.ai_secret.has_key ? '#166534' : 'var(--fg-3)', marginBottom: 10 }}>
            {cfg.ai_secret.has_key ? `Key gesetzt${cfg.ai_secret.updated_at ? ` · aktualisiert ${new Date(cfg.ai_secret.updated_at).toLocaleString()}` : ''}` : 'Noch kein Key gespeichert'}
          </div>
          <div className="field">
            <div className="lbl">Neuen API-Key setzen / ersetzen</div>
            <input className="fld mono" type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn pri" onClick={saveSecret} disabled={secretBusy || !apiKey.trim()}>
              {secretBusy ? 'Speichert…' : 'Key speichern'}
            </button>
            {cfg.ai_secret.has_key && (
              <button className="btn dn" onClick={deleteSecret} disabled={secretBusy}>
                Löschen
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">Token-Limits</div>
        <div className="bd">
          <div className="fg-2">
            <div className="field">
              <div className="lbl">Max. Input-Tokens pro Request</div>
              <input className="fld mono" type="number" min={1} value={cfg.ai_max_input_tokens} onChange={e => set('ai_max_input_tokens', Number(e.target.value))} />
            </div>
            <div className="field">
              <div className="lbl">Max. Output-Tokens pro Request</div>
              <input className="fld mono" type="number" min={1} value={cfg.ai_max_output_tokens} onChange={e => set('ai_max_output_tokens', Number(e.target.value))} />
            </div>
          </div>
          <div className="fg-2">
            <div className="field">
              <div className="lbl">Tageslimit pro Benutzer</div>
              <input className="fld mono" type="number" min={1} value={cfg.ai_daily_user_token_limit} onChange={e => set('ai_daily_user_token_limit', Number(e.target.value))} />
              <div className="sub">Ihr Verbrauch heute: {cfg.ai_usage.daily_user_tokens.toLocaleString()} Tokens</div>
            </div>
            <div className="field">
              <div className="lbl">Monatslimit global</div>
              <input className="fld mono" type="number" min={1} value={cfg.ai_monthly_global_token_limit} onChange={e => set('ai_monthly_global_token_limit', Number(e.target.value))} />
              <div className="sub">Globaler Verbrauch diesen Monat: {cfg.ai_usage.monthly_global_tokens.toLocaleString()} Tokens</div>
            </div>
          </div>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>Gespeichert.</span>}
      </div>
    </div>
  )
}

function SectionMediaRights() {
  const [cfg, setCfg] = useState<AdminConfigRead | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { adminConfig.get().then(setCfg).catch((e: Error) => setError(e.message)) }, [])

  async function save() {
    if (!cfg) return
    setSaving(true); setSaved(false); setError(null)
    try {
      setCfg(await adminConfig.update({
        media_default_license_uri: cfg.media_default_license_uri,
        media_default_rights_holder: cfg.media_default_rights_holder,
      }))
      setSaved(true)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  if (!cfg) return <div className="empty">{error ?? 'Lade…'}</div>
  const holder = cfg.media_default_rights_holder ?? { name: '', uri: '' }
  return <div>
    <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>Diese Angaben werden beim Upload auf jede neue Mediendatei kopiert. Spätere Änderungen gelten nur für neue Uploads.</p>
    <div className="field"><div className="lbl">Standardlizenz</div><input className="fld" value={cfg.media_default_license_uri ?? ''} placeholder="Lizenz-URI" onChange={e => setCfg({ ...cfg, media_default_license_uri: e.target.value || null })} /></div>
    <div className="field"><div className="lbl">Standard-Rechteinhaber</div><input className="fld" value={holder.name} placeholder="Name" onChange={e => setCfg({ ...cfg, media_default_rights_holder: { ...holder, name: e.target.value } })} /><input className="fld" style={{ marginTop: 4 }} value={holder.uri ?? ''} placeholder="URI (optional)" onChange={e => setCfg({ ...cfg, media_default_rights_holder: { ...holder, uri: e.target.value || undefined } })} /></div>
    {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{error}</div>}
    <button className="btn pri" onClick={save} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>{saved && <span style={{ marginLeft: 8, fontSize: 12, color: '#166534' }}>Gespeichert.</span>}
  </div>
}

// ---------------------------------------------------------------------------
// Authority sources section
// ---------------------------------------------------------------------------

function SectionAuthoritySources() {
  const [sources, setSources] = useState<AuthoritySource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean, message: string }>>({})

  useEffect(() => {
    authority.list().then(setSources).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  async function toggle(source: AuthoritySource) {
    setPending(source.id); setError(null)
    try {
      const updated = await authority.setEnabled(source.id, !source.is_enabled)
      setSources(prev => prev.map(s => s.id === updated.id ? updated : s))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(null)
    }
  }

  async function test(source: AuthoritySource) {
    setTesting(source.id)
    const testRequest = AUTHORITY_TESTS[source.id] ?? { query: 'test', href: '#' }
    try {
      const hits = await authority.search(source.id, testRequest.query, 1)
      setTestResults(prev => ({ ...prev, [source.id]: { ok: true, message: `Erreichbar — ${hits.length} Treffer für Testanfrage.` } }))
    } catch (e) {
      setTestResults(prev => ({ ...prev, [source.id]: { ok: false, message: (e as Error).message } }))
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <div className="empty">Lade…</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        Normdatenquellen für Authority-Felder und Vokabular-Term-Lookups. Deaktivierte Quellen stehen bei neuen
        Verknüpfungen nicht mehr zur Auswahl; bereits gespeicherte Verknüpfungen bleiben unverändert erhalten.
      </p>
      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      {sources.map(source => {
        const result = testResults[source.id]
        const testRequest = AUTHORITY_TESTS[source.id] ?? { query: 'test', href: '#' }
        return (
          <div className="card" key={source.id} style={{ marginBottom: 12 }}>
            <div className="hd" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{source.label}</span>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 400 }}>
                <input type="checkbox" checked={source.is_enabled} disabled={pending === source.id} onChange={() => toggle(source)} />
                {source.is_enabled ? 'Aktiviert' : 'Deaktiviert'}
              </label>
            </div>
            <div className="bd">
              <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>ID: <span className="mono">{source.id}</span></div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>
                Testanfrage: <a href={testRequest.href} target="_blank" rel="noreferrer">{testRequest.query}</a>
              </div>
              <button className="btn sm gh" onClick={() => test(source)} disabled={!source.is_enabled || testing === source.id}>
                {testing === source.id ? 'Prüft…' : 'Verbindung testen'}
              </button>
              {!source.is_enabled && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--fg-3)' }}>Quelle deaktiviert — keine Anfragen möglich.</span>}
              {source.is_enabled && result && (
                <span style={{ marginLeft: 8, fontSize: 12, color: result.ok ? '#166534' : '#dc2626' }}>
                  {result.message}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function SectionUeber({ isAdmin, onNavigate }: { isAdmin: boolean; onNavigate: (route: string) => void }) {
  const { t } = useTranslation('screenSettings')
  return (
    <div>
      <div className="card" style={{ padding: 24 }}>
        <h2 style={{ marginTop: 0 }}>{t('ueber.title')}</h2>
        <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('ueber.tagline')}</p>
        <p style={{ fontSize: 13 }}>
          <strong>{t('ueber.licenseLabel')}:</strong> {t('ueber.licenseText')}
        </p>
        <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('ueber.copyright')}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 16, fontSize: 13 }}>
          <a href="https://github.com/karkraeg/Katalon" target="_blank" rel="noreferrer">{t('ueber.links.repo')}</a>
          <a href="https://github.com/karkraeg/Katalon/blob/main/LICENSE" target="_blank" rel="noreferrer">{t('ueber.links.license')}</a>
          <a href="https://katalon-collections.github.io/katalon-docs/" target="_blank" rel="noreferrer">{t('ueber.links.docs')}</a>
        </div>
        {isAdmin && (
          <div style={{ marginTop: 16 }}>
            <button className="btn sm gh" onClick={() => onNavigate('changelog')}>{t('ueber.links.changelog')}</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

function SectionChangelog() {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminConfig.changelog()
      .then(result => setContent(result.content))
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <div style={{ fontSize: 13, color: '#dc2626' }}>{error}</div>
  if (content === null) return <div className="empty">Lade…</div>
  return <div>
    <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>Änderungen dieser Katalon-Version.</p>
    <pre className="card" style={{ margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', font: 'inherit', lineHeight: 1.5 }}>{content}</pre>
  </div>
}

function SectionLanguages() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminConfig.get()
      .then(cfg => setInput((cfg.supported_languages ?? ['de', 'en']).join(', ')))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function save() {
    const parsed = Array.from(new Set(
      input.split(',').map(s => s.trim().toLowerCase()).filter(Boolean),
    ))
    if (parsed.length === 0) { setError('Mindestens eine Sprache erforderlich.'); return }
    setSaving(true); setError(null); setSaved(false)
    try {
      await adminConfig.update({ supported_languages: parsed })
      setInput(parsed.join(', '))
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  if (loading) return <div className="empty">Lade…</div>
  return (
    <div className="card">
      <div className="hd">Sprachen für Metadaten</div>
      <div className="bd">
        <div className="field">
          <div className="lbl">Unterstützte Sprachen (ISO-639-1-Codes, kommagetrennt)</div>
          <input className="fld mono" value={input} onChange={e => setInput(e.target.value)} placeholder="de, en, fr" />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            Erste Sprache ist die Primärsprache (Fallback). Gilt für Feld-Labels und übersetzbare Feldwerte.
          </div>
        </div>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 8 }}>{error}</div>}
        {saved && <div style={{ fontSize: 13, color: '#166534', marginBottom: 8 }}>Gespeichert.</div>}
        <button className="btn pri" onClick={save} disabled={saving}>{saving ? 'Speichert…' : 'Speichern'}</button>
      </div>
    </div>
  )
}

function SectionPresenceLock() {
  const { t } = useTranslation('screenSettings')
  const [mode, setMode] = useState<'warning' | 'blocking'>('warning')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminConfig.get()
      .then(cfg => setMode(cfg.presence_lock_mode))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function save(next: 'warning' | 'blocking') {
    setMode(next)
    setSaving(true); setError(null); setSaved(false)
    try {
      await adminConfig.update({ presence_lock_mode: next })
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  if (loading) return <div className="empty">Lade…</div>
  return (
    <div className="card">
      <div className="hd">{t('presenceLock.title')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          {t('presenceLock.description')}
        </p>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, marginBottom: 10 }}>
          <input type="radio" name="presence_lock_mode" checked={mode === 'warning'} disabled={saving} onChange={() => save('warning')} style={{ marginTop: 3 }} />
          <span><strong>{t('presenceLock.warningLabel')}</strong> — {t('presenceLock.warningDescription')}</span>
        </label>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
          <input type="radio" name="presence_lock_mode" checked={mode === 'blocking'} disabled={saving} onChange={() => save('blocking')} style={{ marginTop: 3 }} />
          <span><strong>{t('presenceLock.blockingLabel')}</strong> — {t('presenceLock.blockingDescription')}</span>
        </label>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginTop: 10 }}>{error}</div>}
        {saved && <div style={{ fontSize: 13, color: '#166534', marginTop: 10 }}>{t('presenceLock.saved')}</div>}
      </div>
    </div>
  )
}

const NAV: { id: Section; label: string; adminOnly?: boolean; feature?: string }[] = [
  { id: 'profil',   label: 'Profil' },
  { id: 'ueber',    label: 'Über Katalon' },
  { id: 'portal',   label: 'Portal & Institution', adminOnly: true },
  { id: 'facetten', label: 'Facetten', adminOnly: true },
  { id: 'sprachen', label: 'Sprachen', adminOnly: true },
  { id: 'idno',     label: 'ID-Schemas', adminOnly: true },
  { id: 'ki',       label: 'KI', adminOnly: true },
  { id: 'medien',   label: 'Medienrechte', adminOnly: true },
  { id: 'authorities', label: 'Normdatenquellen', adminOnly: true },
  { id: 'sperren',  label: 'Bearbeitungssperre', adminOnly: true },
  { id: 'suche',    label: 'Suche & Indexierung', adminOnly: true },
  { id: 'sparql',   label: 'Linked Data & SPARQL', adminOnly: true },
  { id: 'changelog', label: 'Versionshinweise', adminOnly: true },
]

const SECTION_IDS = NAV.map(n => n.id)

function initialSection(): Section {
  const slash = window.location.hash.indexOf('/')
  const requested = slash === -1 ? null : window.location.hash.slice(slash + 1)
  return (requested && SECTION_IDS.includes(requested as Section)) ? requested as Section : 'profil'
}

export function ScreenSettings({ isAdmin, features, onStartTour, onNavigate }: Props) {
  const [section, setSection] = useState<Section>(initialSection)
  const [config, setConfig] = useState<PortalConfigRead | null>(null)
  const [sparqlStatus, setSparqlStatus] = useState<SparqlStatus | null>(null)
  const [loading, setLoading] = useState(isAdmin)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAdmin) return
    req<PortalConfigRead>(`${BASE}/v1/portal/config`)
      .then(setConfig)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
    sparql.status()
      .then(setSparqlStatus)
      .catch(() => setSparqlStatus({ enabled: false, reachable: false, triples_count: null, endpoint_url: '/sparql', require_auth: true, query_timeout: 30 }))
  }, [isAdmin])

  const navItems = NAV.filter(n => {
    if (n.adminOnly && !isAdmin) return false
    if (n.feature && !features.includes(n.feature)) return false
    if (n.id === 'sparql' && !sparqlStatus?.enabled) return false
    return true
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Einstellungen</h1><div className="sub">Account und Systemkonfiguration</div></div>
      </div>

      <div className="settings-layout">
        {/* Sidebar nav (desktop) */}
        <div className="settings-nav">
          {navItems.map(n => (
            <button key={n.id} className={`panel-it${section === n.id ? ' active' : ''}`} onClick={() => {
              setSection(n.id)
              window.history.replaceState(null, '', `#settings/${n.id}`)
            }}>
              {n.label}
            </button>
          ))}
        </div>

        {/* Section select (mobile) */}
        <div className="settings-select field">
          <label className="lbl" htmlFor="settings-section">Bereich</label>
          <select
            id="settings-section"
            className="fld"
            value={section}
            onChange={e => {
              const next = e.target.value as Section
              setSection(next)
              window.history.replaceState(null, '', `#settings/${next}`)
            }}
          >
            {navItems.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>

        {/* Content */}
        <div className="settings-content">
          {loading && <div className="empty">Lade…</div>}
          {error && <div style={{ fontSize: 13, color: '#dc2626' }}>{error}</div>}
          {!loading && section === 'profil' && <SectionProfil onStartTour={isAdmin ? onStartTour : undefined} />}
          {!loading && section === 'ueber' && <SectionUeber isAdmin={isAdmin} onNavigate={(r) => {
            setSection(r as Section)
            window.history.replaceState(null, '', `#settings/${r}`)
          }} />}
          {!loading && isAdmin && config && section === 'portal' && <SectionPortal config={config} onSaved={setConfig} />}
          {!loading && isAdmin && config && section === 'facetten' && <SectionFacetten config={config} onSaved={setConfig} />}
          {!loading && isAdmin && section === 'sprachen' && <SectionLanguages />}
          {!loading && isAdmin && section === 'idno' && <SectionIdnoSchemas />}
          {!loading && isAdmin && section === 'ki' && <SectionAI />}
          {!loading && isAdmin && section === 'medien' && <SectionMediaRights />}
          {!loading && isAdmin && section === 'authorities' && <SectionAuthoritySources />}
          {!loading && isAdmin && section === 'sperren' && <SectionPresenceLock />}
          {!loading && isAdmin && section === 'suche' && <SectionSuche />}
          {!loading && isAdmin && section === 'sparql' && sparqlStatus?.enabled && (
            <SectionSparql
              status={sparqlStatus}
              onRefresh={() => {
                sparql.status().then(setSparqlStatus).catch(() => {})
              }}
              onNavigate={onNavigate}
            />
          )}
          {!loading && isAdmin && section === 'changelog' && <SectionChangelog />}
          {!loading && isAdmin && section === 'gefahrenbereich' && <SectionDangerZone />}
        </div>
      </div>
    </div>
  )
}
