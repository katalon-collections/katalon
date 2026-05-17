import { useState, useEffect, useCallback } from 'react'
import { vocabularies } from '../../api/client'
import type { Vocabulary, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { ChevD, Edit, Plus, Tag, Trash, X } from '../ui/Icons'

export function ScreenVocab() {
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
  const [savingVocab, setSavingVocab] = useState(false)

  // new term form
  const [showNewTerm, setShowNewTerm] = useState(false)
  const [newTermTerm, setNewTermTerm] = useState('')
  const [newTermLabelDe, setNewTermLabelDe] = useState('')
  const [savingTerm, setSavingTerm] = useState(false)

  // edit term inline
  const [editTermId, setEditTermId] = useState<string | null>(null)
  const [editTermTerm, setEditTermTerm] = useState('')
  const [editTermLabelDe, setEditTermLabelDe] = useState('')
  const [savingEditTerm, setSavingEditTerm] = useState(false)
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
    { value: 'term', label: 'Term' },
    { value: 'parent_term', label: 'Parent-Term' },
    { value: 'external_id', label: 'Externe ID' },
    { value: 'label:de', label: 'Label (de)' },
    { value: 'label:en', label: 'Label (en)' },
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
        else if (normalized === 'external_id') acc[header] = 'external_id'
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
          setActiveVocab(data[0].id)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeVocab])

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

  async function createVocab() {
    if (!newVocabName.trim()) return
    setSavingVocab(true)
    try {
      const v = await vocabularies.create({ name: newVocabName.trim(), is_hierarchical: newVocabHierarchical })
      setVocabs(prev => [...prev, v])
      setActiveVocab(v.id)
      setNewVocabName('')
      setNewVocabHierarchical(false)
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
        parent_id: null,
      })
      setNewTermTerm('')
      setNewTermLabelDe('')
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
  }

  async function saveEditTerm(t: VocabularyTerm) {
    setSavingEditTerm(true)
    try {
      await vocabularies.updateTerm(t.id, {
        vocabulary_id: activeVocab!,
        term: editTermTerm.trim(),
        label: { de: editTermLabelDe.trim() },
        parent_id: t.parent_id,
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

  async function runVocabularyImport(dryRun: boolean) {
    if (!activeVocab || !importFile) return
    if (isCsvImport && !hasTermMapping) {
      setImportFeedback("Bitte mindestens eine Spalte auf 'Term' mappen.")
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
              <div className={`tree-it${activeVocab === v.id ? ' active' : ''}`} onClick={() => setActiveVocab(v.id)}>
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

        <div style={{ overflow: 'auto', padding: '18px 24px' }}>
          {vocab && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{vocab.name}</div>
                  <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>
                    {terms.length} Terme · {vocab.is_hierarchical ? 'Hierarchisch' : 'Flach'}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                  <button className="btn pri" onClick={() => setShowNewTerm(v => !v)}><Plus size={13} /> Neuer Term</button>
                </div>
              </div>

              <div className="card" style={{ marginBottom: 12 }}>
                <div className="bd">
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>Vokabular-Import (CSV/JSON)</div>
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
                          <div key={header} style={{ display: 'grid', gridTemplateColumns: '1fr 220px', gap: 8 }}>
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
                        <div className="lbl">Term (intern)</div>
                        <input className="fld mono" value={newTermTerm} onChange={e => setNewTermTerm(e.target.value)} placeholder="z.B. silbergelatine" autoFocus />
                      </div>
                      <div className="field">
                        <div className="lbl">Label DE</div>
                        <input className="fld" value={newTermLabelDe} onChange={e => setNewTermLabelDe(e.target.value)} placeholder="Anzeigetext" />
                      </div>
                    </div>
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
                      <th>Term</th>
                      <th>Label DE</th>
                      <th>Übergeordnet</th>
                      <th className="col-act" />
                    </tr>
                  </thead>
                  <tbody>
                    {termsLoading && <tr><td colSpan={4} className="empty">Lade…</td></tr>}
                    {!termsLoading && terms.length === 0 && (
                      <tr><td colSpan={4} className="empty">Keine Terme.</td></tr>
                    )}
                    {!termsLoading && terms.map(t => (
                      <tr key={t.id}>
                        {editTermId === t.id ? (
                          <>
                            <td><input className="fld mono" value={editTermTerm} onChange={e => setEditTermTerm(e.target.value)} style={{ maxWidth: 160 }} /></td>
                            <td><input className="fld" value={editTermLabelDe} onChange={e => setEditTermLabelDe(e.target.value)} style={{ maxWidth: 200 }} /></td>
                            <td style={{ color: 'var(--fg-3)' }}>{t.parent_id ?? '—'}</td>
                            <td className="col-act">
                              <div className="row-actions">
                                <button className="btn sm pri" onClick={() => saveEditTerm(t)} disabled={savingEditTerm}>OK</button>
                                <button className="btn sm gh" onClick={() => setEditTermId(null)}><X size={12} /></button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="mono" style={{ maxWidth: 180 }}>{t.term}</td>
                            <td style={{ maxWidth: 220 }}>{getLabel(t, '—')}</td>
                            <td style={{ color: 'var(--fg-3)', maxWidth: 160 }}>{t.parent_id ?? '—'}</td>
                            <td className="col-act">
                              <div className="row-actions">
                                <button className="btn sm ico gh" onClick={() => startEditTerm(t)}><Edit size={12} /></button>
                                <button className="btn sm ico gh dn" onClick={() => deleteTerm(t.id)}><Trash size={12} /></button>
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
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
