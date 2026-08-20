import { useState } from 'react'
import type { MappingEntry, UploadResult, XmlSelector } from '../../../api/client'
import type { FieldDefinition } from '../../../types'
import { getLabel } from '../../../types'
import { TransformModal } from '../../importer/TransformModal'
import { FIELD_TYPE_OPTIONS, RECORD_TYPES, type PendingField, type ProfileApplyResult } from './types'

interface Props {
  uploaded: UploadResult
  fields: FieldDefinition[]
  mapping: Record<string, MappingEntry>
  onMappingChange: (m: Record<string, MappingEntry>) => void
  recordType: string
  mediaSelector: string | null
  onMediaSelectorChange: (selector: string | null) => void
  idnoStrategy: string
  idnoColumn: string | null
  onIdnoStrategyChange: (strategy: string, column: string | null) => void
  pendingFields: PendingField[]
  onPendingFieldsChange: (fields: PendingField[]) => void
  missingRequired: FieldDefinition[]
  idnoMissing: boolean
  mappedCount: number
  ignoredCount: number
  dryRunning: boolean
  onDryRun: () => void
  onBack: () => void
  onProfileExport?: () => void
  profileWarnings?: ProfileApplyResult | null
  /** XML only: structured selector list with human-readable labels */
  xmlSelectors?: XmlSelector[]
}


