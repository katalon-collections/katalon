import { Fragment, useState, useEffect, useCallback } from 'react'
import { schema, vocabularies } from '../../api/client'
import type { FieldDefinition, RecordType, Vocabulary, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { AuthorityInput, type AuthorityEntry } from '../AuthorityInput'
import { ChevD, Edit, Plus, Tag, Trash, X } from '../ui/Icons'

const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  object: 'Objekt', entity: 'Entität', place: 'Ort', occurrence: 'Occurrence', procedure: 'Vorgang',
}
const RECORD_TYPES = Object.keys(RECORD_TYPE_LABELS) as RecordType[]

function AppliesCheckboxes({ value, onChange }: { value: RecordType[]; onChange: (v: RecordType[]) => void }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', fontSize: 12 }}>
      {RECORD_TYPES.map(rt => (
        <label key={rt} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={value.includes(rt)}
            onChange={e => onChange(e.target.checked ? [...value, rt] : value.filter(v => v !== rt))}
          />
          {RECORD_TYPE_LABELS[rt]}
        </label>
      ))}
      <span style={{ color: 'var(--fg-3)' }}>(keine Auswahl = alle)</span>
    </div>
  )
}

function appliesLabel(t: Pick<VocabularyTerm, 'applies_from' | 'applies_to'>): string {
  const from = (t.applies_from ?? []) as RecordType[]
  const to = (t.applies_to ?? []) as RecordType[]
  if (from.length === 0 && to.length === 0) return 'alle'
  const fmt = (arr: RecordType[]) => arr.length === 0 ? 'alle' : arr.map(r => RECORD_TYPE_LABELS[r]).join(', ')
  return `${fmt(from)} → ${fmt(to)}`
}

function AppliesPreview({ from, to }: { from: RecordType[]; to: RecordType[] }) {
  return (
    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--fg-3)' }} aria-live="polite">
      Gilt für: <strong>{appliesLabel({ applies_from: from, applies_to: to })}</strong>
      <div>Keine Auswahl in beiden Feldern gilt für alle Kombinationen; Objekt ohne Zieltyp gilt für Objekt → alle.</div>
    </div>
  )
}

function fieldLabel(field: FieldDefinition): string {
  return field.label.de || field.label.en || field.name
}

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

function MetadataSummary({ fields, metadata }: { fields: FieldDefinition[]; metadata: Record<string, unknown> }) {
  const values = fields.flatMap(field => {
    const raw = metadata[field.name]
    if (raw == null || raw === '' || (Array.isArray(raw) && raw.length === 0)) return []
    const items = Array.isArray(raw) ? raw : [raw]
    const text = items.map(item => {
      if (typeof item === 'object' && item && 'external_id' in item) {
        const authority = item as AuthorityEntry
        return authority.label || `${authority.source}:${authority.external_id}`
      }
      return item === true ? 'Ja' : item === false ? 'Nein' : String(item)
    }).join(', ')
    return [`${fieldLabel(field)}: ${text}`]
  })
  return values.length > 0
    ? <div style={{ marginTop: 4, color: 'var(--fg-3)', fontSize: 11 }}>{values.join(' · ')}</div>
    : null
}

interface ScreenVocabProps {
  initialVocab?: string | null
  onVocabSelect?: (name: string) => void
}

