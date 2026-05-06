import { useState, useEffect } from 'react'
import { req, BASE, apiKeys } from '../../api/client'
import type { ApiKey, ApiKeyCreated, UserRead } from '../../types'

const ROLES: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Redakteur',
  cataloger: 'Katalogisierer',
  viewer: 'Betrachter',
}

function ApiKeysPanel({ userId }: { userId: string }) {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [newKeyName, setNewKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { loadKeys() }, [userId])

  function loadKeys() {
    setLoading(true)
    apiKeys.listForUser(userId)
      .then(setKeys)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  async function handleCreate() {
    if (!newKeyName.trim()) return
    setCreating(true)
    setError(null)
    setCreated(null)
    try {
      const result = await apiKeys.createForUser(userId, newKeyName.trim())
      setCreated(result)
      setNewKeyName('')
      loadKeys()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(keyId: string) {
    if (!window.confirm('API-Schlüssel wirklich widerrufen?')) return
    try {
      await apiKeys.revokeForUser(userId, keyId)
      loadKeys()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <div style={{ background: 'var(--bg-s, #f9fafb)', border: '1px solid var(--border-s)', borderRadius: 6, padding: '12px 16px', marginTop: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>API-Schlüssel</div>

      {created && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '10px 12px', marginBottom: 10, fontSize: 12 }}>
          <div style={{ fontWeight: 600, color: '#166534', marginBottom: 4 }}>✓ Schlüssel erstellt — bitte jetzt kopieren, er wird nicht erneut angezeigt:</div>
          <code style={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: 11, background: '#dcfce7', padding: '6px 8px', borderRadius: 4, color: '#14532d' }}>
            {created.key}
          </code>
          <button
            className="btn sm gh"
            style={{ marginTop: 6 }}
            onClick={() => { navigator.clipboard.writeText(created.key) }}
          >
            Kopieren
          </button>
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{error}</div>}

      {loading ? (
        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Lade…</div>
      ) : (
        <>
          {keys.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 10 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-s)' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Name</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Präfix</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Erstellt</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>Zuletzt verwendet</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {keys.map(k => (
                  <tr key={k.id} style={{ borderBottom: '1px solid var(--border-s)' }}>
                    <td style={{ padding: '4px 8px' }}>{k.name}</td>
                    <td style={{ padding: '4px 8px', fontFamily: 'monospace', fontSize: 11 }}>{k.key_prefix}…</td>
                    <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>{new Date(k.created_at).toLocaleDateString('de-DE')}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--fg-3)' }}>
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('de-DE') : '—'}
                    </td>
                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                      <button className="btn sm ico gh dn" onClick={() => handleRevoke(k.id)} title="Widerrufen">🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {keys.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>Keine API-Schlüssel vorhanden.</div>
          )}

          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              className="fld"
              style={{ flex: 1, fontSize: 12, padding: '4px 8px' }}
              placeholder="Name des neuen Schlüssels"
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
            />
            <button className="btn sm pri" onClick={handleCreate} disabled={creating || !newKeyName.trim()}>
              {creating ? '…' : 'Erstellen'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function ScreenUsers() {
  const [users, setUsers] = useState<UserRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('cataloger')
  const [formError, setFormError] = useState<string | null>(null)
  const [formLoading, setFormLoading] = useState(false)

  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadUsers()
  }, [])

  function loadUsers() {
    setLoading(true)
    req<UserRead[]>(`${BASE}/v1/users`)
      .then(setUsers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  async function handleCreate() {
    setFormError(null)
    if (!email.trim() || !password.trim()) {
      setFormError('E-Mail und Passwort sind Pflicht.')
      return
    }
    setFormLoading(true)
    try {
      await req<UserRead>(`${BASE}/v1/users`, {
        method: 'POST',
        body: JSON.stringify({ email, password, role }),
      })
      setShowForm(false)
      setEmail('')
      setPassword('')
      setRole('cataloger')
      loadUsers()
    } catch (e) {
      setFormError((e as Error).message)
    } finally {
      setFormLoading(false)
    }
  }

  async function handleToggleActive(user: UserRead) {
    try {
      await req<UserRead>(`${BASE}/v1/users/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      loadUsers()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleDelete(user: UserRead) {
    if (!window.confirm(`Benutzer ${user.email} wirklich löschen?`)) return
    try {
      await req(`${BASE}/v1/users/${user.id}`, { method: 'DELETE' })
      loadUsers()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function toggleKeys(userId: string) {
    setExpandedKeys(prev => {
      const next = new Set(prev)
      next.has(userId) ? next.delete(userId) : next.add(userId)
      return next
    })
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Benutzer</h1><div className="sub">Benutzerkonten verwalten</div></div>
        <div className="right">
          <button className="btn pri" onClick={() => setShowForm(s => !s)}>
            {showForm ? 'Abbrechen' : 'Benutzer anlegen'}
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ margin: '0 24px 16px', maxWidth: 480 }}>
          <div className="hd">Neuer Benutzer</div>
          <div className="bd">
            <div className="field">
              <div className="lbl">E-Mail</div>
              <input className="fld" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <div className="lbl">Passwort</div>
              <input className="fld" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <div className="field">
              <div className="lbl">Rolle</div>
              <select className="fld" value={role} onChange={e => setRole(e.target.value)}>
                {Object.entries(ROLES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            {formError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{formError}</div>}
            <button className="btn pri" onClick={handleCreate} disabled={formLoading}>
              {formLoading ? 'Anlegen…' : 'Anlegen'}
            </button>
          </div>
        </div>
      )}

      {loading && <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div style={{ padding: '0 24px' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>E-Mail</th>
                <th>Rolle</th>
                <th>Status</th>
                <th>API-Schlüssel</th>
                <th className="col-act" />
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <>
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{ROLES[u.role] ?? u.role}</td>
                    <td>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 4,
                        background: u.is_active ? '#dcfce7' : '#f3f4f6',
                        color: u.is_active ? '#166534' : '#6b7280',
                      }}>
                        {u.is_active ? 'Aktiv' : 'Inaktiv'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn sm gh"
                        onClick={() => toggleKeys(u.id)}
                        title="API-Schlüssel verwalten"
                        style={{ fontSize: 11 }}
                      >
                        {expandedKeys.has(u.id) ? '▲ Schlüssel' : '▼ Schlüssel'}
                      </button>
                    </td>
                    <td className="col-act">
                      <div className="row-actions">
                        <button className="btn sm gh" onClick={() => handleToggleActive(u)}>
                          {u.is_active ? 'Deaktivieren' : 'Aktivieren'}
                        </button>
                        <button className="btn sm ico gh dn" onClick={() => handleDelete(u)} title="Löschen">
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedKeys.has(u.id) && (
                    <tr key={`${u.id}-keys`}>
                      <td colSpan={5} style={{ padding: '0 8px 12px' }}>
                        <ApiKeysPanel userId={u.id} />
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={5} className="empty">Keine Benutzer gefunden.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
