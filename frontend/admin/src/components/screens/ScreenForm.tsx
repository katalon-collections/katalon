import { useState } from 'react'
import { MOCK_FIELDS, MOCK_OBJECTS } from '../../api/mock-data'
import { StatusBadge } from '../ui/StatusBadge'
import { ChevD, Plus, Upload, X } from '../ui/Icons'
import type { Status } from '../../types'

const STATUSES: Status[] = ['draft', 'internal', 'public']
const STATUS_LABELS: Record<Status, string> = { draft: 'Entwurf', internal: 'Intern', public: 'Öffentlich' }

interface Props { objectId?: string; onBack?: () => void }

export function ScreenForm({ objectId, onBack }: Props) {
  const existing = MOCK_OBJECTS.find(o => o.id === objectId)
  const meta = (existing?.metadata_ ?? {}) as Record<string, unknown>

  const [status, setStatus] = useState<Status>((existing?.status ?? 'draft') as Status)
  const [values, setValues] = useState<Record<string, unknown>>(meta)
  const [showAudit, setShowAudit] = useState(false)

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Sticky header */}
      <div style={{ background: 'var(--panel)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>
          {existing ? (meta.title as string) : 'Neues Objekt'}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Status selector */}
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
          <button className="btn gh" onClick={onBack}>Verwerfen</button>
          <button className="btn pri">Speichern</button>
        </div>
      </div>

      <div className="scroll">
        <div className="form-grid">
          {/* Left: dynamic fields */}
          <div>
            <div className="card">
              <div className="hd">Metadaten</div>
              <div className="bd">
                {MOCK_FIELDS.map(f => {
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
                      ) : f.field_type === 'date' ? (
                        <div style={{ display: 'flex', gap: 8 }}>
                          <input className="fld" style={{ flex: 2 }}
                            value={(val as string) ?? ''}
                            onChange={e => setField(f.name, e.target.value)}
                            placeholder='z.B. 1958 oder ca. 1920–1930' />
                        </div>
                      ) : (
                        <input className="fld"
                          value={(val as string) ?? ''}
                          onChange={e => setField(f.name, e.target.value)}
                          placeholder={f.label.de ?? f.name} />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Right: media + relations */}
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

            <div className="card">
              <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowAudit(a => !a)}>
                <span>Letzte Änderungen</span>
                <div className="grow" />
                <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
              </div>
              {showAudit && (
                <div className="bd" style={{ padding: '8px 0' }}>
                  {[
                    { who: 'M. Bauer', when: 'vor 2 Std', what: 'Status geändert' },
                    { who: 'M. Bauer', when: 'vor 4 Std', what: 'Datierung aktualisiert' },
                    { who: 'T. Hofer', when: 'gestern',   what: 'Angelegt' },
                  ].map((e, i) => (
                    <div key={i} style={{ padding: '6px 16px', display: 'flex', gap: 10, fontSize: 12, color: 'var(--fg-3)' }}>
                      <span style={{ flex: 1 }}>{e.what}</span>
                      <span>{e.who}</span>
                      <span>{e.when}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
