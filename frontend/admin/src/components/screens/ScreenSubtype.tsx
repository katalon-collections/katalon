import { useState, useEffect, useCallback } from 'react'
import { subtypes } from '../../api/client'
import type { RecordSubtype } from '../../types'
import { getLabel } from '../../types'
import { Edit, Plus, Trash, X } from '../ui/Icons'

const PRIMARY_TYPES = [
  { id: 'object',     label: 'Objekte' },
  { id: 'entity',     label: 'Entitäten' },
  { id: 'place',      label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
  { id: 'procedure',  label: 'Vorgänge' },
]

interface FormState {
  primary_type: string
  name: string
  label_de: string
  label_en: string
  sort_order: number
  is_default: boolean
}

function emptyForm(primaryType: string): FormState {
  return { primary_type: primaryType, name: '', label_de: '', label_en: '', sort_order: 0, is_default: false }
}

function subtypeToForm(s: RecordSubtype): FormState {
  return {
    primary_type: s.primary_type,
    name: s.name,
    label_de: s.label.de ?? '',
    label_en: s.label.en ?? '',
    sort_order: s.sort_order,
    is_default: s.is_default,
  }
}

export function ScreenSubtype() {
  const [activeType, setActiveType] = useState('object')
  const [items, setItems] = useState<RecordSubtype[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm('object'))
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

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
    if (!form.name.trim()) { setFormError('Interner Name ist erforderlich.'); return }
    setSaving(true)
    setFormError(null)
    try {
      const payload = {
        primary_type: form.primary_type,
        name: form.name.trim(),
        label: { de: form.label_de.trim(), en: form.label_en.trim() },
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
    if (!confirm(`Subtyp „${s.name}" wirklich löschen?`)) return
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
          <h1>Subtypen</h1>
          <div className="sub">Subtypen für Bestandsdaten und Vorgänge verwalten</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={openNew}><Plus size={13} /> Neuer Subtyp</button>
        </div>
      </div>

      <div className="tabs">
        {PRIMARY_TYPES.map(t => (
          <button
            key={t.id}
            className={`tab${activeType === t.id ? ' active' : ''}`}
            onClick={() => { setActiveType(t.id); setShowForm(false) }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div style={{ color: '#b91c1c', fontSize: 13, padding: '12px 24px 0' }}>{error}</div>}

      {showForm && (
        <div style={{ padding: '14px 24px 0' }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <b style={{ fontSize: 13 }}>{editId ? 'Subtyp bearbeiten' : 'Neuer Subtyp'}</b>
              <button className="btn gh" onClick={() => setShowForm(false)}><X size={14} /></button>
            </div>
            {formError && <div style={{ color: '#b91c1c', fontSize: 13, marginBottom: 10 }}>{formError}</div>}
            <div className="fg-2" style={{ marginBottom: 10 }}>
              <div className="field">
                <div className="lbl">Label DE</div>
                <input className="fld" value={form.label_de} onChange={e => set('label_de', e.target.value)} />
              </div>
              <div className="field">
                <div className="lbl">Label EN</div>
                <input className="fld" value={form.label_en} onChange={e => set('label_en', e.target.value)} />
              </div>
            </div>
            <div className="fg-2" style={{ marginBottom: 10 }}>
              <div className="field">
                <div className="lbl">Interner Name <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(wird nach dem Erstellen gesperrt)</span></div>
                <input className="fld mono" value={form.name} onChange={e => set('name', e.target.value)} disabled={!!editId} />
              </div>
              <div className="field">
                <div className="lbl">Sortierung</div>
                <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 14 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                <input type="checkbox" className="ck" checked={form.is_default} onChange={e => set('is_default', e.target.checked)} />
                Standard-Subtyp
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn pri" onClick={handleSave} disabled={saving}>{saving ? 'Speichern…' : 'Speichern'}</button>
              <button className="btn" onClick={() => setShowForm(false)}>Abbrechen</button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty">Lade…</div>
      ) : items.length === 0 ? (
        <div className="empty">
          <div style={{ marginBottom: 6 }}>Keine Subtypen für {PRIMARY_TYPES.find(t => t.id === activeType)?.label} definiert.</div>
          <button className="btn" onClick={openNew}><Plus size={13} /> Ersten Subtyp erstellen</button>
        </div>
      ) : (
        <div className="tw">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: '20%' }}>Name</th>
                <th>Label DE</th>
                <th>Label EN</th>
                <th style={{ width: 100, textAlign: 'center' }}>Standard</th>
                <th style={{ width: 90, textAlign: 'right' }}>Sortierung</th>
                <th className="col-act"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td><span className="mono" style={{ fontSize: 12 }}>{s.name}</span></td>
                  <td>{getLabel(s, '—')}</td>
                  <td>{s.label.en?.trim() || '—'}</td>
                  <td style={{ textAlign: 'center' }}>
                    {s.is_default && <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>Standard</span>}
                  </td>
                  <td style={{ textAlign: 'right', color: 'var(--fg-3)', fontSize: 12 }}>{s.sort_order}</td>
                  <td className="col-act">
                    <div className="row-actions">
                      <button className="btn ico gh" title="Bearbeiten" onClick={() => openEdit(s)}><Edit size={13} /></button>
                      <button className="btn ico gh dn" title="Löschen" onClick={() => handleDelete(s)}><Trash size={13} /></button>
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
