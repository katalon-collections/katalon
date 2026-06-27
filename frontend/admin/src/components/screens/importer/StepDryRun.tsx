import { useState } from 'react'
import type { DryRunResult } from '../../../api/client'
import { UPSERT_STRATEGIES } from './types'

const PAGE = 50

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
  const [page, setPage] = useState(0)

  // Group errors by message to avoid rendering tens of thousands of rows
  const grouped = Object.values(
    dryResult.errors.reduce<Record<string, { message: string; rows: number[]; count: number }>>((acc, e) => {
      const key = e.message
      if (!acc[key]) acc[key] = { message: key, rows: [], count: 0 }
      acc[key].count++
      if (acc[key].rows.length < 5) acc[key].rows.push(e.row ?? 0)
      return acc
    }, {})
  ).sort((a, b) => b.count - a.count)

  const totalPages = Math.ceil(grouped.length / PAGE)
  const pageItems = grouped.slice(page * PAGE, (page + 1) * PAGE)

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

      {grouped.length > 0 && (
        <div className="tw" style={{ marginBottom: 12 }}>
          <table className="tbl">
            <thead><tr><th>Fehler</th><th style={{ width: 80, textAlign: 'right' }}>Zeilen</th><th>Beispiel-Zeilen</th></tr></thead>
            <tbody>
              {pageItems.map((g, i) => (
                <tr key={i}>
                  <td style={{ color: '#b91c1c', fontSize: 12 }}>{g.message}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{g.count}</td>
                  <td className="mono" style={{ fontSize: 11, color: '#6b7280' }}>
                    {g.rows.filter(r => r > 0).join(', ')}{g.count > 5 ? ' …' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, fontSize: 12 }}>
              <button className="btn sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>‹</button>
              <span>{page + 1} / {totalPages} ({grouped.length} verschiedene Fehler)</span>
              <button className="btn sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}>›</button>
            </div>
          )}
        </div>
      )}

      {dryResult.vocab_warnings && dryResult.vocab_warnings.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {dryResult.vocab_warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 12, background: w.high_cardinality ? '#fff7ed' : '#f0fdf4', border: `1px solid ${w.high_cardinality ? '#fed7aa' : '#bbf7d0'}`, borderRadius: 4, padding: '6px 10px', marginBottom: 4 }}>
              {w.high_cardinality
                ? `⚠ Feld „${w.label}": ${w.unique_count} verschiedene Werte, davon ${w.new_count} neu. Soll diese Spalte wirklich als Vokabular verwendet werden?`
                : `Feld „${w.label}": ${w.new_count} neue Vokabular-Terms werden angelegt (${w.unique_count} eindeutige Werte).`
              }
            </div>
          ))}
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
