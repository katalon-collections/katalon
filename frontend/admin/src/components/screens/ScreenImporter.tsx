import { useState, useEffect, useRef } from 'react'
import { importer, schema } from '../../api/client'
import type { UploadResult, DryRunResult, TaskStatus } from '../../api/client'
import type { FieldDefinition } from '../../types'
import { Upload } from '../ui/Icons'

const RECORD_TYPES = [
  { id: 'object',     label: 'Objekte' },
  { id: 'entity',     label: 'Entitäten' },
  { id: 'place',      label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
]

const STEPS = ['Upload', 'Mapping', 'Probelauf', 'Import']

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

export function ScreenImporter() {
  const [step, setStep]               = useState(0)
  const [recordType, setRecordType]   = useState('object')
  const [over, setOver]               = useState(false)
  const [uploading, setUploading]     = useState(false)
  const [uploadErr, setUploadErr]     = useState<string | null>(null)
  const [uploaded, setUploaded]       = useState<UploadResult | null>(null)
  const [fields, setFields]           = useState<FieldDefinition[]>([])
  const [mapping, setMapping]         = useState<Record<string, string>>({})
  const [dryResult, setDryResult]     = useState<DryRunResult | null>(null)
  const [dryRunning, setDryRunning]   = useState(false)
  const [taskId, setTaskId]           = useState<string | null>(null)
  const [taskStatus, setTaskStatus]   = useState<TaskStatus | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load field definitions when record type changes
  useEffect(() => {
    schema.list(recordType).then(setFields).catch(() => setFields([]))
  }, [recordType])

  // Poll task status after import starts
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

  async function handleFile(file: File) {
    setUploadErr(null)
    setUploading(true)
    try {
      const result = await importer.upload(file)
      setUploaded(result)
      // Auto-map by name match
      const autoMap: Record<string, string> = {}
      for (const col of result.headers) {
        const norm = col.toLowerCase().replace(/[\s\-]/g, '_')
        const match = fields.find(f => f.name === norm || f.label.de?.toLowerCase() === col.toLowerCase())
        if (match) autoMap[col] = match.name
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
      const { task_id } = await importer.import(recordType, uploaded.rows, mapping)
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
    if (fileRef.current) fileRef.current.value = ''
  }

  const mappedCount = Object.values(mapping).filter(Boolean).length

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Importer</h1><div className="sub">CSV in Katalon übernehmen</div></div>
        <div className="right">
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Typ:</span>
            {RECORD_TYPES.map(t => (
              <button
                key={t.id}
                className={`btn sm${recordType === t.id ? ' pri' : ' gh'}`}
                onClick={() => { setRecordType(t.id); reset() }}
              >{t.label}</button>
            ))}
          </div>
        </div>
      </div>

      <StepBar step={step} />

      <div style={{ padding: '24px' }}>

        {/* Step 0: Upload */}
        {step === 0 && (
          <>
            <div
              className={`dz${over ? ' over' : ''}`}
              onDragOver={e => { e.preventDefault(); setOver(true) }}
              onDragLeave={() => setOver(false)}
              onDrop={e => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
              onClick={() => fileRef.current?.click()}
            >
              <div className="ic"><Upload size={40} /></div>
              {uploading
                ? <div style={{ fontWeight: 600 }}>Lade…</div>
                : <>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>CSV hier ablegen oder klicken</div>
                    <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>UTF-8, Komma- oder Semikolon-getrennt, max. 10 MB</div>
                  </>
              }
              <input ref={fileRef} type="file" accept=".csv,.tsv" style={{ display: 'none' }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
            </div>
            {uploadErr && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 13 }}>{uploadErr}</div>}
          </>
        )}

        {/* Step 1: Mapping */}
        {step === 1 && uploaded && (
          <>
            <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--fg-2)' }}>
              <b>{uploaded.row_count}</b> Zeilen geladen · {mappedCount} von {uploaded.headers.length} Spalten gemappt
            </div>
            <div className="tw">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>CSV-Spalte</th>
                    <th>Beispielwert</th>
                    <th>→ Katalon-Feld ({RECORD_TYPES.find(t => t.id === recordType)?.label})</th>
                  </tr>
                </thead>
                <tbody>
                  {uploaded.headers.map(col => (
                    <tr key={col}>
                      <td className="mono" style={{ maxWidth: 160 }}>{col}</td>
                      <td style={{ color: 'var(--fg-3)', maxWidth: 220, fontSize: 12 }}>
                        {uploaded.preview[0]?.[col] ?? '—'}
                      </td>
                      <td>
                        <select
                          className="fld"
                          style={{ height: 28, fontSize: 12 }}
                          value={mapping[col] ?? ''}
                          onChange={e => setMapping(m => ({ ...m, [col]: e.target.value }))}
                        >
                          <option value="">— ignorieren —</option>
                          {fields.map(f => (
                            <option key={f.id} value={f.name}>
                              {f.label.de ?? f.name}{f.is_required ? ' *' : ''}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
            <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
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
                    {w.message}
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
                Keine Fehler. {dryResult.valid} Datensätze können als Entwurf importiert werden.
              </div>
            )}

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
          <div style={{ maxWidth: 480 }}>
            {(!taskStatus || taskStatus.state === 'PENDING' || taskStatus.state === 'STARTED') && (
              <div className="card">
                <div className="hd">Import läuft…</div>
                <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                  Der Import läuft im Hintergrund. Bitte warten.
                  <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-3)' }}>Task: {taskId}</div>
                </div>
              </div>
            )}

            {taskStatus?.state === 'SUCCESS' && taskStatus.result && (
              <div className="card">
                <div className="hd">Import abgeschlossen</div>
                <div className="bd">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                    <div style={{ color: '#166534' }}>
                      <b>{taskStatus.result.created}</b> Datensätze als Entwurf angelegt
                    </div>
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

            <div style={{ marginTop: 16 }}>
              <button className="btn gh" onClick={reset}>Neuer Import</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
