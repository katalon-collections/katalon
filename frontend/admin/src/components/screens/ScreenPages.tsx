import { useState, useEffect, useCallback } from 'react'
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
  sort_order: number
}

function emptyForm(): FormState {
  return { slug: '', title_de: '', title_en: '', content_de: '', content_en: '', is_published: false, sort_order: 0 }
}

function pageToForm(p: StaticPage): FormState {
  return {
    slug: p.slug,
    title_de: p.title.de ?? '',
    title_en: p.title.en ?? '',
    content_de: p.content.de ?? '',
    content_en: p.content.en ?? '',
    is_published: p.is_published,
    sort_order: p.sort_order,
  }
}

export function ScreenPages() {
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
  }

  function close() {
    setActiveSlug(null)
    setIsNew(false)
    setForm(null)
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(f => f ? { ...f, [key]: value } : f)
  }

  async function handleSave() {
    if (!form) return
    if (!form.slug.trim()) { setError('Slug darf nicht leer sein.'); return }
    setSaving(true)
    setError(null)
    const payload = {
      title: { de: form.title_de, en: form.title_en },
      content: { de: form.content_de, en: form.content_en },
      is_published: form.is_published,
      sort_order: form.sort_order,
    }
    try {
      if (isNew) {
        await staticPages.create({ slug: form.slug.trim(), ...payload })
      } else {
        await staticPages.update(activeSlug!, payload)
      }
      close()
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(slug: string) {
    if (!window.confirm(`Seite "${slug}" wirklich löschen?`)) return
    try {
      await staticPages.delete(slug)
      if (activeSlug === slug) close()
      load()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Statische Seiten</h1><div className="sub">FAQ, Impressum, Über die Sammlung</div></div>
        <div className="right">
          <button className="btn pri" onClick={openNew}><Plus size={13} /> Neue Seite</button>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Seitenliste */}
        <div style={{ width: 260, flexShrink: 0, borderRight: '1px solid var(--border-s)', overflowY: 'auto' }}>
          {loading && <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>}
          {!loading && pages.length === 0 && <div className="empty">Keine Seiten.</div>}
          {pages.map(p => (
            <div
              key={p.slug}
              className="schema-list"
              style={{ display: 'block' }}
            >
              <div
                className={`item${activeSlug === p.slug ? ' active' : ''}`}
                onClick={() => openPage(p)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="nm">{p.title.de || p.slug}</div>
                  <div className="sub">{p.slug}{!p.is_published ? ' · Entwurf' : ''}</div>
                </div>
                <button
                  className="btn sm ico gh dn"
                  style={{ flexShrink: 0 }}
                  onClick={e => { e.stopPropagation(); handleDelete(p.slug) }}
                >
                  <Trash size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Editor */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {form ? (
            <div className="card" style={{ margin: '18px 24px' }}>
              <div className="hd">
                <span>{isNew ? 'Neue Seite' : (form.title_de || form.slug)}</span>
                {!isNew && <span className="sub">/{form.slug}</span>}
                <div className="grow" />
                <button className="btn sm" onClick={close}>Schließen</button>
              </div>
              <div className="bd">
                {error && <div style={{ marginBottom: 10, color: '#b91c1c', fontSize: 13 }}>{error}</div>}

                <div className="fg-2">
                  <div className="field">
                    <div className="lbl">Slug <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(URL-Pfad, z.B. impressum)</span></div>
                    <input className="fld mono" value={form.slug} onChange={e => set('slug', e.target.value)} disabled={!isNew} />
                  </div>
                  <div className="field" style={{ display: 'flex', gap: 16, flexDirection: 'row', paddingTop: 22 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                      <input type="checkbox" className="ck" checked={form.is_published} onChange={e => set('is_published', e.target.checked)} />
                      Veröffentlicht
                    </label>
                    <div className="field" style={{ margin: 0 }}>
                      <div className="lbl">Reihenfolge</div>
                      <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} style={{ width: 70 }} />
                    </div>
                  </div>
                </div>

                <div className="fg-2">
                  <div className="field">
                    <div className="lbl">Titel DE</div>
                    <input className="fld" value={form.title_de} onChange={e => set('title_de', e.target.value)} />
                  </div>
                  <div className="field">
                    <div className="lbl">Titel EN</div>
                    <input className="fld" value={form.title_en} onChange={e => set('title_en', e.target.value)} />
                  </div>
                </div>

                <div className="field">
                  <div className="lbl">Inhalt DE <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(Markdown)</span></div>
                  <textarea className="fld mono" rows={10} value={form.content_de} onChange={e => set('content_de', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
                </div>
                <div className="field">
                  <div className="lbl">Inhalt EN <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
                  <textarea className="fld mono" rows={6} value={form.content_en} onChange={e => set('content_en', e.target.value)}
                    style={{ resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button className="btn pri" onClick={handleSave} disabled={saving}>
                    {saving ? 'Speichert…' : 'Speichern'}
                  </button>
                  {!isNew && (
                    <button className="btn dn" onClick={() => handleDelete(activeSlug!)} disabled={saving}>
                      Löschen
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty" style={{ paddingTop: 60 }}>Seite auswählen oder neue anlegen.</div>
          )}
        </div>
      </div>
    </div>
  )
}
