import { useState, useEffect, useRef } from 'react'
import { importer, media, schema } from '../../api/client'
import type { UploadResult, DryRunResult, MediaBatchStatus, TaskStatus, CreatedField, MappingEntry } from '../../api/client'
import type { FieldDefinition } from '../../types'
import { getLabel } from '../../types'
import { Upload } from '../ui/Icons'
import { TransformModal } from '../importer/TransformModal'

const RECORD_TYPES = [
  { id: 'object',     label: 'Objekte' },
  { id: 'entity',     label: 'Entitäten' },
  { id: 'place',      label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
]

const IDNO_STRATEGIES = [
  { id: 'auto',   label: 'Automatisch vergeben' },
  { id: 'column', label: 'Aus Spalte "idno" lesen' },
  { id: 'skip',   label: 'Keine ID-Nr. vergeben' },
]

const UPSERT_STRATEGIES = [
  { id: 'skip',    label: 'Bestehende überspringen (nur neue anlegen)' },
  { id: 'merge',   label: 'Zusammenführen (neue Felder hinzufügen)' },
  { id: 'replace', label: 'Ersetzen (komplett überschreiben)' },
]

const FIELD_TYPE_OPTIONS = [
  { id: 'text',     label: 'Text' },
  { id: 'number',   label: 'Zahl' },
  { id: 'date',     label: 'Datum' },
  { id: 'boolean',  label: 'Boolean' },
  { id: 'vocab',    label: 'Vokabular' },
  { id: 'relation', label: 'Relation' },
]

const IMPORTER_TABS = [
  { id: 'metadata', label: 'Metadaten' },
  { id: 'media',    label: 'Medien' },
]

const STEPS = ['Upload', 'Mapping', 'Probelauf', 'Import']
const MEDIA_BATCH_TASK_STORAGE_KEY = 'katalon_media_batch_task_id'
const IMPORTER_STATE_KEY = 'katalon_importer_state'

interface PersistedImporterState {
  recordType: string
  step: number
  mapping: Record<string, MappingEntry>
  idnoStrategy: string
  upsertStrategy: string
  autoPublish: boolean
  uploaded: UploadResult | null
  dryResult: DryRunResult | null
  taskId: string | null
}

function StepBar({ step }: { step: number }) {
  return (
    <div className="steps">
      {STEPS.map((s, i) => (
        <div key={s} className={`step${i === step ? ' active' : i < step ? ' done' : ''}`}>
          <div className="num">{i < step ? '✓' : i + 1}</div>
          {s}
        </div>
      ))}
    </div>
  )
}

function migrateOldMapping(mapping: Record<string, any>): Record<string, MappingEntry> {
  const result: Record<string, MappingEntry> = {}
  for (const [col, entry] of Object.entries(mapping)) {
    if (!entry) continue
    if (typeof entry === 'string') {
      result[col] = { target: entry }
    } else if (entry.target) {
      const transforms = entry.transforms ?? []
      if (entry.delimiter && !transforms.some((t: any) => t.type === 'split')) {
        transforms.push({ type: 'split', delimiter: entry.delimiter, filter_empty: true })
      }
      result[col] = { target: entry.target, transforms: transforms.length > 0 ? transforms : undefined }
    }
  }
  return result
}

function loadPersistedState(): PersistedImporterState | null {
  try {
    const raw = localStorage.getItem(IMPORTER_STATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (typeof parsed.recordType === 'string' && typeof parsed.step === 'number') {
      if (parsed.mapping) {
        parsed.mapping = migrateOldMapping(parsed.mapping)
      }
      return parsed as PersistedImporterState
    }
  } catch {
    // ignore corrupt state
  }
  return null
}

function clearPersistedState() {
  localStorage.removeItem(IMPORTER_STATE_KEY)
}

export function ScreenImporter() {
  const persisted = loadPersistedState()

  const [activeTab, setActiveTab] = useState<'metadata' | 'media'>('metadata')

  // --- Metadata import state ---
  const [step, setStep] = useState(persisted?.step ?? 0)
  const [recordType, setRecordType] = useState(persisted?.recordType ?? 'object')
  const [over, setOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState<string | null>(null)
  const [uploaded, setUploaded] = useState<UploadResult | null>(persisted?.uploaded ?? null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [mapping, setMapping] = useState<Record<string, MappingEntry>>(persisted?.mapping ?? {})
  const [dryResult, setDryResult] = useState<DryRunResult | null>(persisted?.dryResult ?? null)
  const [dryRunning, setDryRunning] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(persisted?.taskId ?? null)
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [idnoStrategy, setIdnoStrategy] = useState(persisted?.idnoStrategy ?? 'auto')
  const [upsertStrategy, setUpsertStrategy] = useState(persisted?.upsertStrategy ?? 'skip')
  const [autoPublish, setAutoPublish] = useState(persisted?.autoPublish ?? false)

  const [newFieldModal, setNewFieldModal] = useState<string | null>(null)
  const [newFieldType, setNewFieldType] = useState('text')
  const [newFieldLabelDe, setNewFieldLabelDe] = useState('')
  const [newFieldLabelEn, setNewFieldLabelEn] = useState('')
  const [newFieldRepeatable, setNewFieldRepeatable] = useState(false)
  const [creatingField, setCreatingField] = useState(false)

  const [transformModalCol, setTransformModalCol] = useState<string | null>(null)

  // --- Media batch import state ---
  const [mediaArchive, setMediaArchive] = useState<File | null>(null)
  const [mediaMapping, setMediaMapping] = useState<File | null>(null)
  const [mediaFolderFiles, setMediaFolderFiles] = useState<File[]>([])
  const [mediaTaskId, setMediaTaskId] = useState<string | null>(null)
  const [mediaTaskStatus, setMediaTaskStatus] = useState<MediaBatchStatus | null>(null)
  const [mediaBusy, setMediaBusy] = useState(false)
  const [mediaErr, setMediaErr] = useState<string | null>(null)
  const mediaPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  // Persist state
  useEffect(() => {
    const state: PersistedImporterState = {
      recordType, step, mapping, idnoStrategy, upsertStrategy, autoPublish,
      uploaded, dryResult, taskId,
    }
    localStorage.setItem(IMPORTER_STATE_KEY, JSON.stringify(state))
  }, [recordType, step, mapping, idnoStrategy, upsertStrategy, autoPublish, uploaded, dryResult, taskId])

  useEffect(() => {
    schema.list(recordType).then(setFields).catch(() => setFields([]))
  }, [recordType])

  useEffect(() => {
    if (!taskId) return
    pollRef.current = setInterval(async () => {
      try {
        const s = await importer.taskStatus(taskId)
        setTaskStatus(s)
        if (s.state === 'SUCCESS' || s.state === 'FAILURE') {
          clearInterval(pollRef.current!)
        }
      } catch {
        clearInterval(pollRef.current!)
      }
    }, 1500)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [taskId])

  useEffect(() => {
    folderInputRef.current?.setAttribute('webkitdirectory', '')
  }, [])

  useEffect(() => {
    const persistedTaskId = localStorage.getItem(MEDIA_BATCH_TASK_STORAGE_KEY)
    if (persistedTaskId) {
      setMediaTaskId(persistedTaskId)
      media.batchTaskStatus(persistedTaskId)
        .then(setMediaTaskStatus)
        .catch(() => setMediaTaskStatus({ state: 'PENDING' }))
    }
  }, [])

  useEffect(() => {
    if (!mediaTaskId) {
      localStorage.removeItem(MEDIA_BATCH_TASK_STORAGE_KEY)
      return
    }
    localStorage.setItem(MEDIA_BATCH_TASK_STORAGE_KEY, mediaTaskId)
    mediaPollRef.current = setInterval(async () => {
      try {
        const status = await media.batchTaskStatus(mediaTaskId)
        setMediaTaskStatus(status)
        if (status.state === 'SUCCESS' || status.state === 'FAILURE') {
          clearInterval(mediaPollRef.current!)
          localStorage.removeItem(MEDIA_BATCH_TASK_STORAGE_KEY)
        }
      } catch {
        clearInterval(mediaPollRef.current!)
        setMediaErr('Batch-Status konnte nicht aktualisiert werden.')
      }
    }, 1500)
    return () => { if (mediaPollRef.current) clearInterval(mediaPollRef.current) }
  }, [mediaTaskId])

  async function handleFile(file: File) {
    setUploadErr(null)
    setUploading(true)
    try {
      const result = await importer.upload(file)
      setUploaded(result)
      const autoMap: Record<string, MappingEntry> = {}
      for (const col of result.headers) {
        const norm = col.toLowerCase().replace(/[\s\-]/g, '_')
        const match = fields.find(f => f.name === norm || f.label.de?.toLowerCase() === col.toLowerCase())
        if (match) autoMap[col] = { target: match.name }
      }
      setMapping(autoMap)
      setStep(1)
    } catch (e) {
      setUploadErr((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function handleDryRun() {
    if (!uploaded) return
    setDryRunning(true)
    try {
      const result = await importer.dryRun(recordType, uploaded.rows, mapping)
      setDryResult(result)
      setStep(2)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setDryRunning(false)
    }
  }

  async function handleImport() {
    if (!uploaded) return
    try {
      const { task_id } = await importer.import(recordType, uploaded.rows, mapping, {
        idno_strategy: idnoStrategy,
        upsert_strategy: upsertStrategy,
        auto_publish: autoPublish,
      })
      setTaskId(task_id)
      setTaskStatus({ state: 'PENDING' })
      setStep(3)
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function reset() {
    setStep(0); setUploaded(null); setMapping({}); setDryResult(null)
    setTaskId(null); setTaskStatus(null); setUploadErr(null)
    setIdnoStrategy('auto'); setUpsertStrategy('skip'); setAutoPublish(false)
    clearPersistedState()
    if (fileRef.current) fileRef.current.value = ''
  }

  async function createNewField(csvColumn: string) {
    if (!uploaded) return
    const suggestion = uploaded.suggestions?.[csvColumn] ?? 'text'
    setNewFieldType(suggestion)
    setNewFieldLabelDe(csvColumn)
    setNewFieldLabelEn(csvColumn)
    // Auto-detect repeatable: if a split transform is configured for this column
    const hasSplitTransform = mapping[csvColumn]?.transforms?.some(t => t.type === 'split') ?? false
    setNewFieldRepeatable(hasSplitTransform)
    setNewFieldModal(csvColumn)
  }

  async function confirmCreateField() {
    if (!newFieldModal || !uploaded) return
    const name = newFieldModal.toLowerCase().replace(/[\s\-]/g, '_')
    setCreatingField(true)
    try {
      const result = await importer.createFields(recordType, [{
        name, field_type: newFieldType,
        label_de: newFieldLabelDe || newFieldModal,
        label_en: newFieldLabelEn || newFieldModal,
        is_repeatable: newFieldRepeatable,
      }])
      if (result.created > 0 && result.fields[0]) {
        const newField = result.fields[0]
        setFields(prev => [...prev, newField as unknown as FieldDefinition])
        setMapping(m => ({ ...m, [newFieldModal]: { target: newField.name } }))
      } else if (result.restored && result.restored.length > 0) {
        // Field was restored (undeleted) or already exists — refresh field list and map to existing
        const freshFields = await schema.list(recordType)
        setFields(freshFields)
        const existing = freshFields.find(f => f.name === name)
        if (existing) {
          setMapping(m => ({ ...m, [newFieldModal]: { target: existing.name } }))
        } else {
          alert(`Feld '${name}' existiert bereits, konnte aber nicht im Schema gefunden werden.`)
        }
      }
      setNewFieldModal(null)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setCreatingField(false)
    }
  }

  async function startMediaBatchImport() {
    if (!mediaArchive && mediaFolderFiles.length === 0) {
      setMediaErr('Bitte ZIP-Datei oder Ordner mit Bildern auswählen.')
      return
    }
    setMediaErr(null)
    setMediaBusy(true)
    try {
      const result = await media.batchImport(mediaArchive, mediaMapping, mediaFolderFiles)
      setMediaTaskId(result.task_id)
      setMediaTaskStatus({ state: 'PENDING' })
    } catch (e) {
      setMediaErr((e as Error).message)
    } finally {
      setMediaBusy(false)
    }
  }

  const mappedCount = Object.values(mapping).filter(m => m.target).length
  const ignoredCount = uploaded ? uploaded.headers.length - mappedCount : 0

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Importer</h1><div className="sub">Daten in Katalon übernehmen</div></div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-soft)', padding: '0 24px' }}>
        {IMPORTER_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as 'metadata' | 'media')}
            style={{
              padding: '10px 20px', fontSize: 14, fontWeight: 500, background: 'none', border: 'none',
              borderBottom: activeTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              color: activeTab === t.id ? 'var(--fg-1)' : 'var(--fg-3)',
              cursor: 'pointer', marginBottom: -1,
            }}
          >{t.label}</button>
        ))}
      </div>

      {/* ===== METADATA TAB ===== */}
      {activeTab === 'metadata' && (
        <div style={{ padding: '24px' }}>
          {/* Record type selector */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 16 }}>
            <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Typ:</span>
            {RECORD_TYPES.map(t => (
              <button
                key={t.id}
                className={`btn sm${recordType === t.id ? ' pri' : ' gh'}`}
                onClick={() => { setRecordType(t.id); reset() }}
              >{t.label}</button>
            ))}
          </div>

          <StepBar step={step} />

          <div style={{ marginTop: 24 }}>
            {/* Step 0: Upload */}
            {step === 0 && (
              <>
                <div
                  className={`dz${over ? ' over' : ''}`}
                  onDragOver={e => { e.preventDefault(); setOver(true) }}
                  onDragLeave={() => setOver(false)}
                  onDrop={e => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) handleFile(f) }}
                  onClick={() => fileRef.current?.click()}
                >
                  <div className="ic"><Upload size={40} /></div>
                  {uploading
                    ? <div style={{ fontWeight: 600 }}>Lade…</div>
                    : <>
                        <div style={{ fontWeight: 600, marginBottom: 8 }}>Datei hier ablegen oder klicken</div>
                        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>CSV, TSV oder Excel (.xlsx), UTF-8, max. 10 MB</div>
                      </>
                  }
                  <input ref={fileRef} type="file" accept=".csv,.tsv,.xlsx" style={{ display: 'none' }}
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
                </div>
                {uploadErr && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 13 }}>{uploadErr}</div>}

                {uploaded && (
                  <div className="card" style={{ marginTop: 16 }}>
                    <div className="hd">Vorschau · {uploaded.row_count} Zeilen · {uploaded.headers.length} Spalten</div>
                    <div className="bd" style={{ overflow: 'auto' }}>
                      <table className="tbl" style={{ fontSize: 12 }}>
                        <thead>
                          <tr>{uploaded.headers.map(h => <th key={h}>{h}</th>)}</tr>
                        </thead>
                        <tbody>
                          {uploaded.preview.map((row, i) => (
                            <tr key={i}>
                              {uploaded.headers.map(h => (
                                <td key={h} style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  {row[h] ?? '—'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Step 1: Mapping */}
            {step === 1 && uploaded && (
              <>
                <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--fg-2)' }}>
                  <b>{uploaded.row_count}</b> Zeilen geladen · <b style={{ color: '#166534' }}>{mappedCount}</b> gemappt · <b style={{ color: 'var(--fg-3)' }}>{ignoredCount}</b> ignoriert
                </div>
                <div className="tw">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>CSV-Spalte</th>
                        <th>Beispielwert</th>
                        <th>→ Katalon-Feld</th>
                        <th style={{ width: 140 }} />
                      </tr>
                    </thead>
                    <tbody>
                      {uploaded.headers.map(col => {
                        const mapped = mapping[col]?.target ?? ''
                        const transformCount = mapping[col]?.transforms?.length ?? 0
                        const isIgnored = !mapped
                        return (
                          <tr key={col}>
                            <td className="mono" style={{ maxWidth: 160 }}>{col}</td>
                            <td style={{ color: 'var(--fg-3)', maxWidth: 220, fontSize: 12 }}>
                              {uploaded.preview[0]?.[col] ?? '—'}
                            </td>
                            <td>
                              <select
                                className="fld"
                                style={{ height: 28, fontSize: 12 }}
                                value={mapped}
                                onChange={e => {
                                  const target = e.target.value
                                  setMapping(prev => {
                                    const next: Record<string, MappingEntry> = { ...prev }
                                    if (target === '') {
                                      delete next[col]
                                    } else {
                                      next[col] = { target, transforms: prev[col]?.transforms }
                                      for (const [otherCol, otherEntry] of Object.entries(next)) {
                                        if (otherCol !== col && otherEntry.target === target) {
                                          delete next[otherCol]
                                        }
                                      }
                                    }
                                    return next
                                  })
                                }}
                              >
                                <option value="">— ignorieren —</option>
                                <optgroup label="Systemfelder">
                                  <option value="__idno__">ID-Nummer (idno)</option>
                                </optgroup>
                                <optgroup label={RECORD_TYPES.find(t => t.id === recordType)?.label ?? 'Felder'}>
                                  {fields.map(f => {
                                    const isMappedByOther = Object.entries(mapping).some(
                                      ([otherCol, otherEntry]) => otherCol !== col && otherEntry.target === f.name
                                    )
                                    return (
                                      <option key={f.id} value={f.name} disabled={isMappedByOther}>
                                        {getLabel(f, f.name)}{f.is_required ? ' *' : ''}{isMappedByOther ? ' (bereits zugewiesen)' : ''}
                                      </option>
                                    )
                                  })}
                                </optgroup>
                              </select>
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                {!isIgnored && (
                                  <button
                                    className="btn sm gh"
                                    onClick={() => setTransformModalCol(col)}
                                    title="Transformationen konfigurieren"
                                  >
                                    ⚙️ {transformCount > 0 && <span style={{ fontSize: 10, marginLeft: 2 }}>({transformCount})</span>}
                                  </button>
                                )}
                                {!isIgnored && (
                                  <button
                                    className="btn sm gh"
                                    onClick={() => setMapping(prev => {
                                      const next = { ...prev }
                                      delete next[col]
                                      return next
                                    })}
                                    style={{ color: '#b91c1c' }}
                                    title="Zuordnung entfernen"
                                  >
                                    ×
                                  </button>
                                )}
                                {isIgnored && (
                                  <button className="btn sm gh" onClick={() => createNewField(col)}>
                                    + Feld
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Transform modal */}
                {transformModalCol && uploaded && (
                  <TransformModal
                    csvColumn={transformModalCol}
                    sampleValue={uploaded.preview[0]?.[transformModalCol] ?? ''}
                    mappingEntry={mapping[transformModalCol] ?? { target: '' }}
                    onSave={entry => {
                      setMapping(prev => ({ ...prev, [transformModalCol]: entry }))
                      setTransformModalCol(null)
                    }}
                    onClose={() => setTransformModalCol(null)}
                  />
                )}

                {/* New field modal */}
                {newFieldModal && (
                  <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 200,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }} onClick={e => { if (e.target === e.currentTarget) setNewFieldModal(null) }}>
                    <div style={{ background: 'var(--panel)', borderRadius: 10, padding: 24, width: 400, maxWidth: '90vw' }}>
                      <h3 style={{ margin: '0 0 16px' }}>Neues Feld erstellen</h3>
                      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
                        Spalte: <span className="mono">{newFieldModal}</span>
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
                        <button className="btn pri" onClick={confirmCreateField} disabled={creatingField}>
                          {creatingField ? 'Erstelle…' : 'Feld erstellen'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={reset}>Zurück</button>
                  <button className="btn pri" onClick={handleDryRun} disabled={dryRunning || mappedCount === 0}>
                    {dryRunning ? 'Prüfe…' : 'Weiter → Probelauf'}
                  </button>
                </div>
              </>
            )}

            {/* Step 2: Dry run */}
            {step === 2 && dryResult && (
              <>
                <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
                  <div style={{ fontWeight: 600 }}>{dryResult.total} Zeilen gesamt</div>
                  <div style={{ fontWeight: 600, color: '#166534' }}>{dryResult.valid} gültig</div>
                  {dryResult.errors.length > 0 && (
                    <div style={{ fontWeight: 600, color: '#b91c1c' }}>{dryResult.errors.length} Fehler</div>
                  )}
                  {dryResult.warnings.length > 0 && (
                    <div style={{ fontWeight: 600, color: '#92400e' }}>{dryResult.warnings.length} Hinweise</div>
                  )}
                </div>

                {dryResult.warnings.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    {dryResult.warnings.map((w, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 4, padding: '6px 10px', marginBottom: 4 }}>
                        {w.row ? `Zeile ${w.row}: ` : ''}{w.message}
                      </div>
                    ))}
                  </div>
                )}

                {dryResult.errors.length > 0 && (
                  <div className="tw" style={{ marginBottom: 12 }}>
                    <table className="tbl">
                      <thead><tr><th>Zeile</th><th>Fehler</th></tr></thead>
                      <tbody>
                        {dryResult.errors.map((e, i) => (
                          <tr key={i}>
                            <td className="mono" style={{ width: 60 }}>{e.row ?? '—'}</td>
                            <td style={{ color: '#b91c1c', fontSize: 12 }}>{e.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {dryResult.errors.length === 0 && (
                  <div style={{ fontSize: 13, color: '#166534', marginBottom: 12 }}>
                    Keine Fehler. {dryResult.valid} Datensätze können importiert werden.
                  </div>
                )}

                {/* Import options */}
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="hd">Import-Optionen</div>
                  <div className="bd" style={{ display: 'grid', gap: 12 }}>
                    <div>
                      <label className="lbl">ID-Nummer</label>
                      <select className="fld" value={idnoStrategy} onChange={e => setIdnoStrategy(e.target.value)}>
                        {IDNO_STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="lbl">Bestehende Datensätze (gleiche ID-Nr.)</label>
                      <select className="fld" value={upsertStrategy} onChange={e => setUpsertStrategy(e.target.value)}>
                        {UPSERT_STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                      </select>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="checkbox" className="ck" id="auto-publish" checked={autoPublish} onChange={e => setAutoPublish(e.target.checked)} />
                      <label htmlFor="auto-publish" style={{ fontSize: 13, cursor: 'pointer' }}>
                        Datensätze direkt veröffentlichen (nur wenn alle Pflichtfelder befüllt)
                      </label>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={() => setStep(1)}>Zurück</button>
                  <button className="btn pri" onClick={handleImport} disabled={dryResult.valid === 0}>
                    Jetzt importieren ({dryResult.valid} Datensätze)
                  </button>
                </div>
              </>
            )}

            {/* Step 3: Import / Result */}
            {step === 3 && (
              <div style={{ maxWidth: 520 }}>
                {(!taskStatus || taskStatus.state === 'PENDING') && (
                  <div className="card">
                    <div className="hd">Import wird gestartet…</div>
                    <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                      Der Import wird in die Warteschlange gestellt.
                    </div>
                  </div>
                )}

                {taskStatus?.state === 'STARTED' && (
                  <div className="card">
                    <div className="hd">Import läuft…</div>
                    <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                      {taskStatus.meta ? (
                        <>
                          <div style={{ marginBottom: 8 }}>
                            Zeile {taskStatus.meta.current} von {taskStatus.meta.total}
                          </div>
                          <div style={{ background: 'var(--border-soft)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                            <div style={{
                              width: `${Math.round((taskStatus.meta.current / taskStatus.meta.total) * 100)}%`,
                              background: 'var(--accent)', height: '100%', transition: 'width .3s',
                            }} />
                          </div>
                        </>
                      ) : 'Der Import läuft im Hintergrund. Bitte warten.'}
                      <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-3)' }}>Task: {taskId}</div>
                    </div>
                  </div>
                )}

                {taskStatus?.state === 'SUCCESS' && taskStatus.result && (
                  <div className="card">
                    <div className="hd">Import abgeschlossen</div>
                    <div className="bd">
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                        <div style={{ color: '#166534' }}><b>{taskStatus.result.created}</b> Datensätze angelegt</div>
                        {taskStatus.result.updated > 0 && (
                          <div style={{ color: '#1e3a8a' }}><b>{taskStatus.result.updated}</b> Datensätze aktualisiert</div>
                        )}
                        {taskStatus.result.skipped > 0 && (
                          <div style={{ color: 'var(--fg-3)' }}><b>{taskStatus.result.skipped}</b> Datensätze übersprungen</div>
                        )}
                        {typeof taskStatus.result.published === 'number' && taskStatus.result.published > 0 && (
                          <div style={{ color: '#1e3a8a' }}><b>{taskStatus.result.published}</b> Datensätze veröffentlicht</div>
                        )}
                        {typeof taskStatus.result.publish_failed === 'number' && taskStatus.result.publish_failed > 0 && (
                          <div style={{ color: '#92400e' }}>
                            <b>{taskStatus.result.publish_failed}</b> Datensätze konnten nicht veröffentlicht werden (Pflichtfelder fehlen)
                          </div>
                        )}
                        {taskStatus.result.errors.length > 0 && (
                          <div style={{ color: '#b91c1c' }}>
                            <b>{taskStatus.result.errors.length}</b> Fehler beim Import
                            <div style={{ marginTop: 6 }}>
                              {taskStatus.result.errors.slice(0, 5).map((e, i) => (
                                <div key={i} style={{ fontSize: 11 }}>Zeile {e.row}: {e.error}</div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {taskStatus?.state === 'FAILURE' && (
                  <div className="card">
                    <div className="hd">Import fehlgeschlagen</div>
                    <div className="bd" style={{ fontSize: 13, color: '#b91c1c' }}>
                      {taskStatus.error ?? 'Unbekannter Fehler'}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={() => setStep(1)}>← Zurück zum Mapping</button>
                  <button className="btn gh" onClick={reset}>Neuer Import</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ===== MEDIA TAB ===== */}
      {activeTab === 'media' && (
        <div style={{ padding: '24px' }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 18 }}>Batch-Medienimport</h2>
          <div className="sub" style={{ marginBottom: 16 }}>
            ZIP + CSV-Mapping oder Bildordner hochladen. Verarbeitung läuft asynchron im Hintergrund.
          </div>

          <div className="card" style={{ marginTop: 12 }}>
            <div className="bd" style={{ display: 'grid', gap: 10 }}>
              <label style={{ fontSize: 12 }}>
                ZIP-Archiv (optional, wenn Ordner-Upload genutzt wird)
                <input
                  type="file"
                  accept=".zip"
                  onChange={e => setMediaArchive(e.target.files?.[0] ?? null)}
                  style={{ display: 'block', marginTop: 4 }}
                />
              </label>
              <label style={{ fontSize: 12 }}>
                CSV-Mapping (optional: Spalten filename/dateiname, object_id/objekt_id, media_type/medientyp)
                <input
                  type="file"
                  accept=".csv,.tsv"
                  onChange={e => setMediaMapping(e.target.files?.[0] ?? null)}
                  style={{ display: 'block', marginTop: 4 }}
                />
              </label>
              <label style={{ fontSize: 12 }}>
                Bildordner (optional)
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  onChange={e => setMediaFolderFiles(Array.from(e.target.files ?? []))}
                  style={{ display: 'block', marginTop: 4 }}
                />
              </label>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                Ordner-Matching ohne CSV: Ordnername = Objekt-ID oder Dateiname startet mit Objekt-ID.
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button className="btn pri" onClick={startMediaBatchImport} disabled={mediaBusy}>
                  {mediaBusy ? 'Starte…' : 'Batch-Import starten'}
                </button>
                {mediaTaskId && <span className="sub">Task: {mediaTaskId}</span>}
              </div>
              {mediaErr && <div style={{ color: '#b91c1c', fontSize: 12 }}>{mediaErr}</div>}
            </div>
          </div>

          {mediaTaskStatus && (
            <div className="card" style={{ marginTop: 12 }}>
              <div className="hd">Batch-Status: {mediaTaskStatus.state}</div>
              <div className="bd" style={{ fontSize: 12 }}>
                {(mediaTaskStatus.state === 'PENDING' || mediaTaskStatus.state === 'STARTED') && (
                  <div>
                    Läuft im Hintergrund — du kannst die Seite verlassen.
                    {mediaTaskStatus.meta && (
                      <div style={{ marginTop: 6 }}>
                        {mediaTaskStatus.meta.processed}/{mediaTaskStatus.meta.total} verarbeitet · {mediaTaskStatus.meta.created} erstellt · {mediaTaskStatus.meta.failed} fehlgeschlagen
                      </div>
                    )}
                  </div>
                )}
                {mediaTaskStatus.state === 'SUCCESS' && mediaTaskStatus.result && (
                  <div style={{ display: 'grid', gap: 6 }}>
                    <div>{mediaTaskStatus.result.created} Medien importiert ({mediaTaskStatus.result.failed} Fehler)</div>
                    <div>Fehlende Dateien: {mediaTaskStatus.result.report.missing_files.length}</div>
                    <div>Doppelte Dateien: {mediaTaskStatus.result.report.duplicate_files.length}</div>
                    <div>Nicht zuordenbar: {mediaTaskStatus.result.report.unmatched_files.length}</div>
                    {mediaTaskStatus.result.report.errors.slice(0, 8).map((err, i) => (
                      <div key={i} style={{ color: '#b91c1c' }}>{err.message}</div>
                    ))}
                  </div>
                )}
                {mediaTaskStatus.state === 'FAILURE' && (
                  <div style={{ color: '#b91c1c' }}>{mediaTaskStatus.error ?? 'Batch-Import fehlgeschlagen'}</div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
