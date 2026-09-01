// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { apiKeys, getTokenUser, users as usersApi } from '../../api/client'
import type { ApiKey, ApiKeyCreated, UserRead } from '../../types'

function ApiKeysPanel({ userId }: { userId: string }) {
  const { t } = useTranslation('screenUsers')
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
    if (!window.confirm(t('apiKeyRevokeConfirm'))) return
    try {
      await apiKeys.revokeForUser(userId, keyId)
      loadKeys()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <div style={{ background: 'var(--bg-s, #f9fafb)', border: '1px solid var(--border-s)', borderRadius: 6, padding: '12px 16px', marginTop: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t('apiKeysTitle')}</div>

      {created && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '10px 12px', marginBottom: 10, fontSize: 12 }}>
          <div style={{ fontWeight: 600, color: '#166534', marginBottom: 4 }}>{t('apiKeyCreated')}</div>
          <code style={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: 11, background: '#dcfce7', padding: '6px 8px', borderRadius: 4, color: '#14532d' }}>
            {created.key}
          </code>
          <button
            className="btn sm gh"
            style={{ marginTop: 6 }}
            onClick={() => { navigator.clipboard.writeText(created.key) }}
          >
            {t('apiKeyCopy')}
          </button>
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{error}</div>}

      {loading ? (
        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>{t('loading')}</div>
      ) : (
        <>
          {keys.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 10 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-s)' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('tableKeyName')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('tableKeyPrefix')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('tableKeyCreated')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: 'var(--fg-3)' }}>{t('tableKeyLastUsed')}</th>
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
                      <button className="btn sm ico gh dn" onClick={() => handleRevoke(k.id)} title={t('apiKeyRevokeTitle')}>🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {keys.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>{t('apiKeyEmpty')}</div>
          )}

          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              className="fld"
              style={{ flex: 1, fontSize: 12, padding: '4px 8px' }}
              placeholder={t('apiKeyNamePlaceholder')}
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
            />
            <button className="btn sm pri" onClick={handleCreate} disabled={creating || !newKeyName.trim()}>
              {creating ? '…' : t('apiKeyCreateButton')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function ScreenUsers({ onNavigate }: { onNavigate?: (route: string) => void }) {
  const { t } = useTranslation('screenUsers')
  const currentUser = getTokenUser()
  const ROLES: Record<string, string> = {
    admin: t('admin'), editor: t('editor'), cataloger: t('cataloger'), viewer: t('viewer'),
  }

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
      setFormError(t('formErrorRequired'))
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
      alert(t('errorSelfDeactivate'))
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
      alert(t('errorSelfDelete'))
      return
    }
    if (!window.confirm(t('deleteConfirm', { email: user.email }))) return
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
      alert(t('errorSelfRole'))
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
      setSaveError(t('errorEmailEmpty'))
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nextEmail)) {
      setSaveError(t('errorEmailInvalid'))
      return
    }
    if (nextPassword && (nextPassword.length < 8 || !/[A-Za-z]/.test(nextPassword) || !/[0-9]/.test(nextPassword))) {
      setSaveError(t('errorPasswordWeak'))
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
        <div><h1>{t('headline')}</h1><div className="sub">{t('subtitle')}</div></div>
        <div className="right">
          {onNavigate && (
            <button className="btn gh" onClick={() => onNavigate('user-roles')}>{t('rolesLink')}</button>
          )}
          <button className="btn pri" onClick={() => setShowForm(s => !s)}>
            {showForm ? t('cancel') : t('newUser')}
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ margin: '0 24px 16px', maxWidth: 480 }}>
          <div className="hd">{t('newUserTitle')}</div>
          <div className="bd">
            <div className="field">
              <div className="lbl">{t('email')}</div>
              <input className="fld" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <div className="lbl">{t('password')}</div>
              <input className="fld" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <div className="field">
              <div className="lbl">{t('role')}</div>
              <select className="fld" value={role} onChange={e => setRole(e.target.value)}>
                {Object.entries(ROLES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            {formError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{formError}</div>}
            <button className="btn pri" onClick={handleCreate} disabled={formLoading}>
              {formLoading ? t('creating') : t('create')}
            </button>
          </div>
        </div>
      )}

      {loading && <div className="empty" style={{ paddingTop: 40 }}>{t('loading')}</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div className="users-table">
          <table className="tbl">
            <thead>
              <tr>
                <th>{t('tableEmail')}</th>
                <th>{t('tableRole')}</th>
                <th>{t('tableStatus')}</th>
                <th>{t('tableCreated')}</th>
                <th>{t('tableLastLogin')}</th>
                <th>{t('tableApiKeys')}</th>
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
                      <div className="role-cell" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
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
                            {roleSaving.has(u.id) ? '…' : t('save')}
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
                        {u.is_active ? t('active') : t('inactive')}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                      {new Date(u.created_at).toLocaleDateString('de-DE')}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString('de-DE') : '—'}
                    </td>
                    <td>
                      <button
                        className="btn sm gh"
                        onClick={() => toggleKeys(u.id)}
                        title={t('apiKeysTitle')}
                        style={{ fontSize: 11 }}
                      >
                        {expandedKeys.has(u.id) ? t('toggleKeysExpanded') : t('toggleKeysCollapsed')}
                      </button>
                    </td>
                    <td className="col-act">
                      <div className="row-actions">
                         {!isSelf && (
                           <button className="btn sm gh" onClick={() => handleToggleActive(u)}>
                             {u.is_active ? t('deactivate') : t('activate')}
                           </button>
                         )}
                         <button className="btn sm gh" onClick={() => toggleCredentials(u)}>
                           {expandedCredentials.has(u.id) ? t('close') : t('credentials')}
                         </button>
                         {!isSelf && (
                           <button className="btn sm ico gh dn" onClick={() => handleDelete(u)} title={t('deleteTitle')}>
                             🗑
                           </button>
                         )}
                      </div>
                    </td>
                  </tr>
                   {expandedKeys.has(u.id) && (
                     <tr key={`${u.id}-keys`}>
                       <td colSpan={7} style={{ padding: '0 8px 12px' }}>
                         <ApiKeysPanel userId={u.id} />
                       </td>
                     </tr>
                   )}
                   {expandedCredentials.has(u.id) && (
                     <tr key={`${u.id}-credentials`}>
                       <td colSpan={7} style={{ padding: '0 8px 12px' }}>
                         <div style={{ background: 'var(--bg-s, #f9fafb)', border: '1px solid var(--border-s)', borderRadius: 6, padding: '12px 16px', marginTop: 4 }}>
<div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t('credentialsTitle')}</div>
                            <div className="field">
                              <div className="lbl">{t('email')}</div>
                              <input className="fld" type="email" value={draftEmail[u.id] ?? ''} onChange={e => setDraftEmail(prev => ({ ...prev, [u.id]: e.target.value }))} />
                            </div>
                            <div className="field">
                              <div className="lbl">{t('newPassword')}</div>
                              <input className="fld" type="password" value={draftPassword[u.id] ?? ''} onChange={e => setDraftPassword(prev => ({ ...prev, [u.id]: e.target.value }))} />
                            </div>
                            {saveError && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{saveError}</div>}
                            <div style={{ display: 'flex', gap: 8 }}>
                              <button className="btn pri" onClick={() => handleSaveCredentials(u)}>{t('save')}</button>
                              <button className="btn gh" onClick={() => toggleCredentials(u)}>{t('cancel')}</button>
                            </div>
                         </div>
                       </td>
                     </tr>
                   )}
                 </>
                )
               })}
               {userList.length === 0 && (
                <tr><td colSpan={7} className="empty">{t('empty')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
