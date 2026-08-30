import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { oaiSets } from '../../api/client'
import type { OAISet, OAISetPayload } from '../../api/client'
import { Plus, Trash, Edit } from '../ui/Icons'

function emptyPayload(): OAISetPayload {
  return { set_spec: '', set_name: '', filter_record_type: null, filter_q: null, filter_status: null, filter_metadata: {} }
}

function setToPayload(s: OAISet): OAISetPayload {
  return {
    set_spec: s.set_spec,
    set_name: s.set_name,
    filter_record_type: s.filter_record_type,
    filter_q: s.filter_q,
    filter_status: s.filter_status,
    filter_metadata: s.filter_metadata ?? {},
  }
}

const inp: React.CSSProperties = {
  width: '100%', border: '1px solid var(--border)', borderRadius: 6,
  padding: '7px 10px', fontSize: 13, background: 'var(--bg)', color: 'var(--fg)',
  outline: 'none', boxSizing: 'border-box',
}

export function ScreenOAISets() {
  const { t } = useTranslation('screenOAISets')
  const [sets, setSets] = useState<OAISet[]>([])
  const [loading, setLoading] = useState(true)
  const [editId, setEditId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<OAISetPayload | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const RECORD_TYPE_OPTIONS = [
    { value: '', label: t('recordTypes.') },
    { value: 'object', label: t('recordTypes.object') },
    { value: 'entity', label: t('recordTypes.entity') },
    { value: 'place', label: t('recordTypes.place') },
    { value: 'occurrence', label: t('recordTypes.occurrence') },
  ]

  const STATUS_OPTIONS = [
    { value: '', label: t('statuses.') },
    { value: 'draft', label: t('statuses.draft') },
    { value: 'internal', label: t('statuses.internal') },
    { value: 'public', label: t('statuses.public') },
  ]

  const load = useCallback(() => {
    setLoading(true)
    oaiSets.list().then(setSets).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function startNew() {
    setEditId(null)
    setIsNew(true)
    setForm(emptyPayload())
    setError(null)
  }

  function startEdit(s: OAISet) {
    setIsNew(false)
    setEditId(s.id)
    setForm(setToPayload(s))
    setError(null)
  }

  function cancel() {
    setEditId(null)
    setIsNew(false)
    setForm(null)
    setError(null)
  }

  async function save() {
    if (!form) return
    if (!form.set_spec.trim()) { setError(t('errorSetSpecRequired')); return }
    if (!form.set_name.trim()) { setError(t('errorNameRequired')); return }
    setSaving(true)
    setError(null)
    try {
      const payload: OAISetPayload = {
        ...form,
        filter_record_type: form.filter_record_type || null,
        filter_q: form.filter_q?.trim() || null,
        filter_status: form.filter_status || null,
      }
      if (isNew) {
        await oaiSets.create(payload)
      } else if (editId) {
        await oaiSets.update(editId, payload)
      }
      cancel()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('errorSave'))
    } finally {
      setSaving(false)
    }
  }

  async function del(s: OAISet) {
    if (!confirm(t('deleteConfirm', { name: s.set_name }))) return
    await oaiSets.delete(s.id).catch(() => {})
    load()
  }

  function field(key: keyof OAISetPayload, value: string | null) {
    setForm(f => f ? { ...f, [key]: value } : f)
  }

  const oaiUrl = new URL('/oai', window.location.origin).href

  return (
    <div className="settings-page settings-page-oai">
      <div className="settings-head" style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t('heading')}</h1>
        <button
          onClick={startNew}
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          <Plus size={14} /> {t('newSet')}
        </button>
      </div>

      <p className="settings-intro" style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 20, lineHeight: 1.6 }}>
        {t('endpointLabel')} <a href={oaiUrl} target="_blank" rel="noreferrer" style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>{oaiUrl}</a>
        <br />
        {t('description')}
      </p>

      {(isNew || editId) && form && (
        <div className="settings-card" style={{ marginTop: 0 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{isNew ? t('formHeadingNew') : t('formHeadingEdit')}</h2>

          <div className="fg-2" style={{ marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>
                {t('setSpecLabel')} <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <input
                style={inp}
                value={form.set_spec}
                onChange={e => field('set_spec', e.target.value.replace(/[^a-z0-9_-]/g, '-').toLowerCase())}
                placeholder={t('setSpecPlaceholder')}
              />
              <small style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('setSpecHint')}</small>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>
                {t('nameLabel')} <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <input
                style={inp}
                value={form.set_name}
                onChange={e => field('set_name', e.target.value)}
                placeholder={t('namePlaceholder')}
              />
            </div>
          </div>

          <div className="fg-3" style={{ marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('typeFilterLabel')}</label>
              <select style={{ ...inp }} value={form.filter_record_type ?? ''} onChange={e => field('filter_record_type', e.target.value || null)}>
                {RECORD_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('statusFilterLabel')}</label>
              <select style={{ ...inp }} value={form.filter_status ?? ''} onChange={e => field('filter_status', e.target.value || null)}>
                {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('searchQueryLabel')}</label>
              <input
                style={inp}
                value={form.filter_q ?? ''}
                onChange={e => field('filter_q', e.target.value)}
                placeholder={t('searchPlaceholder')}
              />
              <small style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('searchHint')}</small>
            </div>
          </div>

          {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

          <div className="settings-actions">
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
      ) : sets.length === 0 ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13, padding: '32px 0', textAlign: 'center' }}>
          {t('empty')}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sets.map(s => (
            <div key={s.id} className="schema-list" style={{ cursor: 'default' }}>
              <div className="item settings-list-item" style={{ cursor: 'default' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{s.set_name}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'monospace', marginTop: 2 }}>{s.set_spec}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {s.filter_record_type && <span>{t('typeDisplay', { label: RECORD_TYPE_OPTIONS.find(o => o.value === s.filter_record_type)?.label ?? s.filter_record_type })}</span>}
                    {s.filter_status && <span>{t('statusDisplay', { value: STATUS_OPTIONS.find(o => o.value === s.filter_status)?.label ?? s.filter_status })}</span>}
                    {s.filter_q && <span>{t('queryDisplay', { q: s.filter_q })}</span>}
                  </div>
                </div>
                <div className="settings-actions">
                  <button
                    onClick={() => startEdit(s)}
                    title={t('editTitle')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}
                  >
                    <Edit size={14} />
                  </button>
                  <button
                    onClick={() => del(s)}
                    title={t('deleteTitle')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: '#dc2626', display: 'flex', alignItems: 'center' }}
                  >
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}