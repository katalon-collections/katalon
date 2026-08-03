import { useState, useEffect, useCallback } from 'react'
import { formVariants, schema, subtypes } from '../../api/client'
import type { FormVariantData } from '../../api/client'
import type { FieldDefinition, FormVariant } from '../../types'
import { Edit, Plus, Trash } from '../ui/Icons'

const TYPES = [
  { id: 'object', label: 'Objekte' },
  { id: 'entity', label: 'Entitäten' },
  { id: 'place', label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
  { id: 'procedure', label: 'Vorgänge' },
]

const ROLES: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Redakteur',
  cataloger: 'Katalogisierer',
  viewer: 'Betrachter',
}

type FormState = FormVariantData & { label_de: string }

function emptyForm(targetType: string, subtype: string): FormState {
  return { target_type: targetType, target_subtype: subtype || null, name: '', label_de: '', field_names: [], is_default_global: false, sort_order: 0 }
}

function variantToForm(v: FormVariant): FormState {
  return {
    target_type: v.target_type,
    target_subtype: v.target_subtype,
    name: v.name,
    label_de: v.label.de ?? '',
    field_names: v.field_names,
    is_default_global: v.is_default_global,
    sort_order: v.sort_order,
  }
}

const inp: React.CSSProperties = {
  width: '100%', border: '1px solid var(--border)', borderRadius: 6,
  padding: '7px 10px', fontSize: 13, background: 'var(--bg)', color: 'var(--fg)',
  outline: 'none', boxSizing: 'border-box',
}

