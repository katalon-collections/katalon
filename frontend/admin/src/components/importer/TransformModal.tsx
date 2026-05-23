import { useState, useMemo } from 'react'
import type { TransformConfig, MappingEntry } from '../../api/client'

interface TransformModalProps {
  csvColumn: string
  sampleValues: string[]
  mappingEntry: MappingEntry
  onSave: (entry: MappingEntry) => void
  onClose: () => void
}

const TRANSFORM_TYPES: { id: TransformConfig['type']; label: string }[] = [
  { id: 'split', label: 'Aufteilen (Split)' },
  { id: 'replace', label: 'Suchen & Ersetzen' },
  { id: 'regex_extract', label: 'Regex-Extract' },
  { id: 'trim', label: 'Trim / Leerzeichen' },
  { id: 'vocab_map', label: 'Vokabular-Mapping' },
  { id: 'expression', label: 'Expression' },
]

function applyTransformsLocal(value: string, transforms: TransformConfig[]): string[] {
  let values = [value]
  for (const t of transforms) {
    const newValues: string[] = []
    for (const v of values) {
      switch (t.type) {
        case 'split': {
          const delim = t.delimiter ?? ';'
          const filterEmpty = t.filter_empty !== false
          const parts = v.split(delim).map(p => p.trim()).filter(p => p || !filterEmpty)
          newValues.push(...parts)
          break
        }
        case 'replace': {
          const search = t.search ?? ''
          const replace = t.replace ?? ''
          const caseSensitive = t.case_sensitive !== false
          const flags = caseSensitive ? 'g' : 'gi'
          newValues.push(v.replace(new RegExp(search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags), replace))
          break
        }
        case 'regex_extract': {
          const pattern = t.pattern ?? ''
          const group = t.group ?? 0
          try {
            const m = v.match(new RegExp(pattern))
            newValues.push(m ? m[group] : v)
          } catch {
            newValues.push(v)
          }
          break
        }
        case 'trim':
          newValues.push(v.trim())
          break
        case 'vocab_map': {
          const map = t.vocab_map ?? {}
          const strict = t.strict === true
          const mapped = map[v.trim()]
          if (mapped !== undefined) {
            newValues.push(mapped)
          } else if (!strict) {
            newValues.push(v)
          }
          break
        }
        case 'expression': {
          const expr = t.expression ?? ''
          let result = expr
          const pattern = /\$\{value(?::([^}]+))?\}/g
          const match = pattern.exec(expr)
          if (match) {
            const filter = match[1]
            let val = v
            if (filter === 'upper') val = v.toUpperCase()
            else if (filter === 'lower') val = v.toLowerCase()
            else if (filter === 'trim') val = v.trim()
            else if (filter?.startsWith('slice(')) {
              const m = filter.match(/slice\((\d+)(?:,(\d+))?\)/)
              if (m) {
                const start = parseInt(m[1])
                const end = m[2] ? parseInt(m[2]) : undefined
                val = v.slice(start, end)
              }
            } else if (filter?.startsWith('replace(')) {
              const m = filter.match(/replace\(([^,]+),([^)]+)\)/)
              if (m) val = v.replaceAll(m[1], m[2])
            }
            result = result.replace(match[0], val)
          } else if (!expr) {
            result = v
          }
          newValues.push(result)
          break
        }
        default:
          newValues.push(v)
      }
    }
    const filterEmpty = t.filter_empty !== false
    values = newValues.filter(v => v.trim() || !filterEmpty)
  }
  return values
}

