import { useState, useEffect, useRef, useCallback } from 'react'
import { objects, entities, places, occurrences, schema, media, vocabularies, BASE } from '../../api/client'
import type { MediaFile } from '../../api/client'
import type { AnyRecord, FieldDefinition, RecordType, Status, VocabularyTerm } from '../../types'
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

  const loadMedia = useCallback((id: string) => {
    media.list(id).then(setMediaFiles).catch(() => {})
  }, [])

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

    const loadSchemaP = schema.list(recordType)
    const loadRecP = isNew ? Promise.resolve(null) : (api.get as (id: string) => Promise<AnyRecord>)(recordId!)

    Promise.all([loadSchemaP, loadRecP])
      .then(([fieldDefs, rec]) => {
        setFields(fieldDefs)
        if (rec) {
          setStatus(rec.status as Status)
          setValues(rec.metadata_)
          const m = rec.metadata_ as Record<string, unknown>
          if (showIdno)  setIdno((rec as { idno?: string | null }).idno ?? '')
          if (subtypeKey) setSubtype(String((rec as unknown as Record<string, unknown>)[subtypeKey] ?? ''))
          if (showGeo) {
            const p = rec as { lat?: number | null; lon?: number | null }
            setLat(p.lat != null ? String(p.lat) : '')
            setLon(p.lon != null ? String(p.lon) : '')
          }
          setTitle(String(m.title ?? m.name ?? (rec as { idno?: string | null }).idno ?? rec.id))
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [recordId, recordType, isNew])

  useEffect(() => {
    if (savedId && showMedia) loadMedia(savedId)
  }, [savedId, showMedia, loadMedia])

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

  async function handleSave() {
    setSaving(true)
    setError(null)
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
        <div className={showMedia || showGeo ? 'form-grid' : undefined} style={showMedia || showGeo ? undefined : { padding: '20px 24px', maxWidth: 680 }}>
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

                  return (
                    <div key={f.id} className="field">
                      <div className="lbl">
                        {f.label.de ?? f.name}
                        {f.is_required && <span className="req">*</span>}
                        {repeatable && <span className="h">wiederholbar</span>}
                      </div>

                      {repeatable ? (
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

          {(showMedia || showGeo) && (
            <div>
              {showMedia && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Medien</span>
                    {mediaFiles.length > 0 && <span className="sub">{mediaFiles.length} Datei{mediaFiles.length !== 1 ? 'en' : ''}</span>}
                  </div>
                  <div className="bd">
                    {mediaFiles.length > 0 && (
                      <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {mediaFiles.map(f => (
                          <div key={f.id} style={{ display: 'grid', gridTemplateColumns: '40px 1fr auto auto auto', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border-s)' }}>
                            {f.status === 'ready' ? (
                              <img
                                src={`${BASE}/v1/objects/${savedId}/media/${f.id}/file`}
                                alt={f.filename}
                                style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4, background: 'var(--bg-s)' }}
                                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                              />
                            ) : (
                              <div style={{ width: 40, height: 40, borderRadius: 4, background: 'var(--bg-s)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Image size={14} style={{ color: 'var(--fg-3)' }} />
                              </div>
                            )}
                            <span style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.filename}>{f.filename}</span>
                            <select
                              className="fld"
                              style={{ fontSize: 11, padding: '2px 6px', height: 26, minWidth: 110 }}
                              value={f.media_type ?? ''}
                              onChange={e => handleSetMediaType(f.id, e.target.value || null)}
                            >
                              <option value="">— Typ —</option>
                              {mediaTypeTerms.map(t => (
                                <option key={t.id} value={t.term}>{t.label.de ?? t.term}</option>
                              ))}
                            </select>
                            <button
                              className={`btn sm${f.is_primary ? ' pri' : ' gh'}`}
                              style={{ fontSize: 11, padding: '2px 8px' }}
                              onClick={() => handleSetPrimary(f.id)}
                              title={f.is_primary ? 'Primärbild' : 'Als Primärbild setzen'}
                              disabled={f.is_primary}
                            >
                              {f.is_primary ? '★' : '☆'}
                            </button>
                            <button className="btn sm ico gh dn" onClick={() => handleDeleteMedia(f.id)}><Trash size={11} /></button>
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

              <div className="card" style={{ marginBottom: 14 }}>
                <div className="hd">
                  <span>Relationen</span>
                  <div className="grow" />
                  <button className="btn sm gh"><Plus size={12} /> Hinzufügen</button>
                </div>
                <div className="bd">
                  <div className="empty" style={{ padding: '20px 0' }}>Noch keine Relationen.</div>
                </div>
              </div>

              {!isNew && (
                <div className="card">
                  <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowAudit(a => !a)}>
                    <span>Letzte Änderungen</span>
                    <div className="grow" />
                    <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                  </div>
                  {showAudit && (
                    <div className="bd" style={{ padding: '8px 0' }}>
                      <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>
                        Vollständiges Log unter Katalon → Audit-Log.
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!showMedia && !showGeo && !isNew && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowAudit(a => !a)}>
                <span>Letzte Änderungen</span>
                <div className="grow" />
                <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
              </div>
              {showAudit && (
                <div className="bd" style={{ padding: '8px 0' }}>
                  <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>
                    Vollständiges Log unter Katalon → Audit-Log.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
