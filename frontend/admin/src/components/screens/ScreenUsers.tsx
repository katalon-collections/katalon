import { useState, useEffect } from 'react'
import { req, BASE } from '../../api/client'
import type { UserRead } from '../../types'

const ROLES: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Redakteur',
  cataloger: 'Katalogisierer',
  viewer: 'Betrachter',
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

  useEffect(() => {
    loadUsers()
  }, [])

  function loadUsers() {
    setLoading(true)
    req<UserRead[]>(`${BASE}/v1/users`)
      .then(setUsers)
      .catch(e => setError(e.message))
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
                <th className="col-act" />
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
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
              ))}
              {users.length === 0 && (
                <tr><td colSpan={4} className="empty">Keine Benutzer gefunden.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
