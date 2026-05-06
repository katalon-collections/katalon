import { useState, useEffect, useCallback, useRef } from 'react'
import { schema, vocabularies } from '../../api/client'
import type { SchemaImportResult } from '../../api/client'
import type { FieldDefinition, Vocabulary } from '../../types'
import { Edit, Grip, Plus, Trash } from '../ui/Icons'

const TYPES = [
  { id: 'object',      label: 'Objekte',     key: 'object' },
  { id: 'entity',      label: 'Entitäten',   key: 'entity' },
  { id: 'place',       label: 'Orte',        key: 'place' },
  { id: 'occurrence',  label: 'Occurrences', key: 'occurrence' },
]

const SUBTYPE_TYPES = new Set(['entity', 'occurrence'])

const FIELD_TYPES = ['text', 'richtext', 'date', 'number', 'boolean', 'vocab', 'vocab_free', 'relation', 'geo', 'pid', 'authority'] as const
const FIELD_TYPE_LABELS: Record<string, string> = {
  text: 'Text', richtext: 'Richtext', date: 'Datum', number: 'Zahl',
  boolean: 'Boolean', vocab: 'Vokabular (strikt)', vocab_free: 'Vokabular (Freitext)',
  relation: 'Relation', geo: 'Geodaten', pid: 'PID',
  authority: 'Normdaten (Authority)',
}

const AUTHORITY_SOURCES = [
  { id: 'gnd',       label: 'GND (Gemeinsame Normdatei)' },
  { id: 'wikidata',  label: 'Wikidata' },
  { id: 'viaf',      label: 'VIAF' },
  { id: 'geonames',  label: 'Geonames' },
  { id: 'tgn',       label: 'Getty TGN' },
  { id: 'iconclass', label: 'ICONCLASS' },
]

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
  validation_regex: string
  authority_source: string
  show_in_detail: boolean
  vocabulary_id: string
}

