import { useState, useEffect, useCallback } from 'react'
import { schema } from '../../api/client'
import type { FieldDefinition } from '../../types'
import { Edit, Grip, Plus, Trash } from '../ui/Icons'

const TYPES = [
  { id: 'object',      label: 'Objekte',     key: 'object' },
  { id: 'entity',      label: 'Entitäten',   key: 'entity' },
  { id: 'place',       label: 'Orte',        key: 'place' },
  { id: 'occurrence',  label: 'Occurrences', key: 'occurrence' },
]

const SUBTYPE_TYPES = new Set(['entity', 'occurrence'])

const FIELD_TYPES = ['text', 'richtext', 'date', 'number', 'boolean', 'vocab', 'relation', 'geo', 'pid'] as const
const FIELD_TYPE_LABELS: Record<string, string> = {
  text: 'Text', richtext: 'Richtext', date: 'Datum', number: 'Zahl',
  boolean: 'Boolean', vocab: 'Vokabular', relation: 'Relation', geo: 'Geodaten', pid: 'PID',
}

type FieldFormState = {
  target_type: string
  target_subtype: string
  name: string
  label_de: string
  label_en: string
  field_type: string
  is_required: boolean
  is_repeatable: boolean
  sort_order: number
}

function emptyForm(targetType: string, sortOrder: number, subtype: string): FieldFormState {
  return { target_type: targetType, target_subtype: subtype, name: '', label_de: '', label_en: '', field_type: 'text', is_required: false, is_repeatable: false, sort_order: sortOrder }
}

function fieldToForm(f: FieldDefinition): FieldFormState {
  return {
    target_type: f.target_type,
    target_subtype: f.target_subtype ?? '',
    name: f.name,
    label_de: f.label.de ?? '',
    label_en: f.label.en ?? '',
    field_type: f.field_type,
    is_required: f.is_required,
    is_repeatable: f.is_repeatable,
    sort_order: f.sort_order,
  }
}

interface FieldDetailProps {
  form: FieldFormState
  isNew: boolean
  saving: boolean
  error: string | null
  showSubtype: boolean
  onChange: (form: FieldFormState) => void
  onSave: () => void
  onDelete: () => void
  onClose: () => void
}

