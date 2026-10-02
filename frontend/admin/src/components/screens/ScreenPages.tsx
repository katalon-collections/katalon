// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { staticPages, PORTAL_URL, PORTAL_ENABLED } from '../../api/client'
import type { PageAsset, StaticPage } from '../../api/client'
import { Check, FileText, Globe, Plus, Trash, Video } from '../ui/Icons'
import { ConfirmModal } from '../ui/ConfirmModal'

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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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
  const [confirmSlug, setConfirmSlug] = useState<string | null>(null)

  // Assets state
  const [assets, setAssets] = useState<PageAsset[]>([])
  const [assetsLoading, setAssetsLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [assetError, setAssetError] = useState<string | null>(null)
  const [confirmAsset, setConfirmAsset] = useState<PageAsset | null>(null)
  const [copiedAssetId, setCopiedAssetId] = useState<string | null>(null)
  const [lastFocusedField, setLastFocusedField] = useState<'de' | 'en'>('de')

  const contentDeRef = useRef<HTMLTextAreaElement>(null)
  const contentEnRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    setLoading(true)
    staticPages.list()
      .then(setPages)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const loadAssets = useCallback((slug: string) => {
    setAssetsLoading(true)
    setAssetError(null)
    staticPages.listAssets(slug)
      .then(setAssets)
      .catch((err: Error) => setAssetError(err.message))
      .finally(() => setAssetsLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!initialSlug || activeSlug) return
    const p = pages.find(p => p.slug === initialSlug)
    if (p) openPage(p)
  }, [pages, initialSlug])

  useEffect(() => {
    if (activeSlug && !isNew) {
      loadAssets(activeSlug)
    } else {
      setAssets([])
    }
  }, [activeSlug, isNew, loadAssets])

  function openNew() {
    setIsNew(true)
    setActiveSlug(null)
    setForm(emptyForm())
    setError(null)
    setAssetError(null)
    setAssets([])
  }

  function openPage(p: StaticPage) {
    setIsNew(false)
    setActiveSlug(p.slug)
    setForm(pageToForm(p))
    setError(null)
    setAssetError(null)
    onSlugChange?.(p.slug)
  }

  function close() {
    setActiveSlug(null)
    setIsNew(false)
    setForm(null)
    setAssets([])
    setAssetError(null)
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
        const created = await staticPages.create({ slug, ...payload })
        setPages(prev => [...prev.filter(p => p.slug !== slug), created])
        setIsNew(false)
        setActiveSlug(slug)
      } else {
        const updated = await staticPages.update(activeSlug!, payload)
        setPages(prev => prev.map(p => p.slug === activeSlug ? updated : p))
      }
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  function handleDelete(slug: string) {
    setConfirmSlug(slug)
  }

  async function confirmDelete() {
    const slug = confirmSlug!
    try {
      setPages(prev => prev.filter(p => p.slug !== slug))
      await staticPages.delete(slug)
      if (activeSlug === slug) close()
      load()
    } catch (e) {
      setError((e as Error).message)
      load()
    } finally {
      setConfirmSlug(null)
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0 || !activeSlug) return
    setUploading(true)
    setAssetError(null)
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        await staticPages.uploadAsset(activeSlug, file, (progress) => {
          setUploadProgress(progress)
        })
      }
      loadAssets(activeSlug)
    } catch (err) {
      setAssetError((err as Error).message)
    } finally {
      setUploading(false)
      setUploadProgress(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function getSnippet(asset: PageAsset): string {
    if (asset.mime_type.startsWith('image/')) {
      return `![${asset.filename}](${asset.url})`
    }
    if (asset.mime_type === 'video/mp4') {
      return `<video controls preload="metadata" style="max-width: 100%;"><source src="${asset.url}" type="video/mp4"></video>`
    }
    return `[${asset.filename} (PDF)](${asset.url})`
  }

  function handleInsertSnippet(asset: PageAsset) {
    const snippet = getSnippet(asset)
    const targetRef = lastFocusedField === 'en' ? contentEnRef.current : contentDeRef.current
    const fieldKey = lastFocusedField === 'en' ? 'content_en' : 'content_de'

    if (targetRef && form) {
      const start = targetRef.selectionStart ?? targetRef.value.length
      const end = targetRef.selectionEnd ?? targetRef.value.length
      const currentVal = form[fieldKey]
      const nextVal = currentVal.substring(0, start) + snippet + currentVal.substring(end)
      set(fieldKey, nextVal)
      setTimeout(() => {
        targetRef.focus()
        targetRef.setSelectionRange(start + snippet.length, start + snippet.length)
      }, 50)
    }

    navigator.clipboard.writeText(snippet).catch(() => {})
    setCopiedAssetId(asset.id)
    setTimeout(() => setCopiedAssetId(null), 2000)
  }

  async function confirmDeleteAssetAction() {
    if (!confirmAsset || !activeSlug) return
    try {
      await staticPages.deleteAsset(activeSlug, confirmAsset.id)
      setAssets(prev => prev.filter(a => a.id !== confirmAsset.id))
    } catch (err) {
      setAssetError((err as Error).message)
    } finally {
      setConfirmAsset(null)
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
                {!isNew && form.is_published && PORTAL_ENABLED && (
                  <a
                    href={`${PORTAL_URL}/page/${form.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn sm gh"
                    title={t('viewInPortal')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 8, textDecoration: 'none' }}
                  >
                    <Globe size={13} /> {t('viewInPortal')}
                  </a>
                )}
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
                  <textarea
                    ref={contentDeRef}
                    className="fld mono"
                    rows={10}
                    value={form.content_de}
                    onFocus={() => setLastFocusedField('de')}
                    onChange={e => set('content_de', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }}
                  />
                </div>
                <div className="field">
                  <div className="lbl">{t('contentEN')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('contentENHint')}</span></div>
                  <textarea
                    ref={contentEnRef}
                    className="fld mono"
                    rows={6}
                    value={form.content_en}
                    onFocus={() => setLastFocusedField('en')}
                    onChange={e => set('content_en', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }}
                  />
                </div>

                {/* Sektion Dateien & Medien */}
                <div className="field" style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-s)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div>
                      <div className="lbl" style={{ margin: 0 }}>{t('assetsHeadline')}</div>
                      <div style={{ color: 'var(--fg-3)', fontSize: 11, marginTop: 2 }}>{t('assetsSubtitle')}</div>
                    </div>
                    {!isNew && (
                      <div>
                        <input
                          type="file"
                          ref={fileInputRef}
                          style={{ display: 'none' }}
                          accept="image/jpeg,image/png,image/webp,image/gif,application/pdf,video/mp4"
                          multiple
                          onChange={e => handleUpload(e.target.files)}
                        />
                        <button
                          type="button"
                          className="btn sm"
                          onClick={() => fileInputRef.current?.click()}
                          disabled={uploading}
                        >
                          <Plus size={12} /> {uploading ? t('uploading') : t('uploadAsset')}
                        </button>
                      </div>
                    )}
                  </div>

                  {isNew ? (
                    <div style={{ padding: '12px 14px', background: 'var(--panel-sub, #f8fafc)', borderRadius: 6, fontSize: 12, color: 'var(--fg-3)' }}>
                      {t('assetsSaveFirst')}
                    </div>
                  ) : (
                    <>
                      {assetError && <div style={{ color: '#b91c1c', fontSize: 12, marginBottom: 8 }}>{assetError}</div>}
                      {uploading && uploadProgress !== null && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ height: 4, background: 'var(--border-s)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${Math.round(uploadProgress * 100)}%`, background: 'var(--accent)' }} />
                          </div>
                        </div>
                      )}
                      {assetsLoading && <div className="empty" style={{ padding: '16px 0', fontSize: 12 }}>{t('loadingAssets')}</div>}
                      {!assetsLoading && assets.length === 0 && (
                        <div
                          onDragOver={e => { e.preventDefault() }}
                          onDrop={e => { e.preventDefault(); handleUpload(e.dataTransfer.files) }}
                          style={{
                            padding: '24px 16px',
                            textAlign: 'center',
                            border: '1px dashed var(--border-s)',
                            borderRadius: 6,
                            fontSize: 12,
                            color: 'var(--fg-3)',
                            background: 'var(--panel-sub, #f8fafc)',
                          }}
                        >
                          {t('assetsEmpty')}
                        </div>
                      )}
                      {assets.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                          {assets.map(a => (
                            <div
                              key={a.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '8px 10px',
                                border: '1px solid var(--border-s)',
                                borderRadius: 6,
                                background: 'var(--panel, #fff)',
                              }}
                            >
                              <div style={{ width: 40, height: 40, flexShrink: 0, borderRadius: 4, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--panel-sub, #f1f5f9)' }}>
                                {a.mime_type.startsWith('image/') ? (
                                  <img src={a.url} alt={a.filename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                ) : a.mime_type === 'video/mp4' ? (
                                  <Video size={18} />
                                ) : (
                                  <FileText size={18} />
                                )}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.filename}>
                                  {a.filename}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                                  {formatFileSize(a.file_size)}
                                </div>
                              </div>
                              <button
                                type="button"
                                className="btn sm gh"
                                onClick={() => handleInsertSnippet(a)}
                                title={t('insertSnippetTitle')}
                                style={{ fontSize: 11, padding: '3px 8px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              >
                                {copiedAssetId === a.id ? <><Check size={11} /> {t('inserted')}</> : t('insertSnippet')}
                              </button>
                              <button
                                type="button"
                                className="btn sm ico gh dn"
                                onClick={() => setConfirmAsset(a)}
                                title={t('deleteAssetTitle', { filename: a.filename })}
                              >
                                <Trash size={12} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
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
      {confirmSlug !== null && (
        <ConfirmModal
          message={t('deleteConfirm', { slug: confirmSlug })}
          confirmLabel={t('delete')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={confirmDelete}
          onCancel={() => setConfirmSlug(null)}
        />
      )}
      {confirmAsset !== null && (
        <ConfirmModal
          message={t('deleteAssetConfirm', { filename: confirmAsset.filename })}
          confirmLabel={t('delete')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={confirmDeleteAssetAction}
          onCancel={() => setConfirmAsset(null)}
        />
      )}
    </div>
  )
}