function emptyForm(targetType: string, sortOrder: number, subtype: string): FieldFormState {
  return { target_type: targetType, target_subtype: subtype, name: '', label_de: '', label_en: '', field_type: 'text', is_required: false, is_repeatable: false, sort_order: sortOrder, validation_regex: '', authority_source: 'gnd', show_in_detail: true, vocabulary_id: '' }
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
    validation_regex: (f.settings?.validation_regex as string) ?? '',
    authority_source: (f.settings?.source as string) ?? 'gnd',
    show_in_detail: f.show_in_detail ?? true,
    vocabulary_id: (f.settings?.vocabulary_id as string) ?? '',
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

  const [allVocabs, setAllVocabs] = useState<Vocabulary[]>([])
  useEffect(() => {
    vocabularies.list().then(setAllVocabs).catch(() => {})
  }, [])

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
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" checked={form.show_in_detail} onChange={e => set('show_in_detail', e.target.checked)} />
              <span style={{ fontSize: 13 }}>In Detailansicht zeigen</span>
            </label>
          </div>
        </div>
        {form.field_type === 'text' && (
          <div className="field">
            <div className="lbl">Validierungs-Regex <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
            <input className="fld mono" value={form.validation_regex} onChange={e => set('validation_regex', e.target.value)}
              placeholder="^97[89]-[0-9]{10}$" />
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>Beispiele: ISBN-13, ISSN, DOI</div>
          </div>
        )}
        {form.field_type === 'authority' && (
          <div className="field">
            <div className="lbl">Normdaten-Quelle</div>
            <select className="fld" value={form.authority_source} onChange={e => set('authority_source', e.target.value)}>
              {AUTHORITY_SOURCES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
        )}
        {(form.field_type === 'vocab' || form.field_type === 'vocab_free') && (
          <div className="field">
            <div className="lbl">
              Vokabular {form.field_type === 'vocab' && <span className="req">*</span>}
              {form.field_type === 'vocab_free' && <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 4 }}>(optional — nur für Vorschläge)</span>}
            </div>
            <select className="fld" value={form.vocabulary_id} onChange={e => set('vocabulary_id', e.target.value)}>
              <option value="">— Vokabular wählen —</option>
              {allVocabs.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
        )}
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

function ImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [dryRun, setDryRun] = useState(true)
  const [overwrite, setOverwrite] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SchemaImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleImport() {
    const file = fileRef.current?.files?.[0]
    if (!file) { setError('Bitte eine Datei auswählen.'); return }
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await schema.import(file, { dryRun, overwrite })
      setResult(res)
      if (!dryRun) onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 480, maxWidth: '90vw' }}>
        <div className="hd">
          <span>Schema-Import</span>
          <div className="grow" />
          <button className="btn sm" onClick={onClose}>Schließen</button>
        </div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-2)', margin: '0 0 12px' }}>
            YAML- oder JSON-Datei mit Felddefinitionen für einen Typ importieren.
          </p>
          <details style={{ marginBottom: 12, fontSize: 12 }}>
            <summary style={{ cursor: 'pointer', color: 'var(--fg-3)', userSelect: 'none' }}>Format-Hilfe</summary>
            <pre style={{ margin: '8px 0 0', padding: '10px 12px', background: 'var(--panel)', borderRadius: 6, overflowX: 'auto', lineHeight: 1.5, fontSize: 11 }}>{`target_type: object   # object | entity | place | occurrence
fields:
  - name: title
    label:
      de: Titel
      en: Title
    field_type: text   # text | date | number | geo | vocab | relation | boolean
    is_required: true
    is_repeatable: false
    sort_order: 0
    settings: {}

  - name: material
    label: {de: Material}
    field_type: vocab
    settings:
      vocabulary: materials`}</pre>
          </details>
          <div className="field">
            <div className="lbl">Datei (YAML / JSON)</div>
            <input ref={fileRef} type="file" accept=".yaml,.yml,.json" className="fld" />
          </div>
          <div className="field" style={{ display: 'flex', gap: 16, flexDirection: 'row', paddingTop: 4 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" className="ck" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
              Dry-Run (nur Vorschau)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" className="ck" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />
              Bestehende überschreiben
            </label>
          </div>
          {error && <div style={{ fontSize: 12, color: '#dc2626', margin: '8px 0' }}>{error}</div>}
          {result && (
            <div style={{ fontSize: 12, background: 'var(--accent-50)', borderRadius: 6, padding: '10px 12px', margin: '8px 0' }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{dryRun ? 'Vorschau (kein Schreiben)' : 'Import abgeschlossen'}</div>
              <div>Neu: {result.created} · Aktualisiert: {result.updated} · Übersprungen: {result.skipped}</div>
              {result.errors.length > 0 && (
                <div style={{ color: '#b91c1c', marginTop: 4 }}>
                  Fehler: {result.errors.map((e, i) => <div key={i}>{e}</div>)}
                </div>
              )}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn pri" onClick={handleImport} disabled={busy}>
              {busy ? 'Lädt…' : dryRun ? 'Vorschau' : 'Importieren'}
            </button>
          </div>
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
  const [showImport, setShowImport] = useState(false)

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
      show_in_detail: form.show_in_detail,
      settings: {
        ...(form.validation_regex.trim() ? { validation_regex: form.validation_regex.trim() } : {}),
        ...(form.field_type === 'authority' ? { source: form.authority_source } : {}),
        ...((form.field_type === 'vocab' || form.field_type === 'vocab_free') && form.vocabulary_id ? { vocabulary_id: form.vocabulary_id } : {}),
      },
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
      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onDone={() => { setShowImport(false); loadFields() }} />
      )}
      <div className="ph">
        <div><h1>Schemata</h1><div className="sub">Felddefinitionen pro Typ</div></div>
        <div className="right">
          <button className="btn gh" onClick={() => setShowImport(true)}>Import</button>
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
