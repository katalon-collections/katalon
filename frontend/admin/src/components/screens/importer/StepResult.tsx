import type { TaskStatus } from '../../../api/client'

interface Props {
  taskStatus: TaskStatus | null
  taskId: string | null
  onBack: () => void
  onReset: () => void
}

export function StepResult({ taskStatus, taskId, onBack, onReset }: Props) {
  return (
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
                <div style={{ marginBottom: 8 }}>Zeile {taskStatus.meta.current} von {taskStatus.meta.total}</div>
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
                  <b>{taskStatus.result.publish_failed}</b> Datensätze konnten nicht veröffentlicht werden
                  {(taskStatus.result.publish_fail_reasons ?? []).length > 0 && (
                    <ul style={{ margin: '4px 0 0 16px', fontSize: 12 }}>
                      {(taskStatus.result.publish_fail_reasons ?? []).map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  )}
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
        <button className="btn" onClick={onBack}>← Zurück zum Mapping</button>
        <button className="btn gh" onClick={onReset}>Neuer Import</button>
      </div>
    </div>
  )
}
