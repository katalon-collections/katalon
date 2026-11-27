// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { req, BASE, apiKeys, users, schema, subtypes, vocabularies, adminConfig, authority, authorizedFetch, sparql } from '../../api/client'
import type { AdminConfigRead, AuthoritySource, SparqlStatus } from '../../api/client'
import type { ApiKey, ApiKeyCreated, FieldDefinition, HomepageBlock, PortalConfigRead, RecordSubtype, RelationFacet, TerminologyEntry, Vocabulary } from '../../types'
import { FacetOrderList, type FacetOrderItem } from './settings/FacetOrderList'
import { RelationFacetsEditor } from './settings/RelationFacetsEditor'
import { SectionFooterNotice } from './settings/SectionFooterNotice'
import { CollectionPicker } from './settings/CollectionPicker'
import type { TourVariant } from '../tour/Tour'
import { ConfirmModal } from '../ui/ConfirmModal'
import { LabelEditor } from '../ui/LabelEditor'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

interface Props {
  onNavigate?: (route: string) => void
  isAdmin: boolean
  features: string[]
  onStartTour?: (variant: TourVariant) => void
}

type Section = 'profil' | 'portal' | 'fusszeile' | 'startseite' | 'terminologie' | 'facetten' | 'sprachen' | 'suche' | 'sparql' | 'idno' | 'ki' | 'medien' | 'authorities' | 'sperren' | 'papierkorb' | 'gefahrenbereich' | 'ueber'

