// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  dashboard,
  getTokenUser,
  locks,
  type DashboardAuditItem,
  type DashboardProcedure,
  type DashboardRecentItem,
  type DashboardSummary,
  type DashboardWorkingSet,
  type LockInfo,
} from '../../api/client'
import { ConfirmModal } from '../ui/ConfirmModal'
import {
  AlertCircle,
  Bookmark,
  Box,
  Check,
  Folder,
  Gear,
  History,
  Image,
  Layers,
  Lightning,
  ListTree,
  Lock,
  MapPin,
  Plus,
  Refresh,
  Unlock,
  User,
  Users,
} from '../ui/Icons'

const RECORD_ROUTES: Record<string, string> = {
  object: 'form',
  collection: 'collections-form',
  entity: 'entities-form',
  place: 'places-form',
  occurrence: 'occurrences-form',
  procedure: 'procedures-form',
  storage_location: 'storage-locations',
}

const DEFAULT_SECTIONS: Record<string, boolean> = {
  recents: true,
  working_sets: true,
  my_locks: true,
  all_locks: true,
  procedures: true,
  drafts: true,
  team: true,
  system: true,
}

const STORAGE_KEY = 'katalon.dashboard_sections'

function loadSavedSections(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SECTIONS }
    const parsed = JSON.parse(raw) as Record<string, boolean>
    return { ...DEFAULT_SECTIONS, ...parsed }
  } catch {
    return { ...DEFAULT_SECTIONS }
  }
}

interface Props {
  onNavigate: (route: string, id?: string | null) => void
}

