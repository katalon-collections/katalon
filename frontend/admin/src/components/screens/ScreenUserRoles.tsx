// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Fragment, useState, useEffect } from 'react'
import { users as usersApi } from '../../api/client'
import type { RolePermission } from '../../types'

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

export function ScreenUserRoles() {
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
    <div className="scroll">
      <div className="ph">
        <div><h1>Rollenrechte</h1><div className="sub">Zugriffsrechte pro Rolle verwalten</div></div>
      </div>

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
    </div>
  )
}
