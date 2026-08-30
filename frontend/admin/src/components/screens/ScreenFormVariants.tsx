import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { formVariants, schema, subtypes } from '../../api/client'
import type { FormVariantData } from '../../api/client'
import type { FieldDefinition, FormVariant } from '../../types'
import { Edit, Plus, Trash } from '../ui/Icons'
import { LabelEditor } from '../ui/LabelEditor'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

const TYPE_IDS = ['object', 'entity', 'place', 'occurrence', 'procedure']

type FormState = FormVariantData & { label: Record<string, string> }

function emptyForm(targetType: string, subtype: string): FormState {
  return { target_type: targetType, target_subtype: subtype || null, name: '', label: {}, field_names: [], is_default_global: false, sort_order: 0 }
}

function variantToForm(v: FormVariant): FormState {
  return {
    target_type: v.target_type,
    target_subtype: v.target_subtype,
    name: v.name,
    label: { ...v.label },
    field_names: v.field_names,
    is_default_global: v.is_default_global,
    sort_order: v.sort_order,
  }
}

function isVariantRequired(field: FieldDefinition): boolean {
  return field.is_required || (field.field_type === 'group' && field.children?.some(child => child.is_required) === true)
}

const inp: React.CSSProperties = {
  width: '100%', border: '1px solid var(--border)', borderRadius: 6,
  padding: '7px 10px', fontSize: 13, background: 'var(--bg)', color: 'var(--fg)',
  outline: 'none', boxSizing: 'border-box',
}

function parseInitial(path?: string | null): { type: string; subtype: string } {
  if (!path) return { type: 'object', subtype: '' }
  const [type, subtype = ''] = path.split('.')
  return TYPE_IDS.includes(type) ? { type, subtype } : { type: 'object', subtype: '' }
}

type Props = { initialPath?: string | null; onPathChange?: (path: string) => void }