export function ScreenFormVariants() {
  const [activeType, setActiveType] = useState('object')
  const [activeSubtype, setActiveSubtype] = useState('')
  const [subtypesList, setSubtypesList] = useState<{ name: string; label: Record<string, string> }[]>([])
  const [availableFields, setAvailableFields] = useState<FieldDefinition[]>([])
  const [variants, setVariants] = useState<FormVariant[]>([])
  const [loading, setLoading] = useState(true)
  const [editId, setEditId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (activeType === 'procedure') { setSubtypesList([]); return }
    subtypes.list(activeType).then(list => setSubtypesList(list)).catch(() => setSubtypesList([]))
  }, [activeType])

  useEffect(() => {
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
      .then(([v, f]) => { setVariants(v); setAvailableFields(f) })
      .catch(() => { setVariants([]); setAvailableFields([]) })
      .finally(() => setLoading(false))
  }, [activeType, activeSubtype])

  useEffect(() => { load() }, [load])

  function startNew() {
    setEditId(null)
    setIsNew(true)
    // Required fields can never be hidden by a variant (backend enforces this
    // too) — pre-select them so the form starts in a savable state.
    const requiredNames = availableFields.filter(f => f.is_required).map(f => f.name)
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
    if (!form.name.trim()) { setError('Name ist erforderlich.'); return }
    setSaving(true)
    setError(null)
    const payload: FormVariantData = {
      target_type: form.target_type,
      target_subtype: form.target_subtype || null,
      name: form.name,
      label: { de: form.label_de },
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
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern.')
    } finally {
      setSaving(false)
    }
  }

  async function del(v: FormVariant) {
    if (!confirm(`Formularvariante "${v.name}" wirklich löschen?`)) return
    await formVariants.delete(v.id).catch(() => {})
    load()
  }

  function toggleField(name: string) {
    const isRequired = availableFields.find(f => f.name === name)?.is_required
    setForm(f => {
      if (!f) return f
      const names = f.field_names ?? []
      const included = names.includes(name)
      if (included && isRequired) return f // required fields can't be unchecked
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
      alert(e instanceof Error ? e.message : 'Fehler beim Setzen des Rollen-Defaults.')
    }
  }

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1000 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Formularvarianten</h1>
        <button
          onClick={startNew}
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          <Plus size={14} /> Neue Variante
        </button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 20, lineHeight: 1.6 }}>
        Varianten wählen und ordnen vorhandene Felder für Schnellerfassung, Vollerfassung oder workflow-spezifische Masken.
        Metadaten bleiben unabhängig von der gewählten Variante gespeichert.
      </p>

      <div className="tabs">
        {TYPES.map(t => (
          <button key={t.id} className={`tab${activeType === t.id ? ' active' : ''}`} onClick={() => setActiveType(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {subtypesList.length > 0 && (
        <div style={{ margin: '14px 0' }}>
          <select style={{ ...inp, maxWidth: 260 }} value={activeSubtype} onChange={e => setActiveSubtype(e.target.value)}>
            <option value="">Alle / Global</option>
            {subtypesList.map(s => <option key={s.name} value={s.name}>{s.label?.de || s.name}</option>)}
          </select>
        </div>
      )}

      {(isNew || editId) && form && (
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 24, margin: '16px 0 24px' }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{isNew ? 'Neue Variante' : 'Variante bearbeiten'}</h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>
                Name <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <input style={inp} value={form.name} onChange={e => setForm(f => f ? { ...f, name: e.target.value } : f)} placeholder="z.B. Schnellerfassung" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>Sortierung</label>
              <input type="number" style={inp} value={form.sort_order} onChange={e => setForm(f => f ? { ...f, sort_order: Number(e.target.value) } : f)} />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" checked={form.is_default_global ?? false} onChange={e => setForm(f => f ? { ...f, is_default_global: e.target.checked } : f)} />
              Globaler Default für diesen Typ/Subtyp
            </label>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--fg-2)' }}>Felder (Auswahl + Reihenfolge)</label>
            <div style={{ border: '1px solid var(--border)', borderRadius: 6, maxHeight: 260, overflowY: 'auto' }}>
              {(form.field_names ?? []).map(name => {
                const fd = availableFields.find(f => f.name === name)
                const required = fd?.is_required ?? false
                return (
                  <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>
                    <input type="checkbox" checked disabled={required} title={required ? 'Pflichtfeld — kann nicht ausgeblendet werden' : undefined} onChange={() => toggleField(name)} />
                    <span style={{ flex: 1, fontSize: 13 }}>{fd?.label.de ?? name}</span>
                    {required && <span style={{ fontSize: 11, color: '#dc2626' }}>Pflicht</span>}
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
                  {f.is_required && <span style={{ fontSize: 11, color: '#dc2626' }}>Pflicht — fehlt noch</span>}
                  <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'monospace' }}>{f.name}</span>
                </div>
              ))}
              {availableFields.length === 0 && <div style={{ padding: 10, fontSize: 13, color: 'var(--fg-3)' }}>Keine Felder für diesen Typ/Subtyp.</div>}
            </div>
          </div>

          {error && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={save} disabled={saving} style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
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
      ) : variants.length === 0 ? (
        <div style={{ color: 'var(--fg-3)', fontSize: 13, padding: '32px 0', textAlign: 'center' }}>
          Noch keine Formularvarianten für diesen Typ/Subtyp.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {variants.map(v => (
            <div key={v.id} className="schema-list" style={{ cursor: 'default' }}>
              <div className="item" style={{ cursor: 'default', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {v.name}
                    {v.is_default_global && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--accent-ink)', background: 'var(--accent-50)', borderRadius: 4, padding: '1px 6px' }}>Global-Default</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{v.field_names.length} Felder{v.target_subtype ? ` · Subtyp ${v.target_subtype}` : ''}</div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 6 }}>
                    {Object.entries(ROLES).map(([role, label]) => (
                      <label key={role} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--fg-3)' }}>
                        <input type="checkbox" checked={v.default_for_roles.includes(role)} onChange={() => toggleRoleDefault(v, role)} />
                        {label}-Default
                      </label>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button onClick={() => startEdit(v)} title="Bearbeiten" style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}>
                    <Edit size={14} />
                  </button>
                  <button onClick={() => del(v)} title="Löschen" style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: '#dc2626', display: 'flex', alignItems: 'center' }}>
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
