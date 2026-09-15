// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { ConflictError, schema, storageLocations, subtypes, VersionConflictError } from '../../api/client'
import { getLabel, type FieldDefinition, type KatalonStorageLocation, type RecordSubtype, type StorageLocationObject } from '../../types'
import { StatusBadge } from '../ui/StatusBadge'
import { AuthorityInput, type AuthorityEntry } from '../AuthorityInput'
import { Box, Plus, Trash, X } from '../ui/Icons'
import { HelpPopover } from '../ui/HelpPopover'
import { ConfirmModal } from '../ui/ConfirmModal'
import { DeleteWithChildrenModal } from '../ui/DeleteWithChildrenModal'

type TreeLocation = { loc: KatalonStorageLocation; depth: number }

/** Depth-first, cycle-safe flatten of the flat location list into a displayable tree order. */
function flattenLocations(locations: KatalonStorageLocation[]): TreeLocation[] {
  const byId = new Map(locations.map(loc => [loc.id, loc]))
  const children = new Map<string, KatalonStorageLocation[]>()
  const roots = locations.filter(loc => !loc.parent_id || !byId.has(loc.parent_id))
  for (const loc of locations) {
    if (loc.parent_id && byId.has(loc.parent_id)) {
      children.set(loc.parent_id, [...(children.get(loc.parent_id) ?? []), loc])
    }
  }

  const flattened: TreeLocation[] = []
  const seen = new Set<string>()
  const visit = (loc: KatalonStorageLocation, depth: number) => {
    if (seen.has(loc.id)) return
    seen.add(loc.id)
    flattened.push({ loc, depth })
    children.get(loc.id)?.forEach(child => visit(child, depth + 1))
  }
  roots.forEach(root => visit(root, 0))
  locations.forEach(loc => visit(loc, 0))
  return flattened
}

/** All ids that are `locId` itself or one of its (transitive) children — excluded from reparent targets. */
function descendantIds(locations: KatalonStorageLocation[], locId: string): Set<string> {
  const descendants = new Set<string>([locId])
  let changed = true
  while (changed) {
    changed = false
    for (const loc of locations) {
      if (loc.parent_id && descendants.has(loc.parent_id) && !descendants.has(loc.id)) {
        descendants.add(loc.id)
        changed = true
      }
    }
  }
  return descendants
}

function locationLabel(loc: Pick<KatalonStorageLocation, 'idno' | 'id'>): string {
  return loc.idno || loc.id.slice(0, 8) + '…'
}

async function fetchAllLocations(): Promise<KatalonStorageLocation[]> {
  const items: KatalonStorageLocation[] = []
  let page = 1
  const pageSize = 200
  for (;;) {
    const res = await storageLocations.list({ page, page_size: pageSize })
    items.push(...res.items)
    if (items.length >= res.total || res.items.length === 0) break
    page += 1
  }
  return items
}

/** Renders field_definitions-driven custom metadata inputs (mirrors ScreenVocab's CustomFieldsEditor). */
function CustomFieldsEditor({ fields, value, onChange }: {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  onChange: (value: Record<string, unknown>) => void
}) {
  function set(name: string, fieldValue: unknown) {
    const next = { ...value }
    if (fieldValue === '' || fieldValue === null || (Array.isArray(fieldValue) && fieldValue.length === 0)) {
      delete next[name]
    } else {
      next[name] = fieldValue
    }
    onChange(next)
  }

  function fieldLabel(field: FieldDefinition): string {
    return field.label.de || field.label.en || field.name
  }

  function renderSingle(field: FieldDefinition, current: unknown, update: (next: unknown) => void) {
    if (field.field_type === 'boolean') {
      return <input type="checkbox" className="ck" checked={current === true} onChange={e => update(e.target.checked)} />
    }
    if (field.field_type === 'authority') {
      return (
        <AuthorityInput
          source={String(field.settings.source ?? '')}
          value={(current as AuthorityEntry | null) ?? null}
          onChange={update}
        />
      )
    }
    return (
      <input
        className="fld"
        type={field.field_type === 'number' ? 'number' : 'text'}
        value={current == null ? '' : String(current)}
        onChange={e => update(field.field_type === 'number'
          ? (e.target.value === '' ? '' : Number(e.target.value))
          : e.target.value)}
      />
    )
  }

  return (
    <>
      {fields.map(field => {
        const current = value[field.name]
        const items = field.is_repeatable ? (Array.isArray(current) ? current : []) : []
        return (
          <div className="field" key={field.id}>
            <div className="lbl">{fieldLabel(field)}{field.is_required && <span className="req"> *</span>}</div>
            {field.is_repeatable ? (
              <>
                {items.map((item, index) => (
                  <div key={index} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ flex: 1 }}>{renderSingle(field, item, next => set(field.name, items.map((old, i) => i === index ? next : old)))}</div>
                    <button type="button" className="btn sm gh" onClick={() => set(field.name, items.filter((_, i) => i !== index))}><X size={12} /></button>
                  </div>
                ))}
                <button type="button" className="btn sm" onClick={() => set(field.name, [...items, field.field_type === 'boolean' ? false : null])}>
                  <Plus size={12} /> Wert
                </button>
              </>
            ) : renderSingle(field, current, next => set(field.name, next))}
          </div>
        )
      })}
    </>
  )
}