function FieldDetail({ form, isNew, saving, error, showSubtype, onChange, onSave, onDelete, onClose }: FieldDetailProps) {
  function set<K extends keyof FieldFormState>(key: K, value: FieldFormState[K]) {
    onChange({ ...form, [key]: value })
  }

  return (
    <div className="card" style={{ margin: '18px 24px' }}>
      <div className="hd">
        <span>{isNew ? 'Neues Feld' : (form.label_de || form.name)}</span>
        {!isNew && <span className="sub">{form.name}</span>}
        <div className="grow" />
        <button className="btn sm" onClick={onClose}>Schließen</button>
      </div>
      <div className="bd">
        {error && <div style={{ marginBottom: 10, color: '#b91c1c', fontSize: 13 }}>{error}</div>}
        <div className="fg-2">
          <div className="field">
            <div className="lbl">Label DE</div>
            <input className="fld" value={form.label_de} onChange={e => set('label_de', e.target.value)} />
          </div>
          <div className="field">
            <div className="lbl">Label EN</div>
            <input className="fld" value={form.label_en} onChange={e => set('label_en', e.target.value)} />
          </div>
        </div>
        <div className="fg-2">
          <div className="field">
            <div className="lbl">Interner Name</div>
            <input className="fld mono" value={form.name} onChange={e => set('name', e.target.value)} disabled={!isNew} />
          </div>
          <div className="field">
            <div className="lbl">Feldtyp</div>
            <select className="fld" value={form.field_type} onChange={e => set('field_type', e.target.value)}>
              {FIELD_TYPES.map(k => <option key={k} value={k}>{FIELD_TYPE_LABELS[k]}</option>)}
            </select>
          </div>
        </div>
        {showSubtype && (
          <div className="field">
            <div className="lbl">Subtyp <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(leer = gilt für alle Subtypen)</span></div>
            <input className="fld mono" value={form.target_subtype} onChange={e => set('target_subtype', e.target.value)}
              placeholder="z.B. person, organisation, event, work" disabled={!isNew} />
          </div>
        )}
        <div className="fg-2">
          <div className="field">
            <div className="lbl">Sortierung</div>
            <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} />
          </div>
          <div className="field" style={{ display: 'flex', flexDirection: 'row', gap: 16, paddingTop: 20 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" checked={form.is_required} onChange={e => set('is_required', e.target.checked)} />
              <span style={{ fontSize: 13 }}>Pflichtfeld</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" checked={form.is_repeatable} onChange={e => set('is_repeatable', e.target.checked)} />
              <span style={{ fontSize: 13 }}>Wiederholbar</span>
            </label>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn pri" onClick={onSave} disabled={saving}>
            {saving ? 'Speichert…' : 'Speichern'}
          </button>
          {!isNew && (
            <button className="btn dn" onClick={onDelete} disabled={saving}>Feld löschen</button>
          )}
        </div>
      </div>
    </div>
  )
}

export function ScreenSchema() {
  const [activeType, setActiveType] = useState('object')
  const [activeSubtype, setActiveSubtype] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FieldFormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const showSubtype = SUBTYPE_TYPES.has(activeType)

  const loadFields = useCallback(() => {
    setLoading(true)
    schema.list(activeType, (showSubtype && activeSubtype) ? activeSubtype : undefined)
      .then(setFields)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [activeType, activeSubtype, showSubtype])

  useEffect(() => {
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
    loadFields()
  }, [loadFields])

  useEffect(() => {
    setActiveSubtype('')
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
  }, [activeType])

  function openNew() {
    setIsNew(true)
    setActiveFieldId(null)
    setForm(emptyForm(activeType, fields.length, activeSubtype))
    setSaveError(null)
  }

  function openExisting(f: FieldDefinition) {
    setIsNew(false)
    setActiveFieldId(f.id)
    setForm(fieldToForm(f))
    setSaveError(null)
  }

  function closeDetail() {
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
  }

  async function handleSave() {
    if (!form) return
    if (!form.name.trim()) {
      setSaveError('Interner Name darf nicht leer sein.')
      return
    }
    setSaving(true)
    setSaveError(null)
    const data = {
      target_type: form.target_type,
      target_subtype: form.target_subtype.trim() || null,
      name: form.name,
      label: { de: form.label_de, en: form.label_en },
      field_type: form.field_type as FieldDefinition['field_type'],
      is_required: form.is_required,
      is_repeatable: form.is_repeatable,
      sort_order: form.sort_order,
      settings: {},
    }
    try {
      if (isNew) {
        await schema.create(data)
      } else {
        await schema.update(activeFieldId!, data)
      }
      closeDetail()
      loadFields()
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!activeFieldId || !window.confirm('Feld wirklich löschen?')) return
    setSaving(true)
    try {
      await schema.delete(activeFieldId)
      closeDetail()
      loadFields()
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const showDetail = form !== null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Schemata</h1><div className="sub">Felddefinitionen pro Typ</div></div>
        <div className="right">
          <button className="btn pri" onClick={openNew}><Plus size={13} /> Neues Feld</button>
        </div>
      </div>

      <div className="schema-grid" style={{ flex: 1, minHeight: 0 }}>
        <div className="schema-list">
          {TYPES.map(t => (
            <div key={t.id}>
              <div
                className={`item${activeType === t.id ? ' active' : ''}`}
                onClick={() => { setActiveType(t.id) }}
              >
                <div>
                  <div className="nm">{t.label}</div>
                  <div className="sub">{t.key}</div>
                </div>
                {activeType === t.id && !loading && (
                  <span className="ct">{fields.length}</span>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="schema-detail" style={{ overflow: 'auto' }}>
          {showDetail ? (
            <FieldDetail
              form={form!}
              isNew={isNew}
              saving={saving}
              error={saveError}
              showSubtype={showSubtype}
              onChange={setForm}
              onSave={handleSave}
              onDelete={handleDelete}
              onClose={closeDetail}
            />
          ) : (
            <>
              {showSubtype && (
                <div style={{ padding: '14px 24px 0' }}>
                  <div className="field" style={{ maxWidth: 320 }}>
                    <div className="lbl">Subtyp-Filter</div>
                    <input className="fld mono" value={activeSubtype}
                      onChange={e => setActiveSubtype(e.target.value)}
                      placeholder="z.B. person — leer = alle anzeigen"
                    />
                  </div>
                </div>
              )}
              {loading ? (
                <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>
              ) : (
                <>
                  <div style={{ margin: '12px 24px 4px', color: 'var(--fg-3)', fontSize: 12 }}>
                    {fields.length} Felder
                  </div>
                  {fields.map(f => (
                    <div key={f.id} className="field-row" onClick={() => openExisting(f)}>
                      <span className="gp"><Grip size={14} /></span>
                      <span className="nm">{f.label.de ?? f.name}</span>
                      <span className="key">{f.name}</span>
                      {f.target_subtype && (
                        <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{f.target_subtype}</span>
                      )}
                      <span className="typ">{FIELD_TYPE_LABELS[f.field_type] ?? f.field_type}</span>
                      {f.is_required && <span className="req-mark">Pflicht</span>}
                      {f.is_repeatable && <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>×n</span>}
                      <div className="actions" onClick={e => e.stopPropagation()}>
                        <button className="btn sm ico gh" onClick={() => openExisting(f)}><Edit size={12} /></button>
                        <button className="btn sm ico gh dn" onClick={async e => {
                          e.stopPropagation()
                          if (!window.confirm('Feld wirklich löschen?')) return
                          try {
                            await schema.delete(f.id)
                            loadFields()
                          } catch (err) {
                            alert((err as Error).message)
                          }
                        }}><Trash size={12} /></button>
                      </div>
                    </div>
                  ))}
                  {fields.length === 0 && <div className="empty">Keine Felder definiert.</div>}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