export function TransformModal({ csvColumn, sampleValues, mappingEntry, onSave, onClose }: TransformModalProps) {
  const [transforms, setTransforms] = useState<TransformConfig[]>(mappingEntry.transforms ?? [])
  const [addingType, setAddingType] = useState<TransformConfig['type'] | ''>('')

  const effectiveSamples = sampleValues.length > 0 ? sampleValues.slice(0, 3) : ['Beispielwert']
  const previews = useMemo(() => {
    return effectiveSamples.map(v => applyTransformsLocal(v, transforms))
  }, [effectiveSamples.join('|'), transforms]) // eslint-disable-line react-hooks/exhaustive-deps

  function addTransform(type: TransformConfig['type']) {
    const base: TransformConfig = { type }
    if (type === 'split') {
      base.delimiter = ','
      base.filter_empty = true
    } else if (type === 'replace') {
      base.search = ''
      base.replace = ''
      base.case_sensitive = true
    } else if (type === 'regex_extract') {
      base.pattern = ''
      base.group = 0
    } else if (type === 'trim') {
      base.trim = true
    } else if (type === 'vocab_map') {
      base.vocab_map = {}
      base.strict = false
    } else if (type === 'expression') {
      base.expression = '${value}'
    }
    setTransforms(prev => [...prev, base])
    setAddingType('')
  }

  function updateTransform(index: number, patch: Partial<TransformConfig>) {
    setTransforms(prev => prev.map((t, i) => i === index ? { ...t, ...patch } : t))
  }

  function removeTransform(index: number) {
    setTransforms(prev => prev.filter((_, i) => i !== index))
  }

  function moveTransform(index: number, direction: -1 | 1) {
    const newIndex = index + direction
    if (newIndex < 0 || newIndex >= transforms.length) return
    setTransforms(prev => {
      const next = [...prev]
      const temp = next[index]
      next[index] = next[newIndex]
      next[newIndex] = temp
      return next
    })
  }

  function handleSave() {
    onSave({ target: mappingEntry.target, transforms: transforms.length > 0 ? transforms : undefined })
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div style={{
        background: 'var(--panel)', borderRadius: 10, padding: 24, width: 520, maxWidth: '90vw',
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
      }}>
        <h3 style={{ margin: '0 0 4px' }}>Transformationen</h3>
        <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 16 }}>
          <span className="mono">{csvColumn}</span> → {mappingEntry.target}
        </div>

        {/* Transform list */}
        <div style={{ flex: 1, overflow: 'auto', marginBottom: 16 }}>
          {transforms.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--fg-3)', padding: '16px 0', textAlign: 'center' }}>
              Keine Transformationen konfiguriert.
            </div>
          )}
          {transforms.map((t, i) => (
            <div key={i} style={{
              border: '1px solid var(--border-soft)', borderRadius: 8, padding: 12, marginBottom: 8,
              background: 'var(--bg)', fontSize: 13,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <b>{i + 1}. {TRANSFORM_TYPES.find(x => x.id === t.type)?.label}</b>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button className="btn sm gh" onClick={() => moveTransform(i, -1)} disabled={i === 0}>↑</button>
                  <button className="btn sm gh" onClick={() => moveTransform(i, 1)} disabled={i === transforms.length - 1}>↓</button>
                  <button className="btn sm gh" onClick={() => removeTransform(i)} style={{ color: '#b91c1c' }}>×</button>
                </div>
              </div>

              {t.type === 'split' && (
                <div style={{ display: 'grid', gap: 8 }}>
                  <div className="field">
                    <label className="lbl">Trennzeichen</label>
                    <input className="fld" style={{ height: 28, fontSize: 12 }}
                      value={t.delimiter ?? ','} onChange={e => updateTransform(i, { delimiter: e.target.value })}
                      placeholder="," />
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input type="checkbox" checked={t.filter_empty !== false}
                      onChange={e => updateTransform(i, { filter_empty: e.target.checked })} />
                    Leere Werte filtern
                  </label>
                </div>
              )}

              {t.type === 'replace' && (
                <div style={{ display: 'grid', gap: 8 }}>
                  <div className="field">
                    <label className="lbl">Suchen</label>
                    <input className="fld" style={{ height: 28, fontSize: 12 }}
                      value={t.search ?? ''} onChange={e => updateTransform(i, { search: e.target.value })} />
                  </div>
                  <div className="field">
                    <label className="lbl">Ersetzen durch</label>
                    <input className="fld" style={{ height: 28, fontSize: 12 }}
                      value={t.replace ?? ''} onChange={e => updateTransform(i, { replace: e.target.value })} />
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input type="checkbox" checked={t.case_sensitive !== false}
                      onChange={e => updateTransform(i, { case_sensitive: e.target.checked })} />
                    Groß-/Kleinschreibung beachten
                  </label>
                </div>
              )}

              {t.type === 'regex_extract' && (
                <div style={{ display: 'grid', gap: 8 }}>
                  <div className="field">
                    <label className="lbl">Regex-Pattern</label>
                    <input className="fld" style={{ height: 28, fontSize: 12 }}
                      value={t.pattern ?? ''} onChange={e => updateTransform(i, { pattern: e.target.value })}
                      placeholder="z.B. \d{4}" />
                  </div>
                  <div className="field">
                    <label className="lbl">Capture Group (0 = ganzer Match)</label>
                    <input className="fld" style={{ height: 28, fontSize: 12, width: 80 }}
                      type="number" min={0}
                      value={t.group ?? 0} onChange={e => updateTransform(i, { group: parseInt(e.target.value) || 0 })} />
                  </div>
                </div>
              )}

              {t.type === 'trim' && (
                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  Entfernt führende und nachfolgende Leerzeichen.
                </div>
              )}

              {t.type === 'vocab_map' && (
                <div style={{ display: 'grid', gap: 8 }}>
                  <VocabMapEditor
                    map={t.vocab_map ?? {}}
                    onChange={map => updateTransform(i, { vocab_map: map })}
                  />
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input type="checkbox" checked={t.strict === true}
                      onChange={e => updateTransform(i, { strict: e.target.checked })} />
                    Unbekannte Werte verwerfen (strict)
                  </label>
                </div>
              )}

              {t.type === 'expression' && (
                <div style={{ display: 'grid', gap: 8 }}>
                  <div className="field">
                    <label className="lbl">Expression</label>
                    <input className="fld" style={{ height: 28, fontSize: 12 }}
                      value={t.expression ?? '${value}'} onChange={e => updateTransform(i, { expression: e.target.value })}
                      placeholder="${value:upper}" />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    Variablen: <code>${'{'}value{'}'}</code>, <code>${'{'}value:upper{'}'}</code>, <code>${'{'}value:lower{'}'}</code>, <code>${'{'}value:trim{'}'}</code>, <code>${'{'}value:slice(0,4){'}'}</code>, <code>${'{'}value:replace(a,b){'}'}</code>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Add transform */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
          <select className="fld" style={{ height: 32, fontSize: 12, flex: 1 }}
            value={addingType} onChange={e => setAddingType(e.target.value as TransformConfig['type'] | '')}>
            <option value="">+ Transformation hinzufügen…</option>
            {TRANSFORM_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <button className="btn sm pri" onClick={() => addingType && addTransform(addingType)}
            disabled={!addingType}>Hinzufügen</button>
        </div>

        {/* Preview */}
        <div style={{
          background: 'var(--bg)', border: '1px solid var(--border-soft)', borderRadius: 8,
          padding: 12, marginBottom: 16, fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Vorschau</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', color: 'var(--fg-3)', fontWeight: 500, paddingBottom: 4, width: '50%' }}>Vorher</th>
                <th style={{ textAlign: 'left', color: 'var(--fg-3)', fontWeight: 500, paddingBottom: 4 }}>Nachher</th>
              </tr>
            </thead>
            <tbody>
              {effectiveSamples.map((raw, i) => (
                <tr key={i} style={{ borderTop: i > 0 ? '1px solid var(--border-soft)' : undefined }}>
                  <td style={{ padding: '3px 8px 3px 0', color: 'var(--fg-2)', fontFamily: 'monospace' }}>"{raw}"</td>
                  <td style={{ padding: '3px 0', color: '#166534', fontFamily: 'monospace' }}>
                    {previews[i].length === 0 ? '(leer)' : previews[i].map(p => `"${p}"`).join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn gh" onClick={onClose}>Abbrechen</button>
          <button className="btn pri" onClick={handleSave}>Speichern</button>
        </div>
      </div>
    </div>
  )
}

function VocabMapEditor({ map, onChange }: { map: Record<string, string>; onChange: (map: Record<string, string>) => void }) {
  const entries = Object.entries(map)
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')

  function addEntry() {
    if (!newKey.trim()) return
    onChange({ ...map, [newKey.trim()]: newVal.trim() })
    setNewKey('')
    setNewVal('')
  }

  function removeEntry(key: string) {
    const next = { ...map }
    delete next[key]
    onChange(next)
  }

  return (
    <div>
      {entries.length === 0 && <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Keine Mappings definiert.</div>}
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
          <span className="mono" style={{ fontSize: 12, minWidth: 80 }}>{k}</span>
          <span style={{ color: 'var(--fg-3)' }}>→</span>
          <span className="mono" style={{ fontSize: 12, flex: 1 }}>{v}</span>
          <button className="btn sm gh" onClick={() => removeEntry(k)} style={{ color: '#b91c1c' }}>×</button>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <input className="fld" style={{ height: 26, fontSize: 12, flex: 1 }}
          placeholder="CSV-Wert" value={newKey} onChange={e => setNewKey(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addEntry()} />
        <input className="fld" style={{ height: 26, fontSize: 12, flex: 1 }}
          placeholder="Zielwert" value={newVal} onChange={e => setNewVal(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addEntry()} />
        <button className="btn sm gh" onClick={addEntry}>+</button>
      </div>
    </div>
  )
}