interface LocationForm {
  idno: string
  storage_location_type: string
  parent_id: string
  metadata_: Record<string, unknown>
}

function emptyForm(parentId: string | null): LocationForm {
  return { idno: '', storage_location_type: '', parent_id: parentId ?? '', metadata_: {} }
}
interface Props {
  initialLocationId?: string | null
  onLocationSelect?: (id: string | null) => void
  onOpenObject?: (id: string) => void
}

export function ScreenStorageLocation({ initialLocationId, onLocationSelect, onOpenObject }: Props = {}) {
  const { t } = useTranslation('screenStorageLocation')

  const [locations, setLocations] = useState<KatalonStorageLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [availableSubtypes, setAvailableSubtypes] = useState<RecordSubtype[]>([])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<LocationForm | null>(null)
  const [version, setVersion] = useState<number | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [childDeleteOpen, setChildDeleteOpen] = useState(false)
  const [forceRetry, setForceRetry] = useState<{ message: string; run: () => Promise<void> } | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [locationObjects, setLocationObjects] = useState<StorageLocationObject[]>([])
  const [objectsTotal, setObjectsTotal] = useState(0)
  const [objectsLoading, setObjectsLoading] = useState(false)
  const [includeSublocations, setIncludeSublocations] = useState(true)

  useEffect(() => {
    if (!initialLocationId) {
      if (selectedId && !creating) {
        setSelectedId(null)
        setForm(null)
        setVersion(null)
        setFormError(null)
      }
      return
    }
    if (selectedId === initialLocationId) return
    const loc = locations.find(l => l.id === initialLocationId)
    if (loc) {
      setSelectedId(loc.id)
      setCreating(false)
      setForm({
        idno: loc.idno ?? '',
        storage_location_type: loc.storage_location_type ?? '',
        parent_id: loc.parent_id ?? '',
        metadata_: { ...(loc.metadata_ ?? {}) },
      })
      setVersion(loc.version)
      setFormError(null)
    }
  }, [initialLocationId, locations, selectedId, creating])

  useEffect(() => {
    if (selectedId) {
      const el = document.querySelector('.vocab-tree .tree-it.active')
      el?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedId])

  useEffect(() => {
    if (!selectedId || creating) {
      setLocationObjects([])
      setObjectsTotal(0)
      return
    }
    let cancelled = false
    setObjectsLoading(true)
    storageLocations
      .objects(selectedId, { include_sublocations: includeSublocations, page: 1, page_size: 50 })
      .then(res => {
        if (!cancelled) {
          setLocationObjects(res.items)
          setObjectsTotal(res.total)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLocationObjects([])
          setObjectsTotal(0)
        }
      })
      .finally(() => {
        if (!cancelled) setObjectsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, creating, includeSublocations])
  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchAllLocations()
      .then(setLocations)
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    subtypes.list('storage_location').then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
  }, [])

  // Re-fetch custom field definitions whenever the edited node's subtype changes.
  useEffect(() => {
    if (!form) { setFields([]); return }
    schema.list('storage_location', form.storage_location_type || undefined)
      .then(setFields)
      .catch(() => setFields([]))
  }, [form?.storage_location_type])

  const displayTree = flattenLocations(locations)

  function set<K extends keyof LocationForm>(k: K, v: LocationForm[K]) {
    setForm(f => f ? { ...f, [k]: v } : f)
  }

  function selectLocation(loc: KatalonStorageLocation) {
    setSelectedId(loc.id)
    setCreating(false)
    const metadata_ = { ...(loc.metadata_ ?? {}) }
    delete metadata_.idno
    setForm({
      idno: loc.idno ?? '',
      storage_location_type: loc.storage_location_type ?? '',
      parent_id: loc.parent_id ?? '',
      metadata_,
    })
    setVersion(loc.version)
    setFormError(null)
    onLocationSelect?.(loc.id)
  }

  function startNewRoot() {
    setSelectedId(null)
    setCreating(true)
    setForm(emptyForm(null))
    setVersion(null)
    setFormError(null)
    onLocationSelect?.(null)
  }

  function startNewChild(parent: KatalonStorageLocation) {
    setSelectedId(null)
    setCreating(true)
    setForm(emptyForm(parent.id))
    setVersion(null)
    setFormError(null)
    onLocationSelect?.(null)
  }

  function cancelForm() {
    setSelectedId(null)
    setCreating(false)
    setForm(null)
    setVersion(null)
    setFormError(null)
    onLocationSelect?.(null)
  }

  const parentOptions = (() => {
    const excluded = selectedId && !creating ? descendantIds(locations, selectedId) : new Set<string>()
    return flattenLocations(locations).filter(({ loc }) => !excluded.has(loc.id))
  })()

  async function handleSave() {
    if (!form) return
    setSaving(true)
    setFormError(null)
    const metadata_ = { ...form.metadata_ }
    delete metadata_.idno
    const payload: Partial<KatalonStorageLocation> = {
      idno: form.idno.trim(),
      storage_location_type: form.storage_location_type || null,
      parent_id: form.parent_id || null,
      metadata_,
    }
    try {
      if (creating) {
        const created = await storageLocations.create(payload)
        setLocations(prev => [...prev, created])
        selectLocation(created)
        await load()
      } else if (selectedId) {
        const updated = await storageLocations.update(selectedId, payload, version ?? undefined)
        setVersion(updated.version)
        setLocations(prev => prev.map(l => l.id === selectedId ? updated : l))
        await load()
      }
    } catch (e) {
      if (e instanceof VersionConflictError) {
        setFormError(t('errorVersionConflict'))
      } else {
        setFormError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      setSaving(false)
    }
  }

  function handleDelete() {
    if (!selectedId) return
    const childCount = locations.filter(l => l.parent_id === selectedId).length
    if (childCount > 0) {
      setChildDeleteOpen(true)
    } else {
      setConfirmDeleteOpen(true)
    }
  }

  async function runDelete(opts?: { force?: boolean; cascade?: boolean; reparent?: boolean }) {
    if (!selectedId) return
    await storageLocations.delete(selectedId, opts)
    cancelForm()
    await load()
  }

  async function confirmDelete() {
    if (!selectedId) return
    setDeleting(true)
    setFormError(null)
    try {
      await runDelete()
      setConfirmDeleteOpen(false)
    } catch (e) {
      if (e instanceof ConflictError) {
        setConfirmDeleteOpen(false)
        setForceRetry({
          message: t('deleteConflictRetry', { message: e.message }),
          run: () => runDelete({ force: true }),
        })
      } else {
        setFormError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      setDeleting(false)
    }
  }

  async function confirmChildDelete(action: 'cascade' | 'reparent') {
    if (!selectedId) return
    try {
      await runDelete({ [action]: true })
      setChildDeleteOpen(false)
    } catch (e) {
      if (e instanceof ConflictError) {
        setChildDeleteOpen(false)
        setForceRetry({
          message: t('deleteConflictRetry', { message: e.message }),
          run: () => runDelete({ [action]: true, force: true }),
        })
      } else {
        throw e
      }
    }
  }

  async function runForceRetry() {
    if (!forceRetry) return
    setDeleting(true)
    setFormError(null)
    try {
      await forceRetry.run()
      setForceRetry(null)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
      setForceRetry(null)
    } finally {
      setDeleting(false)
    }
  }

  const idnoField = fields.find(f => f.name === 'idno')
  const idnoLabel = getLabel(idnoField, t('fieldIdno'))
  const customFields = fields.filter(f => f.name !== 'idno')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>{t('headline')}</h1><div className="sub">{t('headlineSub')}</div></div>
        <div className="right">
          <button className="btn pri" onClick={startNewRoot}><Plus size={13} /> {t('newRootButton')}</button>
        </div>
      </div>

      {error && <div role="alert" style={{ padding: '8px 24px', color: '#b91c1c', fontSize: 13 }}>{error}</div>}

      <div className="vocab-grid" style={{ flex: 1, minHeight: 0 }}>
        <div className="vocab-tree">
          {loading && <div className="empty" style={{ padding: 12, fontSize: 12 }}>{t('loading')}</div>}
          {!loading && displayTree.length === 0 && (
            <div className="empty" style={{ padding: 12, fontSize: 12 }}>{t('emptyTree')}</div>
          )}
          {!loading && displayTree.map(({ loc, depth }) => (
            <div key={loc.id}>
              <div
                className={`tree-it${selectedId === loc.id ? ' active' : ''}`}
                onClick={() => selectLocation(loc)}
                style={{ paddingLeft: 6 + depth * 16 }}
              >
                <Box size={13} className="ic" />
                <span style={{ flex: 1 }}>{locationLabel(loc)}</span>
                <button
                  type="button"
                  className="btn sm ico gh"
                  title={t('newChildButton')}
                  onClick={event => { event.stopPropagation(); startNewChild(loc) }}
                >
                  <Plus size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="vocab-detail">
          {!form && <div className="empty">{t('selectPrompt')}</div>}
          {form && (
            <>
              <div className="vocab-detail-head">
                <span style={{ fontWeight: 600, fontSize: 15 }}>
                  {creating ? t('newHeading') : t('editHeading')}
                </span>
              </div>

              {formError && <div role="alert" style={{ color: '#b91c1c', fontSize: 13, marginBottom: 10 }}>{formError}</div>}

              <div className="fg-2">
                <div className="field">
                  <div className="lbl">{idnoLabel} <span className="req">*</span></div>
                  <input className="fld mono" value={form.idno} onChange={e => set('idno', e.target.value)} autoFocus />
                </div>
                <div className="field">
                  <div className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {t('fieldType')}
                    <HelpPopover
                      title={t('fieldTypeHelpPopover.title')}
                      content={<div>{t('fieldTypeHelpPopover.description')}</div>}
                    />
                  </div>
                  <select className="fld" value={form.storage_location_type} onChange={e => set('storage_location_type', e.target.value)}>
                    <option value="">{t('fieldTypeNone')}</option>
                    {availableSubtypes.map(st => (
                      <option key={st.id} value={st.name}>{st.label.de || st.label.en || st.name}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label className="lbl" htmlFor="storage-location-parent">{t('fieldParent')}</label>
                  <select id="storage-location-parent" className="fld" value={form.parent_id} onChange={e => set('parent_id', e.target.value)}>
                    <option value="">{t('fieldParentNone')}</option>
                    {parentOptions.map(({ loc, depth }) => (
                      <option key={loc.id} value={loc.id}>{`${'— '.repeat(depth)}${locationLabel(loc)}`}</option>
                    ))}
                  </select>
                </div>
              </div>

              <CustomFieldsEditor
                fields={customFields}
                value={form.metadata_}
                onChange={metadata_ => set('metadata_', metadata_)}
              />

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button className="btn pri" onClick={handleSave} disabled={saving}>
                  {saving ? t('saving') : t('save')}
                </button>
                <button className="btn gh" onClick={cancelForm}><X size={12} /> {t('cancel')}</button>
                {!creating && (
                  <button className="btn gh dn" onClick={handleDelete} disabled={deleting} style={{ marginLeft: 'auto' }}>
                    <Trash size={12} /> {deleting ? t('deleting') : t('delete')}
                  </button>
                )}
              </div>

              {!creating && selectedId && (
                <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{t('objectsHeading')}</span>
                      <span className="badge" style={{ fontSize: 11 }}>{objectsTotal}</span>
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--fg-2)' }}>
                      <input
                        type="checkbox"
                        checked={includeSublocations}
                        onChange={e => setIncludeSublocations(e.target.checked)}
                      />
                      {t('includeSublocations')}
                    </label>
                  </div>

                  {objectsLoading ? (
                    <div style={{ padding: '12px 0', fontSize: 12, color: 'var(--fg-3)' }}>{t('loadingObjects')}</div>
                  ) : locationObjects.length === 0 ? (
                    <div style={{ padding: '12px 0', fontSize: 12, color: 'var(--fg-3)' }}>{t('noObjects')}</div>
                  ) : (
                    <div className="tbl-wrap" style={{ maxHeight: 260, overflowY: 'auto' }}>
                      <table className="tbl sm">
                        <thead>
                          <tr>
                            <th>{t('colIdno')}</th>
                            <th>{t('colTitle')}</th>
                            <th>{t('colType')}</th>
                            <th>{t('colLocation')}</th>
                            <th>{t('colStatus')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {locationObjects.map(obj => (
                            <tr key={obj.id}>
                              <td>
                                <button
                                  type="button"
                                  onClick={() => onOpenObject?.(obj.id)}
                                  className="mono"
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: 0,
                                    cursor: onOpenObject ? 'pointer' : 'default',
                                    color: 'var(--accent)',
                                    fontWeight: 500,
                                    fontSize: 'inherit',
                                  }}
                                >
                                  {obj.idno || obj.id.slice(0, 8)}
                                </button>
                              </td>
                              <td>{obj.title || '—'}</td>
                              <td>{obj.object_type || '—'}</td>
                              <td className="mono" style={{ fontSize: 11 }}>{obj.storage_location_idno || '—'}</td>
                              <td>
                                <StatusBadge status={obj.status} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {confirmDeleteOpen && (() => {
        const loc = locations.find(l => l.id === selectedId)
        return loc ? (
          <ConfirmModal
            message={t('deleteConfirm', { name: locationLabel(loc) })}
            confirmLabel={t('delete')}
            cancelLabel={t('cancel')}
            danger
            onConfirm={confirmDelete}
            onCancel={() => setConfirmDeleteOpen(false)}
          />
        ) : null
      })()}
      {childDeleteOpen && (() => {
        const loc = locations.find(l => l.id === selectedId)
        if (!loc) return null
        const childCount = locations.filter(l => l.parent_id === loc.id).length
        return (
          <DeleteWithChildrenModal
            title={t('deleteChildrenModal.title')}
            description={t('deleteConfirm', { name: locationLabel(loc) })}
            warningTitle={t('deleteChildrenModal.warningTitle')}
            warningText={t(childCount === 1 ? 'deleteChildrenModal.warning' : 'deleteChildrenModal.warning_plural', { count: childCount })}
            chooseActionLabel={t('deleteChildrenModal.chooseAction')}
            reparentLabel={t('deleteChildrenModal.optionReparent')}
            reparentDesc={t('deleteChildrenModal.optionReparentDesc')}
            cascadeLabel={t('deleteChildrenModal.optionCascade')}
            cascadeDesc={t('deleteChildrenModal.optionCascadeDesc')}
            cancelLabel={t('cancel')}
            confirmLabel={t('delete')}
            deletingLabel={t('deleting')}
            onConfirm={confirmChildDelete}
            onCancel={() => setChildDeleteOpen(false)}
          />
        )
      })()}
      {forceRetry && (
        <ConfirmModal
          message={forceRetry.message}
          confirmLabel={t('delete')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={runForceRetry}
          onCancel={() => setForceRetry(null)}
        />
      )}
    </div>
  )
}
