import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { subtypes } from '../../api/client'
import type { RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { Edit, Plus, Trash, X } from '../ui/Icons'
import { LabelEditor } from '../ui/LabelEditor'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

const TYPE_IDS: readonly string[] = ['object', 'entity', 'place', 'occurrence', 'procedure']

interface FormState {
  primary_type: string
  name: string
  label: Record<string, string>
  description: string
  sort_order: number
  is_default: boolean
}

function emptyForm(primaryType: string): FormState {
  return { primary_type: primaryType, name: '', label: {}, description: '', sort_order: 0, is_default: false }
}

function subtypeToForm(s: RecordSubtype): FormState {
  return {
    primary_type: s.primary_type,
    name: s.name,
    label: { ...s.label },
    description: s.description ?? '',
    sort_order: s.sort_order,
    is_default: s.is_default,
  }
}

type Props = { initialType?: string | null; onTypeChange?: (type: string) => void }

export function ScreenSubtype({ initialType, onTypeChange }: Props = {}) {
  const { t } = useTranslation('screenSubtype')
  const [activeType, setActiveType] = useState(initialType && TYPE_IDS.includes(initialType) ? initialType : 'object')
  const [items, setItems] = useState<RecordSubtype[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm('object'))
  const [saving, setSaving] = useState(false)
  const languages = useSupportedLanguages()
  const [formError, setFormError] = useState<string | null>(null)

  const primaryTypes = useMemo(() => [
    { id: 'object',     label: t('typeObject') },
    { id: 'entity',     label: t('typeEntity') },
    { id: 'place',      label: t('typePlace') },
    { id: 'occurrence', label: t('typeOccurrence') },
    { id: 'procedure',  label: t('typeProcedure') },
  ], [t])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await subtypes.list(activeType))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [activeType])

  useEffect(() => { load() }, [load])

  function openNew() {
    setEditId(null)
    setForm(emptyForm(activeType))
    setFormError(null)
    setShowForm(true)
  }

  function openEdit(s: RecordSubtype) {
    setEditId(s.id)
    setForm(subtypeToForm(s))
    setFormError(null)
    setShowForm(true)
  }

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm(f => ({ ...f, [k]: v }))
  }

  async function handleSave() {
    if (!form.name.trim()) { setFormError(t('errorNameRequired')); return }
    setSaving(true)
    setFormError(null)
    try {
      const payload = {
        primary_type: form.primary_type,
        name: form.name.trim(),
        label: form.label,
        description: form.description.trim(),
        sort_order: form.sort_order,
        is_default: form.is_default,
      }
      if (editId) {
        await subtypes.update(editId, payload)
      } else {
        await subtypes.create(payload)
      }
      setShowForm(false)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(s: RecordSubtype) {
    if (!confirm(t('deleteConfirm', { name: s.name }))) return
    try {
      await subtypes.delete(s.id)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>{t('headline')}</h1>
          <div className="sub">{t('subtitle')}</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={openNew}><Plus size={13} /> {t('addButton')}</button>
        </div>
      </div>

      <div className="tabs">
        {primaryTypes.map(tp => (
          <button
            key={tp.id}
            className={`tab${activeType === tp.id ? ' active' : ''}`}
            onClick={() => { setActiveType(tp.id); setShowForm(false); onTypeChange?.(tp.id) }}
          >
            {tp.label}
          </button>
        ))}
      </div>

      {error && <div style={{ color: '#b91c1c', fontSize: 13, padding: '12px 24px 0' }}>{error}</div>}

      {showForm && (
        <div style={{ padding: '14px 24px 0' }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <b style={{ fontSize: 13 }}>{editId ? t('editFormHeading') : t('newFormHeading')}</b>
              <button className="btn gh" onClick={() => setShowForm(false)}><X size={14} /></button>
            </div>
            {formError && <div style={{ color: '#b91c1c', fontSize: 13, marginBottom: 10 }}>{formError}</div>}
            <div className="fg-2" style={{ marginBottom: 10 }}>
              <LabelEditor
                languages={languages}
                value={form.label}
                onChange={(lang, val) => set('label', { ...form.label, [lang]: val })}
              />
            </div>
            <div className="field" style={{ marginBottom: 10 }}>
              <div className="lbl">{t('descriptionLabel')}</div>
              <textarea
                className="fld"
                value={form.description}
                onChange={e => set('description', e.target.value)}
                rows={3}
                placeholder={t('descriptionPlaceholder')}
                style={{ height: 'auto', padding: '8px 10px', resize: 'vertical' }}
              />
            </div>
            <div className="fg-2" style={{ marginBottom: 10 }}>
              <div className="field">
                <div className="lbl">{t('internalNameLabel')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>({t('internalNameHint')})</span></div>
                <input className="fld mono" value={form.name} onChange={e => set('name', e.target.value)} disabled={!!editId} />
              </div>
              <div className="field">
                <div className="lbl">{t('sortOrderLabel')}</div>
                <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 14 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                <input type="checkbox" className="ck" checked={form.is_default} onChange={e => set('is_default', e.target.checked)} />
                {t('defaultCheckbox')}
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? t('saving') : t('save')}</button>
              <button className="btn" onClick={() => setShowForm(false)}>{t('cancel')}</button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty">{t('loading')}</div>
      ) : items.length === 0 ? (
        <div className="empty">
          <div style={{ marginBottom: 6 }}>{t('emptyNoSubtypes', { type: primaryTypes.find(tp => tp.id === activeType)?.label })}</div>
          <button className="btn" onClick={openNew}><Plus size={13} /> {t('emptyCreateFirst')}</button>
        </div>
      ) : (
        <div className="tw">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: '20%' }}>{t('tableName')}</th>
                <th>{t('tableLabel')}</th>
                <th>{t('tableDescription')}</th>
                <th style={{ width: 100, textAlign: 'center' }}>{t('tableDefault')}</th>
                <th style={{ width: 90, textAlign: 'right' }}>{t('tableSortOrder')}</th>
                <th className="col-act"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td><span className="mono" style={{ fontSize: 12 }}>{s.name}</span></td>
                  <td>{getLabel(s, '—')}</td>
                  <td style={{ color: 'var(--fg-2)', maxWidth: 340 }}>{s.description?.trim() || '—'}</td>
                  <td style={{ textAlign: 'center' }}>
                    {s.is_default && <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{t('defaultBadge')}</span>}
                  </td>
                  <td style={{ textAlign: 'right', color: 'var(--fg-3)', fontSize: 12 }}>{s.sort_order}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button className="btn ico gh" title={t('editButtonTitle')} onClick={() => openEdit(s)}><Edit size={13} /></button>
                      <button className="btn ico gh dn" title={t('deleteButtonTitle')} onClick={() => handleDelete(s)}><Trash size={13} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}