export function StepMapping({
  uploaded, fields, mapping, onMappingChange, recordType,
  mediaSelector, onMediaSelectorChange,
  idnoStrategy, idnoColumn, onIdnoStrategyChange,
  pendingFields, onPendingFieldsChange,
  missingRequired, idnoMissing, mappedCount, ignoredCount,
  dryRunning, onDryRun, onBack, onProfileExport, profileWarnings, xmlSelectors,
}: Props) {
  const [transformModalCol, setTransformModalCol] = useState<string | null>(null)
  const [warningsExpanded, setWarningsExpanded] = useState(false)
  const [newFieldModal, setNewFieldModal] = useState<string | null>(null)
  const [newFieldType, setNewFieldType] = useState('text')
  const [newFieldLabelDe, setNewFieldLabelDe] = useState('')
  const [newFieldLabelEn, setNewFieldLabelEn] = useState('')
  const [newFieldRepeatable, setNewFieldRepeatable] = useState(false)

  function openNewFieldModal(col: string) {
    const suggestion = uploaded.suggestions?.[col] ?? 'text'
    setNewFieldType(suggestion)
    setNewFieldLabelDe(col)
    setNewFieldLabelEn(col)
    setNewFieldRepeatable(mapping[col]?.transforms?.some(t => t.type === 'split') ?? false)
    setNewFieldModal(col)
  }

  function confirmCreateField() {
    if (!newFieldModal) return
    const name = newFieldModal.toLowerCase().replace(/[\s-]/g, '_')
    const existing = fields.find(f => f.name === name)
    if (existing) {
      onMappingChange({ ...mapping, [newFieldModal]: { target: existing.name } })
      setNewFieldModal(null)
      return
    }
    const pending: PendingField = {
      csvColumn: newFieldModal, name,
      field_type: newFieldType,
      label_de: newFieldLabelDe || newFieldModal,
      label_en: newFieldLabelEn || newFieldModal,
      is_repeatable: newFieldRepeatable,
    }
    const newPending = [...pendingFields.filter(f => f.name !== name), pending]
    onPendingFieldsChange(newPending)
    onMappingChange({ ...mapping, [newFieldModal]: { target: name } })
    setNewFieldModal(null)
  }

  // Build path→label lookup for XML selector labels
  const xmlLabelMap = xmlSelectors
    ? Object.fromEntries(xmlSelectors.map(s => [s.path, s.label]))
    : null

  const suggestedMediaSelector = recordType === 'object'
    ? uploaded.headers.find(selector => {
        const label = xmlLabelMap?.[selector] ?? selector
        const leaf = label.split('/').at(-1)?.split('@')[0].split(':').at(-1)?.toLowerCase()
        return leaf === 'resourceid' || leaf === 'resource_id'
      }) ?? null
    : null

  // Deep LIDO/XML paths share long common prefixes ("...administrativeMetadata/...") —
  // truncating from the end hides exactly the part that differs. Show the last
  // segments instead; the full path is still available via the title tooltip.
  function shortSelectorLabel(full: string): string {
    const segs = full.split('/')
    if (segs.length <= 2) return full
    return `…/${segs.slice(-2).join('/')}`
  }

  // Group key = the enclosing element path (attr suffix and leaf segment stripped),
  // e.g. "lido:recordType/lido:conceptID@lido:type" and ".../lido:term" both group
  // under "lido:recordType". Selectors come back path-sorted, so same-group rows
  // are already adjacent — this only needs to detect the boundary.
  function groupKey(full: string): string {
    const segs = full.split('@')[0].split('/')
    return segs.length > 1 ? segs.slice(0, -1).join('/') : ''
  }

  return (
    <>
      {/* Profile import warnings banner */}
      {profileWarnings && (profileWarnings.missedSelectors.length > 0 || profileWarnings.missingFieldNames.length > 0 || profileWarnings.appliedMapping) && (
        <div style={{ marginBottom: 16, background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6, padding: '10px 14px', fontSize: 13 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ color: '#166534' }}>✓ {Object.keys(profileWarnings.appliedMapping).length} Zuweisungen übernommen</span>
              {profileWarnings.missingFieldNames.length > 0 && (
                <span style={{ color: '#92400e' }}>⚠ {profileWarnings.missingFieldNames.length} Felder werden bei Import neu angelegt</span>
              )}
              {profileWarnings.missedSelectors.length > 0 && (
                <span style={{ color: '#991b1b' }}>✗ {profileWarnings.missedSelectors.length} Selektoren nicht in Datei gefunden</span>
              )}
            </div>
            {(profileWarnings.missingFieldNames.length > 0 || profileWarnings.missedSelectors.length > 0) && (
              <button className="btn sm gh" onClick={() => setWarningsExpanded(v => !v)} style={{ flexShrink: 0, marginLeft: 12 }}>
                {warningsExpanded ? 'Weniger' : 'Details'}
              </button>
            )}
          </div>
          {warningsExpanded && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #bae6fd', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {profileWarnings.missingFieldNames.length > 0 && (
                <div><span style={{ color: '#92400e' }}>Neue Felder:</span> {profileWarnings.missingFieldNames.join(', ')}</div>
              )}
              {profileWarnings.missedSelectors.length > 0 && (
                <div><span style={{ color: '#991b1b' }}>Fehlende Selektoren:</span> {profileWarnings.missedSelectors.join(', ')}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ID-Nummer strategy */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">ID-Nummer</div>
        <div className="bd" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 16 }}>
            {[
              { id: 'column', label: xmlLabelMap ? 'Aus Element zuweisen' : 'Aus Spalte zuweisen' },
              { id: 'auto',   label: 'Automatisch nach Schema vergeben' },
            ].map(opt => (
              <label key={opt.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="radio" name="idno-strategy" value={opt.id}
                  checked={idnoStrategy === opt.id}
                  onChange={() => onIdnoStrategyChange(opt.id, opt.id === 'column' ? idnoColumn : null)}
                />
                {opt.label}
              </label>
            ))}
          </div>
          {idnoStrategy === 'column' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'nowrap' }}>{xmlLabelMap ? 'Element:' : 'Spalte:'}</span>
              <select
                className="fld" style={{ height: 28, fontSize: 12, width: 320 }}
                value={idnoColumn ?? ''}
                onChange={e => onIdnoStrategyChange('column', e.target.value || null)}
              >
                <option value="">{xmlLabelMap ? '— Element wählen —' : '— Spalte wählen —'}</option>
                {xmlLabelMap
                  ? Object.entries(
                      uploaded.headers.reduce<Record<string, string[]>>((groups, h) => {
                        const label = xmlLabelMap[h] ?? h
                        const key = groupKey(label) || label
                        ;(groups[key] ??= []).push(h)
                        return groups
                      }, {})
                    ).map(([group, cols]) => (
                      <optgroup key={group} label={group}>
                        {cols.map(h => <option key={h} value={h}>{shortSelectorLabel(xmlLabelMap[h] ?? h)}</option>)}
                      </optgroup>
                    ))
                  : uploaded.headers.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
              {!idnoColumn && <span style={{ fontSize: 12, color: '#b91c1c' }}>Pflichtfeld</span>}
            </div>
          )}
          {idnoStrategy === 'auto' && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              IDs werden automatisch nach dem konfigurierten Schema vergeben.
            </div>
          )}
        </div>
      </div>

      {recordType === 'object' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hd">Medienzuordnung (optional)</div>
          <div className="bd" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label className="lbl" htmlFor="media-selector">
              {xmlLabelMap ? 'Element mit Dateinamen' : 'Spalte mit Dateinamen'}
            </label>
            <select
              id="media-selector"
              className="fld importer-source-select"
              value={mediaSelector ?? ''}
              aria-describedby="media-selector-help"
              onChange={e => onMediaSelectorChange(e.target.value || null)}
            >
              <option value="">— keine Medien zuordnen —</option>
              {xmlLabelMap
                ? Object.entries(
                    uploaded.headers.reduce<Record<string, string[]>>((groups, h) => {
                      const label = xmlLabelMap[h] ?? h
                      const key = groupKey(label) || label
                      ;(groups[key] ??= []).push(h)
                      return groups
                    }, {})
                  ).map(([group, selectors]) => (
                    <optgroup key={group} label={group}>
                      {selectors.map(selector => {
                        const repeatable = xmlSelectors?.find(s => s.path === selector)?.kind === 'list'
                        return (
                          <option key={selector} value={selector}>
                            {shortSelectorLabel(xmlLabelMap[selector] ?? selector)}{repeatable ? ' (mehrfach)' : ''}
                          </option>
                        )
                      })}
                    </optgroup>
                  ))
                : uploaded.headers.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
            <div id="media-selector-help" style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              Dateinamen werden beim Metadatenimport am Objekt gespeichert. Der spätere Ordner- oder ZIP-Upload ordnet passende Dateien automatisch zu.
            </div>
            {!mediaSelector && suggestedMediaSelector && (
              <div role="status" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                Vorschlag erkannt:{' '}
                <button className="btn sm gh" onClick={() => onMediaSelectorChange(suggestedMediaSelector)}>
                  {xmlLabelMap ? shortSelectorLabel(xmlLabelMap[suggestedMediaSelector] ?? suggestedMediaSelector) : suggestedMediaSelector} verwenden
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--fg-2)' }}>
        <b>{uploaded.row_count}</b> Zeilen geladen ·{' '}
        <b style={{ color: '#166534' }}>{mappedCount}</b> gemappt ·{' '}
        <b style={{ color: 'var(--fg-3)' }}>{ignoredCount}</b> ignoriert
      </div>

      {/* Mapping table */}
      <div className="tw">
        <table className="tbl">
          <thead>
            <tr>
              <th>{xmlLabelMap ? 'XPath-Selector' : 'Quell-Spalte'}</th>
              <th>Beispielwert</th>
              <th>→ Katalon-Feld</th>
              <th style={{ width: 140 }} />
            </tr>
          </thead>
          <tbody>
            {(() => { let prevGroup: string | null = null; return uploaded.headers.flatMap(col => {
              const mapped = mapping[col]?.target ?? ''
              const transformCount = mapping[col]?.transforms?.length ?? 0
              const isIgnored = !mapped
              const fullLabel = xmlLabelMap ? (xmlLabelMap[col] ?? col) : col
              const displayLabel = xmlLabelMap ? shortSelectorLabel(fullLabel) : fullLabel
              const group = xmlLabelMap ? groupKey(fullLabel) : null
              const showGroupHeader = xmlLabelMap && group && group !== prevGroup
              if (xmlLabelMap) prevGroup = group
              const row = (
                <tr key={col}>
                  <td className="mono" style={{ maxWidth: 200 }} title={xmlLabelMap ? fullLabel : undefined}>
                    {displayLabel}
                  </td>
                  <td style={{ color: 'var(--fg-3)', maxWidth: 220, fontSize: 12 }}>
                    {uploaded.preview[0]?.[col] ?? '—'}
                  </td>
                  <td>
                    <select
                      className="fld" style={{ height: 28, fontSize: 12 }}
                      value={mapped}
                      onChange={e => {
                        const target = e.target.value
                        const next: Record<string, MappingEntry> = { ...mapping }
                        if (target === '') {
                          delete next[col]
                        } else {
                          next[col] = { target, transforms: mapping[col]?.transforms }
                          for (const [otherCol, otherEntry] of Object.entries(next)) {
                            if (otherCol !== col && otherEntry.target === target) delete next[otherCol]
                          }
                        }
                        onMappingChange(next)
                      }}
                    >
                      <option value="">— ignorieren —</option>
                      <optgroup label={RECORD_TYPES.find(t => t.id === recordType)?.label ?? 'Felder'}>
                        {fields.map(f => {
                          const isMappedByOther = Object.entries(mapping).some(
                            ([otherCol, otherEntry]) => otherCol !== col && otherEntry.target === f.name
                          )
                          const isPending = pendingFields.some(p => p.name === f.name)
                          return (
                            <option key={f.id} value={f.name} disabled={isMappedByOther}>
                              {getLabel(f, f.name)}{f.is_required ? ' *' : ''}{isPending ? ' (neu)' : ''}{isMappedByOther ? ' (bereits zugewiesen)' : ''}
                            </option>
                          )
                        })}
                      </optgroup>
                    </select>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {!isIgnored && (
                        <button className="btn sm gh" onClick={() => setTransformModalCol(col)} title="Transformationen konfigurieren">
                          ⚙️ {transformCount > 0 && <span style={{ fontSize: 10, marginLeft: 2 }}>({transformCount})</span>}
                        </button>
                      )}
                      {!isIgnored && (
                        <button
                          className="btn sm gh"
                          onClick={() => { const next = { ...mapping }; delete next[col]; onMappingChange(next) }}
                          style={{ color: '#b91c1c' }}
                          title="Zuordnung entfernen"
                        >×</button>
                      )}
                      {isIgnored && (
                        <button className="btn sm gh" onClick={() => openNewFieldModal(col)}>+ Feld</button>
                      )}
                    </div>
                  </td>
                </tr>
              )
              if (!showGroupHeader) return [row]
              return [
                <tr key={`${col}__group`}>
                  <td colSpan={4} style={{ background: 'var(--bg-2)', fontSize: 11, fontWeight: 600, color: 'var(--fg-3)', padding: '4px 8px' }}>
                    {group}
                  </td>
                </tr>,
                row,
              ]
            }) })()}
          </tbody>
        </table>
      </div>

      {/* Transform modal */}
      {transformModalCol && (
        <TransformModal
          csvColumn={transformModalCol}
          sourceColumns={uploaded.headers}
          sampleValues={uploaded.preview.slice(0, 3).map(row => row[transformModalCol] ?? '').filter(v => v !== '')}
          sampleRows={uploaded.preview.slice(0, 3)}
          mappingEntry={mapping[transformModalCol] ?? { target: '' }}
          onSave={entry => {
            const combine = entry.transforms?.find(t => t.type === 'combine')
            const next = { ...mapping, [transformModalCol]: entry }
            for (const source of combine?.sources ?? []) {
              if (source !== transformModalCol) delete next[source]
            }
            onMappingChange(next)
            setTransformModalCol(null)
          }}
          onClose={() => setTransformModalCol(null)}
        />
      )}

      {/* New field modal */}
      {newFieldModal && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={e => { if (e.target === e.currentTarget) setNewFieldModal(null) }}
        >
          <div style={{ background: 'var(--panel)', borderRadius: 10, padding: 24, width: 400, maxWidth: '90vw' }}>
            <h3 style={{ margin: '0 0 16px' }}>Neues Feld erstellen</h3>
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
              {xmlLabelMap ? 'Element' : 'Spalte'}: <span className="mono">{xmlLabelMap ? shortSelectorLabel(xmlLabelMap[newFieldModal] ?? newFieldModal) : newFieldModal}</span>
            </div>
            <div className="field">
              <label className="lbl">Feldtyp</label>
              <select className="fld" value={newFieldType} onChange={e => setNewFieldType(e.target.value)}>
                {FIELD_TYPE_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label className="lbl">Label (Deutsch)</label>
              <input className="fld" value={newFieldLabelDe} onChange={e => setNewFieldLabelDe(e.target.value)} />
            </div>
            <div className="field">
              <label className="lbl">Label (Englisch)</label>
              <input className="fld" value={newFieldLabelEn} onChange={e => setNewFieldLabelEn(e.target.value)} />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', marginBottom: 8 }}>
              <input type="checkbox" checked={newFieldRepeatable} onChange={e => setNewFieldRepeatable(e.target.checked)} />
              Wiederholbar (mehrere Werte erlaubt)
            </label>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
              <button className="btn gh" onClick={() => setNewFieldModal(null)}>Abbrechen</button>
              <button className="btn pri" onClick={confirmCreateField}>Feld erstellen</button>
            </div>
          </div>
        </div>
      )}

      {(missingRequired.length > 0 || idnoMissing) && (
        <div style={{ marginTop: 12, fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 4, padding: '6px 10px' }}>
          {idnoMissing && <div>ID-Nummer: Bitte {xmlLabelMap ? 'ein Element' : 'eine Spalte'} auswählen oder "Automatisch" wählen.</div>}
          {missingRequired.length > 0 && <div>Pflichtfelder nicht gemappt (Import trotzdem möglich): {missingRequired.map(f => getLabel(f, f.name)).join(', ')}</div>}
        </div>
      )}

      <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn" onClick={onBack}>Zurück</button>
        <button className="btn pri" onClick={onDryRun} disabled={dryRunning || mappedCount === 0 || idnoMissing}>
          {dryRunning
            ? <><span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite', marginRight: 6 }} />Prüfe…</>
            : 'Weiter → Probelauf'}
        </button>
        {onProfileExport && Object.keys(mapping).length > 0 && (
          <button className="btn gh" onClick={onProfileExport} style={{ marginLeft: 'auto' }}>
            Profil exportieren
          </button>
        )}
      </div>
    </>
  )
}