const RECORD_TYPES = [
  { key: 'object',     labelKey: 'screenSettings:recordTypes.object' },
  { key: 'entity',     labelKey: 'screenSettings:recordTypes.entity' },
  { key: 'place',      labelKey: 'screenSettings:recordTypes.place' },
  { key: 'occurrence', labelKey: 'screenSettings:recordTypes.occurrence' },
  { key: 'procedure',  labelKey: 'screenSettings:recordTypes.procedure' },
  { key: 'collection', labelKey: 'screenSettings:recordTypes.collection' },
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
  const formId = useId()
  const [pwdCurrent, setPwdCurrent] = useState('')
  const [pwdNew, setPwdNew] = useState('')
  const [pwdConfirm, setPwdConfirm] = useState('')
  const [pwdError, setPwdError] = useState<string | null>(null)
  const [pwdSuccess, setPwdSuccess] = useState(false)
  const [sessionsMsg, setSessionsMsg] = useState<{ ok: boolean, text: string } | null>(null)
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
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null)

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

  function handleRevokeOwnKey(keyId: string) {
    setConfirmRevokeId(keyId)
  }

  async function confirmRevokeOwnKey() {
    const keyId = confirmRevokeId!
    try {
      await apiKeys.revokeOwn(keyId)
      setOwnKeys(prev => prev.filter(k => k.id !== keyId))
    } catch (e) { alert((e as Error).message) }
    finally { setConfirmRevokeId(null) }
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

  async function handleLogoutOthers() {
    setSessionsMsg(null)
    try {
      await users.logoutOthers()
      setSessionsMsg({ ok: true, text: t('profil.sessions.success') })
    } catch (e) { setSessionsMsg({ ok: false, text: (e as Error).message }) }
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
            <label className="lbl" htmlFor={`${formId}-email-new`}>{t('profil.email.newLabel')}</label>
            <input id={`${formId}-email-new`} className="fld" type="email" value={emailNew} onChange={e => setEmailNew(e.target.value)} />
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-email-pwd`}>{t('profil.email.currentPasswordLabel')}</label>
            <input id={`${formId}-email-pwd`} className="fld" type="password" value={emailPassword} onChange={e => setEmailPassword(e.target.value)} />
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
            <label className="lbl" htmlFor={`${formId}-pwd-current`}>{t('profil.password.currentLabel')}</label>
            <input id={`${formId}-pwd-current`} className="fld" type="password" value={pwdCurrent} onChange={e => setPwdCurrent(e.target.value)} />
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-pwd-new`}>{t('profil.password.newLabel')}</label>
            <input id={`${formId}-pwd-new`} className="fld" type="password" value={pwdNew} onChange={e => setPwdNew(e.target.value)} />
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-pwd-confirm`}>{t('profil.password.confirmLabel')}</label>
            <input id={`${formId}-pwd-confirm`} className="fld" type="password" value={pwdConfirm} onChange={e => setPwdConfirm(e.target.value)} />
          </div>
          {pwdError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{pwdError}</div>}
          {pwdSuccess && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{t('profil.password.success')}</div>}
          <button className="btn pri" onClick={handleChangePassword}>{t('profil.password.submit')}</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('profil.sessions.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>{t('profil.sessions.intro')}</p>
          {sessionsMsg && <div style={{ fontSize: 12, color: sessionsMsg.ok ? '#166534' : '#dc2626', marginBottom: 8 }}>{sessionsMsg.text}</div>}
          <button className="btn" onClick={handleLogoutOthers}>{t('profil.sessions.submit')}</button>
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
                    <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('de-DE') : '–'}</td>
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
      {confirmRevokeId !== null && (
        <ConfirmModal
          message={t('profil.apiKeys.revokeConfirm')}
          confirmLabel={t('profil.apiKeys.revoke')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={confirmRevokeOwnKey}
          onCancel={() => setConfirmRevokeId(null)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Portal section
// ---------------------------------------------------------------------------

function SectionPortal({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [logoUploading, setLogoUploading] = useState(false)

  const languages = useSupportedLanguages()
  const [siteTitle, setSiteTitle] = useState(config.site_title)
  const [siteSubtitle, setSiteSubtitle] = useState(config.site_subtitle)
  const [heroText, setHeroText] = useState(config.hero_text)
  const [logoUrl, setLogoUrl] = useState(config.logo_url)
  const [placeholderImageUrl, setPlaceholderImageUrl] = useState(config.placeholder_image_url ?? '')
  const [featuredIds, setFeaturedIds] = useState((config.featured_object_ids ?? []).join('\n'))
  const [browseTypes, setBrowseTypes] = useState(config.browse_enabled_types ?? ['object', 'entity', 'place', 'occurrence'])
  const [accentColor, setAccentColor] = useState(config.accent_color)
  const [detailSidebarPosition, setDetailSidebarPosition] = useState(config.detail_sidebar_position ?? 'right')
  const [metaRowLayout, setMetaRowLayout] = useState(config.meta_row_layout ?? 'stacked')
  const [metaLabelUppercase, setMetaLabelUppercase] = useState(config.meta_label_uppercase ?? false)
  const [showIiifManifestLink, setShowIiifManifestLink] = useState(config.show_iiif_manifest_link ?? true)
  const [showUsageStats, setShowUsageStats] = useState(config.show_usage_stats ?? false)
  const [mediaDownloadEnabled, setMediaDownloadEnabled] = useState(config.media_download_enabled ?? false)
  const [headerShowTitle, setHeaderShowTitle] = useState(config.header_show_title ?? true)
  const [heroHideTitle, setHeroHideTitle] = useState(config.hero_hide_title ?? false)
  const { t: tLayout } = useTranslation('portalLayout')
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
          meta_row_layout: metaRowLayout,
          meta_label_uppercase: metaLabelUppercase,
          header_show_title: headerShowTitle,
          hero_hide_title: heroHideTitle,
          show_iiif_manifest_link: showIiifManifestLink,
          show_usage_stats: showUsageStats,
          media_download_enabled: mediaDownloadEnabled,
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
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? t('common.httpError', { status: String(res.status) })) }
      const c: PortalConfigRead = await res.json()
      setLogoUrl(c.logo_url); onSaved(c)
    } catch (e) { setError((e as Error).message) }
    finally { setLogoUploading(false) }
  }

  function handleLangChange(next: string) { setLang(next); localStorage.setItem('katalon_lang', next) }

  const colorFields = [
    { lbl: t('portal.colors.accent'), val: accentColor, set: setAccentColor },
    { lbl: t('portal.colors.headerBg'), val: headerBg, set: setHeaderBg, ph: '#0b1a33' },
    { lbl: t('portal.colors.headerFg'), val: headerFg, set: setHeaderFg, ph: '#ffffff' },
    { lbl: t('portal.colors.pageBg'), val: pageBg, set: setPageBg, ph: '#f4f5f7' },
    { lbl: t('portal.colors.panelBg'), val: panelBg, set: setPanelBg, ph: '#ffffff' },
  ]

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('portal.institution')}</div>
        <div className="bd">
          <div className="fg-2">
            <LabelEditor languages={languages} value={siteTitle} labelPrefix={t('portal.siteTitle')}
              onChange={(lng, val) => setSiteTitle(prev => ({ ...prev, [lng]: val }))} />
          </div>
          <div className="fg-2">
            <LabelEditor languages={languages} value={siteSubtitle} labelPrefix={t('portal.subtitle')}
              onChange={(lng, val) => setSiteSubtitle(prev => ({ ...prev, [lng]: val }))} />
          </div>
          {languages.map(lng => (
            <div className="field" key={lng}><label className="lbl" htmlFor={`${formId}-hero-${lng}`}>{t('portal.heroText', { lang: lng.toUpperCase() })}</label>
              <textarea id={`${formId}-hero-${lng}`} className="fld" rows={3} value={heroText[lng] ?? ''}
                onChange={e => setHeroText(prev => ({ ...prev, [lng]: e.target.value }))}
                style={{ resize: 'vertical', fontFamily: 'inherit' }} /></div>
          ))}
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-logo-url`}>{t('portal.logo')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('common.optional')}</span></label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {logoUrl && <img src={logoUrl} alt="Logo" style={{ height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />}
              <button className="btn gh sm" onClick={() => logoInputRef.current?.click()} disabled={logoUploading}>{logoUploading ? t('portal.logoUploading') : t('portal.logoUpload')}</button>
              {logoUrl && <button className="btn sm gh" onClick={() => setLogoUrl('')} title={t('portal.logoRemove')}>✕</button>}
              <input ref={logoInputRef} type="file" accept="image/*" style={{ display: 'none' }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleLogoUpload(f); e.target.value = '' }} />
            </div>
            <input id={`${formId}-logo-url`} className="fld mono" value={logoUrl} onChange={e => setLogoUrl(e.target.value)} placeholder={t('portal.logoUrlPlaceholder')} style={{ marginTop: 6, fontSize: 12 }} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 8, opacity: logoUrl ? 1 : 0.6 }}>
              <input type="checkbox" className="ck" checked={headerShowTitle} onChange={e => setHeaderShowTitle(e.target.checked)} />
              {tLayout('header.showTitle')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 4, opacity: logoUrl ? 1 : 0.6 }}>
              <input type="checkbox" className="ck" checked={heroHideTitle} onChange={e => setHeroHideTitle(e.target.checked)} />
              {tLayout('header.hideHeroTitle')}
            </label>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{tLayout('header.hint')}</div>
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-placeholder-img`}>{t('portal.placeholderImage')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('portal.placeholderImageHint')}</span></label>
            <input id={`${formId}-placeholder-img`} className="fld mono" value={placeholderImageUrl} onChange={e => setPlaceholderImageUrl(e.target.value)} placeholder="https://..." style={{ fontSize: 12 }} />
            {placeholderImageUrl && <img src={placeholderImageUrl} alt={t('portal.placeholderImage')} style={{ marginTop: 6, height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--border-s)', borderRadius: 4, padding: 4, background: '#fff' }} />}
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-featured`}>{t('portal.featured')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('portal.featuredHint')}</span></label>
            <textarea id={`${formId}-featured`} className="fld mono" rows={4} value={featuredIds} onChange={e => setFeaturedIds(e.target.value)} style={{ resize: 'vertical', fontSize: 12 }} placeholder={'uuid-1\nuuid-2'} />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('portal.navigation')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
            {t('portal.navigationHint')}
          </p>
          {RECORD_TYPES.filter(({ key }) => key !== 'procedure').map(({ key, labelKey }) => (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={browseTypes.includes(key)}
                onChange={e => setBrowseTypes(types => e.target.checked ? [...types, key] : types.filter(type => type !== key))}
              />
              {t(labelKey)}
            </label>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('detailLayout.title')}</div>
        <div className="bd">
          <div className="field" role="group" aria-labelledby={`${formId}-sidebar-pos`}>
            <div id={`${formId}-sidebar-pos`} className="lbl">{t('detailLayout.sidebar')}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`btn${detailSidebarPosition === 'right' ? ' pri' : ' gh'}`} onClick={() => setDetailSidebarPosition('right')}>{t('detailLayout.right')}</button>
              <button className={`btn${detailSidebarPosition === 'left' ? ' pri' : ' gh'}`} onClick={() => setDetailSidebarPosition('left')}>{t('detailLayout.left')}</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t('detailLayout.sidebarHint')}
            </div>
          </div>
          <div className="field" role="group" aria-labelledby={`${formId}-meta-row`}>
            <div id={`${formId}-meta-row`} className="lbl">{t('detailLayout.metaRowLabel')}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`btn${metaRowLayout === 'stacked' ? ' pri' : ' gh'}`} onClick={() => setMetaRowLayout('stacked')}>{t('detailLayout.metaRowStacked')}</button>
              <button className={`btn${metaRowLayout === 'inline' ? ' pri' : ' gh'}`} onClick={() => setMetaRowLayout('inline')}>{t('detailLayout.metaRowInline')}</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t('detailLayout.metaRowHint')}
            </div>
          </div>
          <div className="field">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={metaLabelUppercase}
                onChange={e => setMetaLabelUppercase(e.target.checked)}
              />
              {t('detailLayout.metaLabelUppercase')}
            </label>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t('detailLayout.metaLabelUppercaseHint')}
            </div>
          </div>
          <div className="field">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={showIiifManifestLink}
                onChange={e => setShowIiifManifestLink(e.target.checked)}
              />
              {t('detailLayout.iiifButton')}
            </label>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t('detailLayout.iiifButtonHint')}
            </div>
          </div>
          <div className="field">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={mediaDownloadEnabled}
                onChange={e => setMediaDownloadEnabled(e.target.checked)}
              />
              {t('detailLayout.mediaDownload')}
            </label>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t('detailLayout.mediaDownloadHint')}
            </div>
          </div>
          <div className="field">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={showUsageStats}
                onChange={e => setShowUsageStats(e.target.checked)}
              />
              {t('detailLayout.usageStats')}
            </label>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
              {t(config.usage_stats_enabled === false ? 'detailLayout.usageStatsOffHint' : 'detailLayout.usageStatsHint')}
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('portal.design')}</div>
        <div className="bd">
          {colorFields.map(({ lbl, val, set, ph }, idx) => (
            <div className="field" key={lbl}>
              <label className="lbl" htmlFor={`${formId}-color-${idx}`}>{lbl}</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="color" aria-label={lbl} value={val || (ph ?? '#000000')} onChange={e => set(e.target.value)}
                  style={{ width: 40, height: 32, padding: 2, border: '1px solid var(--border-s)', borderRadius: 4 }} />
                <input id={`${formId}-color-${idx}`} className="fld mono" value={val} onChange={e => set(e.target.value)} placeholder={ph ?? ''} style={{ flex: 1 }} />
                {val && <button className="btn sm gh" onClick={() => set('')} title={t('common.reset')}>✕</button>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('portal.portalLanguage')}</div>
        <div className="bd">
          <div className="field" role="group" aria-labelledby={`${formId}-portal-lang`}><div id={`${formId}-portal-lang`} className="lbl">{t('portal.language')}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`btn${lang === 'de' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('de')}>Deutsch</button>
              <button className={`btn${lang === 'en' ? ' pri' : ' gh'}`} onClick={() => handleLangChange('en')}>English</button>
            </div>
          </div>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('common.saved')}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Startseite section (#374 — configurable homepage content blocks)
// ---------------------------------------------------------------------------

function newBlock(type: HomepageBlock['type']): HomepageBlock {
  const id = crypto.randomUUID()
  if (type === 'text') return { id, type, enabled: true, title: {}, content: {} }
  if (type === 'objects') return { id, type, enabled: true, title: {}, limit: 12 }
  if (type === 'collections') return { id, type, enabled: true, title: {}, collections_mode: 'top', limit: 12 }
  return { id, type: 'curated', enabled: true, title: {} }
}

function SectionStartseite({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
  const [blocks, setBlocks] = useState<HomepageBlock[]>(config.homepage_blocks ?? [])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update(id: string, patch: Partial<HomepageBlock>) {
    setBlocks(prev => prev.map(b => b.id === id ? { ...b, ...patch } : b))
  }

  function move(id: string, dir: -1 | 1) {
    setBlocks(prev => {
      const i = prev.findIndex(b => b.id === id)
      const j = i + dir
      if (i === -1 || j < 0 || j >= prev.length) return prev
      const next = [...prev]
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  function remove(id: string) {
    setBlocks(prev => prev.filter(b => b.id !== id))
  }

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      const c = await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({ homepage_blocks: blocks }),
      })
      onSaved(c)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('startseite.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>{t('startseite.description')}</p>

          {blocks.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>{t('startseite.empty')}</div>
          )}

          {blocks.map((block, i) => (
            <div key={block.id} className="card" style={{ marginBottom: 12, background: 'var(--bg)' }}>
              <div className="hd" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>
                  {block.type === 'text' && t('startseite.typeText')}
                  {block.type === 'curated' && t('startseite.typeCurated')}
                  {block.type === 'objects' && t('startseite.typeObjects')}
                  {block.type === 'collections' && t('startseite.typeCollections')}
                </span>
                <div className="grow" />
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 400 }}>
                  <input type="checkbox" className="ck" checked={block.enabled} onChange={e => update(block.id, { enabled: e.target.checked })} />
                  {t('startseite.enabled')}
                </label>
                <button className="btn sm gh" disabled={i === 0} onClick={() => move(block.id, -1)} title={t('startseite.moveUp')}>↑</button>
                <button className="btn sm gh" disabled={i === blocks.length - 1} onClick={() => move(block.id, 1)} title={t('startseite.moveDown')}>↓</button>
                <button className="btn sm gh dn" onClick={() => remove(block.id)} title={t('startseite.remove')}>✕</button>
              </div>
              <div className="bd">
                <div className="fg-2">
                  <div className="field">
                    <label className="lbl" htmlFor={`${formId}-${block.id}-title-de`}>{t('startseite.titleDE')}</label>
                    <input id={`${formId}-${block.id}-title-de`} className="fld" value={block.title?.de ?? ''} onChange={e => update(block.id, { title: { ...block.title, de: e.target.value } })} />
                  </div>
                  <div className="field">
                    <label className="lbl" htmlFor={`${formId}-${block.id}-title-en`}>{t('startseite.titleEN')}</label>
                    <input id={`${formId}-${block.id}-title-en`} className="fld" value={block.title?.en ?? ''} onChange={e => update(block.id, { title: { ...block.title, en: e.target.value } })} />
                  </div>
                </div>

                {block.type === 'text' && (
                  <>
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${block.id}-content-de`}>{t('startseite.contentDE')}</label>
                      <textarea id={`${formId}-${block.id}-content-de`} className="fld" rows={4} value={block.content?.de ?? ''} onChange={e => update(block.id, { content: { ...block.content, de: e.target.value } })}
                        style={{ resize: 'vertical', fontFamily: 'inherit' }} />
                    </div>
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${block.id}-content-en`}>{t('startseite.contentEN')}</label>
                      <textarea id={`${formId}-${block.id}-content-en`} className="fld" rows={4} value={block.content?.en ?? ''} onChange={e => update(block.id, { content: { ...block.content, en: e.target.value } })}
                        style={{ resize: 'vertical', fontFamily: 'inherit' }} />
                    </div>
                  </>
                )}

                {block.type === 'curated' && (
                  <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('startseite.curatedHint')}</div>
                )}

                {block.type === 'objects' && (
                  <div className="field">
                    <label className="lbl" htmlFor={`${formId}-${block.id}-limit`}>{t('startseite.limitLabel')}</label>
                    <input id={`${formId}-${block.id}-limit`} className="fld mono" type="number" min={1} max={100} value={block.limit ?? 12}
                      onChange={e => update(block.id, { limit: Number(e.target.value) })} style={{ width: 90 }} />
                  </div>
                )}

                {block.type === 'collections' && (
                  <>
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${block.id}-col-mode`}>{t('startseite.collectionsModeLabel')}</label>
                      <select id={`${formId}-${block.id}-col-mode`} className="fld" value={block.collections_mode ?? 'top'}
                        onChange={e => update(block.id, { collections_mode: e.target.value as HomepageBlock['collections_mode'] })}>
                        <option value="top">{t('startseite.collectionsModeTop')}</option>
                        <option value="all">{t('startseite.collectionsModeAll')}</option>
                        <option value="largest">{t('startseite.collectionsModeLargest')}</option>
                        <option value="selected">{t('startseite.collectionsModeSelected')}</option>
                      </select>
                    </div>
                    {block.collections_mode === 'selected' ? (
                      <div className="field" role="group" aria-labelledby={`${formId}-${block.id}-col-ids`}>
                        <div id={`${formId}-${block.id}-col-ids`} className="lbl">{t('startseite.collectionIdsLabel')}</div>
                        <CollectionPicker value={block.collection_ids ?? []}
                          onChange={ids => update(block.id, { collection_ids: ids })} />
                      </div>
                    ) : (
                      <div className="field">
                        <label className="lbl" htmlFor={`${formId}-${block.id}-col-limit`}>{t('startseite.limitLabel')}</label>
                        <input id={`${formId}-${block.id}-col-limit`} className="fld mono" type="number" min={1} max={100} value={block.limit ?? 12}
                          onChange={e => update(block.id, { limit: Number(e.target.value) })} style={{ width: 90 }} />
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(['text', 'curated', 'objects', 'collections'] as const).map(type => (
              <button key={type} className="btn gh sm" onClick={() => setBlocks(prev => [...prev, newBlock(type)])}>
                + {type === 'text' ? t('startseite.typeText') : type === 'curated' ? t('startseite.typeCurated') : type === 'objects' ? t('startseite.typeObjects') : t('startseite.typeCollections')}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('startseite.saving') : t('startseite.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('startseite.saved')}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Terminologie section (#373 — configurable portal record-type labels)
// ---------------------------------------------------------------------------

const TERMINOLOGY_TYPES = RECORD_TYPES.filter(({ key }) => key !== 'procedure')

function SectionTerminologie({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
  const [terminology, setTerminologyState] = useState<Record<string, TerminologyEntry>>(config.terminology ?? {})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function entryFor(key: string): TerminologyEntry {
    return terminology[key] ?? { singular: {}, plural: {} }
  }

  function update(key: string, form: 'singular' | 'plural', lang: string, value: string) {
    setTerminologyState(prev => {
      const entry = prev[key] ?? { singular: {}, plural: {} }
      return { ...prev, [key]: { ...entry, [form]: { ...entry[form], [lang]: value } } }
    })
  }

  function reset(key: string) {
    setTerminologyState(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      const c = await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({ terminology }),
      })
      onSaved(c)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('terminologie.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>{t('terminologie.description')}</p>

          {TERMINOLOGY_TYPES.map(({ key, labelKey }) => {
            const entry = entryFor(key)
            const hasOverride = Boolean(terminology[key])
            return (
              <div key={key} className="card" style={{ marginBottom: 12, background: 'var(--bg)' }}>
                <div className="hd" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{t(labelKey)}</span>
                  <div className="grow" />
                  <button className="btn sm gh" disabled={!hasOverride} onClick={() => reset(key)}>
                    {t('terminologie.reset')}
                  </button>
                </div>
                <div className="bd">
                  <div className="fg-2">
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${key}-s-de`}>{t('terminologie.singularDE')}</label>
                      <input id={`${formId}-${key}-s-de`} className="fld" value={entry.singular.de ?? ''} onChange={e => update(key, 'singular', 'de', e.target.value)} />
                    </div>
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${key}-s-en`}>{t('terminologie.singularEN')}</label>
                      <input id={`${formId}-${key}-s-en`} className="fld" value={entry.singular.en ?? ''} onChange={e => update(key, 'singular', 'en', e.target.value)} />
                    </div>
                  </div>
                  <div className="fg-2">
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${key}-p-de`}>{t('terminologie.pluralDE')}</label>
                      <input id={`${formId}-${key}-p-de`} className="fld" value={entry.plural.de ?? ''} onChange={e => update(key, 'plural', 'de', e.target.value)} />
                    </div>
                    <div className="field">
                      <label className="lbl" htmlFor={`${formId}-${key}-p-en`}>{t('terminologie.pluralEN')}</label>
                      <input id={`${formId}-${key}-p-en`} className="fld" value={entry.plural.en ?? ''} onChange={e => update(key, 'plural', 'en', e.target.value)} />
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('terminologie.saving') : t('terminologie.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('terminologie.saved')}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Danger zone section
// ---------------------------------------------------------------------------

function SectionDangerZone() {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
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
  const expectedConfirmation = (selectedSubtype?.label?.de || t(active.labelKey)).toUpperCase()

  // Vocabulary reset / delete state
  const [vocabsList, setVocabsList] = useState<Vocabulary[]>([])
  const [activeVocabId, setActiveVocabId] = useState('')
  const [vocabScope, setVocabScope] = useState<'terms' | 'vocabulary'>('terms')
  const [vocabSummary, setVocabSummary] = useState<{ term_count: number; referencing_fields: number; is_system: boolean } | null>(null)
  const [vocabConfirmation, setVocabConfirmation] = useState('')
  const [resettingVocab, setResettingVocab] = useState(false)
  const [vocabError, setVocabError] = useState<string | null>(null)
  const [vocabSuccess, setVocabSuccess] = useState<string | null>(null)

  const selectedVocab = vocabsList.find(v => v.id === activeVocabId)
  const expectedVocabConfirmation = (selectedVocab?.name ?? '').toUpperCase()

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

  useEffect(() => {
    vocabularies.list()
      .then(list => {
        setVocabsList(list)
        if (list.length > 0) setActiveVocabId(list[0].id)
      })
      .catch((e: Error) => setVocabError(e.message))
  }, [])

  useEffect(() => {
    if (!activeVocabId) {
      setVocabSummary(null)
      return
    }
    setVocabSummary(null)
    setVocabConfirmation('')
    setVocabError(null)
    vocabularies.resetSummary(activeVocabId)
      .then(result => {
        setVocabSummary(result)
        if (result.is_system) {
          setVocabScope('terms')
        }
      })
      .catch((e: Error) => setVocabError(e.message))
  }, [activeVocabId])

  async function handleReset() {
    if (confirmation !== expectedConfirmation) return
    setResetting(true); setError(null); setSuccess(null)
    try {
      const result = await schema.reset(activeType, activeSubtype || undefined)
      setSummary(0); setConfirmation('')
      setSuccess(t('dangerZone.schemaSuccess', { count: result.deleted_fields }))
    } catch (e) { setError((e as Error).message) }
    finally { setResetting(false) }
  }

  async function handleVocabAction() {
    if (!selectedVocab || vocabConfirmation !== expectedVocabConfirmation) return
    setResettingVocab(true)
    setVocabError(null)
    setVocabSuccess(null)
    const targetName = selectedVocab.name
    try {
      if (vocabScope === 'terms') {
        const result = await vocabularies.clearTerms(selectedVocab.id)
        setVocabSummary(prev => prev ? { ...prev, term_count: 0 } : null)
        setVocabConfirmation('')
        setVocabSuccess(t('dangerZone.vocabSuccessTerms', { count: result.deleted_terms }))
      } else {
        const result = await vocabularies.deleteVocabulary(selectedVocab.id, { force: true })
        const remaining = vocabsList.filter(v => v.id !== selectedVocab.id)
        setVocabsList(remaining)
        setActiveVocabId(remaining[0]?.id ?? '')
        setVocabConfirmation('')
        setVocabSuccess(
          result.deactivated_fields > 0
            ? t('dangerZone.vocabSuccessFullWithFields', {
                name: targetName,
                count: result.deleted_terms,
                fields: result.deactivated_fields,
              })
            : t('dangerZone.vocabSuccessFull', { name: targetName, count: result.deleted_terms })
        )
      }
    } catch (e) {
      setVocabError((e as Error).message)
    } finally {
      setResettingVocab(false)
    }
  }

  const vocabActionDisabled =
    resettingVocab ||
    !selectedVocab ||
    vocabSummary === null ||
    vocabConfirmation !== expectedVocabConfirmation ||
    (vocabScope === 'terms' && vocabSummary.term_count === 0) ||
    (vocabScope === 'vocabulary' && vocabSummary.is_system)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ borderColor: '#fca5a5' }}>
        <div className="hd" style={{ color: '#b91c1c' }}>{t('dangerZone.nav')} – {t('dangerZone.schemaTitle')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
            {t('dangerZone.schemaDescription')} <code>label</code> {t('dangerZone.schemaDescriptionSuffix')}
          </p>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-record-type`}>{t('dangerZone.recordType')}</label>
            <select id={`${formId}-record-type`} className="fld" value={activeType} onChange={e => setActiveType(e.target.value as typeof activeType)}>
              {RECORD_TYPES.map(type => <option key={type.key} value={type.key}>{t(type.labelKey)}</option>)}
            </select>
          </div>
          {subtypesList.length > 0 && <div className="field">
            <label className="lbl" htmlFor={`${formId}-subtype`}>{t('dangerZone.vocabScopeLabel')}</label>
            <select id={`${formId}-subtype`} className="fld" value={activeSubtype} onChange={e => setActiveSubtype(e.target.value)}>
              <option value="">{t('dangerZone.wholeSchema', { type: t(active.labelKey) })}</option>
              {subtypesList.map(subtype => <option key={subtype.id} value={subtype.name}>{t('dangerZone.onlySubtype', { subtype: subtype.label?.de || subtype.name })}</option>)}
            </select>
          </div>}
          <p style={{ fontSize: 13, marginBottom: 16 }}>
            {summary === null ? t('dangerZone.schemaChecking') : t('dangerZone.schemaSummary', { count: summary })}
          </p>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-schema-confirm`}>{t('dangerZone.confirmPrompt')} <code>{expectedConfirmation}</code> {t('dangerZone.confirmPromptSuffix')}</label>
            <input id={`${formId}-schema-confirm`} className="fld" value={confirmation} onChange={e => setConfirmation(e.target.value)} autoComplete="off" />
          </div>
          {error && <div style={{ fontSize: 12, color: '#b91c1c', marginBottom: 8 }}>{error}</div>}
          {success && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{success}</div>}
          <button className="btn dn" onClick={handleReset} disabled={resetting || summary === 0 || confirmation !== expectedConfirmation}>
            {resetting
              ? t('dangerZone.schemaResetting')
              : selectedSubtype
                ? t('dangerZone.resetSubschema', { subtype: selectedSubtype.label?.de || selectedSubtype.name })
                : t('dangerZone.resetSchema', { type: t(active.labelKey) })}
          </button>
        </div>
      </div>

      <div className="card" style={{ borderColor: '#fca5a5' }}>
        <div className="hd" style={{ color: '#b91c1c' }}>{t('dangerZone.vocabTitle')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
            {t('dangerZone.vocabDescription')}
          </p>
          {vocabsList.length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('dangerZone.vocabEmpty')}</p>
          ) : (
            <>
              <div className="field">
                <label className="lbl" htmlFor={`${formId}-vocab`}>{t('dangerZone.vocabLabel')}</label>
                <select
                  id={`${formId}-vocab`}
                  className="fld"
                  value={activeVocabId}
                  onChange={e => {
                    setActiveVocabId(e.target.value)
                    setVocabSuccess(null)
                  }}
                >
                  {vocabsList.map(v => (
                    <option key={v.id} value={v.id}>{v.name}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="lbl" htmlFor={`${formId}-vocab-scope`}>{t('dangerZone.vocabScopeLabel')}</label>
                <select
                  id={`${formId}-vocab-scope`}
                  className="fld"
                  value={vocabScope}
                  onChange={e => {
                    setVocabScope(e.target.value as 'terms' | 'vocabulary')
                    setVocabConfirmation('')
                    setVocabSuccess(null)
                  }}
                >
                  <option value="terms">{t('dangerZone.vocabScopeTerms')}</option>
                  <option value="vocabulary" disabled={vocabSummary?.is_system === true}>
                    {vocabSummary?.is_system ? t('dangerZone.vocabScopeFullSystemDisabled') : t('dangerZone.vocabScopeFull')}
                  </option>
                </select>
              </div>
              <div style={{ fontSize: 13, marginBottom: 16 }}>
                {vocabSummary === null ? (
                  <div>{t('dangerZone.vocabChecking')}</div>
                ) : vocabScope === 'terms' ? (
                  <div>{t('dangerZone.vocabSummaryTerms', { count: vocabSummary.term_count })}</div>
                ) : (
                  <>
                    <div>{t('dangerZone.vocabSummaryFull', { name: selectedVocab?.name ?? '', count: vocabSummary.term_count })}</div>
                    {vocabSummary.referencing_fields > 0 && (
                      <div style={{ color: '#b91c1c', marginTop: 4 }}>
                        {t('dangerZone.vocabReferencingFieldsWarning', { count: vocabSummary.referencing_fields })}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="field">
                <label className="lbl" htmlFor={`${formId}-vocab-confirm`}>
                  {t('dangerZone.confirmPrompt')} <code>{expectedVocabConfirmation}</code> {t('dangerZone.confirmPromptSuffix')}
                </label>
                <input
                  id={`${formId}-vocab-confirm`}
                  className="fld"
                  value={vocabConfirmation}
                  onChange={e => setVocabConfirmation(e.target.value)}
                  autoComplete="off"
                />
              </div>
              {vocabError && <div style={{ fontSize: 12, color: '#b91c1c', marginBottom: 8 }}>{vocabError}</div>}
              {vocabSuccess && <div style={{ fontSize: 12, color: '#166534', marginBottom: 8 }}>{vocabSuccess}</div>}
              <button className="btn dn" onClick={handleVocabAction} disabled={vocabActionDisabled}>
                {resettingVocab
                  ? t('dangerZone.vocabDeleting')
                  : vocabScope === 'terms'
                    ? t('dangerZone.vocabDeleteTermsBtn', { name: selectedVocab?.name ?? '' })
                    : t('dangerZone.vocabDeleteFullBtn', { name: selectedVocab?.name ?? '' })}
              </button>
            </>
          )}
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
  { name: 'related_entities', labelKey: 'facetSettings:related.entities' },
  { name: 'related_places', labelKey: 'facetSettings:related.places' },
  { name: 'related_occurrences', labelKey: 'facetSettings:related.occurrences' },
  { name: 'related_collections', labelKey: 'facetSettings:related.collections' },
] as const
const RELATED_FACET_NAMES: readonly string[] = RELATED_FACET_DEFS.map(f => f.name)
const SUBFIELD_SEPARATOR = '__'

/** Group sub-fields that can be facets ("<group>__<child>" in facet_fields). */
function facetSubfields(fields: FieldDefinition[]): { name: string; group: FieldDefinition; child: FieldDefinition }[] {
  return fields
    .filter(f => f.field_type === 'group' && f.is_public)
    .flatMap(group => (group.children ?? [])
      .filter(child => child.is_public && child.field_type !== 'group')
      .map(child => ({ name: `${group.name}${SUBFIELD_SEPARATOR}${child.name}`, group, child })))
}

/** Configured order first, remaining names in their default order. */
function applyOrder(names: string[], order: string[] | undefined): string[] {
  if (!order?.length) return names
  const head = order.filter(name => names.includes(name))
  return [...head, ...names.filter(name => !head.includes(name))]
}

function SectionFacetten({ config, onSaved }: { config: PortalConfigRead, onSaved: (c: PortalConfigRead) => void }) {
  const [activeType, setActiveType] = useState<string>('object')
  const [fieldsByType, setFieldsByType] = useState<Record<string, FieldDefinition[]>>({})
  const [loadingFields, setLoadingFields] = useState(true)
  const [systemFacets, setSystemFacets] = useState<string[]>(
    () => config.facet_fields?._system ?? ['record_type', 'subtype']
  )
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
      return Object.fromEntries(RECORD_TYPES.map(({ key }) => [key, base[key] ?? []]))
    }
  )
  const [relationFacets, setRelationFacets] = useState<Record<string, RelationFacet[]>>(() => config.relation_facets ?? {})
  const [facetOrder, setFacetOrder] = useState<Record<string, string[]>>(() => config.facet_order ?? {})
  const [facetSortOverrides, setFacetSortOverrides] = useState<Record<string, Record<string, 'count' | 'alpha'>>>(() => config.facet_sort_overrides ?? {})
  const { t: tFacets, i18n } = useTranslation('facetSettings')
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
          const direct = [
            ...(byType[key] ?? []).filter(f => f.is_facet && f.is_public).map(f => f.name),
            ...facetSubfields(byType[key] ?? []).filter(sub => sub.child.is_facet).map(sub => sub.name),
          ]
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
        const targetType_ = RECORD_TYPES.find(type => type.key === targetType)
        const targetLabel = targetType_ ? tFacets(targetType_.labelKey) : targetType
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
      const changedByType: Record<string, FieldDefinition[]> = {}
      const inheritedToSave: Record<string, string[]> = { _system: systemFacets }
      const subtitleToSave: Record<string, string[]> = {}

      for (const { key } of RECORD_TYPES) {
        const selected = facetFields[key] ?? []
        inheritedToSave[key] = selected.filter(name => name.startsWith('inherited_') || RELATED_FACET_NAMES.includes(name))

        for (const f of fieldsByType[key] ?? []) {
          const shouldBeFacet = selected.includes(f.name)
          if (f.field_type !== 'group' && f.is_facet !== shouldBeFacet) {
            const payload = { ...f, is_facet: shouldBeFacet }
            delete payload.children
            ;(changedByType[key] ??= []).push(payload)
          }
        }
        for (const sub of facetSubfields(fieldsByType[key] ?? [])) {
          const shouldBeFacet = selected.includes(sub.name)
          if (sub.child.is_facet !== shouldBeFacet) {
            const payload = { ...sub.child, is_facet: shouldBeFacet }
            delete payload.children
            ;(changedByType[key] ??= []).push(payload)
          }
        }
        if (changedByType[key]?.length) schemaUpdates.push(schema.bulkUpdate(key, changedByType[key]))

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
              is_facet: f.field_type === 'group' ? f.is_facet : selected.includes(f.name),
              children: f.children?.map(child => ({
                ...child,
                is_facet: selected.includes(`${f.name}${SUBFIELD_SEPARATOR}${child.name}`),
              })),
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
          facet_sort: 'count',
          facet_sort_overrides: Object.fromEntries(
            RECORD_TYPES.map(({ key }) => {
              const activeNames = new Set(orderItemsFor(key).map(item => item.name))
              const entries = [...activeNames]
                .filter(name => getFacetSort(key, name) === 'alpha')
                .map(name => [name, 'alpha' as const])
              return [key, Object.fromEntries(entries)]
            })
          ),
          facet_initial_count: facetInitialCount,
          relation_facets: Object.fromEntries(RECORD_TYPES.map(({ key }) => [key, relationFacets[key] ?? []])),
          facet_order: Object.fromEntries(RECORD_TYPES.map(({ key }) => [key, orderItemsFor(key).map(item => item.name)])),
        }),
      })

      onSaved(portalConfig)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  function isSortableField(type: string, name: string, def?: FieldDefinition): boolean {
    if (RELATED_FACET_NAMES.includes(name) || name.startsWith('inherited_')) return true
    if (!def) return false
    if (def.field_type === 'number' || def.field_type === 'boolean' || def.field_type === 'date') return false
    if (config.facet_kinds?.[type]?.[name]?.kind === 'tree') return false
    return true
  }

  function getFacetSort(type: string, name: string): 'count' | 'alpha' {
    return facetSortOverrides[type]?.[name] ?? (config.facet_sort === 'alpha' ? 'alpha' : 'count')
  }

  function setFacetSortFor(type: string, name: string, sort: 'count' | 'alpha') {
    setFacetSortOverrides(prev => ({
      ...prev,
      [type]: { ...(prev[type] ?? {}), [name]: sort },
    }))
  }

  function renderSortSelect(type: string, name: string, label: string) {
    return (
      <select
        className="fld"
        aria-label={tFacets('order.sortAria', { name: label })}
        value={getFacetSort(type, name)}
        onChange={e => setFacetSortFor(type, name, e.target.value as 'count' | 'alpha')}
        style={{ width: 'auto', height: 26, padding: '0 8px', fontSize: 12 }}
      >
        <option value="count">{tFacets('order.sort.count')}</option>
        <option value="alpha">{tFacets('order.sort.alpha')}</option>
      </select>
    )
  }

  function relatedFacetLabel(name: string): string | undefined {
    const def = RELATED_FACET_DEFS.find(r => r.name === name)
    return def ? tFacets(def.labelKey) : undefined
  }

  function orderItemsFor(type: string): FacetOrderItem[] {
    const lang = i18n.language?.slice(0, 2) || 'de'
    const typeFields = fieldsByType[type] ?? []
    const subfields = facetSubfields(typeFields)
    const inherited = inheritedFacetFieldsFor(type)
    const kinds = config.facet_kinds?.[type] ?? {}
    const items: FacetOrderItem[] = (facetFields[type] ?? []).map(name => {
      const field = typeFields.find(f => f.name === name)
      const sub = subfields.find(s => s.name === name)
      const def = field ?? sub?.child
      const label = sub
        ? tFacets('subfield', { group: sub.group.label?.[lang] || sub.group.label?.de || sub.group.name, field: sub.child.label?.[lang] || sub.child.label?.de || sub.child.name })
        : field
          ? field.label?.[lang] || field.label?.de || field.label?.en || name
          : relatedFacetLabel(name) ?? inherited.find(i => i.name === name)?.label ?? name
      const kind: FacetOrderItem['kind'] = RELATED_FACET_NAMES.includes(name)
        ? 'related'
        : name.startsWith('inherited_')
          ? 'inherited'
          : def?.field_type === 'date' && def.settings?.facet_granularity
            ? 'date'
            : kinds[name]?.kind === 'tree'
              ? 'tree'
              : 'field'
      return { name, label, kind }
    })
    for (const facet of relationFacets[type] ?? []) {
      const name = `relfacet_${facet.key}`
      items.push({
        name,
        label: facet.label?.[lang] || facet.label?.de || facet.key,
        kind: 'relation',
      })
    }
    const ordered = applyOrder(items.map(item => item.name), facetOrder[type])
    return ordered.map(name => items.find(item => item.name === name)!)
  }

  const fields = (fieldsByType[activeType] ?? []).filter(f => f.is_public && f.field_type !== 'group')
  const subfields = facetSubfields(fieldsByType[activeType] ?? [])
  const selected = facetFields[activeType] ?? []
  const inheritedFacetFields = inheritedFacetFieldsFor(activeType)
  const subtitleSelected = subtitleFields[activeType] ?? []

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        {tFacets('intro')}
      </p>

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>{tFacets('systemFacets')}</h4>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="bd">
          {[
            { name: 'record_type', label: tFacets('system.record_type') },
            { name: 'status', label: tFacets('system.status') },
            { name: 'subtype', label: tFacets('system.subtype') },
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

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>{tFacets('display')}</h4>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="bd" style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
            {tFacets('initialCount')}
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

      <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>{tFacets('perType')}</h4>
      <div className="card" style={{ marginBottom: 20, overflow: 'hidden' }}>
        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-s)', background: 'var(--bg-2, rgba(0,0,0,0.02))', padding: '0 8px', flexWrap: 'wrap' }}>
          {RECORD_TYPES.map(({ key, labelKey }) => {
            const count = (facetFields[key]?.length ?? 0) + (relationFacets[key]?.length ?? 0)
            return (
              <button
                key={key}
                type="button"
                onClick={() => setActiveType(key)}
                style={{
                  padding: '10px 14px', fontSize: 13, border: 'none', background: 'none', cursor: 'pointer',
                  borderBottom: activeType === key ? '2px solid var(--accent)' : '2px solid transparent',
                  color: activeType === key ? 'var(--accent)' : 'var(--fg-2)',
                  fontWeight: activeType === key ? 600 : 400,
                  marginBottom: -1,
                }}
              >
                {tFacets(labelKey)}
                {count > 0 && (
                  <span style={{ marginLeft: 6, fontSize: 10, background: 'var(--accent)', color: '#fff', borderRadius: 10, padding: '1px 5px' }}>
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="bd">
          {loadingFields ? (
            <div className="empty">{tFacets('loadingFields')}</div>
          ) : (
            <div>
              {fields.length === 0 && inheritedFacetFields.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>{tFacets('noFields')}</div>
              )}
              {fields.map(f => {
                const label = f.label?.de || f.label?.en || f.name
                const isChecked = selected.includes(f.name)
                return (
                  <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', fontSize: 13 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, cursor: 'pointer', minWidth: 0 }}>
                      <input
                        type="checkbox"
                        className="ck"
                        checked={isChecked}
                        onChange={() => toggle(activeType, f.name)}
                      />
                      <span style={{ flex: 1 }}>{label}</span>
                    </label>
                    {isChecked && isSortableField(activeType, f.name, f) && renderSortSelect(activeType, f.name, label)}
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
                  </div>
                )
              })}
              {subfields.map(sub => {
                const label = tFacets('subfield', {
                  group: sub.group.label?.de || sub.group.label?.en || sub.group.name,
                  field: sub.child.label?.de || sub.child.label?.en || sub.child.name,
                })
                const isChecked = selected.includes(sub.name)
                return (
                  <div key={sub.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', fontSize: 13 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, cursor: 'pointer', minWidth: 0 }}>
                      <input
                        type="checkbox"
                        className="ck"
                        checked={isChecked}
                        onChange={() => toggle(activeType, sub.name)}
                      />
                      <span style={{ flex: 1 }}>{label}</span>
                    </label>
                    {isChecked && isSortableField(activeType, sub.name, sub.child) && renderSortSelect(activeType, sub.name, label)}
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{sub.name}</span>
                  </div>
                )
              })}
              {inheritedFacetFields.length > 0 && (
                <>
                  <div style={{ borderTop: '1px solid var(--border-s)', margin: '10px 0 4px', paddingTop: 10, fontSize: 12, color: 'var(--fg-3)' }}>
                    {tFacets('inheritedFields')}
                  </div>
                  {inheritedFacetFields.map(f => {
                    const isChecked = selected.includes(f.name)
                    return (
                      <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', fontSize: 13 }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, cursor: 'pointer', minWidth: 0 }}>
                          <input
                            type="checkbox"
                            className="ck"
                            checked={isChecked}
                            onChange={() => toggle(activeType, f.name)}
                          />
                          <span style={{ flex: 1 }}>{f.label}</span>
                        </label>
                        {isChecked && renderSortSelect(activeType, f.name, f.label)}
                        <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
                      </div>
                    )
                  })}
                </>
              )}
              <div style={{ borderTop: '1px solid var(--border-s)', margin: '10px 0 4px', paddingTop: 10, fontSize: 12, color: 'var(--fg-3)' }}>
                {tFacets('relatedFacets')}
              </div>
              {RELATED_FACET_DEFS.map(f => {
                const isChecked = selected.includes(f.name)
                return (
                  <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', fontSize: 13 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, cursor: 'pointer', minWidth: 0 }}>
                      <input
                        type="checkbox"
                        className="ck"
                        checked={isChecked}
                        onChange={() => toggle(activeType, f.name)}
                      />
                      <span style={{ flex: 1 }}>{tFacets(f.labelKey)}</span>
                    </label>
                    {isChecked && renderSortSelect(activeType, f.name, tFacets(f.labelKey))}
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{f.name}</span>
                  </div>
                )
              })}
            </div>
          )}

          <div style={{ borderTop: '1px solid var(--border-s)', marginTop: 20, paddingTop: 16 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>{tFacets('order.title')}</h4>
            <p style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 10 }}>{tFacets('order.hint')}</p>
            <FacetOrderList
              items={orderItemsFor(activeType)}
              onChange={names => setFacetOrder(prev => ({ ...prev, [activeType]: names }))}
            />
          </div>

          <div style={{ borderTop: '1px solid var(--border-s)', marginTop: 20, paddingTop: 16 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>{tFacets('relations.title')}</h4>
            <p style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 10 }}>{tFacets('relations.hint')}</p>
            <RelationFacetsEditor
              recordType={activeType}
              value={relationFacets[activeType] ?? []}
              onChange={next => setRelationFacets(prev => ({ ...prev, [activeType]: next }))}
              sortByKey={Object.fromEntries(
                (relationFacets[activeType] ?? []).map(facet => [
                  `relfacet_${facet.key}`,
                  getFacetSort(activeType, `relfacet_${facet.key}`),
                ])
              )}
              onSortChange={(facetName, sort) => setFacetSortFor(activeType, facetName, sort)}
            />
          </div>

          <div style={{ borderTop: '1px solid var(--border-s)', marginTop: 20, paddingTop: 16 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>{tFacets('subtitle.title')}</h4>
            <p style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 10 }}>
              {tFacets('subtitle.description')}
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                className="ck"
                checked={subtitleSelected.includes('record_type')}
                onChange={() => toggleSubtitle(activeType, 'record_type')}
              />
              <span style={{ flex: 1 }}>{tFacets('system.record_type')}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>record_type</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                className="ck"
                checked={subtitleSelected.includes('status')}
                onChange={() => toggleSubtitle(activeType, 'status')}
              />
              <span style={{ flex: 1 }}>{tFacets('system.status')}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>status</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                className="ck"
                checked={subtitleSelected.includes('idno')}
                onChange={() => toggleSubtitle(activeType, 'idno')}
              />
              <span style={{ flex: 1 }}>{tFacets('system.idno')}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>idno</span>
            </label>
            {(() => {
              const options = [
                ...fields.filter(f => selected.includes(f.name)).map(f => ({ name: f.name, label: f.label?.de || f.label?.en || f.name })),
                ...inheritedFacetFields.filter(f => selected.includes(f.name)),
              ]
              return options.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>
                  {tFacets('subtitle.empty')}
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
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? tFacets('screenSettings:common.saving') : tFacets('screenSettings:common.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{tFacets('screenSettings:common.saved')}</span>}
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
  const { t } = useTranslation('screenSettings')
  const [health, setHealth] = useState<IndexHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null)
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
    } catch { /* ignore – widget still shows counts without config controls */ }
  }

  useEffect(() => { load(); loadCfg() }, [])

  async function saveCfg(patch: Partial<AdminConfigRead>) {
    if (!cfg) return
    const next = { ...cfg, ...patch }
    setCfg(next)
    setCfgSaving(true)
    try {
      await adminConfig.update(patch)
    } catch (e) { setMsg({ text: t('search.saveError', { message: (e as Error).message }), error: true }) }
    finally { setCfgSaving(false) }
  }

  async function handleReconcile(mode: 'count' | 'id_diff') {
    setRunning(mode); setMsg(null)
    try {
      await req(`${BASE}/v1/admin/index-health/reconcile?mode=${mode}`, { method: 'POST' })
      setMsg({ text: t('search.reconcileStarted'), error: false })
      setTimeout(() => setMsg(null), 8000)
    } catch (e) { setMsg({ text: t('search.error', { message: (e as Error).message }), error: true }) }
    finally { setRunning(null) }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="hd">{t('search.indexStatus')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          {t('search.indexStatusDescription')}
        </p>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 10 }}>{error}</div>}
        {msg && (
          <div style={{ fontSize: 12, color: msg.error ? '#dc2626' : '#166534', marginBottom: 10 }}>
            {msg.text}
          </div>
        )}
        {loading && <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>{t('common.loading')}</p>}
        {!loading && health && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginBottom: 12 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '4px 8px' }}>{t('search.type')}</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>DB</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>ES</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>{t('search.delta')}</th>
              </tr>
            </thead>
            <tbody>
              {RECORD_TYPES.map(({ key, labelKey }) => {
                const entry = health.types[key]
                if (!entry) return null
                const ok = entry.delta === 0
                return (
                  <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '4px 8px' }}>{t(labelKey)}</td>
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
          <button className="btn sm gh" onClick={load} disabled={loading}>{t('search.refresh')}</button>
          <button className="btn sm gh" onClick={() => handleReconcile('count')} disabled={running !== null}>
            {running === 'count' ? t('search.running') : t('search.checkCount')}
          </button>
          <button className="btn sm pri" onClick={() => handleReconcile('id_diff')} disabled={running !== null}>
            {running === 'id_diff' ? t('search.running') : t('search.runIdDiff')}
          </button>
        </div>
        {cfg && (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }} role="group" aria-labelledby="search-auto-reconcile-lbl">
            <div id="search-auto-reconcile-lbl" className="lbl" style={{ marginBottom: 8 }}>{t('search.autoReconcile')}</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={cfg.reconciliation_enabled}
                disabled={cfgSaving}
                onChange={e => saveCfg({ reconciliation_enabled: e.target.checked })}
              />
              {t('search.dailyCount')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={cfg.reconciliation_id_diff_enabled}
                disabled={cfgSaving}
                onChange={e => saveCfg({ reconciliation_id_diff_enabled: e.target.checked })}
              />
              {t('search.weeklyIdDiff')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              {t('search.threshold')}
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
  const { t } = useTranslation('screenSettings')
  const [reindexing, setReindexing] = useState<string | null>(null)
  const [reindexMsg, setReindexMsg] = useState<{ text: string; error: boolean } | null>(null)
  const [confirmReindexType, setConfirmReindexType] = useState<string | 'all' | null>(null)

  function handleReindex(type?: string) {
    setConfirmReindexType(type ?? 'all')
  }

  async function confirmReindex() {
    const type = confirmReindexType === 'all' ? undefined : confirmReindexType ?? undefined
    const key = type ?? 'all'
    setConfirmReindexType(null)
    setReindexing(key); setReindexMsg(null)
    try {
      const url = type ? `${BASE}/v1/search/reindex/${type}` : `${BASE}/v1/search/reindex`
      await req(url, { method: 'POST' })
      setReindexMsg({ text: t('search.reindexStarted'), error: false })
      setTimeout(() => setReindexMsg(null), 5000)
    } catch (e) { setReindexMsg({ text: t('search.error', { message: (e as Error).message }), error: true }) }
    finally { setReindexing(null) }
  }

  return (
    <>
    <IndexHealthWidget />
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="hd">{t('search.title')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          {t('search.description')}
        </p>
        {reindexMsg && (
          <div style={{ fontSize: 12, color: reindexMsg.error ? '#dc2626' : '#166534', marginBottom: 10 }}>
            {reindexMsg.text}
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {(['object', 'entity', 'place', 'occurrence'] as const).map(type => (
            <button key={type} className="btn sm gh" onClick={() => handleReindex(type)} disabled={reindexing !== null}>
              {reindexing === type ? t('search.running') : t('search.reindexType', { type: t(`recordTypes.${type}`) })}
            </button>
          ))}
          <button className="btn sm pri" onClick={() => handleReindex()} disabled={reindexing !== null} style={{ marginLeft: 8 }}>
            {reindexing === 'all' ? t('search.running') : t('search.reindexAll')}
          </button>
        </div>
      </div>
    </div>
    {confirmReindexType !== null && (
      <ConfirmModal
        message={confirmReindexType === 'all' ? t('search.confirmAll') : t('search.confirmType', { type: t(`recordTypes.${confirmReindexType}`) })}
        confirmLabel={confirmReindexType === 'all' ? t('search.reindexAll') : t('search.reindexType', { type: t(`recordTypes.${confirmReindexType}`) })}
        cancelLabel={t('cancel')}
        onConfirm={confirmReindex}
        onCancel={() => setConfirmReindexType(null)}
      />
    )}
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
  const formId = useId()
  const [rebuilding, setRebuilding] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [copied, setCopied] = useState(false)
  const [confirmRebuildOpen, setConfirmRebuildOpen] = useState(false)

  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const fullEndpoint = `${origin}${status.endpoint_url}`

  function handleRebuild() {
    setConfirmRebuildOpen(true)
  }

  async function confirmRebuild() {
    setConfirmRebuildOpen(false)
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
              {status.triples_count != null ? status.triples_count.toLocaleString() : '–'}
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
          <label className="lbl" htmlFor={`${formId}-endpoint`}>{t('sparql.endpointUrl')}</label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              id={`${formId}-endpoint`}
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
      {confirmRebuildOpen && (
        <ConfirmModal
          message={t('sparql.rebuildConfirm')}
          confirmLabel={t('sparql.rebuildBtn')}
          cancelLabel={t('cancel')}
          onConfirm={confirmRebuild}
          onCancel={() => setConfirmRebuildOpen(false)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ID-Schemas section
// ---------------------------------------------------------------------------

function SectionIdnoSchemas() {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
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

  if (loading) return <div className="empty">{t('common.loading')}</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        {t('idno.description')}
      </p>

      {RECORD_TYPES.map(({ key, labelKey }) => (
        <div className="card" key={key} style={{ marginBottom: 16 }}>
          <div className="hd">{t(labelKey)}</div>
          <div className="bd">
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-${key}-schema`}>{t('idno.schema')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('common.optional')}</span></label>
              <input
                id={`${formId}-${key}-schema`}
                className="fld mono"
                value={schemas[key] ?? ''}
                onChange={e => setSchema(key, e.target.value)}
                placeholder={t('idno.schemaPlaceholder')}
              />
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                {t('idno.placeholders')}
              </div>
            </div>
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-${key}-pattern`}>{t('idno.pattern')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('common.optional')}</span></label>
              <input
                id={`${formId}-${key}-pattern`}
                className="fld mono"
                value={patterns[key] ?? ''}
                onChange={e => setPattern(key, e.target.value)}
                placeholder={t('idno.patternPlaceholder')}
              />
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                {t('idno.patternHint')}
              </div>
            </div>
          </div>
        </div>
      ))}

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('common.saved')}</span>}
      </div>
    </div>
  )
}

function SectionAI() {
  const { t, i18n } = useTranslation('screenSettings')
  const formId = useId()
  const [cfg, setCfg] = useState<AdminConfigRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [secretBusy, setSecretBusy] = useState(false)
  const [checkBusy, setCheckBusy] = useState(false)
  const [checkResult, setCheckResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [confirmDeleteSecretOpen, setConfirmDeleteSecretOpen] = useState(false)

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

  function deleteSecret() {
    if (!cfg) return
    setConfirmDeleteSecretOpen(true)
  }

  async function confirmDeleteSecret() {
    setConfirmDeleteSecretOpen(false)
    setSecretBusy(true); setError(null)
    try {
      const secret = await adminConfig.deleteAiSecret()
      setCfg(prev => prev ? { ...prev, ai_secret: secret } : prev)
    } catch (e) { setError((e as Error).message) }
    finally { setSecretBusy(false) }
  }

  if (loading) return <div className="empty">{t('common.loading')}</div>
  if (!cfg) return <div className="empty">{t('common.noConfig')}</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        {t('ai.description')}
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('ai.connection')}</div>
        <div className="bd">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 12 }}>
            <input type="checkbox" className="ck" checked={cfg.ai_enabled} onChange={e => set('ai_enabled', e.target.checked)} />
            {t('ai.enabled')}
          </label>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-base-url`}>{t('ai.baseUrl')}</label>
            <input id={`${formId}-base-url`} className="fld mono" value={cfg.ai_base_url ?? ''} onChange={e => set('ai_base_url', e.target.value)} placeholder="https://api.openai.com/v1" />
            <div className="sub">{t('ai.baseUrlHintBefore')} <code>/chat/completions</code> {t('ai.baseUrlHintMiddle')} <code>https://openrouter.ai/api/v1</code>.</div>
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-model`}>{t('ai.model')}</label>
            <input id={`${formId}-model`} className="fld mono" value={cfg.ai_model ?? ''} onChange={e => set('ai_model', e.target.value)} placeholder="gpt-4.1-mini" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn gh" onClick={checkAi} disabled={checkBusy}>
              {checkBusy ? t('common.checking') : t('ai.testConnection')}
            </button>
            {checkResult && (
              <span style={{ fontSize: 12, color: checkResult.ok ? '#166534' : '#b91c1c' }}>
                {checkResult.ok ? `✓ ${t('ai.response', { message: checkResult.message })}` : `✗ ${checkResult.message}`}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('ai.apiKey')}</div>
        <div className="bd">
          <div style={{ fontSize: 12, color: cfg.ai_secret.has_key ? '#166534' : 'var(--fg-3)', marginBottom: 10 }}>
            {cfg.ai_secret.has_key
              ? cfg.ai_secret.updated_at
                ? t('ai.keySetUpdated', { date: new Date(cfg.ai_secret.updated_at).toLocaleString(i18n.language) })
                : t('ai.keySet')
              : t('ai.noKey')}
          </div>
          <div className="field">
            <label className="lbl" htmlFor={`${formId}-new-key`}>{t('ai.newKey')}</label>
            <input id={`${formId}-new-key`} className="fld mono" type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn pri" onClick={saveSecret} disabled={secretBusy || !apiKey.trim()}>
              {secretBusy ? t('common.saving') : t('ai.saveKey')}
            </button>
            {cfg.ai_secret.has_key && (
              <button className="btn dn" onClick={deleteSecret} disabled={secretBusy}>
                {t('common.delete')}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('ai.tokenLimits')}</div>
        <div className="bd">
          <div className="fg-2">
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-max-input`}>{t('ai.maxInput')}</label>
              <input id={`${formId}-max-input`} className="fld mono" type="number" min={1} value={cfg.ai_max_input_tokens} onChange={e => set('ai_max_input_tokens', Number(e.target.value))} />
            </div>
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-max-output`}>{t('ai.maxOutput')}</label>
              <input id={`${formId}-max-output`} className="fld mono" type="number" min={1} value={cfg.ai_max_output_tokens} onChange={e => set('ai_max_output_tokens', Number(e.target.value))} />
            </div>
          </div>
          <div className="fg-2">
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-daily-limit`}>{t('ai.dailyLimit')}</label>
              <input id={`${formId}-daily-limit`} className="fld mono" type="number" min={1} value={cfg.ai_daily_user_token_limit} onChange={e => set('ai_daily_user_token_limit', Number(e.target.value))} />
              <div className="sub">{t('ai.dailyUsage', { count: cfg.ai_usage.daily_user_tokens.toLocaleString(i18n.language) })}</div>
            </div>
            <div className="field">
              <label className="lbl" htmlFor={`${formId}-monthly-limit`}>{t('ai.monthlyLimit')}</label>
              <input id={`${formId}-monthly-limit`} className="fld mono" type="number" min={1} value={cfg.ai_monthly_global_token_limit} onChange={e => set('ai_monthly_global_token_limit', Number(e.target.value))} />
              <div className="sub">{t('ai.monthlyUsage', { count: cfg.ai_usage.monthly_global_tokens.toLocaleString(i18n.language) })}</div>
            </div>
          </div>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('common.saved')}</span>}
      </div>
      {confirmDeleteSecretOpen && (
        <ConfirmModal
          message={t('ai.deleteKeyConfirm')}
          confirmLabel={t('common.delete')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={confirmDeleteSecret}
          onCancel={() => setConfirmDeleteSecretOpen(false)}
        />
      )}
    </div>
  )
}

function SectionMediaRights() {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
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

  if (!cfg) return <div className="empty">{error ?? t('common.loading')}</div>
  const holder = cfg.media_default_rights_holder ?? { name: '', uri: '' }
  return <div>
    <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>{t('media.description')}</p>
    <div className="field"><label className="lbl" htmlFor={`${formId}-license`}>{t('media.license')}</label><input id={`${formId}-license`} className="fld" value={cfg.media_default_license_uri ?? ''} placeholder={t('media.licensePlaceholder')} onChange={e => setCfg({ ...cfg, media_default_license_uri: e.target.value || null })} /></div>
    <div className="field"><label className="lbl" htmlFor={`${formId}-rights-name`}>{t('media.rightsHolder')}</label><input id={`${formId}-rights-name`} className="fld" value={holder.name} placeholder={t('media.name')} onChange={e => setCfg({ ...cfg, media_default_rights_holder: { ...holder, name: e.target.value } })} /><input className="fld" style={{ marginTop: 4 }} value={holder.uri ?? ''} placeholder={t('media.uriOptional')} aria-label={`${t('media.rightsHolder')} – ${t('media.uriOptional')}`} onChange={e => setCfg({ ...cfg, media_default_rights_holder: { ...holder, uri: e.target.value || undefined } })} /></div>
    {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{error}</div>}
    <button className="btn pri" onClick={save} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>{saved && <span style={{ marginLeft: 8, fontSize: 12, color: '#166534' }}>{t('common.saved')}</span>}
  </div>
}

// ---------------------------------------------------------------------------
// Authority sources section
// ---------------------------------------------------------------------------

function SectionAuthoritySources() {
  const { t } = useTranslation('screenSettings')
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
      setTestResults(prev => ({ ...prev, [source.id]: { ok: true, message: t('authorities.reachable', { count: hits.length }) } }))
    } catch (e) {
      setTestResults(prev => ({ ...prev, [source.id]: { ok: false, message: (e as Error).message } }))
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <div className="empty">{t('common.loading')}</div>

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 16 }}>
        {t('authorities.description')}
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
                {source.is_enabled ? t('authorities.enabled') : t('authorities.disabled')}
              </label>
            </div>
            <div className="bd">
              <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>ID: <span className="mono">{source.id}</span></div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>
                {t('authorities.testQuery')} <a href={testRequest.href} target="_blank" rel="noreferrer">{testRequest.query}</a>
              </div>
              <button className="btn sm gh" onClick={() => test(source)} disabled={!source.is_enabled || testing === source.id}>
                {testing === source.id ? t('common.checking') : t('ai.testConnection')}
              </button>
              {!source.is_enabled && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--fg-3)' }}>{t('authorities.disabledHint')}</span>}
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

function SectionUeber() {
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
          <a href="https://github.com/katalon-collections/katalon" target="_blank" rel="noreferrer">{t('ueber.links.repo')}</a>
          <a href="https://github.com/katalon-collections/katalon/blob/main/LICENSE" target="_blank" rel="noreferrer">{t('ueber.links.license')}</a>
          <a href="https://katalon-collections.github.io/katalon-docs/" target="_blank" rel="noreferrer">{t('ueber.links.docs')}</a>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

function SectionLanguages() {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
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
    if (parsed.length === 0) { setError(t('languages.required')); return }
    setSaving(true); setError(null); setSaved(false)
    try {
      await adminConfig.update({ supported_languages: parsed })
      setInput(parsed.join(', '))
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  if (loading) return <div className="empty">{t('common.loading')}</div>
  return (
    <div className="card">
      <div className="hd">{t('languages.title')}</div>
      <div className="bd">
        <div className="field">
          <label className="lbl" htmlFor={`${formId}-languages`}>{t('languages.label')}</label>
          <input id={`${formId}-languages`} className="fld mono" value={input} onChange={e => setInput(e.target.value)} placeholder="de, en, fr" />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            {t('languages.hint')}
          </div>
        </div>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginBottom: 8 }}>{error}</div>}
        {saved && <div style={{ fontSize: 13, color: '#166534', marginBottom: 8 }}>{t('common.saved')}</div>}
        <button className="btn pri" onClick={save} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
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

  if (loading) return <div className="empty">{t('common.loading')}</div>
  return (
    <div className="card">
      <div className="hd">{t('presenceLock.title')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          {t('presenceLock.description')}
        </p>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, marginBottom: 10 }}>
          <input type="radio" name="presence_lock_mode" checked={mode === 'warning'} disabled={saving} onChange={() => save('warning')} style={{ marginTop: 3 }} />
          <span><strong>{t('presenceLock.warningLabel')}</strong> – {t('presenceLock.warningDescription')}</span>
        </label>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
          <input type="radio" name="presence_lock_mode" checked={mode === 'blocking'} disabled={saving} onChange={() => save('blocking')} style={{ marginTop: 3 }} />
          <span><strong>{t('presenceLock.blockingLabel')}</strong> – {t('presenceLock.blockingDescription')}</span>
        </label>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginTop: 10 }}>{error}</div>}
        {saved && <div style={{ fontSize: 13, color: '#166534', marginTop: 10 }}>{t('presenceLock.saved')}</div>}
      </div>
    </div>
  )
}

