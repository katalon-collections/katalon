import { useRef, useState } from 'react'
import type { UploadResult } from '../../../api/client'
import { Upload } from '../../ui/Icons'
import type { ImportProfile } from './types'

interface Props {
  uploaded: UploadResult | null
  uploading: boolean
  uploadErr: string | null
  onFile: (file: File) => void
  onProfileLoaded?: (profile: ImportProfile) => void
}

export function StepUpload({ uploaded, uploading, uploadErr, onFile, onProfileLoaded }: Props) {
  const [over, setOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const profileRef = useRef<HTMLInputElement>(null)
  const [profileErr, setProfileErr] = useState<string | null>(null)

  function handleProfileFile(file: File) {
    setProfileErr(null)
    const reader = new FileReader()
    reader.onload = e => {
      try {
        const parsed = JSON.parse(e.target?.result as string)
        if (parsed.version !== 1 || typeof parsed.mapping !== 'object') {
          setProfileErr('Ungültiges Profilformat (version 1 erwartet).')
          return
        }
        onProfileLoaded?.(parsed as ImportProfile)
      } catch {
        setProfileErr('Datei konnte nicht gelesen werden.')
      }
    }
    reader.readAsText(file)
  }

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

      {uploaded && onProfileLoaded && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn sm gh"
            onClick={() => profileRef.current?.click()}
          >Import-Profil laden</button>
          <input
            ref={profileRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={e => { const f = e.target.files?.[0]; if (f) handleProfileFile(f); e.target.value = '' }}
          />
          {profileErr && <span style={{ fontSize: 12, color: '#dc2626' }}>{profileErr}</span>}
        </div>
      )}

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
