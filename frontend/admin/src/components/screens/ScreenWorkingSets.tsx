// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { authorizedFetch, schema, workingSets } from '../../api/client'
import type {
  FieldDefinition,
  ListableRecordType,
  WorkingSet,
  WorkingSetDetail,
  WorkingSetItem,
} from '../../types'
import { ActionMenu } from '../ui/ActionMenu'
import {
  ChevD,
  ChevL,
  ChevU,
  Edit,
  Folder,
  Layers,
  Plus,
  Search,
  Trash,
  X,
} from '../ui/Icons'
import { StatusBadge } from '../ui/StatusBadge'
import { BatchEditModal } from './BatchEditModal'

const RECORD_TYPES: { key: string; labelKey: string }[] = [
  { key: 'object', labelKey: 'recordTypes.object' },
  { key: 'entity', labelKey: 'recordTypes.entity' },
  { key: 'place', labelKey: 'recordTypes.place' },
  { key: 'occurrence', labelKey: 'recordTypes.occurrence' },
  { key: 'procedure', labelKey: 'recordTypes.procedure' },
  { key: 'collection', labelKey: 'recordTypes.collection' },
]

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString('de-CH', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}
function ItemThumbnail({ url, alt }: { url: string | null; alt: string }) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    if (!url) {
      setSrc(null)
      return
    }
    let cancelled = false
    let objectUrl: string | null = null
    authorizedFetch(url)
      .then((res) => {
        if (!res.ok) throw new Error()
        return res.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setSrc(null)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  if (!src) {
    return (
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 4,
          background: 'var(--bg-2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--fg-4)',
        }}
      >
        <Folder size={18} />
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      style={{
        width: 36,
        height: 36,
        objectFit: 'cover',
        borderRadius: 4,
        display: 'block',
      }}
    />
  )
}

interface Props {
  initialSetId?: string | null
  onOpenRecord?: (recordType: string, recordId: string) => void
}

