import { Fragment, useState, useEffect } from 'react'
import { apiKeys, getTokenUser, users as usersApi } from '../../api/client'
import type { ApiKey, ApiKeyCreated, RolePermission, UserRead } from '../../types'

const ROLES: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Redakteur',
  cataloger: 'Katalogisierer',
  viewer: 'Betrachter',
}

const RECORD_TYPES: { id: RolePermission['record_type']; label: string }[] = [
  { id: 'object', label: 'Objekte' },
  { id: 'entity', label: 'Entitäten' },
  { id: 'place', label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
  { id: 'procedure', label: 'Vorgänge' },
]
const ACTIONS: { id: RolePermission['action']; label: string }[] = [
  { id: 'read', label: 'Lesen' },
  { id: 'create', label: 'Anlegen' },
  { id: 'update', label: 'Bearbeiten' },
  { id: 'delete', label: 'Löschen' },
]
const PERMISSION_ROLES: RolePermission['role'][] = ['editor', 'cataloger', 'viewer']

function RolePermissionsPanel() {
  const [permissions, setPermissions] = useState<RolePermission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    usersApi.permissions().then(setPermissions).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  function has(role: RolePermission['role'], recordType: RolePermission['record_type'], action: RolePermission['action']) {
    return permissions.some(p => p.role === role && p.record_type === recordType && p.action === action)
  }

  function toggle(role: RolePermission['role'], recordType: RolePermission['record_type'], action: RolePermission['action']) {
    setPermissions(current => has(role, recordType, action)
      ? current.filter(p => !(p.role === role && p.record_type === recordType && p.action === action))
      : [...current, { role, record_type: recordType, action }])
  }

  async function save(role: RolePermission['role']) {
    setSaving(role)
    setError(null)
    try {
      const saved = await usersApi.updatePermissions(role, permissions.filter(p => p.role === role))
      setPermissions(current => [...current.filter(p => p.role !== role), ...saved])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(null)
    }
  }

  return (
    <section className="card" style={{ margin: '0 24px 16px' }} aria-labelledby="permissions-title">
      <div className="hd" id="permissions-title">Rollenrechte</div>
      <div className="bd">
        <p style={{ marginTop: 0, fontSize: 12, color: 'var(--fg-3)' }}>Öffentliche Portal-Inhalte bleiben davon unberührt. Rechte steuern interne Datensätze und Aktionen.</p>
        {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{error}</div>}
        {loading ? <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Lade…</div> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: 720 }}>
              <thead><tr><th>Datensatztyp</th>{ACTIONS.map(action => <th key={action.id}>{action.label}</th>)}<th /></tr></thead>
              <tbody>{PERMISSION_ROLES.map(role => (
                <Fragment key={role}><tr><td colSpan={6} style={{ fontWeight: 600, background: 'var(--bg-s, #f9fafb)' }}>{ROLES[role]}</td></tr>
                {RECORD_TYPES.map(type => <tr key={`${role}-${type.id}`}><td>{type.label}</td>{ACTIONS.map(action => <td key={action.id}><input type="checkbox" checked={has(role, type.id, action.id)} onChange={() => toggle(role, type.id, action.id)} aria-label={`${ROLES[role]}: ${type.label} ${action.label}`} /></td>)}<td /></tr>)}
                <tr><td colSpan={6} style={{ textAlign: 'right' }}><button className="btn sm pri" onClick={() => save(role)} disabled={saving === role}>{saving === role ? 'Speichert…' : `${ROLES[role]} speichern`}</button></td></tr>
                </Fragment>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
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
  const currentUser = getTokenUser()

  const [userList, setUserList] = useState<UserRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('cataloger')
  const [formError, setFormError] = useState<string | null>(null)
  const [formLoading, setFormLoading] = useState(false)

  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const [expandedCredentials, setExpandedCredentials] = useState<Set<string>>(new Set())
  const [draftEmail, setDraftEmail] = useState<Record<string, string>>({})
  const [draftPassword, setDraftPassword] = useState<Record<string, string>>({})
  const [saveError, setSaveError] = useState<string | null>(null)

  const [draftRole, setDraftRole] = useState<Record<string, string>>({})
  const [roleSaving, setRoleSaving] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadUsers()
  }, [])

  function loadUsers() {
    setLoading(true)
    usersApi.list()
      .then(setUserList)
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
      await usersApi.create({ email, password, role })
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
    if (user.email === currentUser?.email) {
      alert('Eigenes Konto kann nicht deaktiviert werden.')
      return
    }
    try {
      await usersApi.update(user.id, { is_active: !user.is_active })
      loadUsers()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleDelete(user: UserRead) {
    if (user.email === currentUser?.email) {
      alert('Eigenes Konto kann nicht gelöscht werden.')
      return
    }
    if (!window.confirm(`Benutzer ${user.email} wirklich löschen?`)) return
    try {
      await usersApi.remove(user.id)
      loadUsers()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleRoleChange(user: UserRead) {
    const nextRole = draftRole[user.id]
    if (!nextRole || nextRole === user.role) return
    if (user.email === currentUser?.email) {
      alert('Eigene Rolle kann nicht geändert werden.')
      return
    }
    setRoleSaving(prev => new Set(prev).add(user.id))
    try {
      await usersApi.update(user.id, { role: nextRole })
      loadUsers()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setRoleSaving(prev => {
        const next = new Set(prev)
        next.delete(user.id)
        return next
      })
    }
  }

  function toggleKeys(userId: string) {
    setExpandedKeys(prev => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  function toggleCredentials(user: UserRead) {
    setSaveError(null)
    setExpandedCredentials(prev => {
      const next = new Set(prev)
      if (next.has(user.id)) next.delete(user.id)
      else next.add(user.id)
      return next
    })
    setDraftEmail(prev => ({ ...prev, [user.id]: prev[user.id] ?? user.email }))
    setDraftPassword(prev => ({ ...prev, [user.id]: prev[user.id] ?? '' }))
  }

  async function handleSaveCredentials(user: UserRead) {
    const nextEmail = (draftEmail[user.id] ?? '').trim()
    const nextPassword = draftPassword[user.id] ?? ''
    if (!nextEmail) {
      setSaveError('E-Mail darf nicht leer sein.')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nextEmail)) {
      setSaveError('Bitte eine gültige E-Mail-Adresse eingeben.')
      return
    }
    if (nextPassword && (nextPassword.length < 8 || !/[A-Za-z]/.test(nextPassword) || !/[0-9]/.test(nextPassword))) {
      setSaveError('Neues Passwort muss mindestens 8 Zeichen sowie Buchstaben und Zahlen enthalten.')
      return
    }
    try {
      await usersApi.update(user.id, { email: nextEmail, ...(nextPassword ? { password: nextPassword } : {}) })
      setDraftPassword(prev => ({ ...prev, [user.id]: '' }))
      setExpandedCredentials(prev => {
        const next = new Set(prev)
        next.delete(user.id)
        return next
      })
      loadUsers()
    } catch (e) {
      setSaveError((e as Error).message)
    }
  }

  return (
    <div className="scroll users-screen">
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

      <RolePermissionsPanel />

      {loading && <div className="empty" style={{ paddingTop: 40 }}>Lade…</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div className="users-table">
          <table className="tbl">
            <thead>
              <tr>
                <th>E-Mail</th>
                <th>Rolle</th>
                <th>Status</th>
                <th>Erstellt</th>
                <th>API-Schlüssel</th>
                 <th className="col-act" />
               </tr>
            </thead>
            <tbody>
               {userList.map(u => {
                const isSelf = u.email === currentUser?.email
                const roleChanged = (draftRole[u.id] ?? u.role) !== u.role
                return (
                <>
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <select
                          className="fld"
                          style={{ fontSize: 12, padding: '2px 6px', minWidth: 130 }}
                          value={draftRole[u.id] ?? u.role}
                          disabled={isSelf}
                          onChange={e => setDraftRole(prev => ({ ...prev, [u.id]: e.target.value }))}
                        >
                          {Object.entries(ROLES).map(([k, v]) => (
                            <option key={k} value={k}>{v}</option>
                          ))}
                        </select>
                        {roleChanged && !isSelf && (
                          <button
                            className="btn sm pri"
                            style={{ fontSize: 11, padding: '2px 8px' }}
                            disabled={roleSaving.has(u.id)}
                            onClick={() => handleRoleChange(u)}
                          >
                            {roleSaving.has(u.id) ? '…' : 'Speichern'}
                          </button>
                        )}
                      </div>
                    </td>
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
                    <td style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                      {new Date(u.created_at).toLocaleDateString('de-DE')}
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
                         {!isSelf && (
                           <button className="btn sm gh" onClick={() => handleToggleActive(u)}>
                             {u.is_active ? 'Deaktivieren' : 'Aktivieren'}
                           </button>
                         )}
                         <button className="btn sm gh" onClick={() => toggleCredentials(u)}>
                           {expandedCredentials.has(u.id) ? 'Schließen' : 'Zugangsdaten'}
                         </button>
                         {!isSelf && (
                           <button className="btn sm ico gh dn" onClick={() => handleDelete(u)} title="Löschen">
                             🗑
                           </button>
                         )}
                      </div>
                    </td>
                  </tr>
                   {expandedKeys.has(u.id) && (
                     <tr key={`${u.id}-keys`}>
                       <td colSpan={6} style={{ padding: '0 8px 12px' }}>
                         <ApiKeysPanel userId={u.id} />
                       </td>
                     </tr>
                   )}
                   {expandedCredentials.has(u.id) && (
                     <tr key={`${u.id}-credentials`}>
                       <td colSpan={6} style={{ padding: '0 8px 12px' }}>
                         <div style={{ background: 'var(--bg-s, #f9fafb)', border: '1px solid var(--border-s)', borderRadius: 6, padding: '12px 16px', marginTop: 4 }}>
                           <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Zugangsdaten ändern</div>
                           <div className="field">
                             <div className="lbl">E-Mail</div>
                             <input className="fld" type="email" value={draftEmail[u.id] ?? ''} onChange={e => setDraftEmail(prev => ({ ...prev, [u.id]: e.target.value }))} />
                           </div>
                           <div className="field">
                             <div className="lbl">Neues Passwort (optional)</div>
                             <input className="fld" type="password" value={draftPassword[u.id] ?? ''} onChange={e => setDraftPassword(prev => ({ ...prev, [u.id]: e.target.value }))} />
                           </div>
                           {saveError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{saveError}</div>}
                           <div style={{ display: 'flex', gap: 8 }}>
                             <button className="btn pri" onClick={() => handleSaveCredentials(u)}>Speichern</button>
                             <button className="btn gh" onClick={() => toggleCredentials(u)}>Abbrechen</button>
                           </div>
                         </div>
                       </td>
                     </tr>
                   )}
                 </>
                )
               })}
               {userList.length === 0 && (
                <tr><td colSpan={6} className="empty">Keine Benutzer gefunden.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
