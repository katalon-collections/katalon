import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { media } from '../../../api/client'
import type { MediaBatchStatus } from '../../../api/client'

const MEDIA_BATCH_TASK_STORAGE_KEY = 'katalon_media_batch_task_id'

interface Props {
  focusHeading?: boolean
}

export function StepMedia({ focusHeading = false }: Props) {
  const { t } = useTranslation('stepMedia')
  const [mediaArchive, setMediaArchive] = useState<File | null>(null)
  const [mediaMapping, setMediaMapping] = useState<File | null>(null)
  const [mediaFolderFiles, setMediaFolderFiles] = useState<File[]>([])
  const [mediaTaskId, setMediaTaskId] = useState<string | null>(null)
  const [mediaTaskStatus, setMediaTaskStatus] = useState<MediaBatchStatus | null>(null)
  const [mediaBusy, setMediaBusy] = useState(false)
  const [mediaErr, setMediaErr] = useState<string | null>(null)
  const mediaPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    folderInputRef.current?.setAttribute('webkitdirectory', '')
  }, [])

  useEffect(() => {
    if (focusHeading) headingRef.current?.focus()
  }, [focusHeading])

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
        setMediaErr(t('batchStatusUpdateFailed'))
      }
    }, 1500)
    return () => { if (mediaPollRef.current) clearInterval(mediaPollRef.current) }
  }, [mediaTaskId])

  async function startMediaBatchImport() {
    if (!mediaArchive && mediaFolderFiles.length === 0) {
      setMediaErr(t('selectFileOrFolder'))
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

  return (
    <div className="media-import-content" style={{ padding: '24px' }}>
      <h2 ref={headingRef} tabIndex={-1} style={{ margin: '0 0 4px', fontSize: 18 }}>{t('heading')}</h2>
      <div className="sub" style={{ marginBottom: 16 }}>
        {t('subtitle')}
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="bd" style={{ display: 'grid', gap: 10 }}>
          <label className="media-import-file" style={{ fontSize: 12 }}>
            {t('zipLabel')}
            <input type="file" accept=".zip" onChange={e => setMediaArchive(e.target.files?.[0] ?? null)} style={{ display: 'block', marginTop: 4 }} />
          </label>
          <label className="media-import-file" style={{ fontSize: 12 }}>
            {t('folderLabel')}
            <input ref={folderInputRef} type="file" multiple onChange={e => setMediaFolderFiles(Array.from(e.target.files ?? []))} style={{ display: 'block', marginTop: 4 }} />
          </label>
          <details className="media-import-manual">
            <summary>{t('manualMappingSummary')}</summary>
            <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
              <label className="media-import-file" style={{ fontSize: 12 }}>
                {t('csvLabel')}
                <input type="file" accept=".csv,.tsv" onChange={e => setMediaMapping(e.target.files?.[0] ?? null)} style={{ display: 'block', marginTop: 4 }} />
              </label>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                {t('uuidFallbackHint')}
              </div>
            </div>
          </details>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="btn pri" onClick={startMediaBatchImport} disabled={mediaBusy}>
              {mediaBusy ? t('starting') : t('startButton')}
            </button>
            {mediaTaskId && <span className="sub">{t('taskLabel', { id: mediaTaskId })}</span>}
          </div>
          {mediaErr && <div role="alert" style={{ color: '#b91c1c', fontSize: 12 }}>{mediaErr}</div>}
        </div>
      </div>

      {mediaTaskStatus && (
        <div className="card" style={{ marginTop: 12 }} role="status">
          <div className="hd">{t('statusLabel', { state: mediaTaskStatus.state })}</div>
          <div className="bd" style={{ fontSize: 12 }}>
            {(mediaTaskStatus.state === 'PENDING' || mediaTaskStatus.state === 'STARTED') && (
              <div>
                {t('runningInBackground')}
                {mediaTaskStatus.meta && (
                  <div style={{ marginTop: 6 }}>
                    {t('progressDetail', {
                      processed: mediaTaskStatus.meta.processed,
                      total: mediaTaskStatus.meta.total,
                      created: mediaTaskStatus.meta.created,
                      skipped: mediaTaskStatus.meta.skipped,
                      failed: mediaTaskStatus.meta.failed,
                    })}
                  </div>
                )}
              </div>
            )}
            {mediaTaskStatus.state === 'SUCCESS' && mediaTaskStatus.result && (
              <div style={{ display: 'grid', gap: 6 }}>
                <div>{t('successSummary', { created: mediaTaskStatus.result.created, skipped: mediaTaskStatus.result.skipped, failed: mediaTaskStatus.result.failed })}</div>
                <div>{t('missingFiles', { count: mediaTaskStatus.result.report.missing_files.length })}</div>
                <div>{t('duplicateFiles', { count: mediaTaskStatus.result.report.duplicate_files.length })}</div>
                <div>{t('unmatchedFiles', { count: mediaTaskStatus.result.report.unmatched_files.length })}</div>
                {mediaTaskStatus.result.report.errors.slice(0, 8).map((err, i) => (
                  <div key={i} style={{ color: '#b91c1c' }}>{err.message}</div>
                ))}
              </div>
            )}
            {mediaTaskStatus.state === 'FAILURE' && (
              <div style={{ color: '#b91c1c' }}>{mediaTaskStatus.error ?? t('importFailed')}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