export function ScreenVocab({ initialVocab, onVocabSelect }: ScreenVocabProps = {}) {
  const [vocabs, setVocabs] = useState<Vocabulary[]>([])
  const [terms, setTerms] = useState<VocabularyTerm[]>([])
  const [activeVocab, setActiveVocab] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [termsLoading, setTermsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // new vocab form
  const [showNewVocab, setShowNewVocab] = useState(false)
  const [newVocabName, setNewVocabName] = useState('')
  const [newVocabHierarchical, setNewVocabHierarchical] = useState(false)
  const [newVocabKind, setNewVocabKind] = useState<'term' | 'relation'>('term')
  const [savingVocab, setSavingVocab] = useState(false)

  // new term form
  const [showNewTerm, setShowNewTerm] = useState(false)
  const [newTermTerm, setNewTermTerm] = useState('')
  const [newTermLabelDe, setNewTermLabelDe] = useState('')
  const [newTermInverseLabelDe, setNewTermInverseLabelDe] = useState('')
  const [newTermAppliesFrom, setNewTermAppliesFrom] = useState<RecordType[]>([])
  const [newTermAppliesTo, setNewTermAppliesTo] = useState<RecordType[]>([])
  const [savingTerm, setSavingTerm] = useState(false)
  const [newTermMetadata, setNewTermMetadata] = useState<Record<string, unknown>>({})

  // edit term inline
  const [editTermId, setEditTermId] = useState<string | null>(null)
  const [editTermTerm, setEditTermTerm] = useState('')
  const [editTermLabelDe, setEditTermLabelDe] = useState('')
  const [editTermInverseLabelDe, setEditTermInverseLabelDe] = useState('')
  const [editTermAppliesFrom, setEditTermAppliesFrom] = useState<RecordType[]>([])
  const [editTermAppliesTo, setEditTermAppliesTo] = useState<RecordType[]>([])
  const [savingEditTerm, setSavingEditTerm] = useState(false)
  const [editTermMetadata, setEditTermMetadata] = useState<Record<string, unknown>>({})
  const [termFields, setTermFields] = useState<FieldDefinition[]>([])
  const [importFile, setImportFile] = useState<File | null>(null)
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [importStrategy, setImportStrategy] = useState<'append' | 'replace'>('append')
  const [importBusy, setImportBusy] = useState(false)
  const [importFeedback, setImportFeedback] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<null | {
    created: number
    updated: number
    deleted: number
    dry_run: boolean
    errors: { row: number | null; message: string }[]
  }>(null)
  const [isDragging, setIsDragging] = useState(false)

  const CSV_TARGETS = [
    { value: '', label: 'Ignorieren' },
    { value: 'term', label: 'ID' },
    { value: 'parent_term', label: 'Parent-ID' },
    { value: 'label:de', label: 'Label (de)' },
    { value: 'label:en', label: 'Label (en)' },
    { value: 'inverse_label:de', label: 'Gegenrichtung (de)' },
    { value: 'inverse_label:en', label: 'Gegenrichtung (en)' },
  ]

  function detectDelimiter(line: string): string {
    const candidates = [',', ';', '\t', '|']
    let best = ','
    let bestCount = -1
    for (const delimiter of candidates) {
      const count = line.split(delimiter).length
      if (count > bestCount) {
        best = delimiter
        bestCount = count
      }
    }
    return best
  }

  async function prepareCsvMapping(file: File) {
    const text = await file.text()
    const firstLine = text.split(/\r?\n/)[0] ?? ''
    const delimiter = detectDelimiter(firstLine)
    const headers = firstLine.split(delimiter).map(v => v.trim()).filter(Boolean)
    setCsvHeaders(headers)
    setMapping(
      headers.reduce<Record<string, string>>((acc, header) => {
        const normalized = header.toLowerCase()
        if (normalized === 'term') acc[header] = 'term'
        else if (normalized === 'parent_term' || normalized === 'parent') acc[header] = 'parent_term'
        else if (normalized === 'label_de' || normalized === 'de') acc[header] = 'label:de'
        else if (normalized === 'label_en' || normalized === 'en') acc[header] = 'label:en'
        else acc[header] = ''
        return acc
      }, {}),
    )
  }

  async function handleFile(file: File | null) {
    setImportFeedback(null)
    setImportResult(null)
    setImportFile(file)
    setCsvHeaders([])
    setMapping({})
    if (!file) return
    const lower = file.name.toLowerCase()
    if (lower.endsWith('.csv') || lower.endsWith('.tsv')) {
      await prepareCsvMapping(file)
    }
  }

  const loadVocabs = useCallback(() => {
    setLoading(true)
    vocabularies.list()
      .then(data => {
        setVocabs(data)
        if (data.length > 0 && !activeVocab) {
          const target = initialVocab ? data.find(v => v.name === initialVocab) : null
          setActiveVocab(target ? target.id : data[0].id)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeVocab, initialVocab])

  useEffect(() => { loadVocabs() }, [])

  const loadTerms = useCallback(() => {
    if (!activeVocab) return
    setTermsLoading(true)
    vocabularies.listTerms(activeVocab)
      .then(setTerms)
      .catch(console.error)
      .finally(() => setTermsLoading(false))
  }, [activeVocab])

  useEffect(() => { loadTerms() }, [loadTerms])
  useEffect(() => {
    if (!activeVocab) {
      setTermFields([])
      return
    }
    schema.list('vocabulary_term', activeVocab)
      .then(setTermFields)
      .catch(() => setTermFields([]))
    setNewTermMetadata({})
    setEditTermId(null)
  }, [activeVocab])

  async function createVocab() {
    if (!newVocabName.trim()) return
    setSavingVocab(true)
    try {
      const v = await vocabularies.create({
        name: newVocabName.trim(),
        is_hierarchical: newVocabHierarchical,
        kind: newVocabKind,
      })
      setVocabs(prev => [...prev, v])
      setActiveVocab(v.id)
      onVocabSelect?.(v.name)
      setNewVocabName('')
      setNewVocabHierarchical(false)
      setNewVocabKind('term')
      setShowNewVocab(false)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingVocab(false)
    }
  }

  async function createTerm() {
    if (!activeVocab || !newTermTerm.trim()) return
    setSavingTerm(true)
    try {
      await vocabularies.createTerm(activeVocab, {
        vocabulary_id: activeVocab,
        term: newTermTerm.trim(),
        label: { de: newTermLabelDe.trim() },
        inverse_label: vocab?.kind === 'relation' && newTermInverseLabelDe.trim() ? { de: newTermInverseLabelDe.trim() } : {},
        metadata_: newTermMetadata,
        parent_id: null,
        applies_from: vocab?.kind === 'relation' ? newTermAppliesFrom : [],
        applies_to: vocab?.kind === 'relation' ? newTermAppliesTo : [],
      })
      setNewTermTerm('')
      setNewTermLabelDe('')
      setNewTermInverseLabelDe('')
      setNewTermAppliesFrom([])
      setNewTermAppliesTo([])
      setNewTermMetadata({})
      setShowNewTerm(false)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingTerm(false)
    }
  }

  function startEditTerm(t: VocabularyTerm) {
    setEditTermId(t.id)
    setEditTermTerm(t.term)
    setEditTermLabelDe(t.label.de ?? '')
    setEditTermInverseLabelDe(t.inverse_label?.de ?? '')
    setEditTermAppliesFrom((t.applies_from ?? []) as RecordType[])
    setEditTermAppliesTo((t.applies_to ?? []) as RecordType[])
    setEditTermMetadata({ ...(t.metadata_ ?? {}) })
  }

  async function saveEditTerm(t: VocabularyTerm) {
    setSavingEditTerm(true)
    try {
      await vocabularies.updateTerm(t.id, {
        vocabulary_id: activeVocab!,
        term: editTermTerm.trim(),
        label: { de: editTermLabelDe.trim() },
        inverse_label: vocab?.kind === 'relation' && editTermInverseLabelDe.trim() ? { de: editTermInverseLabelDe.trim() } : {},
        metadata_: editTermMetadata,
        parent_id: t.parent_id,
        applies_from: vocab?.kind === 'relation' ? editTermAppliesFrom : [],
        applies_to: vocab?.kind === 'relation' ? editTermAppliesTo : [],
      })
      setEditTermId(null)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingEditTerm(false)
    }
  }

  async function deleteTerm(id: string) {
    if (!window.confirm('Term wirklich löschen?')) return
    try {
      await vocabularies.deleteTerm(id)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  const isCsvImport = importFile ? /\.(csv|tsv)$/i.test(importFile.name) : false
  const hasTermMapping = Object.values(mapping).includes('term')
  const hasLabelMapping = Object.values(mapping).some(v => v.startsWith('label:'))

  async function runVocabularyImport(dryRun: boolean) {
    if (!activeVocab || !importFile) return
    if (isCsvImport && !hasTermMapping && !hasLabelMapping) {
      setImportFeedback("Bitte mindestens eine Spalte auf 'ID' oder 'Label' mappen. Ohne ID-Spalte wird die ID aus dem Label abgeleitet.")
      return
    }
    setImportBusy(true)
    setImportFeedback(null)
    try {
      const result = await vocabularies.importTerms(activeVocab, importFile, {
        dryRun,
        strategy: importStrategy,
        mapping: isCsvImport ? mapping : undefined,
      })
      setImportResult(result)
      if (!dryRun && result.errors.length === 0) {
        loadTerms()
      }
    } catch (e) {
      setImportFeedback((e as Error).message)
    } finally {
      setImportBusy(false)
    }
  }

  const vocab = vocabs.find(v => v.id === activeVocab)

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Vokabular</h1><div className="sub">Kontrollierte Vokabulare und Terme</div></div>
        <div className="right">
          <button className="btn" onClick={() => setShowNewVocab(v => !v)}><Plus size={13} /> Neues Vokabular</button>
        </div>
      </div>

      {error && <div style={{ padding: '8px 24px', color: '#b91c1c', fontSize: 13 }}>{error}</div>}

      {showNewVocab && (
        <div className="card" style={{ margin: '0 24px 12px', flexShrink: 0 }}>
          <div className="bd">
            <div className="fg-2">
              <div className="field">
                <div className="lbl">Name</div>
                <input className="fld" value={newVocabName} onChange={e => setNewVocabName(e.target.value)} placeholder="Vokabular-Name" autoFocus />
              </div>
              <div className="field">
                <div className="lbl">Art</div>
                <select className="fld" value={newVocabKind} onChange={e => setNewVocabKind(e.target.value as 'term' | 'relation')}>
                  <option value="term">Termvokabular</option>
                  <option value="relation">Relationsvokabular</option>
                </select>
              </div>
              <div className="field" style={{ paddingTop: 20 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={newVocabHierarchical} onChange={e => setNewVocabHierarchical(e.target.checked)} />
                  <span style={{ fontSize: 13 }}>Hierarchisch</span>
                </label>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn pri" onClick={createVocab} disabled={savingVocab}>Anlegen</button>
              <button className="btn gh" onClick={() => setShowNewVocab(false)}><X size={12} /></button>
            </div>
          </div>
        </div>
      )}

      <div className="vocab-grid" style={{ flex: 1, minHeight: 0 }}>
        <div className="vocab-tree">
          {vocabs.map(v => (
            <div key={v.id}>
              <div className={`tree-it${activeVocab === v.id ? ' active' : ''}`} onClick={() => { setActiveVocab(v.id); onVocabSelect?.(v.name) }}>
                <span className="caret">
                  {v.is_hierarchical ? <ChevD size={12} /> : null}
                </span>
                <Tag size={13} className="ic" />
                <span style={{ flex: 1 }}>{v.name}</span>
                {activeVocab === v.id && !termsLoading && <span className="ct">{terms.length}</span>}
              </div>
            </div>
          ))}
          {vocabs.length === 0 && <div className="empty" style={{ padding: 12, fontSize: 12 }}>Keine Vokabulare.</div>}
        </div>

        <div className="vocab-detail">
          {vocab && (
            <>
              <div className="vocab-detail-head">
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{vocab.name}</div>
                  <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>
                    {terms.length} Terme · {vocab.is_hierarchical ? 'Hierarchisch' : 'Flach'} · {vocab.kind === 'relation' ? 'Relationen' : 'Auswahlliste'}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                  <button className="btn pri" onClick={() => setShowNewTerm(v => !v)}><Plus size={13} /> Neuer Term</button>
                </div>
              </div>

              <div className="card" style={{ marginBottom: 12 }}>
                <div className="bd">
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>Vokabular-Import (CSV/JSON)</div>
                  <div className="help" style={{ marginBottom: 8 }}>
                    Hierarchische Listen: eine Spalte auf „Parent-ID" mappen — Inhalt ist die ID oder das Label des Elternterms (z.&nbsp;B. „Kopierschutz"). Ohne gemappte ID-Spalte wird die ID automatisch aus dem Label abgeleitet (z.&nbsp;B. „Kopierschutz DRM" → „kopierschutz-drm").
                  </div>
                  <div
                    onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={e => {
                      e.preventDefault()
                      setIsDragging(false)
                      void handleFile(e.dataTransfer.files?.[0] ?? null)
                    }}
                    style={{
                      border: `1px dashed ${isDragging ? 'var(--ac)' : 'var(--line)'}`,
                      background: isDragging ? 'color-mix(in oklab, var(--ac) 8%, white)' : 'transparent',
                      borderRadius: 8,
                      padding: 10,
                      fontSize: 12,
                      marginBottom: 10,
                    }}
                  >
                    Datei hier ablegen oder auswählen
                    <div style={{ marginTop: 8 }}>
                      <input
                        type="file"
                        accept=".csv,.tsv,.json"
                        onChange={e => { void handleFile(e.target.files?.[0] ?? null) }}
                      />
                    </div>
                    {importFile && <div style={{ marginTop: 8, color: 'var(--fg-3)' }}>{importFile.name}</div>}
                  </div>

                  {isCsvImport && csvHeaders.length > 0 && (
                    <div style={{ marginBottom: 10 }}>
                      <div className="lbl" style={{ marginBottom: 6 }}>Mapping-Dialog (CSV-Spalten → Zielfelder)</div>
                      <div style={{ display: 'grid', gap: 6 }}>
                        {csvHeaders.map(header => (
                          <div key={header} className="vocab-mapping-row">
                            <input className="fld mono" value={header} readOnly />
                            <select
                              className="fld"
                              value={mapping[header] ?? ''}
                              onChange={e => setMapping(prev => ({ ...prev, [header]: e.target.value }))}
                            >
                              {CSV_TARGETS.map(opt => <option key={opt.value || 'ignore'} value={opt.value}>{opt.label}</option>)}
                            </select>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <select
                      className="fld"
                      style={{ maxWidth: 220 }}
                      value={importStrategy}
                      onChange={e => setImportStrategy(e.target.value as 'append' | 'replace')}
                    >
                      <option value="append">Strategie: Ergänzen</option>
                      <option value="replace">Strategie: Komplett ersetzen</option>
                    </select>
                    <button className="btn" disabled={!importFile || importBusy} onClick={() => void runVocabularyImport(true)}>Dry-Run</button>
                    <button className="btn pri" disabled={!importFile || importBusy} onClick={() => void runVocabularyImport(false)}>Import ausführen</button>
                  </div>

                  {importFeedback && (
                    <div style={{ marginTop: 8, color: '#b91c1c', fontSize: 12 }}>{importFeedback}</div>
                  )}

                  {importResult && (
                    <div style={{ marginTop: 10, fontSize: 12 }}>
                      <div>
                        {importResult.dry_run ? 'Dry-Run' : 'Import'} · erstellt: {importResult.created} · aktualisiert: {importResult.updated} · gelöscht: {importResult.deleted}
                      </div>
                      {importResult.errors.length > 0 && (
                        <ul role="alert" style={{ marginTop: 6, color: '#b91c1c', paddingLeft: 16 }}>
                          {importResult.errors.map((err, idx) => (
                            <li key={`${err.row ?? 'x'}-${idx}`}>Zeile {err.row ?? '—'}: {err.message}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {showNewTerm && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <div className="bd">
                    <div className="fg-2">
                      <div className="field">
                        <div className="lbl">ID (intern)</div>
                        <input className="fld mono" value={newTermTerm} onChange={e => setNewTermTerm(e.target.value)} placeholder="z.B. silbergelatine" autoFocus />
                      </div>
                      <div className="field">
                        <div className="lbl">Label DE</div>
                        <input className="fld" value={newTermLabelDe} onChange={e => setNewTermLabelDe(e.target.value)} placeholder="Anzeigetext (Hinrichtung)" />
                      </div>
                      {vocab.kind === 'relation' && (
                        <div className="field">
                          <div className="lbl">Gegenrichtung DE</div>
                          <input className="fld" value={newTermInverseLabelDe} onChange={e => setNewTermInverseLabelDe(e.target.value)} placeholder="Anzeigetext (Rückrichtung, optional)" />
                        </div>
                      )}
                    </div>
                    {vocab.kind === 'relation' && (
                      <>
                        <div className="fg-2" style={{ marginTop: 8 }}>
                          <div className="field">
                            <div className="lbl">Quelltypen</div>
                            <AppliesCheckboxes value={newTermAppliesFrom} onChange={setNewTermAppliesFrom} />
                          </div>
                          <div className="field">
                            <div className="lbl">Zieltypen</div>
                            <AppliesCheckboxes value={newTermAppliesTo} onChange={setNewTermAppliesTo} />
                          </div>
                        </div>
                        <AppliesPreview from={newTermAppliesFrom} to={newTermAppliesTo} />
                      </>
                    )}
                    <CustomFieldsEditor fields={termFields} value={newTermMetadata} onChange={setNewTermMetadata} />
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button className="btn pri" onClick={createTerm} disabled={savingTerm}>Anlegen</button>
                      <button className="btn gh" onClick={() => setShowNewTerm(false)}><X size={12} /></button>
                    </div>
                  </div>
                </div>
              )}

              <div className="tw">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Label DE</th>
                      {vocab.kind === 'relation' && <th>Gegenrichtung DE</th>}
                      {vocab.kind === 'relation' && <th>Typen</th>}
                      <th>Übergeordnet</th>
                      <th className="col-act" />
                    </tr>
                  </thead>
                  <tbody>
                    {termsLoading && <tr><td colSpan={vocab.kind === 'relation' ? 6 : 4} className="empty">Lade…</td></tr>}
                    {!termsLoading && terms.length === 0 && (
                      <tr><td colSpan={vocab.kind === 'relation' ? 6 : 4} className="empty">Keine Terme.</td></tr>
                    )}
                    {!termsLoading && terms.map(t => (
                      editTermId === t.id ? (
                        <Fragment key={t.id}>
                          <tr>
                            <td><input className="fld mono" value={editTermTerm} onChange={e => setEditTermTerm(e.target.value)} style={{ maxWidth: 160 }} /></td>
                            <td><input className="fld" value={editTermLabelDe} onChange={e => setEditTermLabelDe(e.target.value)} style={{ maxWidth: 200 }} /></td>
                            {vocab.kind === 'relation' && <td><input className="fld" value={editTermInverseLabelDe} onChange={e => setEditTermInverseLabelDe(e.target.value)} style={{ maxWidth: 200 }} placeholder="Gegenrichtung" /></td>}
                            {vocab.kind === 'relation' && <td style={{ fontSize: 12, color: 'var(--fg-3)' }}>{appliesLabel(t)}</td>}
                            <td style={{ color: 'var(--fg-3)' }}>{t.parent_id ?? '—'}</td>
                            <td className="col-act">
                              <div className="row-actions">
                                <button className="btn sm pri" onClick={() => saveEditTerm(t)} disabled={savingEditTerm}>OK</button>
                                <button className="btn sm gh" onClick={() => setEditTermId(null)}><X size={12} /></button>
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td colSpan={vocab.kind === 'relation' ? 6 : 4} style={{ background: 'var(--panel)' }}>
                              {vocab.kind === 'relation' && (
                                <>
                                  <div className="fg-2" style={{ marginBottom: 8 }}>
                                    <div className="field">
                                      <div className="lbl">Quelltypen</div>
                                      <AppliesCheckboxes value={editTermAppliesFrom} onChange={setEditTermAppliesFrom} />
                                    </div>
                                    <div className="field">
                                      <div className="lbl">Zieltypen</div>
                                      <AppliesCheckboxes value={editTermAppliesTo} onChange={setEditTermAppliesTo} />
                                    </div>
                                  </div>
                                  <AppliesPreview from={editTermAppliesFrom} to={editTermAppliesTo} />
                                </>
                              )}
                              <CustomFieldsEditor fields={termFields} value={editTermMetadata} onChange={setEditTermMetadata} />
                            </td>
                          </tr>
                        </Fragment>
                      ) : (
                        <tr key={t.id}>
                          <td className="mono" style={{ maxWidth: 180 }}>{t.term}</td>
                          <td style={{ maxWidth: 220 }}>
                            {getLabel(t, '—')}
                            <MetadataSummary fields={termFields} metadata={t.metadata_ ?? {}} />
                          </td>
                          {vocab.kind === 'relation' && <td style={{ color: 'var(--fg-3)', maxWidth: 220 }}>{t.inverse_label?.de ?? '—'}</td>}
                          {vocab.kind === 'relation' && <td style={{ color: 'var(--fg-3)', maxWidth: 220, fontSize: 12 }}>{appliesLabel(t)}</td>}
                          <td style={{ color: 'var(--fg-3)', maxWidth: 160 }}>{t.parent_id ?? '—'}</td>
                          <td className="col-act">
                            <div className="row-actions">
                              <button className="btn sm ico gh" onClick={() => startEditTerm(t)}><Edit size={12} /></button>
                              <button className="btn sm ico gh dn" onClick={() => deleteTerm(t.id)}><Trash size={12} /></button>
                            </div>
                          </td>
                        </tr>
                      )
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {!vocab && vocabs.length > 0 && (
            <div className="empty">Vokabular auswählen.</div>
          )}
        </div>
      </div>
    </div>
  )
}