function SectionAutoPurge() {
  const { t } = useTranslation('screenSettings')
  const formId = useId()
  const [enabled, setEnabled] = useState(true)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminConfig.get()
      .then(cfg => { setEnabled(cfg.auto_purge_enabled); setDays(cfg.purge_retention_days) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function save(patch: { auto_purge_enabled?: boolean; purge_retention_days?: number }) {
    setSaving(true); setError(null); setSaved(false)
    try {
      const cfg = await adminConfig.update(patch)
      setEnabled(cfg.auto_purge_enabled); setDays(cfg.purge_retention_days)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  if (loading) return <div className="empty">{t('common.loading')}</div>
  return (
    <div className="card">
      <div className="hd">{t('autoPurge.title')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>
          {t('autoPurge.description')}
        </p>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={enabled}
            disabled={saving}
            onChange={e => { setEnabled(e.target.checked); save({ auto_purge_enabled: e.target.checked }) }}
            style={{ marginTop: 3 }}
          />
          <span>{t('autoPurge.enabledLabel')}</span>
        </label>
        <label className="lbl" htmlFor={`${formId}-days`}>{t('autoPurge.daysLabel')}</label>
        <input
          id={`${formId}-days`}
          className="fld mono"
          type="number"
          min={1}
          style={{ maxWidth: 120 }}
          value={days}
          disabled={saving || !enabled}
          onChange={e => setDays(Number(e.target.value))}
          onBlur={() => { if (days >= 1) save({ purge_retention_days: days }) }}
        />
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          {t('autoPurge.daysHint')}
        </div>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginTop: 10 }}>{error}</div>}
        {saved && <div style={{ fontSize: 13, color: '#166534', marginTop: 10 }}>{t('autoPurge.saved')}</div>}
      </div>
    </div>
  )
}

function SectionUsageStats() {
  const { t } = useTranslation('screenSettings')
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminConfig.get()
      .then(cfg => setEnabled(cfg.usage_stats_enabled))
      .catch((e: Error) => setError(e.message))
  }, [])

  async function save(value: boolean) {
    setSaving(true); setError(null)
    try {
      setEnabled((await adminConfig.update({ usage_stats_enabled: value })).usage_stats_enabled)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="hd">{t('usageStats.title')}</div>
      <div className="bd">
        <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 12 }}>{t('usageStats.description')}</p>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={enabled ?? false}
            disabled={saving || enabled === null}
            onChange={e => { void save(e.target.checked) }}
            style={{ marginTop: 3 }}
          />
          <span>{t('usageStats.enabledLabel')}</span>
        </label>
        {error && <div style={{ fontSize: 13, color: '#dc2626', marginTop: 10 }}>{error}</div>}
      </div>
    </div>
  )
}

