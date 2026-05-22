import { useRef, useState } from 'react'
import type { UploadResult } from '../../../api/client'
import { Upload } from '../../ui/Icons'

interface Props {
  uploaded: UploadResult | null
  uploading: boolean
  uploadErr: string | null
  onFile: (file: File) => void
}

export function StepUpload({ uploaded, uploading, uploadErr, onFile }: Props) {
  const [over, setOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  return (
    <>
      <div
        className={`dz${over ? ' over' : ''}`}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f) }}
        onClick={() => fileRef.current?.click()}
      >
        <div className="ic"><Upload size={40} /></div>
        {uploading
          ? <div style={{ fontWeight: 600 }}>Lade…</div>
          : <>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Datei hier ablegen oder klicken</div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>CSV, TSV, Excel (.xlsx) oder XML · max. 500 MB</div>
            </>
        }
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.tsv,.xlsx,.xml"
          style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f) }}
        />
      </div>

      {uploadErr && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 13 }}>{uploadErr}</div>}

      {uploaded && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="hd">
            Vorschau · {uploaded.row_count} Zeilen · {uploaded.headers.length} Spalten
          </div>
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
  )
}
