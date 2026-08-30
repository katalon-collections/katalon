import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { staticPages } from '../../api/client'
import type { StaticPage } from '../../api/client'
import { Plus, Trash } from '../ui/Icons'

type FormState = {
  slug: string
  title_de: string
  title_en: string
  content_de: string
  content_en: string
  is_published: boolean
  placement: 'header' | 'footer' | 'none'
  sort_order: number
}

function emptyForm(): FormState {
  return { slug: '', title_de: '', title_en: '', content_de: '', content_en: '', is_published: false, placement: 'footer', sort_order: 0 }
}

function pageToForm(p: StaticPage): FormState {
  return {
    slug: p.slug,
    title_de: p.title.de ?? '',
    title_en: p.title.en ?? '',
    content_de: p.content.de ?? '',
    content_en: p.content.en ?? '',
    is_published: p.is_published,
    placement: p.placement,
    sort_order: p.sort_order,
  }
}

type Props = { initialSlug?: string | null; onSlugChange?: (slug: string | null) => void }

export function ScreenPages({ initialSlug, onSlugChange }: Props = {}) {
  const { t } = useTranslation('screenPages')
  const [pages, setPages] = useState<StaticPage[]>([])
  const [loading, setLoading] = useState(true)
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    staticPages.list()
      .then(setPages)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!initialSlug || activeSlug) return
    const p = pages.find(p => p.slug === initialSlug)
    if (p) openPage(p)
  }, [pages, initialSlug])

  function openNew() {
    setIsNew(true)
    setActiveSlug(null)
    setForm(emptyForm())
    setError(null)
  }

  function openPage(p: StaticPage) {
    setIsNew(false)
    setActiveSlug(p.slug)
    setForm(pageToForm(p))
    setError(null)
    onSlugChange?.(p.slug)
  }

  function close() {
    setActiveSlug(null)
    setIsNew(false)
    setForm(null)
    onSlugChange?.(null)
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(f => f ? { ...f, [key]: value } : f)
  }

  async function handleSave() {
    if (!form) return
    if (!form.slug.trim()) { setError(t('errorSlugEmpty')); return }
    setSaving(true)
    setError(null)
    const payload = {
      title: { de: form.title_de, en: form.title_en },
      content: { de: form.content_de, en: form.content_en },
      is_published: form.is_published,
      placement: form.placement,
      sort_order: form.sort_order,
    }
    try {
      if (isNew) {
        const slug = form.slug.trim()
        await staticPages.create({ slug, ...payload })
        setIsNew(false)
        setActiveSlug(slug)
      } else {
        await staticPages.update(activeSlug!, payload)
      }
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(slug: string) {
    if (!window.confirm(t('deleteConfirm', { slug }))) return
    try {
      await staticPages.delete(slug)
      if (activeSlug === slug) close()
      load()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <div className={`pages-screen${form ? ' has-editor' : ''}`}>
      <div className="ph">
        <div><h1>{t('headline')}</h1><div className="sub">{t('subtitle')}</div></div>
        <div className="right">
          <button className="btn pri" onClick={openNew}><Plus size={13} /> {t('newPage')}</button>
        </div>
      </div>

      <div className="pages-layout">
        {/* Seitenliste */}
        <div className="pages-list">
          {loading && <div className="empty" style={{ paddingTop: 40 }}>{t('loading')}</div>}
          {!loading && pages.length === 0 && <div className="empty">{t('empty')}</div>}
          {pages.map(p => (
            <div
              key={p.slug}
              className="schema-list"
              style={{ display: 'block' }}
            >
              <div className={`item${activeSlug === p.slug ? ' active' : ''}`}>
                <button
                  type="button"
                  className="pages-open"
                  onClick={() => openPage(p)}
                  aria-label={t('openAria', { title: p.title.de || p.slug })}
                >
                  <div className="nm">{p.title.de || p.slug}</div>
                  <div className="sub">{p.slug}{!p.is_published ? t('draftSuffix') : ''}</div>
                </button>
                <button
                  className="btn sm ico gh dn"
                  style={{ flexShrink: 0 }}
                  onClick={() => handleDelete(p.slug)}
                  aria-label={t('deleteAria', { title: p.title.de || p.slug })}
                  title={t('deleteTitle', { title: p.title.de || p.slug })}
                >
                  <Trash size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Editor */}
        <div className="pages-editor">
          {form ? (
            <div className="card" style={{ margin: '18px 24px' }}>
              <div className="hd">
                <span>{isNew ? t('editorNew') : (form.title_de || form.slug)}</span>
                {!isNew && <span className="sub">/{form.slug}</span>}
                <div className="grow" />
                <button className="btn sm" onClick={close}>{t('close')}</button>
              </div>
              <div className="bd">
                {error && <div style={{ marginBottom: 10, color: '#b91c1c', fontSize: 13 }}>{error}</div>}

                <div className="fg-2">
                  <div className="field">
                    <div className="lbl">{t('slugLabel')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('slugHint')}</span></div>
                    <input className="fld mono" value={form.slug} onChange={e => set('slug', e.target.value)} disabled={!isNew} />
                  </div>
                  <div className="field" style={{ display: 'flex', gap: 16, flexDirection: 'row', paddingTop: 22 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                      <input type="checkbox" className="ck" checked={form.is_published} onChange={e => set('is_published', e.target.checked)} />
                      {t('published')}
                    </label>
                    <div className="field" style={{ margin: 0 }}>
                      <div className="lbl">{t('placementLabel')}</div>
                      <select className="fld" value={form.placement} onChange={e => set('placement', e.target.value as FormState['placement'])}>
                        <option value="footer">{t('placementFooter')}</option>
                        <option value="header">{t('placementHeader')}</option>
                        <option value="none">{t('placementNone')}</option>
                      </select>
                    </div>
                    <div className="field" style={{ margin: 0 }}>
                      <div className="lbl">{t('sortOrder')}</div>
                      <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} style={{ width: 70 }} />
                    </div>
                  </div>
                </div>

                <div className="fg-2">
                  <div className="field">
                    <div className="lbl">{t('titleDE')}</div>
                    <input className="fld" value={form.title_de} onChange={e => set('title_de', e.target.value)} />
                  </div>
                  <div className="field">
                    <div className="lbl">{t('titleEN')}</div>
                    <input className="fld" value={form.title_en} onChange={e => set('title_en', e.target.value)} />
                  </div>
                </div>

                <div className="field">
                  <div className="lbl">{t('contentDE')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('contentDEHint')}</span></div>
                  <textarea className="fld mono" rows={10} value={form.content_de} onChange={e => set('content_de', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
                </div>
                <div className="field">
                  <div className="lbl">{t('contentEN')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('contentENHint')}</span></div>
                  <textarea className="fld mono" rows={6} value={form.content_en} onChange={e => set('content_en', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button className="btn pri" onClick={handleSave} disabled={saving}>
                    {saving ? t('saving') : t('save')}
                  </button>
                  {!isNew && (
                    <button className="btn dn" onClick={() => handleDelete(activeSlug!)} disabled={saving}>
                      {t('delete')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty" style={{ paddingTop: 60 }}>{t('emptyEditor')}</div>
          )}
        </div>
      </div>
    </div>
  )
}