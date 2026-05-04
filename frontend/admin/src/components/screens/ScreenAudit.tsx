import { useState, useEffect } from 'react'
import { audit } from '../../api/client'
import type { AuditEntry } from '../../types'
import { Check, Edit, Trash, Globe } from '../ui/Icons'

const ACTION_LABELS: Record<string, string> = {
  create: 'Angelegt', update: 'Geändert', delete: 'Gelöscht', publish: 'Veröffentlicht',
}
const ACTION_ICON: Record<string, React.ReactNode> = {
  create:  <Check size={13} />,
  update:  <Edit size={13} />,
  delete:  <Trash size={13} />,
  publish: <Globe size={13} />,
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function userDisplay(entry: AuditEntry) {
  return entry.user_name ?? (entry.user_id ? entry.user_id.slice(-8) : '—')
}

export function ScreenAudit() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    audit.list({ limit: 200 })
      .then(setEntries)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const items = filter === 'all' ? entries : entries.filter(e => e.action === filter)

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Audit-Log</h1><div className="sub">Alle Änderungen im System</div></div>
      </div>

      <div className="toolbar">
        {['all', 'create', 'update', 'delete', 'publish'].map(a => (
          <button key={a} className={`btn${filter === a ? ' pri' : ' gh'}`} onClick={() => setFilter(a)}>
            {a === 'all' ? 'Alle' : ACTION_LABELS[a]}
          </button>
        ))}
      </div>

      {loading && <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div className="timeline">
          {items.map(evt => {
            const diff = evt.changed_fields as { old?: Record<string, string>; new?: Record<string, string> }
            return (
              <div key={evt.id} className={`evt ic-${evt.action}`}>
                <div className="when">{fmt(evt.created_at)}</div>
                <div className="ic">{ACTION_ICON[evt.action]}</div>
                <div className="body">
                  <div className="ti">
                    {ACTION_LABELS[evt.action] ?? evt.action}: <b>{String(evt.record_id)}</b>
                  </div>
                  <div className="sub">{evt.record_type} · {evt.action}</div>
                  {diff.old && (
                    <div className="diff">
                      {Object.entries(diff.old).map(([k, v]) => (
                        <div key={k}>
                          <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{k}: </span>
                          <span className="rem">{String(v)}</span>
                          {' → '}
                          <span className="add">{String((diff.new ?? {})[k] ?? '')}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="who">
                  <div className="av">{(userDisplay(evt)[0] ?? '?').toUpperCase()}</div>
                  {userDisplay(evt)}
                </div>
              </div>
            )
          })}
          {items.length === 0 && <div className="empty">Keine Einträge.</div>}
        </div>
      )}
    </div>
  )
}
