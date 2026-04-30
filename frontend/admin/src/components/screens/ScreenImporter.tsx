import { useState } from 'react'
import { MOCK_FIELDS } from '../../api/mock-data'
import { Upload } from '../ui/Icons'

const STEPS = ['Upload', 'Mapping', 'Probelauf', 'Import']

const SAMPLE_COLS = [
  { col: 'Titel',          sample: 'Bahnhofstraße bei Nacht' },
  { col: 'Inventar-Nr.',   sample: 'FOT.1958.0412' },
  { col: 'Fotograf',       sample: 'Henri Cartier' },
  { col: 'Jahr',           sample: '1958' },
  { col: 'Material',       sample: 'Silbergelatine' },
  { col: 'Schlagwörter',   sample: 'Architektur; Nacht; Stadt' },
]

const DRY_RUN = [
  { row: 2,  status: 'ok',    msg: 'Wird angelegt' },
  { row: 3,  status: 'ok',    msg: 'Wird angelegt' },
  { row: 4,  status: 'warn',  msg: 'Material „Lith-Druck" nicht im Vokabular' },
  { row: 5,  status: 'ok',    msg: 'Wird angelegt' },
  { row: 12, status: 'error', msg: 'Inventar-Nr. fehlt (Pflichtfeld)' },
]

export function ScreenImporter() {
  const [step, setStep] = useState(0)
  const [over, setOver] = useState(false)
  const [file, setFile] = useState<string | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})

  function handleDrop(e: React.DragEvent) {
    e.preventDefault(); setOver(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f.name)
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Importer</h1><div className="sub">CSV / Excel in Katalon übernehmen</div></div>
      </div>

      {/* Steps */}
      <div className="steps">
        {STEPS.map((s, i) => (
          <div key={s} className={`step${i === step ? ' active' : i < step ? ' done' : ''}`}>
            <div className="num">{i < step ? '✓' : i + 1}</div>
            {s}
          </div>
        ))}
      </div>

      <div style={{ padding: '24px' }}>
        {/* Step 0: Upload */}
        {step === 0 && (
          <div
            className={`dz${over ? ' over' : ''}`}
            onDragOver={e => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={handleDrop}
          >
            <div className="ic"><Upload size={40} /></div>
            {file
              ? <><div style={{ fontWeight: 600, marginBottom: 8 }}>{file}</div><div style={{ fontSize: 12 }}>Datei erkannt</div></>
              : <><div style={{ fontWeight: 600, marginBottom: 8 }}>CSV oder Excel hierher ziehen</div><div style={{ fontSize: 12 }}>oder <label style={{ color: 'var(--accent)', cursor: 'pointer' }}>Datei auswählen<input type="file" style={{ display: 'none' }} onChange={e => setFile(e.target.files?.[0]?.name ?? null)} /></label></div></>
            }
          </div>
        )}

        {/* Step 1: Mapping */}
        {step === 1 && (
          <div className="tw">
            <table className="tbl">
              <thead><tr><th>CSV-Spalte</th><th>Beispielwert</th><th>→ Katalon-Feld</th></tr></thead>
              <tbody>
                {SAMPLE_COLS.map(({ col, sample }) => (
                  <tr key={col}>
                    <td className="mono" style={{ maxWidth: 160 }}>{col}</td>
                    <td style={{ color: 'var(--fg-3)', maxWidth: 220 }}>{sample}</td>
                    <td style={{ maxWidth: 200 }}>
                      <select className="fld" style={{ height: 28, fontSize: 12 }}
                        value={mapping[col] ?? ''}
                        onChange={e => setMapping(m => ({ ...m, [col]: e.target.value }))}>
                        <option value="">— ignorieren —</option>
                        {MOCK_FIELDS.map(f => <option key={f.id} value={f.name}>{f.label.de ?? f.name}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Step 2: Dry run */}
        {step === 2 && (
          <>
            <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
              {[['ok','Angelegt','var(--st-p-fg)'],['warn','Warnungen','var(--st-i-fg)'],['error','Fehler','#b91c1c']].map(([s,l,c]) => (
                <div key={s} style={{ fontWeight: 600, color: c as string }}>
                  {DRY_RUN.filter(r => r.status === s).length} {l}
                </div>
              ))}
            </div>
            <div className="tw">
              <table className="tbl">
                <thead><tr><th>Zeile</th><th>Status</th><th>Meldung</th></tr></thead>
                <tbody>
                  {DRY_RUN.map(r => (
                    <tr key={r.row}>
                      <td className="mono" style={{ maxWidth: 60 }}>{r.row}</td>
                      <td style={{ maxWidth: 80 }}>
                        <span className={`st ${r.status === 'ok' ? 'public' : r.status === 'warn' ? 'internal' : 'draft'}`}>
                          <span className="dot" />{r.status}
                        </span>
                      </td>
                      <td style={{ color: 'var(--fg-2)' }}>{r.msg}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Step 3: Import */}
        {step === 3 && (
          <div style={{ maxWidth: 480 }}>
            <div className="card">
              <div className="hd">Import abgeschlossen</div>
              <div className="bd">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                  <div>✅ <b>4</b> Datensätze angelegt</div>
                  <div>⚠️ <b>1</b> Warnung (Vokabular-Term fehlt)</div>
                  <div>❌ <b>1</b> Fehler (Pflichtfeld leer, Zeile 12)</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
          {step > 0 && <button className="btn" onClick={() => setStep(s => s - 1)}>Zurück</button>}
          {step < 3
            ? <button className="btn pri" onClick={() => setStep(s => s + 1)} disabled={step === 0 && !file}>
                {step === 2 ? 'Jetzt importieren' : 'Weiter'}
              </button>
            : <button className="btn gh" onClick={() => { setStep(0); setFile(null) }}>Neuer Import</button>
          }
        </div>
      </div>
    </div>
  )
}
