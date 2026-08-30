import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { UploadResult } from '../../../api/client'
import { Upload } from '../../ui/Icons'
import type { ImportProfile } from './types'

interface Props {
  uploaded: UploadResult | null
  uploading: boolean
  uploadErr: string | null
  needsReupload?: boolean
  onFile: (files: File | File[]) => void
  onProfileLoaded?: (profile: ImportProfile) => void
}

export function StepUpload({ uploaded, uploading, uploadErr, needsReupload, onFile, onProfileLoaded }: Props) {
  const { t } = useTranslation('stepUpload')
  const [over, setOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const profileRef = useRef<HTMLInputElement>(null)
  const [profileErr, setProfileErr] = useState<string | null>(null)
  const [dropErr, setDropErr] = useState<string | null>(null)

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setOver(false)
    // Reject dropped folders early: a folder isn't readable as file content and
    // would otherwise fail deep inside fetch() with an opaque "Failed to fetch".
    const items = Array.from(e.dataTransfer.items ?? [])
    const hasDirectory = items.some(it => {
      const entry = it.webkitGetAsEntry?.()
      return entry != null && entry.isDirectory
    })
    if (hasDirectory) {
      setDropErr(t('folderDropNotSupported'))
      return
    }
    setDropErr(null)
    const fs = Array.from(e.dataTransfer.files ?? [])
    if (fs.length === 1) onFile(fs[0])
    else if (fs.length > 1) onFile(fs)
  }

  function handleProfileFile(file: File) {
    setProfileErr(null)
    const reader = new FileReader()
    reader.onload = e => {
      try {
        const parsed = JSON.parse(e.target?.result as string)
        if (parsed.version !== 1 || typeof parsed.mapping !== 'object') {
          setProfileErr(t('invalidProfileFormat'))
          return
        }
        onProfileLoaded?.(parsed as ImportProfile)
      } catch {
        setProfileErr(t('profileReadFailed'))
      }
    }
    reader.readAsText(file)
  }

  return (
    <>
      {needsReupload && (
        <div style={{
          marginBottom: 16, padding: '10px 14px', background: '#fefce8',
          border: '1px solid #fde047', borderRadius: 8, fontSize: 13, color: '#854d0e',
        }}>
          {t('reuploadNotice')}
        </div>
      )}
      <div
        className={`dz${over ? ' over' : ''}`}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <div className="ic"><Upload size={40} /></div>
        {uploading
          ? <div style={{ fontWeight: 600 }}>{t('loading')}</div>
          : <>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{t('dropOrClick')}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('fileTypeHint')}</div>
            </>
        }
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.tsv,.xlsx,.xml"
          multiple
          style={{ display: 'none' }}
          onChange={e => { const fs = Array.from(e.target.files ?? []); if (fs.length === 1) onFile(fs[0]); else if (fs.length > 1) onFile(fs); e.target.value = '' }}
        />
      </div>

      {uploadErr && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 13 }}>{uploadErr}</div>}
      {dropErr && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 13 }}>{dropErr}</div>}

      {uploaded && onProfileLoaded && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn sm gh"
            onClick={() => profileRef.current?.click()}
          >{t('loadProfileButton')}</button>
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
            {t('previewSummary', { rows: uploaded.row_count, columns: uploaded.headers.length })}
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
