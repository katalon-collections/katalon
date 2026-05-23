import type { DryRunResult } from '../../../api/client'
import { UPSERT_STRATEGIES } from './types'

interface Props {
  dryResult: DryRunResult
  upsertStrategy: string
  onUpsertStrategyChange: (s: string) => void
  autoPublish: boolean
  onAutoPublishChange: (v: boolean) => void
  idnoStrategy: string
  onImport: () => void
  onBack: () => void
}

export function StepDryRun({
  dryResult, upsertStrategy, onUpsertStrategyChange,
  autoPublish, onAutoPublishChange, idnoStrategy, onImport, onBack,
}: Props) {
  return (
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
            <label className="lbl">Bestehende Datensätze (gleiche ID-Nr.)</label>
            <select className="fld" value={upsertStrategy} onChange={e => onUpsertStrategyChange(e.target.value)}>
              {UPSERT_STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" id="auto-publish" checked={autoPublish} onChange={e => onAutoPublishChange(e.target.checked)} />
              <label htmlFor="auto-publish" style={{ fontSize: 13, cursor: 'pointer' }}>
                Datensätze direkt veröffentlichen (nur wenn alle Pflichtfelder befüllt)
              </label>
            </div>
            {autoPublish && idnoStrategy === 'skip' && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#b91c1c' }}>
                Datensätze ohne ID-Nummer können nicht veröffentlicht werden. Bitte eine andere ID-Strategie wählen.
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn" onClick={onBack}>Zurück</button>
        <button className="btn pri" onClick={onImport} disabled={dryResult.valid === 0}>
          Jetzt importieren ({dryResult.valid} Datensätze)
        </button>
      </div>
    </>
  )
}
