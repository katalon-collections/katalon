import { useEffect, useRef, useState } from 'react'
import { importer } from '../../api/client'
import type { TaskStatus } from '../../api/client'
import { IMPORTER_STATE_KEY } from '../screens/importer/types'

function readTaskId(): string | null {
  try {
    const raw = localStorage.getItem(IMPORTER_STATE_KEY)
    if (!raw) return null
    return JSON.parse(raw)?.taskId ?? null
  } catch { return null }
}

function clearTaskId() {
  try {
    const raw = localStorage.getItem(IMPORTER_STATE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    localStorage.setItem(IMPORTER_STATE_KEY, JSON.stringify({ ...parsed, taskId: null }))
  } catch { /* ignore */ }
}

interface Props {
  currentRoute: string
}

export function ImportStatusBanner({ currentRoute }: Props) {
  const [taskId, setTaskId] = useState<string | null>(readTaskId)
  const [status, setStatus] = useState<TaskStatus | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Re-read taskId from localStorage when returning from import screen
  useEffect(() => {
    const id = readTaskId()
    if (id !== taskId) {
      setTaskId(id)
      setDismissed(false)
      setStatus(null)
    }
  }, [currentRoute]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!taskId) return
    const poll = async () => {
      try {
        const s = await importer.taskStatus(taskId)
        setStatus(s)
        if (s.state === 'SUCCESS' || s.state === 'FAILURE') {
          clearInterval(pollRef.current!)
        }
      } catch {
        clearTaskId()
        setTaskId(null)
        setStatus(null)
        clearInterval(pollRef.current!)
      }
    }
    poll()
    pollRef.current = setInterval(poll, 2000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [taskId])

  function dismiss() {
    setDismissed(true)
    clearTaskId()
    if (pollRef.current) clearInterval(pollRef.current)
  }

  async function cancel() {
    if (!taskId) return
    await importer.cancelTask(taskId).catch(() => {})
  }

  if (!taskId || dismissed || currentRoute === 'import') return null

  const done = status?.state === 'SUCCESS' || status?.state === 'FAILURE'
  const res = status?.result

  const bg = status?.state === 'FAILURE' ? '#fef2f2' : done ? '#f0fdf4' : '#eff6ff'
  const border = status?.state === 'FAILURE' ? '#fca5a5' : done ? '#86efac' : '#93c5fd'
  const color = status?.state === 'FAILURE' ? '#b91c1c' : done ? '#166534' : '#1d4ed8'

  function label() {
    if (!status || status.state === 'PENDING') return 'Import läuft…'
    if (status.state === 'STARTED') {
      const m = status.meta
      return m ? `Import läuft… ${m.current} / ${m.total}` : 'Import läuft…'
    }
    if (status.state === 'FAILURE') return `Import fehlgeschlagen: ${status.error ?? ''}`
    if (res) {
      const parts = [`${res.created} angelegt`, `${res.updated} aktualisiert`]
      if (res.errors?.length) parts.push(`${res.errors.length} Fehler`)
      return `Import abgeschlossen: ${parts.join(', ')}`
    }
    return 'Import abgeschlossen'
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '6px 16px', fontSize: 12, fontWeight: 500,
      background: bg, borderBottom: `1px solid ${border}`, color,
    }}>
      {!done && (
        <span style={{
          display: 'inline-block', width: 10, height: 10, flexShrink: 0,
          border: `2px solid ${color}40`, borderTopColor: color,
          borderRadius: '50%', animation: 'spin .7s linear infinite',
        }} />
      )}
      <span style={{ flex: 1 }}>{label()}</span>
      {!done && (
        <button
          onClick={cancel}
          style={{ background: 'none', border: `1px solid ${color}60`, borderRadius: 4, cursor: 'pointer', color, fontSize: 11, padding: '2px 8px' }}
        >Abbrechen</button>
      )}
      {done && (
        <button
          onClick={dismiss}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color, fontSize: 14, lineHeight: 1, padding: '0 2px' }}
          aria-label="Schließen"
        >×</button>
      )}
    </div>
  )
}
