// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Fragment, useState, useEffect } from 'react'
import { users as usersApi } from '../../api/client'
import type { FeaturePermission, RolePermission } from '../../types'

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
  { id: 'collection', label: 'Sammlungen' },
  { id: 'storage_location', label: 'Lagerorte' },
  { id: 'vocabulary_term', label: 'Vokabular-Terme' },
]
const ACTIONS: { id: RolePermission['action']; label: string }[] = [
  { id: 'read', label: 'Lesen' },
  { id: 'create', label: 'Anlegen' },
  { id: 'update', label: 'Bearbeiten' },
  { id: 'delete', label: 'Löschen' },
]
const PERMISSION_ROLES: FeaturePermission['role'][] = ['editor', 'cataloger', 'viewer']

const FEATURES: { id: FeaturePermission['feature']; label: string }[] = [
  { id: 'export', label: 'Export' },
  { id: 'sparql', label: 'SPARQL-Query-Builder' },
  { id: 'import', label: 'Import' },
  { id: 'working_sets', label: 'Arbeitslisten' },
  { id: 'audit_log', label: 'Audit-Log' },
  { id: 'vocab_terms', label: 'Vokabular-Terme pflegen' },
  { id: 'vocab_structure', label: 'Vokabular-Struktur ändern' },
  { id: 'form_variants', label: 'Formularvarianten' },
  { id: 'storage_locations', label: 'Lagerorte verwalten' },
  { id: 'pages', label: 'Statische Seiten' },
  { id: 'oai_sets', label: 'OAI-PMH Sets' },
  { id: 'banners', label: 'Banner' },
  { id: 'manual_lock', label: 'Manuelle Sperre setzen' },
]

export function ScreenUserRoles() {
  const [recordPermissions, setRecordPermissions] = useState<RolePermission[]>([])
  const [featurePermissions, setFeaturePermissions] = useState<FeaturePermission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      usersApi.permissions(),
      usersApi.features(),
    ]).then(([perms, feats]) => {
      setRecordPermissions(perms)
      setFeaturePermissions(feats)
    }).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  function hasRecord(role: RolePermission['role'], recordType: RolePermission['record_type'], action: RolePermission['action']) {
    return recordPermissions.some(p => p.role === role && p.record_type === recordType && p.action === action)
  }
  function toggleRecord(role: RolePermission['role'], recordType: RolePermission['record_type'], action: RolePermission['action']) {
    setRecordPermissions(current => hasRecord(role, recordType, action)
      ? current.filter(p => !(p.role === role && p.record_type === recordType && p.action === action))
      : [...current, { role, record_type: recordType, action }])
  }

  function hasFeature(role: FeaturePermission['role'], feature: FeaturePermission['feature']) {
    return featurePermissions.some(p => p.role === role && p.feature === feature)
  }
  function toggleFeature(role: FeaturePermission['role'], feature: FeaturePermission['feature']) {
    setFeaturePermissions(current => hasFeature(role, feature)
      ? current.filter(p => !(p.role === role && p.feature === feature))
      : [...current, { role, feature }])
  }

  async function saveRecord(role: RolePermission['role']) {
    setSaving(`record-${role}`)
    setError(null)
    try {
      const saved = await usersApi.updatePermissions(role, recordPermissions.filter(p => p.role === role))
      setRecordPermissions(current => [...current.filter(p => p.role !== role), ...saved])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(null)
    }
  }

  async function saveAllFeatures() {
    setSaving('features')
    setError(null)
    try {
      for (const role of PERMISSION_ROLES) {
        const saved = await usersApi.updateFeatures(role, featurePermissions.filter(p => p.role === role))
        setFeaturePermissions(current => [...current.filter(p => p.role !== role), ...saved])
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(null)
    }
  }

  function recordTypesForRole(role: string): { id: RolePermission['record_type']; label: string }[] {
    if (role === 'viewer') return RECORD_TYPES.filter(r => r.id !== 'procedure' && r.id !== 'storage_location')
    return RECORD_TYPES
  }

  if (loading) return <div className="scroll"><div className="ph"><div><h1>Rollenrechte</h1><div className="sub">Lade…</div></div></div></div>

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Rollenrechte</h1><div className="sub">Zugriffsrechte pro Rolle verwalten</div></div>
      </div>

      {error && <div style={{ margin: '0 24px 16px', fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {/* Record Permission Matrix */}
      <section className="card" style={{ margin: '0 24px 16px' }} aria-labelledby="record-permissions-title">
        <div className="hd" id="record-permissions-title">Datensatz-Rechte</div>
        <div className="bd">
          <p style={{ marginTop: 0, fontSize: 12, color: 'var(--fg-3)' }}>
            Welche Rolle darf welchen Datensatztyp lesen, anlegen, bearbeiten oder löschen?
            Admin/Superuser haben immer vollen Zugriff.
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: 720 }}>
              <thead><tr><th>Datensatztyp</th>{ACTIONS.map(action => <th key={action.id}>{action.label}</th>)}<th /></tr></thead>
              <tbody>{PERMISSION_ROLES.map(role => (
                <Fragment key={role}><tr><td colSpan={6} style={{ fontWeight: 600, background: 'var(--bg-s, #f9fafb)' }}>{ROLES[role]}</td></tr>
                {recordTypesForRole(role).map(type => <tr key={`${role}-${type.id}`}><td>{type.label}</td>{ACTIONS.map(action => <td key={action.id}><input type="checkbox" checked={hasRecord(role, type.id, action.id)} onChange={() => toggleRecord(role, type.id, action.id)} aria-label={`${ROLES[role]}: ${type.label} ${action.label}`} /></td>)}<td /></tr>)}
                <tr><td colSpan={6} style={{ textAlign: 'right' }}><button className="btn sm pri" onClick={() => saveRecord(role)} disabled={saving === `record-${role}`}>{saving === `record-${role}` ? 'Speichert…' : `${ROLES[role]} speichern`}</button></td></tr>
                </Fragment>
              ))}</tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Feature Permission Matrix */}
      <section className="card" style={{ margin: '0 24px 16px' }} aria-labelledby="feature-permissions-title">
        <div className="hd" id="feature-permissions-title">Feature-Rechte</div>
        <div className="bd">
          <p style={{ marginTop: 0, fontSize: 12, color: 'var(--fg-3)' }}>
            Darf die Rolle bestimmte Funktionen wie Export, Import oder Vokabular-Pflege nutzen?
            Admin/Superuser haben immer Zugriff auf alle Funktionen.
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: 600 }}>
              <thead><tr><th>Feature</th>{PERMISSION_ROLES.map(role => <th key={role}>{ROLES[role]}</th>)}</tr></thead>
              <tbody>{FEATURES.map(feature => (
                <tr key={feature.id}>
                  <td>{feature.label}</td>
                  {PERMISSION_ROLES.map(role => <td key={role}><input type="checkbox" checked={hasFeature(role, feature.id)} onChange={() => toggleFeature(role, feature.id)} aria-label={`${ROLES[role]}: ${feature.label}`} /></td>)}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div style={{ marginTop: 12, textAlign: 'right' }}>
            <button className="btn sm pri" onClick={saveAllFeatures} disabled={saving === 'features'} style={{ minWidth: 120 }}>{saving === 'features' ? 'Speichert…' : 'Feature-Rechte speichern'}</button>
          </div>
        </div>
      </section>
    </div>
  )
}