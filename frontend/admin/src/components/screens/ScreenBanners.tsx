import { useCallback, useEffect, useState } from 'react'
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
    if (!form.message.trim()) { setError('Nachricht ist erforderlich.'); return }
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
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern.')
    } finally {
      setSaving(false)
    }
  }

  async function del(b: Banner) {
    if (!confirm(`Banner wirklich löschen?`)) return
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
    <div style={{ padding: '32px 40px', maxWidth: 860 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Banner</h1>
        <button
          onClick={startNew}
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          <Plus size={14} /> Neuer Banner
        </button>
      </div>

      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 24, lineHeight: 1.6 }}>
        Banner werden oben in der Admin-Oberfläche und/oder im öffentlichen Portal angezeigt.
        Sie können unabhängig aktiviert, deaktiviert und mit einem Ablaufdatum versehen werden.
      </p>

      {(isNew || editId) && form && (
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 24, marginBottom: 24 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{isNew ? 'Neuer Banner' : 'Banner bearbeiten'}</h2>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>
              Nachricht <span style={{ color: '#dc2626' }}>*</span>
            </label>
            <textarea
              style={{ ...inp, minHeight: 72, resize: 'vertical' }}
              value={form.message}
              onChange={e => set('message', e.target.value)}
              placeholder="z.B. Das System ist am Sonntag von 10–12 Uhr für Wartungsarbeiten nicht erreichbar."
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>Farbe</label>
              <select style={{ ...inp }} value={form.color} onChange={e => set('color', e.target.value as Banner['color'])}>
                {COLORS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>Ablaufdatum (optional)</label>
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

          <div style={{ display: 'flex', gap: 20, marginBottom: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.show_admin} onChange={e => set('show_admin', e.target.checked)} />
              Im Admin anzeigen
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.show_portal} onChange={e => set('show_portal', e.target.checked)} />
              Im Portal anzeigen
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} />
              Aktiv
            </label>
          </div>

          {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={save}
              disabled={saving}
              style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
            >
              {saving ? 'Speichere…' : 'Speichern'}
            </button>
            <button onClick={cancel} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }}>
              Abbrechen
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>Lade…</div>
      ) : banners.length === 0 ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13, padding: '32px 0', textAlign: 'center' }}>
          Noch keine Banner konfiguriert.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {banners.map(b => {
            const expired = b.expires_at != null && b.expires_at < now
            return (
              <div key={b.id} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', display: 'flex', alignItems: 'flex-start', gap: 12, opacity: expired || !b.is_active ? 0.5 : 1 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ ...colorStyle(b.color), marginBottom: 6, display: 'inline-block' }}>
                    <Bell size={13} style={{ marginRight: 6 }} />
                    {b.message}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    {b.show_admin && <span>Admin</span>}
                    {b.show_portal && <span>Portal</span>}
                    {b.expires_at && <span>Läuft ab: {new Date(b.expires_at).toLocaleString('de-DE')}</span>}
                    {expired && <span style={{ color: '#dc2626' }}>Abgelaufen</span>}
                    {!b.is_active && !expired && <span style={{ color: 'var(--fg-3)' }}>Inaktiv</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => toggle(b)}
                    title={b.is_active ? 'Deaktivieren' : 'Aktivieren'}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 10px', cursor: 'pointer', fontSize: 12, color: 'var(--fg-2)' }}
                  >
                    {b.is_active ? 'Aus' : 'An'}
                  </button>
                  <button
                    onClick={() => startEdit(b)}
                    title="Bearbeiten"
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}
                  >
                    <Edit size={14} />
                  </button>
                  <button
                    onClick={() => del(b)}
                    title="Löschen"
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
