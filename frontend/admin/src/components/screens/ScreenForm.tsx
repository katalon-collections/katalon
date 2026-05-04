import { useState, useEffect, useRef, useCallback } from 'react'
import { objects, entities, places, occurrences, schema, media, vocabularies, relations as relationsApi, search as searchApi, BASE } from '../../api/client'
import type { MediaFile } from '../../api/client'
import type { AnyRecord, AuditEntry, FieldDefinition, RecordType, Relation, SearchResult, Snapshot, Status, VocabularyTerm } from '../../types'
import { ChevD, Plus, Upload, X, Trash, Image } from '../ui/Icons'

const STATUSES: Status[] = ['draft', 'internal', 'public']
const STATUS_LABELS: Record<Status, string> = { draft: 'Entwurf', internal: 'Intern', public: 'Öffentlich' }

const TYPE_LABELS: Record<RecordType, string> = {
  object:     'Objekt',
  entity:     'Entität',
  place:      'Ort',
  occurrence: 'Occurrence',
}

const SUBTYPE_KEY: Partial<Record<RecordType, string>> = {
  entity:     'entity_type',
  occurrence: 'occurrence_type',
}

function getApi(recordType: RecordType) {
  switch (recordType) {
    case 'object':     return objects
    case 'entity':     return entities
    case 'place':      return places
    case 'occurrence': return occurrences
  }
}

interface Props {
  recordType: RecordType
  recordId?: string
  onBack?: () => void
  onSaved?: (id: string) => void
}