const NAV: { id: Section; i18nKey: string; adminOnly?: boolean; feature?: string }[] = [
  { id: 'profil',   i18nKey: 'screenSettings:nav.profil' },
  { id: 'ueber',    i18nKey: 'screenSettings:nav.ueber' },
  { id: 'portal',   i18nKey: 'screenSettings:nav.portal', adminOnly: true },
  { id: 'fusszeile', i18nKey: 'portalLayout:nav', adminOnly: true },
  { id: 'startseite', i18nKey: 'screenSettings:startseite.nav', adminOnly: true },
  { id: 'terminologie', i18nKey: 'screenSettings:terminologie.nav', adminOnly: true },
  { id: 'facetten', i18nKey: 'screenSettings:nav.facetten', adminOnly: true },
  { id: 'sprachen', i18nKey: 'screenSettings:nav.sprachen', adminOnly: true },
  { id: 'idno',     i18nKey: 'screenSettings:nav.idno', adminOnly: true },
  { id: 'ki',       i18nKey: 'screenSettings:nav.ki', adminOnly: true },
  { id: 'medien',   i18nKey: 'screenSettings:nav.medien', adminOnly: true },
  { id: 'authorities', i18nKey: 'screenSettings:nav.authorities', adminOnly: true },
  { id: 'sperren',  i18nKey: 'screenSettings:nav.sperren', adminOnly: true },
  { id: 'papierkorb', i18nKey: 'screenSettings:nav.papierkorb', adminOnly: true },
  { id: 'suche',    i18nKey: 'screenSettings:search.title', adminOnly: true },
  { id: 'sparql',   i18nKey: 'screenSettings:sparql.nav', adminOnly: true },
  { id: 'gefahrenbereich', i18nKey: 'screenSettings:dangerZone.nav', adminOnly: true },
]

