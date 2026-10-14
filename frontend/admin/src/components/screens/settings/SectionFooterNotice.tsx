// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { authorizedFetch, BASE, req } from '../../../api/client'
import { useSupportedLanguages } from '../../../hooks/useSupportedLanguages'
import type { FooterColumn, FooterConfig, FooterLink, FooterLogo, NoticeConfig, PortalConfigRead } from '../../../types'
import { LabelEditor } from '../../ui/LabelEditor'

const EMPTY_FOOTER: FooterConfig = { columns: [], bottom: { text: {}, links: [] } }
const EMPTY_NOTICE: NoticeConfig = { enabled: false, version: 1, title: {}, text: {}, accept_label: {} }

function newColumn(type: FooterColumn['type']): FooterColumn {
  return { type, title: {}, content: {}, links: [], include_footer_pages: false, logos: [] }
}

function MarkdownByLanguage({ languages, value, onChange, label }: {
  languages: string[]
  value: Record<string, string>
  onChange: (next: Record<string, string>) => void
  label: string
}) {
  return (
    <>
      {languages.map(lang => (
        <div className="field" key={lang}>
          <div className="lbl">{label} {lang.toUpperCase()}</div>
          <textarea
            className="fld"
            rows={4}
            value={value[lang] ?? ''}
            onChange={e => onChange({ ...value, [lang]: e.target.value })}
            style={{ resize: 'vertical', fontFamily: 'inherit' }}
          />
        </div>
      ))}
    </>
  )
}

function LinksEditor({ links, languages, onChange }: {
  links: FooterLink[]
  languages: string[]
  onChange: (next: FooterLink[]) => void
}) {
  const { t } = useTranslation('portalLayout')
  const update = (index: number, patch: Partial<FooterLink>) =>
    onChange(links.map((link, i) => (i === index ? { ...link, ...patch } : link)))
  return (
    <div>
      {links.map((link, index) => (
        <div key={index} style={{ border: '1px solid var(--border-s)', borderRadius: 6, padding: 10, marginBottom: 8 }}>
          <div className="fg-2">
            <LabelEditor
              languages={languages}
              value={link.label}
              labelPrefix={t('footer.linkLabel')}
              onChange={(lang, val) => update(index, { label: { ...link.label, [lang]: val } })}
            />
          </div>
          <div className="field">
            <div className="lbl">{t('footer.url')}</div>
            <input className="fld mono" value={link.url} onChange={e => update(index, { url: e.target.value })} placeholder="https://…" />
          </div>
          <button type="button" className="btn sm gh" onClick={() => onChange(links.filter((_, i) => i !== index))}>{t('footer.removeLink')}</button>
        </div>
      ))}
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 6 }}>{t('footer.urlHint')}</div>
      <button type="button" className="btn sm" onClick={() => onChange([...links, { label: {}, url: '' }])}>{t('footer.addLink')}</button>
    </div>
  )
}

function LogosEditor({ logos, languages, onChange, onError }: {
  logos: FooterLogo[]
  languages: string[]
  onChange: (next: FooterLogo[]) => void
  onError: (message: string) => void
}) {
  const { t } = useTranslation('portalLayout')
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploadFor, setUploadFor] = useState<number | null>(null)
  const update = (index: number, patch: Partial<FooterLogo>) =>
    onChange(logos.map((logo, i) => (i === index ? { ...logo, ...patch } : logo)))

  async function upload(file: File) {
    if (uploadFor === null) return
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await authorizedFetch(`${BASE}/v1/portal/footer-assets`, { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? `Error ${res.status}`)
      }
      const { url } = await res.json() as { url: string }
      update(uploadFor, { src: url })
    } catch (e) {
      onError((e as Error).message)
    } finally {
      setUploadFor(null)
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        style={{ display: 'none' }}
        onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }}
      />
      {logos.map((logo, index) => (
        <div key={index} style={{ border: '1px solid var(--border-s)', borderRadius: 6, padding: 10, marginBottom: 8 }}>
          <div className="field">
            <div className="lbl">{t('footer.logoSrc')}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {logo.src && <img src={logo.src} alt="" style={{ height: 36, maxWidth: 120, objectFit: 'contain', background: '#fff', border: '1px solid var(--border-s)', borderRadius: 4, padding: 2 }} />}
              <input className="fld mono" style={{ flex: 1, minWidth: 200 }} value={logo.src} onChange={e => update(index, { src: e.target.value })} />
              <button
                type="button"
                className="btn sm gh"
                disabled={uploadFor !== null}
                onClick={() => { setUploadFor(index); inputRef.current?.click() }}
              >
                {uploadFor === index ? t('footer.uploading') : t('footer.upload')}
              </button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('footer.uploadHint')}</div>
          </div>
          <div className="fg-2">
            <LabelEditor
              languages={languages}
              value={logo.alt}
              labelPrefix={t('footer.logoAlt')}
              onChange={(lang, val) => update(index, { alt: { ...logo.alt, [lang]: val } })}
            />
          </div>
          <div className="field">
            <div className="lbl">{t('footer.logoHref')}</div>
            <input className="fld mono" value={logo.href ?? ''} onChange={e => update(index, { href: e.target.value || null })} placeholder="https://…" />
          </div>
          <button type="button" className="btn sm gh" onClick={() => onChange(logos.filter((_, i) => i !== index))}>{t('footer.removeLogo')}</button>
        </div>
      ))}
      <button type="button" className="btn sm" onClick={() => onChange([...logos, { src: '', alt: {}, href: null }])}>{t('footer.addLogo')}</button>
    </div>
  )
}