export function ScreenFormVariants({ initialPath, onPathChange }: Props = {}) {
  const { t } = useTranslation('screenFormVariants')
  const initial = parseInitial(initialPath)
  const [activeType, setActiveType] = useState(initial.type)
  const [activeSubtype, setActiveSubtype] = useState(initial.subtype)
  const skipResetRef = useRef(true)
  const [subtypesList, setSubtypesList] = useState<{ name: string; label: Record<string, string> }[]>([])
  const [availableFields, setAvailableFields] = useState<FieldDefinition[]>([])
  const [variants, setVariants] = useState<FormVariant[]>([])
  const [loading, setLoading] = useState(true)
  const languages = useSupportedLanguages()
  const [editId, setEditId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const TYPES = [
    { id: 'object', label: t('types.object') },
    { id: 'entity', label: t('types.entity') },
    { id: 'place', label: t('types.place') },
    { id: 'occurrence', label: t('types.occurrence') },
    { id: 'procedure', label: t('types.procedure') },
  ]

  const ROLES: Record<string, string> = {
    admin: t('roles.admin'),
    editor: t('roles.editor'),
    cataloger: t('roles.cataloger'),
    viewer: t('roles.viewer'),
  }

  useEffect(() => {
    subtypes.list(activeType).then(list => setSubtypesList(list)).catch(() => setSubtypesList([]))
  }, [activeType])

  useEffect(() => {
    if (skipResetRef.current) { skipResetRef.current = false; return }
    setActiveSubtype('')
    setEditId(null)
    setIsNew(false)
    setForm(null)
  }, [activeType])

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      formVariants.list(activeType, activeSubtype || undefined),
      schema.list(activeType, activeSubtype || undefined),
    ])
      .then(([v, f]) => { setVariants(v); setAvailableFields(activeSubtype ? f : f.filter(field => field.target_subtype == null)) })
      .catch(() => { setVariants([]); setAvailableFields([]) })
      .finally(() => setLoading(false))
  }, [activeType, activeSubtype])

  useEffect(() => { load() }, [load])

  function startNew() {
    setEditId(null)
    setIsNew(true)
    const requiredNames = availableFields.filter(isVariantRequired).map(f => f.name)
    setForm({ ...emptyForm(activeType, activeSubtype), field_names: requiredNames })
    setError(null)
  }

  function startEdit(v: FormVariant) {
    setIsNew(false)
    setEditId(v.id)
    setForm(variantToForm(v))
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
    if (!form.name.trim()) { setError(t('errorNameRequired')); return }
    setSaving(true)
    setError(null)
    const payload: FormVariantData = {
      target_type: form.target_type,
      target_subtype: form.target_subtype || null,
      name: form.name,
      label: form.label,
      field_names: form.field_names,
      is_default_global: form.is_default_global,
      sort_order: form.sort_order,
    }
    try {
      if (isNew) await formVariants.create(payload)
      else if (editId) await formVariants.update(editId, payload)
      cancel()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('errorSave'))
    } finally {
      setSaving(false)
    }
  }

  async function del(v: FormVariant) {
    if (!confirm(t('deleteConfirm', { name: v.name }))) return
    await formVariants.delete(v.id).catch(() => {})
    load()
  }

  function toggleField(name: string) {
    const isRequired = availableFields.some(f => f.name === name && isVariantRequired(f))
    setForm(f => {
      if (!f) return f
      const names = f.field_names ?? []
      const included = names.includes(name)
      if (included && isRequired) return f
      return { ...f, field_names: included ? names.filter(n => n !== name) : [...names, name] }
    })
  }

  function moveField(name: string, dir: -1 | 1) {
    setForm(f => {
      if (!f) return f
      const names = [...(f.field_names ?? [])]
      const i = names.indexOf(name)
      const j = i + dir
      if (i < 0 || j < 0 || j >= names.length) return f
      ;[names[i], names[j]] = [names[j], names[i]]
      return { ...f, field_names: names }
    })
  }

  async function toggleRoleDefault(v: FormVariant, role: string) {
    const active = v.default_for_roles.includes(role)
    try {
      if (active) await formVariants.removeRoleDefault(v.id, role)
      else await formVariants.setRoleDefault(v.id, role)
      load()
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t('errorDeleteRoleDefault'))
    }
  }

  return (
    <div className="settings-page">
      <div className="settings-head" style={{ marginBottom: 8 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t('heading')}</h1>
        <button
          onClick={startNew}
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          <Plus size={14} /> {t('newVariant')}
        </button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 20, lineHeight: 1.6 }}>
        {t('description')}
      </p>

      <div className="tabs">
        {TYPES.map(t => (
          <button key={t.id} className={`tab${activeType === t.id ? ' active' : ''}`} onClick={() => { setActiveType(t.id); onPathChange?.(t.id) }}>
            {t.label}
          </button>
        ))}
      </div>

      {subtypesList.length > 0 && (
        <div style={{ margin: '14px 0' }}>
          <select style={{ ...inp, maxWidth: 260 }} value={activeSubtype} onChange={e => { setActiveSubtype(e.target.value); onPathChange?.(e.target.value ? `${activeType}.${e.target.value}` : activeType) }}>
            <option value="">{t('allGlobal')}</option>
            {subtypesList.map(s => <option key={s.name} value={s.name}>{s.label?.de || s.name}</option>)}
          </select>
        </div>
      )}

      {(isNew || editId) && form && (
        <div className="settings-card">
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{isNew ? t('formHeadingNew') : t('formHeadingEdit')}</h2>

          <div className="fg-2" style={{ marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>
                {t('nameLabel')} <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <input style={inp} value={form.name} onChange={e => setForm(f => f ? { ...f, name: e.target.value } : f)} placeholder={t('namePlaceholder')} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>{t('sortOrderLabel')}</label>
              <input type="number" style={inp} value={form.sort_order} onChange={e => setForm(f => f ? { ...f, sort_order: Number(e.target.value) } : f)} />
            </div>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--fg-2)' }}>{t('displayNameLabel')}</label>
            <div className="fg-2" style={{ gap: 10 }}>
              <LabelEditor
                languages={languages}
                value={form.label}
                onChange={(lang, val) => setForm(f => f ? { ...f, label: { ...f.label, [lang]: val } } : f)}
              />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" checked={form.is_default_global ?? false} onChange={e => setForm(f => f ? { ...f, is_default_global: e.target.checked } : f)} />
              {t('globalDefault')}
            </label>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--fg-2)' }}>{t('fieldListLabel')}</label>
            <div style={{ border: '1px solid var(--border)', borderRadius: 6, maxHeight: 260, overflowY: 'auto' }}>
              {(form.field_names ?? []).map(name => {
                const fd = availableFields.find(f => f.name === name)
                const required = fd ? isVariantRequired(fd) : false
                return (
                  <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>
                    <input type="checkbox" checked disabled={required} title={required ? t('requiredTooltip') : undefined} onChange={() => toggleField(name)} />
                    <span style={{ flex: 1, fontSize: 13 }}>{fd?.label.de ?? name}</span>
                    {required && <span style={{ fontSize: 11, color: '#dc2626' }}>{t('requiredBadge')}</span>}
                    <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'monospace' }}>{name}</span>
                    <button onClick={() => moveField(name, -1)} style={{ background: 'none', border: 0, cursor: 'pointer', color: 'var(--fg-3)' }}>↑</button>
                    <button onClick={() => moveField(name, 1)} style={{ background: 'none', border: 0, cursor: 'pointer', color: 'var(--fg-3)' }}>↓</button>
                  </div>
                )
              })}
              {availableFields.filter(f => !(form.field_names ?? []).includes(f.name)).map(f => (
                <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>
                  <input type="checkbox" checked={false} onChange={() => toggleField(f.name)} />
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--fg-3)' }}>{f.label.de ?? f.name}</span>
                  {isVariantRequired(f) && <span style={{ fontSize: 11, color: '#dc2626' }}>{t('requiredMissing')}</span>}
                  <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'monospace' }}>{f.name}</span>
                </div>
              ))}
              {availableFields.length === 0 && <div style={{ padding: 10, fontSize: 13, color: 'var(--fg-3)' }}>{t('noFields')}</div>}
            </div>
          </div>

          {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

          <div className="settings-actions">
            <button onClick={save} disabled={saving} style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
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
      ) : variants.length === 0 ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13, padding: '32px 0', textAlign: 'center' }}>
          {t('empty')}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {variants.map(v => (
            <div key={v.id} className="schema-list" style={{ cursor: 'default' }}>
              <div className="item settings-list-item" style={{ cursor: 'default', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {v.name}
                    {v.is_default_global && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--accent-ink)', background: 'var(--accent-50)', borderRadius: 4, padding: '1px 6px' }}>{t('globalDefaultBadge')}</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{t('fieldsCount', { n: v.field_names.length })}{v.target_subtype ? ` · ${t('subtype', { name: v.target_subtype })}` : ''}</div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 6 }}>
                    {Object.entries(ROLES).map(([role, label]) => (
                      <label key={role} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--fg-3)' }}>
                        <input type="checkbox" checked={v.default_for_roles.includes(role)} onChange={() => toggleRoleDefault(v, role)} />
                        {t('roleDefault', { label })}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="settings-actions">
                  <button onClick={() => startEdit(v)} title={t('editTitle')} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}>
                    <Edit size={14} />
                  </button>
                  <button onClick={() => del(v)} title={t('deleteTitle')} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: '#dc2626', display: 'flex', alignItems: 'center' }}>
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