export function ScreenDashboard({ onNavigate }: Props) {
  const { t } = useTranslation('screenDashboard')
  const user = getTokenUser()
  const isAdmin = user?.role === 'admin' || user?.role === 'superuser'
  const canCreateObject = isAdmin || user?.role === 'editor' || user?.role === 'cataloger'

  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [sections, setSections] = useState<Record<string, boolean>>(loadSavedSections)
  const [showCustomize, setShowCustomize] = useState(false)

  // Unlock confirmation modal state
  const [unlockTarget, setUnlockTarget] = useState<{
    type: string
    id: string
    email: string
    isForce: boolean
  } | null>(null)

  const fetchSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await dashboard.summary()
      setSummary(data)
    } catch (e) {
      setError((e as Error).message || t('error'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void fetchSummary()
  }, [fetchSummary])

  function toggleSection(key: string) {
    setSections(prev => {
      const next = { ...prev, [key]: !prev[key] }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  function resetSections() {
    setSections({ ...DEFAULT_SECTIONS })
    localStorage.removeItem(STORAGE_KEY)
  }

  async function handleUnlockConfirm() {
    if (!unlockTarget) return
    const { type, id, isForce } = unlockTarget
    try {
      if (isForce) {
        await locks.forceUnlock(type, id)
      } else {
        await locks.release(type, id)
      }
      setUnlockTarget(null)
      await fetchSummary()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function formatRelative(dateStr: string): string {
    const d = new Date(dateStr)
    const now = new Date()
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000)
    if (diffSec < 60) return 'Gerade eben'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m`
    const diffHours = Math.floor(diffMin / 60)
    if (diffHours < 24) return `${diffHours}h`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) return 'Gestern'
    if (diffDays < 7) return `${diffDays}d`
    return d.toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })
  }

  function renderRecordIcon(type: string) {
    switch (type) {
      case 'object': return <Image size={13} />
      case 'collection': return <Folder size={13} />
      case 'entity': return <User size={13} />
      case 'place': return <MapPin size={13} />
      case 'occurrence': return <Lightning size={13} />
      case 'procedure': return <ListTree size={13} />
      case 'storage_location': return <Box size={13} />
      default: return <Layers size={13} />
    }
  }

  function renderActionLabel(action: string): string {
    switch (action) {
      case 'create': return t('actionCreate')
      case 'update': return t('actionUpdate')
      case 'delete': return t('actionDelete')
      case 'lock_set': return t('actionLockSet')
      case 'lock_released': return t('actionLockReleased')
      default: return action
    }
  }

  function renderRecordTypeLabel(type: string): string {
    const map: Record<string, string> = {
      object: 'Objekt',
      collection: 'Sammlung',
      entity: 'Entität',
      place: 'Ort',
      occurrence: 'Occurrence',
      procedure: 'Vorgang',
      storage_location: 'Lagerort',
    }
    return map[type] || type
  }

  const displayName = user?.email ? user.email.split('@')[0] : 'Katalon'

  return (
    <div className="scroll" style={{ background: 'var(--bg, #f4f5f7)', minHeight: '100%' }}>
      {/* Page Header */}
      <div className="ph" style={{ borderBottom: '1px solid var(--border)', background: 'var(--panel, #ffffff)', marginBottom: 20 }}>
        <div>
          <h1>{t('greeting', { name: displayName })}</h1>
          <div className="sub" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="badge sm" style={{ textTransform: 'capitalize' }}>
              {t(`roles.${user?.role ?? 'viewer'}`)}
            </span>
            <span>·</span>
            <span>{t('subtitle')}</span>
          </div>
        </div>

        <div className="right" style={{ flexWrap: 'wrap', gap: 10 }}>
          {/* New Object button */}
          {canCreateObject && (
            <button
              type="button"
              className="btn sm pri"
              onClick={() => onNavigate('form', null)}
            >
              <Plus size={13} />
              <span>{t('newObject')}</span>
            </button>
          )}

          {/* Customize sections dropdown button */}
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              className={`btn sm ${showCustomize ? 'sel' : 'gh'}`}
              onClick={() => setShowCustomize(!showCustomize)}
              title={t('customize')}
              aria-expanded={showCustomize}
            >
              <Gear size={13} />
              <span>{t('customize')}</span>
            </button>

            {showCustomize && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '100%',
                  marginTop: 6,
                  width: 240,
                  background: 'var(--panel, #fff)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  boxShadow: '0 8px 24px rgba(0,0,0,.12)',
                  zIndex: 20,
                  padding: 12,
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, paddingBottom: 6, borderBottom: '1px solid var(--border)' }}>
                  {t('customize')}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.recents} onChange={() => toggleSection('recents')} />
                    <span>{t('sectionRecents')}</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.working_sets} onChange={() => toggleSection('working_sets')} />
                    <span>{t('sectionWorkingSets')}</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.my_locks} onChange={() => toggleSection('my_locks')} />
                    <span>{t('sectionMyLocks')}</span>
                  </label>
                  {isAdmin && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input type="checkbox" checked={sections.all_locks} onChange={() => toggleSection('all_locks')} />
                      <span>{t('sectionAllLocks')}</span>
                    </label>
                  )}
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.procedures} onChange={() => toggleSection('procedures')} />
                    <span>{t('sectionProcedures')}</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.drafts} onChange={() => toggleSection('drafts')} />
                    <span>{t('sectionDrafts')}</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={sections.team} onChange={() => toggleSection('team')} />
                    <span>{t('sectionTeam')}</span>
                  </label>
                  {isAdmin && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input type="checkbox" checked={sections.system} onChange={() => toggleSection('system')} />
                      <span>{t('sectionSystem')}</span>
                    </label>
                  )}
                </div>
                <div style={{ marginTop: 10, paddingTop: 6, borderTop: '1px solid var(--border)', textAlign: 'right' }}>
                  <button type="button" className="btn sm gh" onClick={resetSections} style={{ fontSize: 11 }}>
                    {t('resetCustomization')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content State: Loading / Error / Data */}
      {loading && !summary && (
        <div className="empty" style={{ paddingTop: 80 }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
          <div>{t('loading')}</div>
        </div>
      )}

      {error && (
        <div className="empty" style={{ paddingTop: 80, color: 'var(--danger, #dc2626)' }}>
          <AlertCircle size={24} style={{ marginBottom: 8 }} />
          <div>{error}</div>
          <button type="button" className="btn sm pri" onClick={fetchSummary} style={{ marginTop: 12 }}>
            <Refresh size={12} />
            <span>{t('retry')}</span>
          </button>
        </div>
      )}

      {summary && (
        <div
          style={{
            maxWidth: 1400,
            margin: '0 auto',
            padding: '0 24px 40px',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            gap: 20,
            alignItems: 'start',
          }}
        >
          {/* ========================================================= */}
          {/* LEFT COLUMN: OPERATIVER ARBEITSVORRAT                      */}
          {/* ========================================================= */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* 1. ZULETZT VON MIR BEARBEITET */}
            {sections.recents && (
              <section className="card" aria-labelledby="heading-recents" style={{ margin: 0 }}>
                <div className="hd" id="heading-recents">
                  <History size={14} />
                  <span>{t('sectionRecents')}</span>
                  <span className="sub">({summary.recents.length})</span>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.recents.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noRecents')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.recents.map((item: DashboardRecentItem) => {
                        const route = RECORD_ROUTES[item.record_type] ?? 'form'
                        return (
                          <div
                            key={`${item.record_type}-${item.record_id}`}
                            onClick={() => onNavigate(route, String(item.record_id))}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '10px 16px',
                              borderBottom: '1px solid var(--border-soft)',
                              cursor: 'pointer',
                              transition: 'background .12s ease',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-2, #f9fafb)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          >
                            <span style={{ color: 'var(--fg-3)', display: 'flex', alignItems: 'center' }}>
                              {renderRecordIcon(item.record_type)}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {item.record_label}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--fg-4)', textTransform: 'capitalize' }}>
                                {renderRecordTypeLabel(item.record_type)} · {renderActionLabel(item.action)}
                              </div>
                            </div>
                            <span style={{ fontSize: 11, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--fg-4)', whiteSpace: 'nowrap' }}>
                              {formatRelative(item.created_at)}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 2. MEINE ARBEITSLISTEN */}
            {sections.working_sets && (
              <section className="card" aria-labelledby="heading-workingsets" style={{ margin: 0 }}>
                <div className="hd" id="heading-workingsets">
                  <Bookmark size={14} />
                  <span>{t('sectionWorkingSets')}</span>
                  <span className="grow" />
                  <button
                    type="button"
                    className="btn sm gh"
                    onClick={() => onNavigate('working-sets', null)}
                    style={{ fontSize: 11 }}
                  >
                    {t('viewList')}
                  </button>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.working_sets.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noWorkingSets')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.working_sets.map((ws: DashboardWorkingSet) => (
                        <div
                          key={ws.id}
                          onClick={() => onNavigate('working-sets', ws.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '10px 16px',
                            borderBottom: '1px solid var(--border-soft)',
                            cursor: 'pointer',
                            transition: 'background .12s ease',
                          }}
                          onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-2, #f9fafb)')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                        >
                          <span style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center' }}>
                            <Bookmark size={14} />
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {ws.name}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--fg-4)' }}>
                              {ws.record_type ? renderRecordTypeLabel(ws.record_type) : 'Mischliste'}
                            </div>
                          </div>
                          <span className="badge sm" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                            {t('itemsCount', { count: ws.item_count })}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 3. MEINE GESPERRTEN DATENSÄTZE */}
            {sections.my_locks && (
              <section className="card" aria-labelledby="heading-mylocks" style={{ margin: 0 }}>
                <div className="hd" id="heading-mylocks">
                  <Lock size={14} />
                  <span>{t('sectionMyLocks')}</span>
                  <span className="sub">({summary.my_locks.length})</span>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.my_locks.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noMyLocks')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.my_locks.map((lk: LockInfo) => {
                        const route = RECORD_ROUTES[lk.resource_type] ?? 'form'
                        return (
                          <div
                            key={`${lk.resource_type}-${lk.resource_id}`}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '10px 16px',
                              borderBottom: '1px solid var(--border-soft)',
                            }}
                          >
                            <span style={{ color: '#b91c1c', display: 'flex', alignItems: 'center' }}>
                              <Lock size={13} />
                            </span>
                            <div
                              style={{ flex: 1, minWidth: 0, cursor: 'pointer' }}
                              onClick={() => onNavigate(route, lk.resource_id)}
                            >
                              <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {lk.title || lk.idno || lk.resource_id}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--fg-4)' }}>
                                {lk.reason ? `Grund: ${lk.reason} · ` : ''}
                                Seit {formatRelative(lk.locked_at)}
                              </div>
                            </div>
                            <button
                              type="button"
                              className="btn sm gh"
                              title={t('unlock')}
                              onClick={() =>
                                setUnlockTarget({
                                  type: lk.resource_type,
                                  id: lk.resource_id,
                                  email: lk.locked_by_email,
                                  isForce: false,
                                })
                              }
                            >
                              <Unlock size={13} />
                              <span>{t('unlock')}</span>
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 4. ALLE AKTIVEN SPERREN IM SYSTEM (Admin / Curators) */}
            {isAdmin && sections.all_locks && summary.all_locks && (
              <section className="card" aria-labelledby="heading-alllocks" style={{ margin: 0 }}>
                <div className="hd" id="heading-alllocks">
                  <Lock size={14} style={{ color: 'var(--fg-3)' }} />
                  <span>{t('sectionAllLocks')}</span>
                  <span className="sub">({summary.all_locks.length})</span>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.all_locks.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noAllLocks')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.all_locks.map((lk: LockInfo) => {
                        const route = RECORD_ROUTES[lk.resource_type] ?? 'form'
                        return (
                          <div
                            key={`all-${lk.resource_type}-${lk.resource_id}`}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '10px 16px',
                              borderBottom: '1px solid var(--border-soft)',
                            }}
                          >
                            <span style={{ color: 'var(--fg-4)', display: 'flex', alignItems: 'center' }}>
                              {renderRecordIcon(lk.resource_type)}
                            </span>
                            <div
                              style={{ flex: 1, minWidth: 0, cursor: 'pointer' }}
                              onClick={() => onNavigate(route, lk.resource_id)}
                            >
                              <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {lk.title || lk.idno || lk.resource_id}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--fg-4)' }}>
                                {t('lockedBy', { email: lk.locked_by_email })}
                                {lk.reason ? ` · „${lk.reason}“` : ''}
                              </div>
                            </div>
                            <button
                              type="button"
                              className="btn sm dn"
                              onClick={() =>
                                setUnlockTarget({
                                  type: lk.resource_type,
                                  id: lk.resource_id,
                                  email: lk.locked_by_email,
                                  isForce: true,
                                })
                              }
                            >
                              <Unlock size={12} />
                              <span>{t('forceUnlock')}</span>
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          {/* ========================================================= */}
          {/* RIGHT COLUMN: FRISTEN, PRÜFVORRAT & TEAM-AKTIVITÄT         */}
          {/* ========================================================= */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* 5. FÄLLIGE VORGÄNGE & FRISTEN */}
            {sections.procedures && (
              <section className="card" aria-labelledby="heading-procedures" style={{ margin: 0 }}>
                <div className="hd" id="heading-procedures">
                  <ListTree size={14} />
                  <span>{t('sectionProcedures')}</span>
                  <span className="grow" />
                  <button
                    type="button"
                    className="btn sm gh"
                    onClick={() => onNavigate('procedures-list', null)}
                    style={{ fontSize: 11 }}
                  >
                    {t('viewList')}
                  </button>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.due_procedures.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noProcedures')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.due_procedures.map((proc: DashboardProcedure) => {
                        const isOverdue = proc.days_left != null && proc.days_left < 0
                        const isDueSoon = proc.days_left != null && proc.days_left <= 7
                        return (
                          <div
                            key={proc.id}
                            onClick={() => onNavigate('procedures-form', proc.id)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '10px 16px',
                              borderBottom: '1px solid var(--border-soft)',
                              cursor: 'pointer',
                              transition: 'background .12s ease',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-2, #f9fafb)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          >
                            <span style={{ color: 'var(--fg-3)', display: 'flex', alignItems: 'center' }}>
                              <ListTree size={13} />
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {proc.title}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--fg-4)' }}>
                                {proc.procedure_type} {proc.reference_number ? `· ${proc.reference_number}` : ''}
                              </div>
                            </div>
                            <span
                              className={`badge sm ${isOverdue ? 'dn' : isDueSoon ? 'warning' : ''}`}
                              style={{
                                fontFamily: 'IBM Plex Mono, monospace',
                                background: isOverdue ? '#fee2e2' : isDueSoon ? '#fef3c7' : undefined,
                                color: isOverdue ? '#991b1b' : isDueSoon ? '#92400e' : undefined,
                              }}
                            >
                              {proc.days_left == null
                                ? proc.due_date
                                : proc.days_left < 0
                                  ? t('overdue', { days: Math.abs(proc.days_left) })
                                  : proc.days_left === 0
                                    ? t('dueToday')
                                    : t('dueIn', { days: proc.days_left })}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 6. ENTWURFS-VORRAT */}
            {sections.drafts && (
              <section className="card" aria-labelledby="heading-drafts" style={{ margin: 0 }}>
                <div className="hd" id="heading-drafts">
                  <Layers size={14} />
                  <span>{t('sectionDrafts')}</span>
                </div>
                <div className="bd" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div
                    onClick={() => onNavigate('list', 'draft')}
                    style={{
                      padding: 12,
                      background: 'var(--panel-2, #f9fafb)',
                      borderRadius: 8,
                      border: '1px solid var(--border-soft)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 600, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--accent)' }}>
                      {summary.draft_counts.object ?? 0}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{t('draftObjects')}</div>
                  </div>

                  <div
                    onClick={() => onNavigate('procedures-list', 'draft')}
                    style={{
                      padding: 12,
                      background: 'var(--panel-2, #f9fafb)',
                      borderRadius: 8,
                      border: '1px solid var(--border-soft)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 600, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--fg-2)' }}>
                      {summary.draft_counts.procedure ?? 0}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{t('draftProcedures')}</div>
                  </div>
                </div>
              </section>
            )}

            {/* 7. TEAM-AKTIVITÄT (AUDIT) */}
            {sections.team && (
              <section className="card" aria-labelledby="heading-team" style={{ margin: 0 }}>
                <div className="hd" id="heading-team">
                  <Users size={14} />
                  <span>{t('sectionTeam')}</span>
                  <span className="grow" />
                  <button
                    type="button"
                    className="btn sm gh"
                    onClick={() => onNavigate('audit', null)}
                    style={{ fontSize: 11 }}
                  >
                    {t('viewList')}
                  </button>
                </div>
                <div className="bd" style={{ padding: 0 }}>
                  {summary.team_activity.length === 0 ? (
                    <div style={{ padding: '24px 16px', color: 'var(--fg-4)', fontSize: 13, textAlign: 'center' }}>
                      {t('noTeam')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {summary.team_activity.map((it: DashboardAuditItem, idx: number) => {
                        const route = RECORD_ROUTES[it.record_type] ?? 'form'
                        return (
                          <div
                            key={`team-${it.record_id}-${idx}`}
                            onClick={() => onNavigate(route, String(it.record_id))}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '10px 16px',
                              borderBottom: '1px solid var(--border-soft)',
                              cursor: 'pointer',
                              transition: 'background .12s ease',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-2, #f9fafb)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          >
                            <span style={{ color: 'var(--fg-4)', display: 'flex', alignItems: 'center' }}>
                              {renderRecordIcon(it.record_type)}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {it.record_label}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--fg-4)' }}>
                                <span style={{ fontWeight: 500, color: 'var(--fg-2)' }}>{it.user_name}</span> · {renderActionLabel(it.action)}
                              </div>
                            </div>
                            <span style={{ fontSize: 11, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--fg-4)', whiteSpace: 'nowrap' }}>
                              {formatRelative(it.created_at)}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 8. SYSTEM STATUS (Admin only) */}
            {isAdmin && sections.system && (
              <section className="card" aria-labelledby="heading-system" style={{ margin: 0 }}>
                <div className="hd" id="heading-system">
                  <Check size={14} style={{ color: '#16a34a' }} />
                  <span>{t('sectionSystem')}</span>
                  <span className="grow" />
                  <button
                    type="button"
                    className="btn sm gh"
                    onClick={() => onNavigate('settings', null)}
                    style={{ fontSize: 11 }}
                  >
                    Einstellungen
                  </button>
                </div>
                <div className="bd" style={{ padding: '12px 16px', fontSize: 12, color: 'var(--fg-3)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#15803d', fontWeight: 500 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} />
                    {t('systemHealthy')}
                  </div>
                  <div style={{ marginTop: 4, color: 'var(--fg-4)' }}>{t('systemNotice')}</div>
                </div>
              </section>
            )}
          </div>
        </div>
      )}

      {/* Unlock Confirmation Modal */}
      {unlockTarget && (
        <ConfirmModal
          title={unlockTarget.isForce ? t('forceUnlock') : t('unlock')}
          message={
            unlockTarget.isForce
              ? t('forceUnlockConfirm', { email: unlockTarget.email })
              : t('unlockConfirm')
          }
          confirmLabel={unlockTarget.isForce ? t('forceUnlock') : t('unlock')}
          cancelLabel="Abbrechen"
          danger={unlockTarget.isForce}
          onConfirm={handleUnlockConfirm}
          onCancel={() => setUnlockTarget(null)}
        />
      )}
    </div>
  )
}
