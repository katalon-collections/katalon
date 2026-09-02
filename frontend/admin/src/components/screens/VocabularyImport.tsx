// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { vocabularies } from '../../api/client'
import type { Vocabulary } from '../../types'

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
  return [',', ';', '\t', '|'].reduce((best, delimiter) =>
    line.split(delimiter).length > line.split(best).length ? delimiter : best,
  )
}

export function VocabularyImport() {
  const [vocabs, setVocabs] = useState<Vocabulary[]>([])
  const [vocabId, setVocabId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [strategy, setStrategy] = useState<'append' | 'replace'>('append')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [result, setResult] = useState<null | { created: number; updated: number; deleted: number; dry_run: boolean; errors: { row: number | null; message: string }[] }>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => { void vocabularies.list().then(setVocabs).catch(error => setFeedback(error.message)) }, [])

  const vocab = vocabs.find(item => item.id === vocabId)
  const isCsv = file ? /\.(csv|tsv)$/i.test(file.name) : false
  const csvTargets = vocab?.kind === 'relation' ? CSV_TARGETS.filter(target => target.value !== 'parent_term') : CSV_TARGETS

  async function selectFile(nextFile: File | null) {
    setFeedback(null)
    setResult(null)
    setFile(nextFile)
    setHeaders([])
    setMapping({})
    if (!nextFile || !/\.(csv|tsv)$/i.test(nextFile.name)) return
    const firstLine = (await nextFile.text()).split(/\r?\n/)[0] ?? ''
    const headers = firstLine.split(detectDelimiter(firstLine))
      .map(value => value.trim()).filter(Boolean) ?? []
    setHeaders(headers)
    setMapping(headers.reduce<Record<string, string>>((next, header) => {
      const normalized = header.toLowerCase()
      next[header] = normalized === 'term' ? 'term'
        : (normalized === 'parent_term' || normalized === 'parent') && vocab?.kind !== 'relation' ? 'parent_term'
          : normalized === 'label_de' || normalized === 'de' ? 'label:de'
            : normalized === 'label_en' || normalized === 'en' ? 'label:en' : ''
      return next
    }, {}))
  }

  async function runImport(dryRun: boolean) {
    if (!file || !vocabId) return
    if (isCsv && !Object.values(mapping).some(value => value === 'term' || value.startsWith('label:'))) {
      setFeedback("Bitte mindestens eine Spalte auf 'ID' oder 'Label' mappen. Ohne ID-Spalte wird die ID aus dem Label abgeleitet.")
      return
    }
    setBusy(true)
    setFeedback(null)
    try {
      setResult(await vocabularies.importTerms(vocabId, file, { dryRun, strategy, mapping: isCsv ? mapping : undefined }))
    } catch (error) {
      setFeedback((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="importer-content">
      <div className="field" style={{ maxWidth: 360 }}>
        <label className="lbl" htmlFor="vocabulary-import-target">Zielvokabular</label>
        <select id="vocabulary-import-target" className="fld" value={vocabId} onChange={event => { setVocabId(event.target.value); void selectFile(null) }}>
          <option value="">Vokabular auswählen</option>
          {vocabs.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </div>

      {vocab && <div className="card" style={{ marginTop: 16 }}>
        <div className="bd">
          <div className="help" style={{ marginBottom: 8 }}>
            {vocab.kind === 'relation'
              ? 'Relationstypen sind flach. Ohne ID-Spalte wird die ID automatisch aus dem Label abgeleitet.'
              : 'Hierarchische Listen: eine Spalte auf „Parent-ID“ mappen. Ohne ID-Spalte wird die ID aus dem Label abgeleitet.'}
          </div>
          <div
            onDragOver={event => { event.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={event => { event.preventDefault(); setIsDragging(false); void selectFile(event.dataTransfer.files?.[0] ?? null) }}
            style={{ border: `1px dashed ${isDragging ? 'var(--ac)' : 'var(--line)'}`, background: isDragging ? 'color-mix(in oklab, var(--ac) 8%, white)' : 'transparent', borderRadius: 8, padding: 10, fontSize: 12, marginBottom: 10 }}
          >
            Datei hier ablegen oder auswählen
            <div style={{ marginTop: 8 }}><input type="file" accept=".csv,.tsv,.json" onChange={event => { void selectFile(event.target.files?.[0] ?? null) }} /></div>
            {file && <div style={{ marginTop: 8, color: 'var(--fg-3)' }}>{file.name}</div>}
          </div>

          {isCsv && headers.length > 0 && <div style={{ marginBottom: 10 }}>
            <div className="lbl" style={{ marginBottom: 6 }}>CSV-Spalten zuordnen</div>
            <div style={{ display: 'grid', gap: 6 }}>
              {headers.map(header => <div key={header} className="vocab-mapping-row">
                <input className="fld mono" value={header} readOnly />
                <select className="fld" value={mapping[header] ?? ''} onChange={event => setMapping(current => ({ ...current, [header]: event.target.value }))}>
                  {csvTargets.map(target => <option key={target.value || 'ignore'} value={target.value}>{target.label}</option>)}
                </select>
              </div>)}
            </div>
          </div>}

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <select className="fld" style={{ maxWidth: 220 }} value={strategy} onChange={event => setStrategy(event.target.value as 'append' | 'replace')}>
              <option value="append">Strategie: Ergänzen</option>
              <option value="replace">Strategie: Komplett ersetzen</option>
            </select>
            <button className="btn" disabled={!file || busy} onClick={() => void runImport(true)}>Dry-Run</button>
            <button className="btn pri" disabled={!file || busy} onClick={() => void runImport(false)}>Import ausführen</button>
          </div>

          {feedback && <div role="alert" style={{ marginTop: 8, color: '#b91c1c', fontSize: 12 }}>{feedback}</div>}
          {result && <div style={{ marginTop: 10, fontSize: 12 }}>
            <div>{result.dry_run ? 'Dry-Run' : 'Import'} · erstellt: {result.created} · aktualisiert: {result.updated} · gelöscht: {result.deleted}</div>
            {result.errors.length > 0 && <ul role="alert" style={{ marginTop: 6, color: '#b91c1c', paddingLeft: 16 }}>
              {result.errors.map((error, index) => <li key={`${error.row ?? 'x'}-${index}`}>Zeile {error.row ?? '—'}: {error.message}</li>)}
            </ul>}
          </div>}
        </div>
      </div>}
    </div>
  )
}