const SECTION_IDS = NAV.map(n => n.id)

function initialSection(): Section {
  const slash = window.location.hash.indexOf('/')
  const requested = slash === -1 ? null : window.location.hash.slice(slash + 1)
  return (requested && SECTION_IDS.includes(requested as Section)) ? requested as Section : 'profil'
}

export function ScreenSettings({ isAdmin, features, onStartTour, onNavigate }: Props) {
  const [section, setSection] = useState<Section>(initialSection)
  const { t: tNav } = useTranslation()
  const navLabel = (n: (typeof NAV)[number]) => tNav(n.i18nKey)
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
        <div><h1>{tNav('screenSettings:title')}</h1><div className="sub">{tNav('screenSettings:subtitle')}</div></div>
      </div>

      <div className="settings-layout">
        {/* Sidebar nav (desktop) */}
        <div className="settings-nav">
          {navItems.map(n => (
            <button key={n.id} className={`panel-it${section === n.id ? ' active' : ''}`} onClick={() => {
              setSection(n.id)
              window.history.replaceState(null, '', `#settings/${n.id}`)
            }}>
              {navLabel(n)}
            </button>
          ))}
        </div>

        {/* Section select (mobile) */}
        <div className="settings-select field">
          <label className="lbl" htmlFor="settings-section">{tNav('screenSettings:sectionLabel')}</label>
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
            {navItems.map(n => <option key={n.id} value={n.id}>{navLabel(n)}</option>)}
          </select>
        </div>

        {/* Content */}
        <div className="settings-content">
          {loading && <div className="empty">{tNav('screenSettings:common.loading')}</div>}
          {error && <div style={{ fontSize: 13, color: '#dc2626' }}>{error}</div>}
          {!loading && section === 'profil' && <SectionProfil onStartTour={isAdmin ? onStartTour : undefined} />}
          {!loading && section === 'ueber' && <SectionUeber />}
          {!loading && isAdmin && config && section === 'portal' && <><SectionPortal config={config} onSaved={setConfig} /><SectionUsageStats /></>}
          {!loading && isAdmin && config && section === 'fusszeile' && <SectionFooterNotice config={config} onSaved={setConfig} />}
          {!loading && isAdmin && config && section === 'startseite' && <SectionStartseite config={config} onSaved={setConfig} />}
          {!loading && isAdmin && config && section === 'terminologie' && <SectionTerminologie config={config} onSaved={setConfig} />}
          {!loading && isAdmin && config && section === 'facetten' && <SectionFacetten config={config} onSaved={setConfig} />}
          {!loading && isAdmin && section === 'sprachen' && <SectionLanguages />}
          {!loading && isAdmin && section === 'idno' && <SectionIdnoSchemas />}
          {!loading && isAdmin && section === 'ki' && <SectionAI />}
          {!loading && isAdmin && section === 'medien' && <SectionMediaRights />}
          {!loading && isAdmin && section === 'authorities' && <SectionAuthoritySources />}
          {!loading && isAdmin && section === 'sperren' && <SectionPresenceLock />}
          {!loading && isAdmin && section === 'papierkorb' && <SectionAutoPurge />}
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
          {!loading && isAdmin && section === 'gefahrenbereich' && <SectionDangerZone />}
        </div>
      </div>
    </div>
  )
}
