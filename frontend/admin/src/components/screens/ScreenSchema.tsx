import { useState } from 'react'
import { MOCK_FIELDS } from '../../api/mock-data'
import { Edit, Grip, Plus, Trash } from '../ui/Icons'
import type { FieldDefinition } from '../../types'

const TYPES = [
  { id: 'object',     label: 'Objekte',     key: 'object' },
  { id: 'entity',    label: 'Entitäten',   key: 'entity' },
  { id: 'place',     label: 'Orte',        key: 'place' },
  { id: 'occurrence',label: 'Occurrences', key: 'occurrence' },
]

const FIELD_TYPE_LABELS: Record<string, string> = {
  text: 'Text', date: 'Datum', number: 'Zahl',
  vocab: 'Vokabular', relation: 'Relation', geo: 'Geodaten',
  boolean: 'Boolean', richtext: 'Richtext',
}

function FieldDetail({ field, onClose }: { field: FieldDefinition; onClose: () => void }) {
  return (
    <div className="card" style={{ margin: '18px 24px' }}>
      <div className="hd">
        <span>{field.label.de ?? field.name}</span>
        <span className="sub">{field.name}</span>
        <div className="grow" />
        <button className="btn sm" onClick={onClose}>Schließen</button>
      </div>
      <div className="bd">
        <div className="fg-2">
          <div className="field">
            <div className="lbl">Label DE</div>
            <input className="fld" defaultValue={field.label.de ?? ''} />
          </div>
          <div className="field">
            <div className="lbl">Label EN</div>
            <input className="fld" defaultValue={field.label.en ?? ''} />
          </div>
        </div>
        <div className="fg-2">
          <div className="field">
            <div className="lbl">Interner Name</div>
            <input className="fld mono" defaultValue={field.name} />
          </div>
          <div className="field">
            <div className="lbl">Feldtyp</div>
            <select className="fld" defaultValue={field.field_type}>
              {Object.entries(FIELD_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
        <div className="fg-2">
          <label className="field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" className="ck" defaultChecked={field.is_required} />
            <span style={{ fontSize: 13 }}>Pflichtfeld</span>
          </label>
          <label className="field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" className="ck" defaultChecked={field.is_repeatable} />
            <span style={{ fontSize: 13 }}>Wiederholbar</span>
          </label>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn pri">Speichern</button>
          <button className="btn dn">Feld löschen</button>
        </div>
      </div>
    </div>
  )
}

export function ScreenSchema() {
  const [activeType, setActiveType] = useState('object')
  const [activeField, setActiveField] = useState<FieldDefinition | null>(null)

  const fields = MOCK_FIELDS.filter(f => f.target_type === activeType)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Schemata</h1><div className="sub">Felddefinitionen pro Typ</div></div>
        <div className="right">
          <button className="btn pri"><Plus size={13} /> Neues Feld</button>
        </div>
      </div>

      <div className="schema-grid" style={{ flex: 1, minHeight: 0 }}>
        {/* Left: type + field list */}
        <div className="schema-list">
          {TYPES.map(t => (
            <div key={t.id}>
              <div
                className={`item${activeType === t.id ? ' active' : ''}`}
                onClick={() => { setActiveType(t.id); setActiveField(null) }}
              >
                <div>
                  <div className="nm">{t.label}</div>
                  <div className="sub">{t.key}</div>
                </div>
                <span className="ct">{t.id === 'object' ? MOCK_FIELDS.length : 0}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Right: field list + detail */}
        <div className="schema-detail" style={{ overflow: 'auto' }}>
          {activeField ? (
            <FieldDetail field={activeField} onClose={() => setActiveField(null)} />
          ) : (
            <>
              <div style={{ marginBottom: 12, color: 'var(--fg-3)', fontSize: 12 }}>
                {fields.length} Felder — ziehen zum Sortieren
              </div>
              {fields.map(f => (
                <div key={f.id} className="field-row" onClick={() => setActiveField(f)}>
                  <span className="gp"><Grip size={14} /></span>
                  <span className="nm">{f.label.de ?? f.name}</span>
                  <span className="key">{f.name}</span>
                  <span className="typ">{FIELD_TYPE_LABELS[f.field_type] ?? f.field_type}</span>
                  {f.is_required && <span className="req-mark">Pflicht</span>}
                  {f.is_repeatable && <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>×n</span>}
                  <div className="actions" onClick={e => e.stopPropagation()}>
                    <button className="btn sm ico gh"><Edit size={12} /></button>
                    <button className="btn sm ico gh dn"><Trash size={12} /></button>
                  </div>
                </div>
              ))}
              {fields.length === 0 && <div className="empty">Keine Felder definiert.</div>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