export function ScreenForm({ recordType, recordId, onBack, onSaved }: Props) {
  const isNew = !recordId || recordId === 'new'
  const currentId = isNew ? null : recordId!
  const api = getApi(recordType)
  const label = TYPE_LABELS[recordType]
  const subtypeKey = SUBTYPE_KEY[recordType]
  const showIdno  = recordType === 'object'
  const showMedia = recordType === 'object'
  const showGeo   = recordType === 'place'

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [idno, setIdno]       = useState('')
  const [subtype, setSubtype] = useState('')
  const [lat, setLat]         = useState('')
  const [lon, setLon]         = useState('')
  const [status, setStatus]   = useState<Status>('draft')
  const [values, setValues]   = useState<Record<string, unknown>>({})
  const [showAudit, setShowAudit] = useState(false)
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [dateFieldErrors, setDateFieldErrors] = useState<Record<string, string>>({})
  const [showSnapshots, setShowSnapshots] = useState(false)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [snapLabel, setSnapLabel] = useState('')
  const [snapCreating, setSnapCreating] = useState(false)
  const [snapRestoring, setSnapRestoring] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [title, setTitle]     = useState(isNew ? `Neues ${label}` : '…')

  const [mediaFiles, setMediaFiles]     = useState<MediaFile[]>([])
  const [uploading, setUploading]       = useState(false)
  const [uploadError, setUploadError]   = useState<string | null>(null)
  const [dragOver, setDragOver]         = useState(false)
  const [mediaTypeTerms, setMediaTypeTerms] = useState<VocabularyTerm[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [savedId, setSavedId] = useState<string | null>(currentId)

  const [rels, setRels]           = useState<Relation[]>([])
  const [relTitles, setRelTitles] = useState<Record<string, string>>({})
  const [addOpen, setAddOpen]     = useState(false)
  const [addTargetType, setAddTargetType] = useState<RecordType>('object')
  const [addSearchQ, setAddSearchQ]       = useState('')
  const [addResults, setAddResults]       = useState<SearchResult[]>([])
  const [addSearching, setAddSearching]   = useState(false)
  const [addRelType, setAddRelType]       = useState('')
  const [addSelected, setAddSelected]     = useState<SearchResult | null>(null)
  const [addSaving, setAddSaving]         = useState(false)

  const loadMedia = useCallback((id: string) => {
    media.list(id).then(setMediaFiles).catch(() => {})
  }, [])

  const loadSnapshots = useCallback((id: string) => {
    if (recordType === 'object') {
      objects.snapshots.list(id).then(setSnapshots).catch(() => {})
    }
  }, [recordType])

  const loadAudit = useCallback((id: string) => {
    setAuditLoading(true)
    api.audit(id).then(setAuditEntries).catch(() => {}).finally(() => setAuditLoading(false))
  }, [api])

  const loadRelations = useCallback(async (id: string) => {
    try {
      const loaded = await relationsApi.list({ from_type: recordType, from_id: id })
      setRels(loaded)
      const titleMap: Record<string, string> = {}
      await Promise.all(loaded.map(async r => {
        const key = `${r.to_type}/${r.to_id}`
        try {
          const rec = await (getApi(r.to_type as RecordType).get as (id: string) => Promise<AnyRecord>)(r.to_id)
          const m = rec.metadata_ as Record<string, unknown>
          titleMap[key] = String(m.title ?? m.name ?? (rec as { idno?: string | null }).idno ?? r.to_id)
        } catch {
          titleMap[key] = r.to_id.slice(0, 8) + '…'
        }
      }))
      setRelTitles(titleMap)
    } catch {
      // silently ignore
    }
  }, [recordType])

  useEffect(() => {
    setLoading(true)
    setTitle(isNew ? `Neues ${label}` : '…')
    setSavedId(currentId)
    setIdno('')
    setSubtype('')
    setLat('')
    setLon('')
    setStatus('draft')
    setValues({})
    setMediaFiles([])
    setRels([])
    setRelTitles({})
    setAddOpen(false)

    const loadRecP = isNew ? Promise.resolve(null) : (api.get as (id: string) => Promise<AnyRecord>)(recordId!)

    loadRecP
      .then(async rec => {
        let recSubtype: string | undefined
        if (rec) {
          setStatus(rec.status as Status)
          setValues(rec.metadata_)
          const m = rec.metadata_ as Record<string, unknown>
          if (showIdno)  setIdno((rec as { idno?: string | null }).idno ?? '')
          if (subtypeKey) {
            recSubtype = String((rec as unknown as Record<string, unknown>)[subtypeKey] ?? '') || undefined
            setSubtype(recSubtype ?? '')
          }
          if (showGeo) {
            const p = rec as { lat?: number | null; lon?: number | null }
            setLat(p.lat != null ? String(p.lat) : '')
            setLon(p.lon != null ? String(p.lon) : '')
          }
          setTitle(String(m.title ?? m.name ?? (rec as { idno?: string | null }).idno ?? rec.id))
        }
        const fieldDefs = await schema.list(recordType, recSubtype)
        setFields(fieldDefs)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

    if (!isNew && currentId) loadRelations(currentId)
  }, [recordId, recordType, isNew])

  useEffect(() => {
    if (savedId && showMedia) loadMedia(savedId)
  }, [savedId, showMedia, loadMedia])

  useEffect(() => {
    if (savedId) loadSnapshots(savedId)
  }, [savedId, loadSnapshots])

  useEffect(() => {
    if (!showMedia) return
    vocabularies.list()
      .then(vocabs => {
        const mt = vocabs.find(v => v.name === 'media_types')
        if (mt) return vocabularies.listTerms(mt.id)
        return []
      })
      .then(setMediaTypeTerms)
      .catch(() => {})
  }, [showMedia])

  useEffect(() => {
    if (!addOpen || addSearchQ.trim().length < 2) { setAddResults([]); return }
    setAddSearching(true)
    const timer = setTimeout(() => {
      searchApi.query(addSearchQ.trim(), addTargetType, 6)
        .then(r => setAddResults(r.items))
        .catch(() => setAddResults([]))
        .finally(() => setAddSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [addSearchQ, addTargetType, addOpen])

  async function handleAddRelation() {
    if (!addSelected || !addRelType.trim() || !savedId) return
    setAddSaving(true)
    try {
      const created = await relationsApi.create({
        from_type: recordType, from_id: savedId,
        to_type: addSelected.record_type, to_id: addSelected.id,
        relation_type: addRelType.trim(),
      })
      setRels(prev => [...prev, created])
      setRelTitles(prev => ({ ...prev, [`${created.to_type}/${created.to_id}`]: addSelected.title }))
      setAddOpen(false); setAddSearchQ(''); setAddRelType(''); setAddSelected(null); setAddResults([])
    } catch (e) { alert((e as Error).message) }
    finally { setAddSaving(false) }
  }

  async function handleDeleteRelation(id: string) {
    if (!window.confirm('Relation wirklich löschen?')) return
    try {
      await relationsApi.delete(id)
      setRels(prev => prev.filter(r => r.id !== id))
    } catch (e) { alert((e as Error).message) }
  }

  function setField(name: string, value: unknown) { setValues(v => ({ ...v, [name]: value })) }
  function addRepeat(name: string) {
    const cur = (values[name] as string[] | undefined) ?? []
    setValues(v => ({ ...v, [name]: [...cur, ''] }))
  }
  function removeRepeat(name: string, idx: number) {
    setValues(v => ({ ...v, [name]: ((v[name] as string[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updateRepeat(name: string, idx: number, val: string) {
    const cur = [...((values[name] as string[]) ?? [])]
    cur[idx] = val
    setValues(v => ({ ...v, [name]: cur }))
  }

  type PidEntry = { value: string; label: string }
  function addPid(name: string) {
    const cur = (values[name] as PidEntry[] | undefined) ?? []
    setValues(v => ({ ...v, [name]: [...cur, { value: '', label: '' }] }))
  }
  function removePid(name: string, idx: number) {
    setValues(v => ({ ...v, [name]: ((v[name] as PidEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updatePid(name: string, idx: number, key: 'value' | 'label', val: string) {
    const cur = [...((values[name] as PidEntry[]) ?? [])]
    cur[idx] = { ...cur[idx], [key]: val }
    setValues(v => ({ ...v, [name]: cur }))
  }

  function validateDates(): Record<string, string> {
    const errors: Record<string, string> = {}
    for (const f of fields) {
      if (f.field_type !== 'date') continue
      const val = values[f.name]
      const toCheck: string[] = f.is_repeatable ? ((val as string[] | undefined) ?? []) : [val as string | undefined ?? '']
      for (const v of toCheck) {
        if (!v) continue
        const ok = /^\d{4}(-\d{2}(-\d{2})?)?$/.test(v)
        if (!ok) {
          errors[f.name] = 'Ungültiges Datum. Erlaubte Formate: YYYY, YYYY-MM, YYYY-MM-DD'
          break
        }
      }
    }
    return errors
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    const dateErrors = validateDates()
    if (Object.keys(dateErrors).length > 0) {
      setDateFieldErrors(dateErrors)
      setSaving(false)
      setError('Bitte korrigieren Sie die markierten Datumsfelder.')
      return
    }
    setDateFieldErrors({})
    try {
      const payload: Record<string, unknown> = { status, metadata_: values }
      if (showIdno)   payload.idno = idno || null
      if (subtypeKey) payload[subtypeKey] = subtype
      if (showGeo) {
        payload.lat = lat ? parseFloat(lat) : null
        payload.lon = lon ? parseFloat(lon) : null
      }

      if (isNew) {
        const created = await (api.create as (d: typeof payload) => Promise<AnyRecord>)(payload)
        setSavedId(created.id)
        onSaved?.(created.id)
        if (showMedia) loadMedia(created.id)
      } else {
        await (api.update as (id: string, d: typeof payload) => Promise<AnyRecord>)(recordId!, payload)
        onBack?.()
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleUpload(file: File) {
    if (!savedId) return
    setUploading(true)
    setUploadError(null)
    try {
      const f = await media.upload(savedId, file)
      setMediaFiles(prev => [...prev, f])
    } catch (e) {
      setUploadError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function handleDeleteMedia(mediaId: string) {
    if (!savedId || !window.confirm('Medium wirklich löschen?')) return
    try {
      await media.delete(savedId, mediaId)
      setMediaFiles(prev => prev.filter(f => f.id !== mediaId))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleSetPrimary(mediaId: string) {
    if (!savedId) return
    try {
      await media.patch(savedId, mediaId, { is_primary: true })
      setMediaFiles(prev => prev.map(f => ({ ...f, is_primary: f.id === mediaId })))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleSetMediaType(mediaId: string, mediaType: string | null) {
    if (!savedId) return
    try {
      const updated = await media.patch(savedId, mediaId, { media_type: mediaType })
      setMediaFiles(prev => prev.map(f => f.id === mediaId ? { ...f, media_type: updated.media_type } : f))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  const hasSavedId   = Boolean(savedId)
  const justCreated  = isNew && hasSavedId
  const showTwoCol   = showMedia || !isNew

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ background: 'var(--panel)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', border: '1px solid var(--border-s)', borderRadius: 6, overflow: 'hidden' }}>
            {STATUSES.map(s => (
              <button key={s} onClick={() => setStatus(s)}
                style={{ border: 0, padding: '5px 10px', fontSize: 12, fontWeight: 500, fontFamily: 'inherit', cursor: 'pointer',
                  background: status === s ? 'var(--accent)' : '#fff',
                  color: status === s ? '#fff' : 'var(--fg-2)',
                  borderLeft: s !== 'draft' ? '1px solid var(--border-s)' : undefined }}>
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
          <button className="btn gh" onClick={onBack} disabled={saving}>
            {justCreated ? 'Zur Liste' : 'Verwerfen'}
          </button>
          {!justCreated && (
            <button className="btn pri" onClick={handleSave} disabled={saving}>
              {saving ? 'Speichert…' : 'Speichern'}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca', padding: '8px 24px', fontSize: 13, color: '#b91c1c', flexShrink: 0 }}>
          {error}
        </div>
      )}

      {justCreated && (
        <div style={{ background: '#f0fdf4', borderBottom: '1px solid #bbf7d0', padding: '8px 24px', fontSize: 13, color: '#166534', flexShrink: 0 }}>
          {label} gespeichert.{showMedia ? ' Bilder können jetzt hochgeladen werden.' : ''}
        </div>
      )}

      <div className="scroll">
        <div className={showTwoCol ? 'form-grid' : undefined} style={showTwoCol ? undefined : { padding: '20px 24px', maxWidth: 680 }}>
          <div>
            <div className="card">
              <div className="hd">Metadaten</div>
              <div className="bd">
                {showIdno && (
                  <div className="field">
                    <div className="lbl">Inventar-Nr.</div>
                    <input className="fld mono" value={idno} onChange={e => setIdno(e.target.value)} placeholder="z.B. FOT.1958.0412" disabled={justCreated} />
                  </div>
                )}

                {subtypeKey && (
                  <div className="field">
                    <div className="lbl">{subtypeKey === 'entity_type' ? 'Entitätstyp' : 'Occurrence-Typ'}</div>
                    <input className="fld" value={subtype} onChange={e => setSubtype(e.target.value)}
                      placeholder={subtypeKey === 'entity_type' ? 'z.B. person, organisation' : 'z.B. event, work'} disabled={justCreated} />
                  </div>
                )}

                {showGeo && (
                  <div className="field">
                    <div className="lbl">Koordinaten</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input className="fld mono" value={lat} onChange={e => setLat(e.target.value)} placeholder="Breite (lat)" disabled={justCreated} />
                      <input className="fld mono" value={lon} onChange={e => setLon(e.target.value)} placeholder="Länge (lon)" disabled={justCreated} />
                    </div>
                  </div>
                )}

                {fields.map(f => {
                  const val = values[f.name]
                  const repeatable = f.is_repeatable
                  const vals = repeatable ? ((val as string[] | undefined) ?? []) : undefined

                  const pidEntries = f.field_type === 'pid' && repeatable
                    ? ((val as PidEntry[] | undefined) ?? [])
                    : undefined
                  const pidSingle = f.field_type === 'pid' && !repeatable
                    ? ((val as PidEntry | undefined) ?? { value: '', label: '' })
                    : undefined

                  return (
                    <div key={f.id} className="field">
                      <div className="lbl">
                        {f.label.de ?? f.name}
                        {f.is_required && <span className="req">*</span>}
                        {repeatable && <span className="h">wiederholbar</span>}
                      </div>

                      {f.field_type === 'pid' ? (
                        repeatable ? (
                          <>
                            {(pidEntries ?? []).map((entry, i) => (
                              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                                <input className="fld mono" value={entry.value}
                                  onChange={e => updatePid(f.name, i, 'value', e.target.value)}
                                  placeholder="URI / ID (z.B. https://d-nb.info/…)"
                                  disabled={justCreated} style={{ flex: 2 }} />
                                <input className="fld" value={entry.label}
                                  onChange={e => updatePid(f.name, i, 'label', e.target.value)}
                                  placeholder="Anzeigebezeichnung"
                                  disabled={justCreated} style={{ flex: 1 }} />
                                <button className="btn sm ico gh" onClick={() => removePid(f.name, i)} disabled={justCreated}><X size={12} /></button>
                              </div>
                            ))}
                            <button className="btn sm gh" onClick={() => addPid(f.name)} disabled={justCreated}>
                              <Plus size={12} /> PID hinzufügen
                            </button>
                          </>
                        ) : (
                          <div style={{ display: 'flex', gap: 6 }}>
                            <input className="fld mono" value={pidSingle!.value}
                              onChange={e => setField(f.name, { ...pidSingle!, value: e.target.value })}
                              placeholder="URI / ID (z.B. https://d-nb.info/…)"
                              disabled={justCreated} style={{ flex: 2 }} />
                            <input className="fld" value={pidSingle!.label}
                              onChange={e => setField(f.name, { ...pidSingle!, label: e.target.value })}
                              placeholder="Anzeigebezeichnung"
                              disabled={justCreated} style={{ flex: 1 }} />
                          </div>
                        )
                      ) : repeatable ? (
                        <>
                          {(vals ?? []).map((v, i) => (
                            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                              <input className="fld" value={v}
                                onChange={e => updateRepeat(f.name, i, e.target.value)}
                                placeholder={f.label.de ?? f.name}
                                disabled={justCreated} />
                              <button className="btn sm ico gh" onClick={() => removeRepeat(f.name, i)} disabled={justCreated}><X size={12} /></button>
                            </div>
                          ))}
                          <button className="btn sm gh" onClick={() => addRepeat(f.name)} disabled={justCreated}>
                            <Plus size={12} /> Weiteren Wert
                          </button>
                        </>
                      ) : f.field_type === 'richtext' ? (
                        <textarea className="fld" rows={4}
                          value={(val as string) ?? ''}
                          onChange={e => setField(f.name, e.target.value)}
                          placeholder={f.label.de ?? f.name}
                          disabled={justCreated} />
                      ) : f.field_type === 'boolean' ? (
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <input type="checkbox" className="ck"
                            checked={Boolean(val)}
                            onChange={e => setField(f.name, e.target.checked)}
                            disabled={justCreated} />
                          <span style={{ fontSize: 13 }}>{f.label.de}</span>
                        </label>
                      ) : f.field_type === 'date' ? (
                        <>
                          <input className="fld"
                            type="text"
                            value={(val as string) ?? ''}
                            onChange={e => {
                              setField(f.name, e.target.value)
                              if (dateFieldErrors[f.name]) {
                                setDateFieldErrors(err => { const n = { ...err }; delete n[f.name]; return n })
                              }
                            }}
                            placeholder="YYYY, YYYY-MM oder YYYY-MM-DD"
                            disabled={justCreated}
                            style={dateFieldErrors[f.name] ? { borderColor: '#dc2626', background: '#fef2f2' } : undefined} />
                          {dateFieldErrors[f.name] && (
                            <div style={{ fontSize: 11, color: '#dc2626', marginTop: 4 }}>{dateFieldErrors[f.name]}</div>
                          )}
                        </>
                      ) : (
                        <input className="fld"
                          value={(val as string) ?? ''}
                          onChange={e => setField(f.name, e.target.value)}
                          placeholder={f.label.de ?? f.name}
                          disabled={justCreated} />
                      )}
                    </div>
                  )
                })}

                {fields.length === 0 && !showIdno && !subtypeKey && !showGeo && (
                  <div className="empty">Keine Felder definiert. Schema unter Konfiguration → Schemata anlegen.</div>
                )}
                {fields.length === 0 && (showIdno || subtypeKey || showGeo) && (
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', paddingTop: 4 }}>
                    Keine weiteren dynamischen Felder. Schema unter Konfiguration → Schemata anlegen.
                  </div>
                )}
              </div>
            </div>
          </div>

          {showTwoCol && (
            <div>
              {showMedia && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Medien</span>
                    {mediaFiles.length > 0 && <span className="sub">{mediaFiles.length} Datei{mediaFiles.length !== 1 ? 'en' : ''}</span>}
                  </div>
                  <div className="bd">
                    {mediaFiles.length > 0 && (
                      <div style={{ marginBottom: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 10 }}>
                        {mediaFiles.map(f => (
                          <div key={f.id} style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border-s)', background: 'var(--bg-s)' }}>
                            <a href={`${BASE}/v1/objects/${savedId}/media/${f.id}/file`} target="_blank" rel="noreferrer" style={{ display: 'block', aspectRatio: '1', overflow: 'hidden' }}>
                              {f.status === 'ready' ? (
                                <img
                                  src={`${BASE}/v1/objects/${savedId}/media/${f.id}/file`}
                                  alt={f.filename}
                                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                                />
                              ) : null}
                              {f.status !== 'ready' && (
                                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <Image size={20} style={{ color: 'var(--fg-3)' }} />
                                </div>
                              )}
                            </a>
                            <div style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={f.filename}>{f.filename}</span>
                              <button
                                className={`btn sm${f.is_primary ? ' pri' : ' gh'}`}
                                style={{ fontSize: 10, padding: '1px 4px', flexShrink: 0 }}
                                onClick={() => handleSetPrimary(f.id)}
                                title={f.is_primary ? 'Primärbild' : 'Als Primärbild setzen'}
                                disabled={f.is_primary}
                              >
                                {f.is_primary ? '★' : '☆'}
                              </button>
                              <button className="btn sm ico gh dn" style={{ padding: '1px 4px' }} onClick={() => handleDeleteMedia(f.id)} title="Löschen"><Trash size={10} /></button>
                            </div>
                            <select
                              className="fld"
                              style={{ fontSize: 10, padding: '2px 4px', height: 22, borderRadius: 0, border: '0 solid var(--border-s)', borderTopWidth: 1 }}
                              value={f.media_type ?? ''}
                              onChange={e => handleSetMediaType(f.id, e.target.value || null)}
                            >
                              <option value="">— Typ —</option>
                              {mediaTypeTerms.map(t => (
                                <option key={t.id} value={t.term}>{t.label.de ?? t.term}</option>
                              ))}
                            </select>
                          </div>
                        ))}
                      </div>
                    )}

                    {hasSavedId ? (
                      <div
                        className="dz"
                        style={{ padding: '20px 16px', opacity: uploading ? 0.5 : 1, border: dragOver ? '2px dashed var(--accent)' : undefined }}
                        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={onDrop}
                      >
                        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
                          <Upload size={24} style={{ color: 'var(--fg-4)' }} />
                        </div>
                        {uploading ? (
                          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Hochladen…</div>
                        ) : (
                          <>
                            <div style={{ fontSize: 12 }}>Hierher ziehen oder</div>
                            <label style={{ color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
                              &nbsp;auswählen
                              <input ref={fileInputRef} type="file" style={{ display: 'none' }} accept="image/jpeg,image/png,image/tiff,image/webp" onChange={onFileChange} />
                            </label>
                          </>
                        )}
                        {uploadError && <div style={{ fontSize: 11, color: '#dc2626', marginTop: 6 }}>{uploadError}</div>}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--fg-3)', textAlign: 'center', padding: '16px 0' }}>
                        Objekt zuerst speichern, dann Bilder hochladen.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!isNew && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Relationen</span>
                    {rels.length > 0 && <span className="sub">{rels.length}</span>}
                    <div className="grow" />
                    {!addOpen && hasSavedId && (
                      <button className="btn sm gh" onClick={() => setAddOpen(true)}><Plus size={12} /> Hinzufügen</button>
                    )}
                  </div>
                  <div className="bd">
                    {rels.length > 0 && (
                      <div style={{ marginBottom: addOpen ? 12 : 0 }}>
                        {rels.map(r => (
                          <div key={r.id} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
                            <span style={{ color: 'var(--fg-2)', fontFamily: 'var(--mono)' }}>{r.relation_type}</span>
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={`${r.to_type}: ${r.to_id}`}>
                              <span style={{ fontSize: 10, color: 'var(--fg-4)', marginRight: 4 }}>{r.to_type}</span>
                              {relTitles[`${r.to_type}/${r.to_id}`] ?? r.to_id.slice(0, 8) + '…'}
                            </span>
                            <button className="btn sm ico gh dn" onClick={() => handleDeleteRelation(r.id)}><Trash size={11} /></button>
                          </div>
                        ))}
                      </div>
                    )}
                    {rels.length === 0 && !addOpen && (
                      <div className="empty" style={{ padding: '16px 0' }}>Noch keine Relationen.</div>
                    )}
                    {addOpen && (
                      <div style={{ borderTop: rels.length > 0 ? '1px solid var(--border-s)' : undefined, paddingTop: rels.length > 0 ? 12 : 0 }}>
                        <div className="field" style={{ marginBottom: 8 }}>
                          <div className="lbl">Ziel-Typ</div>
                          <select className="fld" value={addTargetType} onChange={e => { setAddTargetType(e.target.value as RecordType); setAddSelected(null); setAddResults([]) }}>
                            <option value="object">Objekt</option>
                            <option value="entity">Entität</option>
                            <option value="place">Ort</option>
                            <option value="occurrence">Occurrence</option>
                          </select>
                        </div>
                        <div className="field" style={{ marginBottom: 8 }}>
                          <div className="lbl">Datensatz suchen</div>
                          {addSelected ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span style={{ fontSize: 13, flex: 1 }}>{addSelected.title}</span>
                              <button className="btn sm ico gh" onClick={() => { setAddSelected(null); setAddSearchQ('') }}><X size={12} /></button>
                            </div>
                          ) : (
                            <>
                              <input className="fld" value={addSearchQ} onChange={e => setAddSearchQ(e.target.value)}
                                placeholder="Suchbegriff (mind. 2 Zeichen)…" autoFocus />
                              {addSearching && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>Suche…</div>}
                              {addResults.length > 0 && !addSearching && (
                                <div style={{ border: '1px solid var(--border-s)', borderRadius: 4, marginTop: 4, maxHeight: 140, overflowY: 'auto' }}>
                                  {addResults.map(r => (
                                    <div key={r.id} onClick={() => { setAddSelected(r); setAddSearchQ('') }}
                                      style={{ padding: '6px 10px', cursor: 'pointer', fontSize: 12, borderBottom: '1px solid var(--border-s)' }}
                                      className="hover-row">
                                      {r.title}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {addSearchQ.trim().length >= 2 && addResults.length === 0 && !addSearching && (
                                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>Keine Ergebnisse.</div>
                              )}
                            </>
                          )}
                        </div>
                        <div className="field" style={{ marginBottom: 10 }}>
                          <div className="lbl">Relationstyp</div>
                          <input className="fld mono" value={addRelType} onChange={e => setAddRelType(e.target.value)}
                            placeholder="z.B. depicts, created_by, part_of" />
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn pri sm" onClick={handleAddRelation} disabled={!addSelected || !addRelType.trim() || addSaving}>
                            {addSaving ? 'Speichert…' : 'Speichern'}
                          </button>
                          <button className="btn gh sm" onClick={() => { setAddOpen(false); setAddSearchQ(''); setAddRelType(''); setAddSelected(null); setAddResults([]) }}>
                            Abbrechen
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!isNew && recordType === 'object' && savedId && (
                <div className="card">
                  <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowSnapshots(s => !s)}>
                    <span>Versionen ({snapshots.length})</span>
                    <div className="grow" />
                    <ChevD size={14} style={{ transform: showSnapshots ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                  </div>
                  {showSnapshots && (
                    <div className="bd" style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <input
                          style={{ flex: 1, fontSize: 12, padding: '4px 8px', border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg)', color: 'var(--fg)' }}
                          placeholder="Bezeichnung (z.B. 'vor Bearbeitung')"
                          value={snapLabel}
                          onChange={e => setSnapLabel(e.target.value)}
                        />
                        <button
                          style={{ fontSize: 12, padding: '4px 10px', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 4, cursor: 'pointer' }}
                          disabled={snapCreating || !snapLabel.trim()}
                          onClick={async () => {
                            if (!snapLabel.trim() || !savedId) return
                            setSnapCreating(true)
                            try {
                              const snap = await objects.snapshots.create(savedId, snapLabel.trim())
                              setSnapshots(s => [snap, ...s])
                              setSnapLabel('')
                            } finally {
                              setSnapCreating(false)
                            }
                          }}
                        >
                          {snapCreating ? '…' : 'Speichern'}
                        </button>
                      </div>
                      {snapshots.length === 0 && (
                        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Noch keine Versionen.</div>
                      )}
                      {snapshots.map(snap => (
                        <div key={snap.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 600 }}>{snap.label}</div>
                            <div style={{ color: 'var(--fg-3)' }}>{new Date(snap.created_at).toLocaleString('de')}</div>
                          </div>
                          <button
                            style={{ fontSize: 11, padding: '3px 8px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer' }}
                            disabled={snapRestoring === snap.id}
                            onClick={async () => {
                              if (!savedId || !window.confirm(`Version „${snap.label}" wiederherstellen?`)) return
                              setSnapRestoring(snap.id)
                              try {
                                const restored = await objects.snapshots.restore(savedId, snap.id)
                                setStatus(restored.status as Status)
                                setIdno(restored.idno ?? '')
                                setValues(restored.metadata_ as Record<string, unknown>)
                              } finally {
                                setSnapRestoring(null)
                              }
                            }}
                          >
                            {snapRestoring === snap.id ? '…' : 'Wiederherstellen'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {!isNew && (
                <div className="card">
                  <div className="hd" style={{ cursor: 'pointer' }} onClick={() => {
                    if (!showAudit && savedId) loadAudit(savedId)
                    setShowAudit(a => !a)
                  }}>
                    <span>Audit-Log</span>
                    <div className="grow" />
                    <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                  </div>
                  {showAudit && (
                    <div className="bd" style={{ padding: '8px 0' }}>
                      {auditLoading && <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>Lade…</div>}
                      {!auditLoading && auditEntries.length === 0 && (
                        <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>Keine Einträge.</div>
                      )}
                      {!auditLoading && auditEntries.map(evt => (
                        <div key={evt.id} style={{ padding: '6px 16px', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontWeight: 600 }}>{evt.action}</span>
                            <span style={{ color: 'var(--fg-3)' }}>{new Date(evt.created_at).toLocaleString('de-CH')}</span>
                          </div>
                          <div style={{ color: 'var(--fg-2)' }}>von {evt.user_name ?? evt.user_id ?? '—'}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