/** Settings → Footer & notice: footer columns and bottom line, one-time usage notice. */
export function SectionFooterNotice({ config, onSaved }: { config: PortalConfigRead; onSaved: (c: PortalConfigRead) => void }) {
  const { t } = useTranslation('portalLayout')
  const languages = useSupportedLanguages()
  const [footer, setFooter] = useState<FooterConfig>(() => ({ ...EMPTY_FOOTER, ...(config.footer ?? {}) }))
  const [notice, setNotice] = useState<NoticeConfig>(() => ({ ...EMPTY_NOTICE, ...(config.notice ?? {}) }))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateColumn = (index: number, patch: Partial<FooterColumn>) =>
    setFooter(f => ({ ...f, columns: f.columns.map((c, i) => (i === index ? { ...c, ...patch } : c)) }))
  const moveColumn = (index: number, delta: number) =>
    setFooter(f => {
      const next = [...f.columns]
      const [moved] = next.splice(index, 1)
      next.splice(index + delta, 0, moved)
      return { ...f, columns: next }
    })

  async function handleSave() {
    setSaving(true); setSaved(false); setError(null)
    try {
      const c = await req<PortalConfigRead>(`${BASE}/v1/portal/config`, {
        method: 'PUT',
        body: JSON.stringify({ footer, notice }),
      })
      onSaved(c)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  return (
    <div>
      {error && <div role="alert" style={{ fontSize: 13, color: '#b91c1c', marginBottom: 12 }}>{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('footer.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginTop: 0 }}>{t('footer.hint')}</p>
          {footer.columns.map((column, index) => (
            <div key={index} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                  {t('footer.columnType')}
                  <select className="fld" value={column.type} onChange={e => updateColumn(index, { type: e.target.value as FooterColumn['type'] })}>
                    {(['text', 'links', 'logos'] as const).map(type => <option key={type} value={type}>{t(`footer.type.${type}`)}</option>)}
                  </select>
                </label>
                <span style={{ flex: 1 }} />
                <button type="button" className="btn sm ico gh" disabled={index === 0} onClick={() => moveColumn(index, -1)} aria-label={t('footer.moveUp')}>↑</button>
                <button type="button" className="btn sm ico gh" disabled={index === footer.columns.length - 1} onClick={() => moveColumn(index, 1)} aria-label={t('footer.moveDown')}>↓</button>
                <button type="button" className="btn sm gh" onClick={() => setFooter(f => ({ ...f, columns: f.columns.filter((_, i) => i !== index) }))}>{t('footer.removeColumn')}</button>
              </div>
              <div className="fg-2">
                <LabelEditor
                  languages={languages}
                  value={column.title}
                  labelPrefix={t('footer.columnTitle')}
                  onChange={(lang, val) => updateColumn(index, { title: { ...column.title, [lang]: val } })}
                />
              </div>
              {column.type === 'text' && (
                <MarkdownByLanguage languages={languages} value={column.content} label={t('footer.content')} onChange={content => updateColumn(index, { content })} />
              )}
              {column.type === 'links' && (
                <>
                  <LinksEditor languages={languages} links={column.links} onChange={links => updateColumn(index, { links })} />
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 10 }}>
                    <input type="checkbox" className="ck" checked={column.include_footer_pages} onChange={e => updateColumn(index, { include_footer_pages: e.target.checked })} />
                    {t('footer.includeFooterPages')}
                  </label>
                </>
              )}
              {column.type === 'logos' && (
                <LogosEditor languages={languages} logos={column.logos} onChange={logos => updateColumn(index, { logos })} onError={setError} />
              )}
            </div>
          ))}
          <button type="button" className="btn sm" onClick={() => setFooter(f => ({ ...f, columns: [...f.columns, newColumn('text')] }))} disabled={footer.columns.length >= 6}>
            {t('footer.addColumn')}
          </button>

          <h4 style={{ fontSize: 13, fontWeight: 600, margin: '20px 0 6px' }}>{t('footer.bottom')}</h4>
          <MarkdownByLanguage languages={languages} value={footer.bottom.text} label={t('footer.bottomText')} onChange={text => setFooter(f => ({ ...f, bottom: { ...f.bottom, text } }))} />
          <LinksEditor languages={languages} links={footer.bottom.links} onChange={links => setFooter(f => ({ ...f, bottom: { ...f.bottom, links } }))} />
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('notice.title')}</div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-3)', marginTop: 0 }}>{t('notice.hint')}</p>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 10 }}>
            <input type="checkbox" className="ck" checked={notice.enabled} onChange={e => setNotice(n => ({ ...n, enabled: e.target.checked }))} />
            {t('notice.enabled')}
          </label>
          <div className="fg-2">
            <LabelEditor languages={languages} value={notice.title} labelPrefix={t('notice.dialogTitle')} onChange={(lang, val) => setNotice(n => ({ ...n, title: { ...n.title, [lang]: val } }))} />
          </div>
          <MarkdownByLanguage languages={languages} value={notice.text} label={t('notice.text')} onChange={text => setNotice(n => ({ ...n, text }))} />
          <div className="fg-2">
            <LabelEditor languages={languages} value={notice.accept_label} labelPrefix={t('notice.acceptLabel')} onChange={(lang, val) => setNotice(n => ({ ...n, accept_label: { ...n.accept_label, [lang]: val } }))} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('notice.version', { version: notice.version })}</span>
            <button type="button" className="btn sm gh" onClick={() => setNotice(n => ({ ...n, version: n.version + 1 }))}>{t('notice.showAgain')}</button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('notice.showAgainHint')}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('saving') : t('save')}</button>
        {saved && <span style={{ fontSize: 13, color: '#166534', alignSelf: 'center' }}>{t('saved')}</span>}
      </div>
    </div>
  )
}
