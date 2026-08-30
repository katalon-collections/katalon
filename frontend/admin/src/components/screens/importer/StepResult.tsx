import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TaskStatus } from '../../../api/client'

interface Props {
  taskStatus: TaskStatus | null
  taskId: string | null
  onBack: () => void
  onReset: () => void
  onOpenMedia: () => void
  mediaReferencesSelected: boolean
}

export function StepResult({ taskStatus, taskId, onBack, onReset, onOpenMedia, mediaReferencesSelected }: Props) {
  const { t } = useTranslation('stepResult')
  const historyRef = useRef<{ t: number; n: number }[]>([])
  const [eta, setEta] = useState<number | null>(null)

  function formatEta(seconds: number): string {
    if (seconds < 60) return t('etaSeconds', { count: seconds })
    return t('etaMinutes', { count: Math.ceil(seconds / 60) })
  }

  useEffect(() => {
    if (taskStatus?.state !== 'STARTED' || !taskStatus.meta) return
    const now = Date.now()
    const cur = taskStatus.meta.current
    historyRef.current = [
      ...historyRef.current.filter(p => now - p.t < 10_000),
      { t: now, n: cur },
    ]
    if (historyRef.current.length >= 2) {
      const oldest = historyRef.current[0]
      const newest = historyRef.current[historyRef.current.length - 1]
      const rate = (newest.n - oldest.n) / ((newest.t - oldest.t) / 1000)
      if (rate > 0) setEta(Math.ceil((taskStatus.meta.total - newest.n) / rate))
    }
  }, [taskStatus?.state, taskStatus?.meta?.current])

  return (
    <div style={{ maxWidth: 520 }}>
      {(!taskStatus || taskStatus.state === 'PENDING') && (
        <div className="card">
          <div className="hd">{t('startingHeading')}</div>
          <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
            {t('queuedMessage')}
          </div>
        </div>
      )}

      {taskStatus?.state === 'STARTED' && (
        <div className="card">
          <div className="hd">{t('runningHeading')}</div>
          <div className="bd" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
            {taskStatus.meta ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
                  <span>{t('rowProgress', { current: taskStatus.meta.current, total: taskStatus.meta.total })}</span>
                  {eta !== null && <span style={{ color: 'var(--fg-3)' }}>{t('etaRemaining', { eta: formatEta(eta) })}</span>}
                </div>
                <div style={{ background: 'var(--border-soft)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.round((taskStatus.meta.current / taskStatus.meta.total) * 100)}%`,
                    background: 'var(--accent)', height: '100%', transition: 'width .3s',
                  }} />
                </div>
              </>
            ) : t('runningInBackground')}
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-3)' }}>{t('taskLabel', { id: taskId })}</div>
          </div>
        </div>
      )}

      {taskStatus?.state === 'SUCCESS' && taskStatus.result && (
        <div className="card">
          <div className="hd">{t('completedHeading')}</div>
          <div className="bd">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
              <div style={{ color: '#166534' }}><b>{taskStatus.result.created}</b> {t('createdCount')}</div>
              {taskStatus.result.updated > 0 && (
                <div style={{ color: '#1e3a8a' }}><b>{taskStatus.result.updated}</b> {t('updatedCount')}</div>
              )}
              {taskStatus.result.skipped > 0 && (
                <div style={{ color: 'var(--fg-3)' }}><b>{taskStatus.result.skipped}</b> {t('skippedCount')}</div>
              )}
              {typeof taskStatus.result.published === 'number' && taskStatus.result.published > 0 && (
                <div style={{ color: '#1e3a8a' }}><b>{taskStatus.result.published}</b> {t('publishedCount')}</div>
              )}
              {typeof taskStatus.result.publish_failed === 'number' && taskStatus.result.publish_failed > 0 && (
                <div style={{ color: '#92400e' }}>
                  <b>{taskStatus.result.publish_failed}</b> {t('publishFailedCount')}
                  {(taskStatus.result.publish_fail_reasons ?? []).length > 0 && (
                    <ul style={{ margin: '4px 0 0 16px', fontSize: 12 }}>
                      {(taskStatus.result.publish_fail_reasons ?? []).map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  )}
                </div>
              )}
              {mediaReferencesSelected && (
                <div style={{ color: '#166534' }}>
                  <b>{taskStatus.result.media_references_created ?? 0}</b> {t('mediaReferencesCount')}
                </div>
              )}
              {taskStatus.result.errors.length > 0 && (
                <div style={{ color: '#b91c1c' }}>
                  <b>{taskStatus.result.errors.length}</b> {t('errorCount')}
                  <div style={{ marginTop: 6 }}>
                    {taskStatus.result.errors.slice(0, 5).map((e, i) => (
                      <div key={i} style={{ fontSize: 11 }}>{t('rowError', { row: e.row, error: e.error })}</div>
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
          <div className="hd">{t('failedHeading')}</div>
          <div className="bd" style={{ fontSize: 13, color: '#b91c1c' }}>
            {taskStatus.error ?? t('unknownError')}
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn" onClick={onBack}>{t('backToMapping')}</button>
        {taskStatus?.state === 'SUCCESS' && mediaReferencesSelected && (
          <button className="btn pri" onClick={onOpenMedia}>{t('uploadMedia')}</button>
        )}
        <button className="btn gh" onClick={onReset}>{t('newImport')}</button>
      </div>
    </div>
  )
}