export function ScreenWorkingSets({ initialSetId, onOpenRecord }: Props) {
  const { t } = useTranslation('screenWorkingSets')
  const { t: tRoot } = useTranslation()

  const [sets, setSets] = useState<WorkingSet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [tab, setTab] = useState<'all' | 'mine' | 'shared'>('all')

  const [activeSetId, setActiveSetId] = useState<string | null>(initialSetId ?? null)
  const [detail, setDetail] = useState<WorkingSetDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Edit / Create modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSet, setEditingSet] = useState<WorkingSet | null>(null)
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formType, setFormType] = useState('object')
  const [formShared, setFormShared] = useState(false)
  const [modalSaving, setModalSaving] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)

  // Inline note editing
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [noteVal, setNoteVal] = useState('')

  // Batch edit modal
  const [batchEditOpen, setBatchEditOpen] = useState(false)
  const [schemaFields, setSchemaFields] = useState<FieldDefinition[]>([])

  const loadSets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await workingSets.list(typeFilter ? { record_type: typeFilter } : undefined)
      setSets(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Fehler beim Laden der Arbeitslisten')
    } finally {
      setLoading(false)
    }
  }, [typeFilter])

  useEffect(() => {
    loadSets()
  }, [loadSets])

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    try {
      const d = await workingSets.get(id)
      setDetail(d)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Fehler beim Laden der Arbeitsliste')
      setActiveSetId(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeSetId) {
      loadDetail(activeSetId)
    } else {
      setDetail(null)
    }
  }, [activeSetId, loadDetail])

  // Open modal for new set
  const openNewModal = () => {
    setEditingSet(null)
    setFormName('')
    setFormDesc('')
    setFormType('object')
    setFormShared(false)
    setModalError(null)
    setModalOpen(true)
  }

  // Open modal for editing set
  const openEditModal = (s: WorkingSet) => {
    setEditingSet(s)
    setFormName(s.name)
    setFormDesc(s.description ?? '')
    setFormType(s.record_type)
    setFormShared(s.is_shared)
    setModalError(null)
    setModalOpen(true)
  }

  const handleSaveModal = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formName.trim()) return
    setModalSaving(true)
    setModalError(null)
    try {
      if (editingSet) {
        const updated = await workingSets.update(editingSet.id, {
          name: formName.trim(),
          description: formDesc.trim() || null,
          is_shared: formShared,
        })
        setSets((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
        if (detail && detail.id === updated.id) {
          setDetail((prev) => (prev ? { ...prev, ...updated } : prev))
        }
      } else {
        const created = await workingSets.create({
          name: formName.trim(),
          description: formDesc.trim() || null,
          record_type: formType,
          is_shared: formShared,
        })
        setSets((prev) => [created, ...prev])
      }
      setModalOpen(false)
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : 'Fehler beim Speichern')
    } finally {
      setModalSaving(false)
    }
  }

  const handleDeleteSet = async (s: WorkingSet) => {
    if (!window.confirm(t('deleteSetConfirm', { name: s.name }))) return
    try {
      await workingSets.delete(s.id)
      setSets((prev) => prev.filter((it) => it.id !== s.id))
      if (activeSetId === s.id) {
        setActiveSetId(null)
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Fehler beim Löschen')
    }
  }

  const handleRemoveItem = async (itemId: string) => {
    if (!activeSetId || !window.confirm(t('removeItemConfirm'))) return
    try {
      await workingSets.deleteItem(activeSetId, itemId)
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((it) => it.id !== itemId),
              item_count: Math.max(0, prev.item_count - 1),
            }
          : prev
      )
      setSets((prev) =>
        prev.map((s) =>
          s.id === activeSetId ? { ...s, item_count: Math.max(0, s.item_count - 1) } : s
        )
      )
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Fehler beim Entfernen')
    }
  }

  const handleMoveItem = async (index: number, direction: 'up' | 'down') => {
    if (!detail || !activeSetId) return
    const targetIdx = direction === 'up' ? index - 1 : index + 1
    if (targetIdx < 0 || targetIdx >= detail.items.length) return

    const newItems = [...detail.items]
    const temp = newItems[index]
    newItems[index] = newItems[targetIdx]
    newItems[targetIdx] = temp

    setDetail({ ...detail, items: newItems })

    try {
      await workingSets.reorder(
        activeSetId,
        newItems.map((it) => it.id)
      )
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Fehler beim Sortieren')
      loadDetail(activeSetId)
    }
  }

  const handleSaveNote = async (item: WorkingSetItem) => {
    if (!activeSetId) return
    try {
      const updated = await workingSets.updateItem(activeSetId, item.id, {
        note: noteVal.trim() || null,
      })
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((it) => (it.id === updated.id ? updated : it)),
            }
          : prev
      )
      setEditingNoteId(null)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Fehler beim Speichern der Notiz')
    }
  }

  const openBatchEdit = async () => {
    if (!detail || detail.items.length === 0) return
    try {
      const fields = await schema.list(detail.record_type)
      setSchemaFields(fields)
      setBatchEditOpen(true)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Fehler beim Laden der Schemafelder')
    }
  }

  // Filtered sets list
  const filteredSets = useMemo(() => {
    return sets.filter((s) => {
      if (tab === 'mine' && s.is_shared) return false
      if (tab === 'shared' && !s.is_shared) return false
      if (q) {
        const query = q.toLowerCase()
        const matchName = s.name.toLowerCase().includes(query)
        const matchDesc = s.description?.toLowerCase().includes(query)
        if (!matchName && !matchDesc) return false
      }
      return true
    })
  }, [sets, tab, q])

  // ---------------------------------------------------------------------------
  // DETAIL VIEW
  // ---------------------------------------------------------------------------
  if (activeSetId && detail) {
    const recTypeLabel = tRoot(`recordTypes.${detail.record_type}`, {
      defaultValue: detail.record_type,
    })

    return (
      <div className="scroll">
        <div className="ph">
          <div>
            <button
              className="btn sm gh"
              onClick={() => setActiveSetId(null)}
              style={{ marginBottom: 6, display: 'inline-flex', alignItems: 'center', gap: 4 }}
            >
              <ChevL size={13} /> {t('backToList')}
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h1>{detail.name}</h1>
              <span
                style={{
                  fontSize: 12,
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: 'var(--bg-card)',
                  color: 'var(--fg-2)',
                  border: '1px solid var(--border)',
                }}
              >
                {recTypeLabel}
              </span>
              {detail.is_shared && (
                <span
                  style={{
                    fontSize: 12,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: '#dbeafe',
                    color: '#1e40af',
                  }}
                >
                  {t('sharedSets')}
                </span>
              )}
            </div>
            {detail.description && <div className="sub">{detail.description}</div>}
          </div>
          <div className="right">
            <span style={{ fontSize: 13, color: 'var(--fg-3)', marginRight: 4 }}>
              {t('itemsCount', { count: detail.items.length })}
            </span>
            <button
              className="btn"
              onClick={openBatchEdit}
              disabled={detail.items.length === 0}
              title={t('batchEdit')}
            >
              <Layers size={13} /> {t('batchEdit')}
            </button>
            <button className="btn gh" onClick={() => openEditModal(detail)}>
              <Edit size={13} /> {t('editSet')}
            </button>
            <button
              className="btn gh dn"
              onClick={() => handleDeleteSet(detail)}
            >
              <Trash size={13} /> {t('deleteSet')}
            </button>
          </div>
        </div>

        <div className="tw">
          {detailLoading ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--fg-3)' }}>
              Lade Datensätze…
            </div>
          ) : detail.items.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <div style={{ color: 'var(--fg-3)', fontSize: 15, marginBottom: 8 }}>
                {t('emptyItems')}
              </div>
              <div style={{ color: 'var(--fg-4)', fontSize: 13 }}>{t('emptyItemsHint')}</div>
            </div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 70 }}>Pos.</th>
                  <th style={{ width: 52 }}></th>
                  <th>{t('tableTitle')}</th>
                  <th style={{ width: 130 }}>{t('tableIdno')}</th>
                  <th style={{ width: 140 }}>{t('tableStatus')}</th>
                  <th>{t('tableNote')}</th>
                  <th style={{ width: 48 }}></th>
                </tr>
              </thead>
              <tbody>
                {detail.items.map((it, idx) => (
                  <tr key={it.id}>
                    <td style={{ verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', gap: 2 }}>
                        <button
                          className="btn-icon-sm"
                          disabled={idx === 0}
                          onClick={() => handleMoveItem(idx, 'up')}
                          title={t('moveUp')}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            cursor: idx === 0 ? 'default' : 'pointer',
                            opacity: idx === 0 ? 0.3 : 1,
                            padding: 4,
                          }}
                        >
                          <ChevU size={14} />
                        </button>
                        <button
                          className="btn-icon-sm"
                          disabled={idx === detail.items.length - 1}
                          onClick={() => handleMoveItem(idx, 'down')}
                          title={t('moveDown')}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            cursor: idx === detail.items.length - 1 ? 'default' : 'pointer',
                            opacity: idx === detail.items.length - 1 ? 0.3 : 1,
                            padding: 4,
                          }}
                        >
                          <ChevD size={14} />
                        </button>
                      </div>
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      <ItemThumbnail url={it.thumbnail_url} alt={it.label || ''} />
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      {onOpenRecord ? (
                        <button
                          onClick={() => onOpenRecord(detail.record_type, it.record_id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            color: 'inherit',
                            fontWeight: 500,
                            textAlign: 'left',
                            cursor: 'pointer',
                            textDecoration: 'none',
                          }}
                          className="link-hover"
                        >
                          {it.label || it.record_id}
                        </button>
                      ) : (
                        <span style={{ fontWeight: 500 }}>{it.label || it.record_id}</span>
                      )}
                    </td>
                    <td className="mono" style={{ verticalAlign: 'middle', fontSize: 13 }}>
                      {it.idno || '–'}
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      <StatusBadge status={it.status ?? 'draft'} />
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      {editingNoteId === it.id ? (
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          <input
                            type="text"
                            value={noteVal}
                            onChange={(e) => setNoteVal(e.target.value)}
                            placeholder={t('notePlaceholder')}
                            className="fld"
                            style={{ flex: 1, padding: '4px 8px', fontSize: 13 }}
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveNote(it)
                              if (e.key === 'Escape') setEditingNoteId(null)
                            }}
                          />
                          <button className="btn sm pri" onClick={() => handleSaveNote(it)}>
                            {t('save')}
                          </button>
                          <button className="btn sm gh" onClick={() => setEditingNoteId(null)}>
                            {t('cancel')}
                          </button>
                        </div>
                      ) : (
                        <div
                          onClick={() => {
                            setEditingNoteId(it.id)
                            setNoteVal(it.note ?? '')
                          }}
                          style={{
                            cursor: 'pointer',
                            minHeight: 24,
                            display: 'flex',
                            alignItems: 'center',
                            color: it.note ? 'var(--fg)' : 'var(--fg-4)',
                            fontSize: 13,
                          }}
                          title={t('notePlaceholder')}
                        >
                          {it.note || <span style={{ fontStyle: 'italic' }}>+ {t('note')}</span>}
                        </div>
                      )}
                    </td>
                    <td style={{ verticalAlign: 'middle', textAlign: 'right' }}>
                      <button
                        className="btn-icon-sm"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--fg-4)',
                          cursor: 'pointer',
                          padding: 4,
                        }}
                        onClick={() => handleRemoveItem(it.id)}
                        title={t('removeItem')}
                      >
                        <Trash size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {batchEditOpen && (
          <BatchEditModal
            recordType={detail.record_type as ListableRecordType}
            fields={schemaFields}
            selection={{
              mode: 'ids',
              ids: detail.items.map((it) => it.record_id),
              filters: {},
              count: detail.items.length,
            }}
            onClose={() => setBatchEditOpen(false)}
            onSuccess={() => {
              setBatchEditOpen(false)
              loadDetail(detail.id)
            }}
          />
        )}
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // LIST OVERVIEW VIEW
  // ---------------------------------------------------------------------------
  return (
    <div className="scroll">
      <div className="ph">
        <div>
          <h1>{t('title')}</h1>
          <div className="sub">{t('subtitle')}</div>
        </div>
        <div className="right">
          <button className="btn pri" onClick={openNewModal}>
            <Plus size={13} /> {t('createSet')}
          </button>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab${tab === 'all' ? ' active' : ''}`}
          onClick={() => setTab('all')}
        >
          Alle
        </button>
        <button
          className={`tab${tab === 'mine' ? ' active' : ''}`}
          onClick={() => setTab('mine')}
        >
          {t('mySets')}
        </button>
        <button
          className={`tab${tab === 'shared' ? ' active' : ''}`}
          onClick={() => setTab('shared')}
        >
          {t('sharedSets')}
        </button>
      </div>

      <div className="toolbar">
        <div className="search">
          <Search className="ic" size={14} />
          <input
            placeholder={t('searchPlaceholder')}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <select
          className="fld"
          style={{ maxWidth: 200 }}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">{t('filterAllTypes')}</option>
          {RECORD_TYPES.map((rt) => (
            <option key={rt.key} value={rt.key}>
              {tRoot(rt.labelKey, { defaultValue: rt.key })}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div
          style={{
            margin: '14px 24px',
            padding: '12px 16px',
            background: '#fee2e2',
            color: '#991b1b',
            borderRadius: 6,
          }}
        >
          {error}
        </div>
      )}

      <div className="tw">
        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--fg-3)' }}>
            Lade Arbeitslisten…
          </div>
        ) : filteredSets.length === 0 ? (
          <div style={{ padding: 64, textAlign: 'center' }}>
            <div style={{ color: 'var(--fg-3)', fontSize: 16, fontWeight: 500, marginBottom: 8 }}>
              {t('emptyTitle')}
            </div>
            <div style={{ color: 'var(--fg-4)', fontSize: 14, maxWidth: 440, margin: '0 auto' }}>
              {t('emptySubtitle')}
            </div>
          </div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>{t('name')}</th>
                <th style={{ width: 140 }}>{t('recordType')}</th>
                <th style={{ width: 120 }}>{t('itemsCount', { count: 0 }).replace('0 ', '')}</th>
                <th style={{ width: 180 }}>{t('owner')}</th>
                <th style={{ width: 120 }}>{t('updated')}</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {filteredSets.map((s) => {
                const rtLabel = tRoot(`recordTypes.${s.record_type}`, {
                  defaultValue: s.record_type,
                })
                return (
                  <tr key={s.id}>
                    <td>
                      <button
                        onClick={() => setActiveSetId(s.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          fontWeight: 600,
                          fontSize: 14,
                          color: 'inherit',
                          textAlign: 'left',
                          cursor: 'pointer',
                        }}
                        className="link-hover"
                      >
                        {s.name}
                      </button>
                      {s.description && (
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--fg-3)',
                            marginTop: 2,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: 400,
                          }}
                        >
                          {s.description}
                        </div>
                      )}
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      <span
                        style={{
                          fontSize: 12,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: 'var(--bg-2)',
                          color: 'var(--fg-2)',
                        }}
                      >
                        {rtLabel}
                      </span>
                    </td>
                    <td style={{ verticalAlign: 'middle', fontWeight: 500 }}>
                      {t('itemsCount', { count: s.item_count })}
                    </td>
                    <td style={{ verticalAlign: 'middle', fontSize: 13, color: 'var(--fg-2)' }}>
                      <div>{s.user_name || '–'}</div>
                      {s.is_shared && (
                        <span style={{ fontSize: 11, color: '#2563eb' }}>{t('sharedSets')}</span>
                      )}
                    </td>
                    <td style={{ verticalAlign: 'middle', fontSize: 13, color: 'var(--fg-3)' }}>
                      {fmt(s.updated_at)}
                    </td>
                    <td style={{ verticalAlign: 'middle', textAlign: 'right' }}>
                      <ActionMenu
                        ariaLabel={t('actions')}
                        items={[
                          {
                            key: 'open',
                            label: t('openRecord'),
                            icon: <Folder size={13} />,
                            onClick: () => setActiveSetId(s.id),
                          },
                          {
                            key: 'edit',
                            label: t('editSet'),
                            icon: <Edit size={13} />,
                            onClick: () => openEditModal(s),
                          },
                          {
                            key: 'delete',
                            label: t('deleteSet'),
                            icon: <Trash size={13} />,
                            danger: true,
                            onClick: () => handleDeleteSet(s),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* CREATE / EDIT MODAL */}
      {modalOpen && (
        <div className="batch-modal-backdrop" onClick={() => setModalOpen(false)} role="dialog" aria-modal="true">
          <div
            className="batch-modal"
            style={{ width: 480 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="batch-modal-header">
              <h2>{editingSet ? t('editSet') : t('createSet')}</h2>
              <button
                type="button"
                className="btn ico gh"
                onClick={() => setModalOpen(false)}
                aria-label={t('cancel')}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSaveModal} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <div className="batch-modal-body">
                {modalError && (
                  <div
                    style={{
                      marginBottom: 16,
                      padding: 10,
                      background: '#fee2e2',
                      color: '#991b1b',
                      borderRadius: 6,
                      fontSize: 13,
                    }}
                  >
                    {modalError}
                  </div>
                )}

                <div style={{ marginBottom: 14 }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 12,
                      fontWeight: 600,
                      marginBottom: 4,
                      color: 'var(--fg-2)',
                    }}
                  >
                    {t('name')} *
                  </label>
                  <input
                    type="text"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder={t('namePlaceholder')}
                    className="fld"
                    style={{ width: '100%', boxSizing: 'border-box' }}
                    autoFocus
                  />
                </div>

                {!editingSet && (
                  <div style={{ marginBottom: 14 }}>
                    <label
                      style={{
                        display: 'block',
                        fontSize: 12,
                        fontWeight: 600,
                        marginBottom: 4,
                        color: 'var(--fg-2)',
                      }}
                    >
                      {t('recordType')}
                    </label>
                    <select
                      className="fld"
                      style={{ width: '100%', boxSizing: 'border-box' }}
                      value={formType}
                      onChange={(e) => setFormType(e.target.value)}
                    >
                      {RECORD_TYPES.map((rt) => (
                        <option key={rt.key} value={rt.key}>
                          {tRoot(rt.labelKey, { defaultValue: rt.key })}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div style={{ marginBottom: 14 }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 12,
                      fontWeight: 600,
                      marginBottom: 4,
                      color: 'var(--fg-2)',
                    }}
                  >
                    {t('description')}
                  </label>
                  <textarea
                    value={formDesc}
                    onChange={(e) => setFormDesc(e.target.value)}
                    placeholder={t('descriptionPlaceholder')}
                    className="fld"
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      minHeight: 70,
                      resize: 'vertical',
                    }}
                  />
                </div>

                <div style={{ marginBottom: 10 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={formShared}
                      onChange={(e) => setFormShared(e.target.checked)}
                      className="ck"
                    />
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{t('isShared')}</span>
                  </label>
                  <div style={{ fontSize: 12, color: 'var(--fg-4)', marginTop: 4, marginLeft: 24 }}>
                    {t('isSharedHelp')}
                  </div>
                </div>
              </div>

              <div className="batch-modal-footer">
                <button
                  type="button"
                  className="btn gh"
                  onClick={() => setModalOpen(false)}
                  disabled={modalSaving}
                >
                  {t('cancel')}
                </button>
                <button type="submit" className="btn pri" disabled={modalSaving || !formName.trim()}>
                  {modalSaving ? 'Speichere…' : editingSet ? t('save') : t('create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
