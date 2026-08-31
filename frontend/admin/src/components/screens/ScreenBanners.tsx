import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { bannersApi } from '../../api/client'
import type { Banner } from '../../types'
import { Bell, Edit, Plus, Trash } from '../ui/Icons'

const COLORS: { value: Banner['color']; label: string; bg: string; fg: string }[] = [
  { value: 'blue',   label: 'Blau',  bg: '#dbeafe', fg: '#1e40af' },
  { value: 'yellow', label: 'Gelb',  bg: '#fef9c3', fg: '#854d0e' },
  { value: 'red',    label: 'Rot',   bg: '#fee2e2', fg: '#991b1b' },
  { value: 'green',  label: 'Grün',  bg: '#dcfce7', fg: '#166534' },
]

const inp: React.CSSProperties = {
  width: '100%', border: '1px solid var(--border)', borderRadius: 6,
  padding: '7px 10px', fontSize: 13, background: 'var(--bg)', color: 'var(--fg)',
  outline: 'none', boxSizing: 'border-box',
}

interface FormState {
  message: string
  color: Banner['color']
  show_admin: boolean
  show_portal: boolean
  is_active: boolean
  expires_at: string
}

function emptyForm(): FormState {
  return { message: '', color: 'blue', show_admin: true, show_portal: true, is_active: true, expires_at: '' }
}

function bannerToForm(b: Banner): FormState {
  return {
    message: b.message,
    color: b.color,
    show_admin: b.show_admin,
    show_portal: b.show_portal,
    is_active: b.is_active,
    expires_at: b.expires_at ? b.expires_at.slice(0, 16) : '',
  }
}

function colorStyle(color: Banner['color']): React.CSSProperties {
  const c = COLORS.find(x => x.value === color)!
  return { background: c.bg, color: c.fg, borderRadius: 6, padding: '8px 14px', fontSize: 13, marginBottom: 4 }
}

export function ScreenBanners() {
  const { t } = useTranslation('screenBanners')
  const [banners, setBanners] = useState<Banner[]>([])
  const [loading, setLoading] = useState(true)
  const [editId, setEditId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    bannersApi.list().then(setBanners).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function startNew() {
    setIsNew(true)
    setEditId(null)
    setForm(emptyForm())
    setError(null)
  }

  function startEdit(b: Banner) {
    setIsNew(false)
    setEditId(b.id)
    setForm(bannerToForm(b))
    setError(null)
  }

  function cancel() {
    setIsNew(false)
    setEditId(null)
    setForm(null)
    setError(null)
  }

  async function save() {
    if (!form) return
    if (!form.message.trim()) { setError(t('messageRequired')); return }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        ...form,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      }
      if (isNew) {
        await bannersApi.create(payload)
      } else if (editId) {
        await bannersApi.update(editId, payload)
      }
      cancel()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('saveError'))
    } finally {
      setSaving(false)
    }
  }

  async function del(b: Banner) {
    if (!confirm(t('deleteConfirm'))) return
    await bannersApi.remove(b.id).catch(() => {})
    load()
  }

  async function toggle(b: Banner) {
    await bannersApi.update(b.id, { is_active: !b.is_active }).catch(() => {})
    load()
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(f => f ? { ...f, [key]: value } : f)
  }

  const now = new Date().toISOString()

  return (
    <div className="banners-page settings-page">
      <div className="settings-head" style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t('headline')}</h1>
        <button
          onClick={startNew}
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          <Plus size={14} /> {t('addButton')}
        </button>
      </div>

      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 24, lineHeight: 1.6 }}>
        {t('description')}
      </p>

      {(isNew || editId) && form && (
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 24, marginBottom: 24 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{isNew ? t('newBanner') : t('editBanner')}</h2>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('messageLabel')} <span style={{ color: '#dc2626' }}>*</span></label>
            <textarea
              style={{ ...inp, minHeight: 72, resize: 'vertical' }}
              value={form.message}
              onChange={e => set('message', e.target.value)}
              placeholder={t('messagePlaceholder')}
            />
          </div>

          <div className="fg-2" style={{ marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('colorLabel')}</label>
              <select style={{ ...inp }} value={form.color} onChange={e => set('color', e.target.value as Banner['color'])}>
                {COLORS.map(c => <option key={c.value} value={c.value}>{t('color' + c.value.charAt(0).toUpperCase() + c.value.slice(1))}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('expiresLabel')}</label>
              <input
                type="datetime-local"
                style={inp}
                value={form.expires_at}
                onChange={e => set('expires_at', e.target.value)}
              />
            </div>
          </div>

          {form.message && (
            <div style={{ ...colorStyle(form.color), marginBottom: 14 }}>
              <Bell size={14} style={{ marginRight: 6 }} />
              {form.message}
            </div>
          )}

          <div className="banner-form-checks">
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.show_admin} onChange={e => set('show_admin', e.target.checked)} />
              {t('showAdmin')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.show_portal} onChange={e => set('show_portal', e.target.checked)} />
              {t('showPortal')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} />
              {t('isActive')}
            </label>
          </div>

          {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={save}
              disabled={saving}
              style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
            >
              {saving ? t('saving') : t('save')}
            </button>
            <button onClick={cancel} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }}>
              {t('cancel')}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('loading')}</div>
      ) : banners.length === 0 ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13, padding: '32px 0', textAlign: 'center' }}>
          {t('empty')}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {banners.map(b => {
            const expired = b.expires_at != null && b.expires_at < now
            return (
              <div key={b.id} className="banner-row" style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', opacity: expired || !b.is_active ? 0.5 : 1 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ ...colorStyle(b.color), marginBottom: 6, display: 'inline-block', overflowWrap: 'anywhere' }}>
                    <Bell size={13} style={{ marginRight: 6 }} />
                    {b.message}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    {b.show_admin && <span>{t('adminTag')}</span>}
                    {b.show_portal && <span>{t('portalTag')}</span>}
                    {b.expires_at && <span>{t('expiresAt', { date: new Date(b.expires_at).toLocaleString('de-DE') })}</span>}
                    {expired && <span style={{ color: '#dc2626' }}>{t('expired')}</span>}
                    {!b.is_active && !expired && <span style={{ color: 'var(--fg-3)' }}>{t('inactive')}</span>}
                  </div>
                </div>
                <div className="banner-actions">
                  <button
                    onClick={() => toggle(b)}
                    title={b.is_active ? t('deactivate') : t('activate')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 10px', cursor: 'pointer', fontSize: 12, color: 'var(--fg-2)' }}
                  >
                    {b.is_active ? t('toggleOff') : t('toggleOn')}
                  </button>
                  <button
                    onClick={() => startEdit(b)}
                    title={t('editTitle')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}
                  >
                    <Edit size={14} />
                  </button>
                  <button
                    onClick={() => del(b)}
                    title={t('deleteTitle')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: '#dc2626', display: 'flex', alignItems: 'center' }}
                  >
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
