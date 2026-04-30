import { useState, useEffect } from 'react'
import { objects, schema } from '../../api/client'
import type { FieldDefinition, KatalonObject, Status } from '../../types'
import { ChevD, Plus, Upload, X } from '../ui/Icons'

const STATUSES: Status[] = ['draft', 'internal', 'public']
const STATUS_LABELS: Record<Status, string> = { draft: 'Entwurf', internal: 'Intern', public: 'Öffentlich' }

interface Props { objectId?: string; onBack?: () => void }

export function ScreenForm({ objectId, onBack }: Props) {
  const isNew = !objectId || objectId === 'new'

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [idno, setIdno] = useState('')
  const [status, setStatus] = useState<Status>('draft')
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [showAudit, setShowAudit] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState(isNew ? 'Neues Objekt' : '…')

  useEffect(() => {
    setLoading(true)
    const loadSchema = schema.list('object')
    const loadObj = isNew ? Promise.resolve(null) : objects.get(objectId!)

    Promise.all([loadSchema, loadObj])
      .then(([fieldDefs, obj]) => {
        setFields(fieldDefs)
        if (obj) {
          setIdno(obj.idno ?? '')
          setStatus(obj.status as Status)
          setValues(obj.metadata_)
          const m = obj.metadata_ as Record<string, unknown>
          setTitle(String(m.title ?? obj.idno ?? obj.id))
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [objectId, isNew])

  function setField(name: string, value: unknown) {
    setValues(v => ({ ...v, [name]: value }))
  }
  function addRepeat(name: string) {
    const cur = (values[name] as string[] | undefined) ?? []
    setValues(v => ({ ...v, [name]: [...cur, ''] }))
  }
  function removeRepeat(name: string, idx: number) {
    const cur = (values[name] as string[]) ?? []
    setValues(v => ({ ...v, [name]: cur.filter((_, i) => i !== idx) }))
  }
  function updateRepeat(name: string, idx: number, val: string) {
    const cur = [...((values[name] as string[]) ?? [])]
    cur[idx] = val
    setValues(v => ({ ...v, [name]: cur }))
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const payload: Partial<KatalonObject> = { idno: idno || null, status, metadata_: values }
      if (isNew) {
        await objects.create(payload)
      } else {
        await objects.update(objectId!, payload)
      }
      onBack?.()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ background: 'var(--panel)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', border: '1px solid var(--border-s)', borderRadius: 6, overflow: 'hidden' }}>
            {STATUSES.map(s => (
              <button key={s} onClick={() => setStatus(s)}
                style={{ border: 0, padding: '5px 10px', fontSize: 12, fontWeight: 500, fontFamily: 'inherit', cursor: 'pointer',
                  background: status === s ? 'var(--accent)' : '#fff',
                  color: status === s ? '#fff' : 'var(--fg-2)',
                  borderLeft: s !== 'draft' ? '1px solid var(--border-s)' : undefined }}>
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
          <button className="btn gh" onClick={onBack} disabled={saving}>Verwerfen</button>
          <button className="btn pri" onClick={handleSave} disabled={saving}>
            {saving ? 'Speichert…' : 'Speichern'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca', padding: '8px 24px', fontSize: 13, color: '#b91c1c', flexShrink: 0 }}>
          {error}
        </div>
      )}

      <div className="scroll">
        <div className="form-grid">
          <div>
            <div className="card">
              <div className="hd">Metadaten</div>
              <div className="bd">
                <div className="field">
                  <div className="lbl">Inventar-Nr.</div>
                  <input className="fld mono" value={idno} onChange={e => setIdno(e.target.value)} placeholder="z.B. FOT.1958.0412" />
                </div>

                {fields.map(f => {
                  const val = values[f.name]
                  const repeatable = f.is_repeatable
                  const vals = repeatable ? ((val as string[] | undefined) ?? []) : undefined

                  return (
                    <div key={f.id} className="field">
                      <div className="lbl">
                        {f.label.de ?? f.name}
                        {f.is_required && <span className="req">*</span>}
                        {repeatable && <span className="h">wiederholbar</span>}
                      </div>

                      {repeatable ? (
                        <>
                          {(vals ?? []).map((v, i) => (
                            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                              <input className="fld" value={v}
                                onChange={e => updateRepeat(f.name, i, e.target.value)}
                                placeholder={f.label.de ?? f.name} />
                              <button className="btn sm ico gh" onClick={() => removeRepeat(f.name, i)}><X size={12} /></button>
                            </div>
                          ))}
                          <button className="btn sm gh" onClick={() => addRepeat(f.name)}>
                            <Plus size={12} /> Weiteren Wert
                          </button>
                        </>
                      ) : f.field_type === 'richtext' ? (
                        <textarea className="fld" rows={4}
                          value={(val as string) ?? ''}
                          onChange={e => setField(f.name, e.target.value)}
                          placeholder={f.label.de ?? f.name} />
                      ) : f.field_type === 'boolean' ? (
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <input type="checkbox" className="ck"
                            checked={Boolean(val)}
                            onChange={e => setField(f.name, e.target.checked)} />
                          <span style={{ fontSize: 13 }}>{f.label.de}</span>
                        </label>
                      ) : (
                        <input className="fld"
                          value={(val as string) ?? ''}
                          onChange={e => setField(f.name, e.target.value)}
                          placeholder={f.label.de ?? f.name} />
                      )}
                    </div>
                  )
                })}

                {fields.length === 0 && (
                  <div className="empty">Keine Felder definiert. Schema unter Konfiguration → Schemata anlegen.</div>
                )}
              </div>
            </div>
          </div>

          <div>
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="hd">Medien</div>
              <div className="bd">
                <div className="dz" style={{ padding: '24px 16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
                    <Upload size={28} style={{ color: 'var(--fg-4)' }} />
                  </div>
                  <div style={{ fontSize: 12 }}>Bilder hierher ziehen oder</div>
                  <label style={{ color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
                    auswählen<input type="file" style={{ display: 'none' }} accept="image/*" />
                  </label>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="hd">
                <span>Relationen</span>
                <div className="grow" />
                <button className="btn sm gh"><Plus size={12} /> Hinzufügen</button>
              </div>
              <div className="bd">
                <div className="empty" style={{ padding: '20px 0' }}>Noch keine Relationen.</div>
              </div>
            </div>

            {!isNew && (
              <div className="card">
                <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowAudit(a => !a)}>
                  <span>Letzte Änderungen</span>
                  <div className="grow" />
                  <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                </div>
                {showAudit && (
                  <div className="bd" style={{ padding: '8px 0' }}>
                    <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>
                      Audit-Log unter Katalon → Audit-Log verfügbar.
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
