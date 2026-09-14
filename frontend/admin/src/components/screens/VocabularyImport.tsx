// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { vocabularies } from '../../api/client'
import type { Vocabulary, VocabularyImportResult } from '../../types'

const CSV_TARGETS = [
  { value: '', labelKey: 'importDialog.ignore', defaultLabel: 'Ignorieren' },
  { value: 'term', labelKey: 'importDialog.targetId', defaultLabel: 'ID' },
  { value: 'parent_term', labelKey: 'importDialog.targetParentId', defaultLabel: 'Parent-ID' },
  { value: 'label:de', labelKey: 'importDialog.targetLabelDe', defaultLabel: 'Label (de)' },
  { value: 'label:en', labelKey: 'importDialog.targetLabelEn', defaultLabel: 'Label (en)' },
  { value: 'inverse_label:de', labelKey: 'importDialog.targetInvDe', defaultLabel: 'Gegenrichtung (de)' },
  { value: 'inverse_label:en', labelKey: 'importDialog.targetInvEn', defaultLabel: 'Gegenrichtung (en)' },
  { value: 'uri', labelKey: 'importDialog.targetUri', defaultLabel: 'URI (Kanonisch)' },
  { value: 'exact_match_uris', labelKey: 'importDialog.targetExactMatch', defaultLabel: 'Exact Match URIs' },
]

function detectDelimiter(line: string): string {
  return [',', ';', '\t', '|'].reduce((best, delimiter) =>
    line.split(delimiter).length > line.split(best).length ? delimiter : best,
  )
}

export interface VocabularyImportProps {
  initialVocabId?: string
  onImportComplete?: () => void
  onClose?: () => void
}

export function VocabularyImport({ initialVocabId, onImportComplete, onClose }: VocabularyImportProps = {}) {
  const { t } = useTranslation('screenVocab')
  const [vocabs, setVocabs] = useState<Vocabulary[]>([])
  const [vocabId, setVocabId] = useState(initialVocabId ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [strategy, setStrategy] = useState<'append' | 'replace'>('append')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [result, setResult] = useState<VocabularyImportResult | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  // SKOS-specific filters & options
  const [conceptScheme, setConceptScheme] = useState('')
  const [topConcept, setTopConcept] = useState('')
  const [maxDepth, setMaxDepth] = useState('')
  const [maxTerms, setMaxTerms] = useState('')

  useEffect(() => {
    if (initialVocabId) {
      setVocabId(initialVocabId)
    }
  }, [initialVocabId])

  useEffect(() => {
    void vocabularies.list().then(setVocabs).catch(error => setFeedback((error as Error).message))
  }, [])

  const vocab = vocabs.find(item => item.id === vocabId)
  const isCsv = file ? /\.(csv|tsv)$/i.test(file.name) : false
  const isSkos = file ? /\.(ttl|rdf|xml|jsonld|json)$/i.test(file.name) && !isCsv : false
  const csvTargets = vocab?.kind === 'relation' ? CSV_TARGETS.filter(target => target.value !== 'parent_term') : CSV_TARGETS

  async function selectFile(nextFile: File | null) {
    setFeedback(null)
    setResult(null)
    setFile(nextFile)
    setHeaders([])
    setMapping({})
    if (!nextFile || !/\.(csv|tsv)$/i.test(nextFile.name)) return
    const firstLine = (await nextFile.text()).split(/\r?\n/)[0] ?? ''
    const foundHeaders = firstLine.split(detectDelimiter(firstLine))
      .map(value => value.trim()).filter(Boolean) ?? []
    setHeaders(foundHeaders)
    setMapping(foundHeaders.reduce<Record<string, string>>((next, header) => {
      const normalized = header.toLowerCase()
      next[header] = normalized === 'term' ? 'term'
        : (normalized === 'parent_term' || normalized === 'parent') && vocab?.kind !== 'relation' ? 'parent_term'
          : normalized === 'label_de' || normalized === 'de' ? 'label:de'
            : normalized === 'label_en' || normalized === 'en' ? 'label:en'
              : normalized === 'uri' ? 'uri'
                : normalized === 'exact_match_uris' || normalized === 'exact_matches' || normalized === 'exact_match' ? 'exact_match_uris' : ''
      return next
    }, {}))
  }

  async function runImport(dryRun: boolean) {
    if (!file || !vocabId) return
    if (isCsv && !Object.values(mapping).some(value => value === 'term' || value.startsWith('label:'))) {
      setFeedback(t('importDialog.csvRequireTermOrLabel'))
      return
    }
    setBusy(true)
    setFeedback(null)
    try {
      let res: VocabularyImportResult
      if (isSkos) {
        res = await vocabularies.importSkos(vocabId, file, {
          dryRun,
          strategy,
          conceptScheme: conceptScheme.trim() || undefined,
          topConcept: topConcept.trim() || undefined,
          maxDepth: maxDepth ? parseInt(maxDepth, 10) : undefined,
          maxTerms: maxTerms ? parseInt(maxTerms, 10) : undefined,
        })
      } else {
        res = await vocabularies.importTerms(vocabId, file, {
          dryRun,
          strategy,
          mapping: isCsv ? mapping : undefined,
        })
      }
      setResult(res)
      if (!dryRun && res.errors.length === 0) {
        onImportComplete?.()
      }
    } catch (error) {
      setFeedback((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="importer-content">
      {!initialVocabId && (
        <div className="field" style={{ maxWidth: 360 }}>
          <label className="lbl" htmlFor="vocabulary-import-target">{t('importDialog.targetVocab')}</label>
          <select id="vocabulary-import-target" className="fld" value={vocabId} onChange={event => { setVocabId(event.target.value); void selectFile(null) }}>
            <option value="">{t('importDialog.selectVocab')}</option>
            {vocabs.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
      )}

      {vocab && (
        <div className="card" style={{ marginTop: initialVocabId ? 0 : 16 }}>
          <div className="bd">
            <div className="help" style={{ marginBottom: 8 }}>
              {vocab.kind === 'relation'
                ? t('importDialog.relationNotice')
                : t('importDialog.hierarchyNotice')}
            </div>
            <div
              onDragOver={event => { event.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={event => { event.preventDefault(); setIsDragging(false); void selectFile(event.dataTransfer.files?.[0] ?? null) }}
              style={{
                border: `1px dashed ${isDragging ? 'var(--ac)' : 'var(--line)'}`,
                background: isDragging ? 'color-mix(in oklab, var(--ac) 8%, white)' : 'transparent',
                borderRadius: 8,
                padding: 12,
                fontSize: 12,
                marginBottom: 10,
              }}
            >
              <div>{t('importDialog.dropzonePrompt')}</div>
              <div style={{ marginTop: 2, color: 'var(--fg-3)', fontSize: 11 }}>
                {t('importDialog.acceptedFormats')}
              </div>
              <div style={{ marginTop: 8 }}>
                <input
                  type="file"
                  accept=".csv,.tsv,.json,.ttl,.rdf,.xml,.jsonld"
                  onChange={event => { void selectFile(event.target.files?.[0] ?? null) }}
                />
              </div>
              {file && (
                <div style={{ marginTop: 8, color: 'var(--fg-1)', fontWeight: 500 }}>
                  {file.name} {isSkos && <span className="badge" style={{ marginLeft: 6, fontSize: 10 }}>SKOS / RDF</span>}
                </div>
              )}
            </div>

            {isCsv && headers.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div className="lbl" style={{ marginBottom: 6 }}>{t('importDialog.csvMapping')}</div>
                <div style={{ display: 'grid', gap: 6 }}>
                  {headers.map(header => (
                    <div key={header} className="vocab-mapping-row">
                      <input className="fld mono" value={header} readOnly />
                      <select className="fld" value={mapping[header] ?? ''} onChange={event => setMapping(current => ({ ...current, [header]: event.target.value }))}>
                        {csvTargets.map(target => (
                          <option key={target.value || 'ignore'} value={target.value}>
                            {t(target.labelKey, target.defaultLabel)}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {isSkos && (
              <div style={{ marginBottom: 14, padding: 10, background: 'var(--bg-2, #f9fafb)', borderRadius: 6, display: 'grid', gap: 10 }}>
                <div className="lbl" style={{ fontWeight: 600 }}>{t('importDialog.skosOptions')}</div>

                <div className="field">
                  <label className="lbl">{t('importDialog.conceptScheme')}</label>
                  <input
                    className="fld mono"
                    placeholder={t('importDialog.conceptSchemeHelp')}
                    value={conceptScheme}
                    onChange={e => setConceptScheme(e.target.value)}
                  />
                </div>

                <div className="field">
                  <label className="lbl">{t('importDialog.topConcept')}</label>
                  <input
                    className="fld mono"
                    placeholder={t('importDialog.topConceptHelp')}
                    value={topConcept}
                    onChange={e => setTopConcept(e.target.value)}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="field">
                    <label className="lbl">{t('importDialog.maxDepth')}</label>
                    <input
                      type="number"
                      min="1"
                      className="fld"
                      placeholder="z. B. 2"
                      value={maxDepth}
                      onChange={e => setMaxDepth(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label className="lbl">{t('importDialog.maxTerms')}</label>
                    <input
                      type="number"
                      min="1"
                      className="fld"
                      placeholder="50000"
                      value={maxTerms}
                      onChange={e => setMaxTerms(e.target.value)}
                    />
                  </div>
                </div>

                {result?.detected_schemes && result.detected_schemes.length > 0 && (
                  <div style={{ marginTop: 4, padding: 8, background: 'var(--bg-1, #fff)', border: '1px solid var(--line, #e5e7eb)', borderRadius: 6 }}>
                    <div className="lbl" style={{ fontSize: 11, marginBottom: 4 }}>{t('importDialog.detectedSchemes')}</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {result.detected_schemes.map(s => (
                        <button
                          key={s.uri}
                          type="button"
                          className="btn sm gh"
                          style={{ fontSize: 11 }}
                          onClick={() => setConceptScheme(s.uri)}
                          title={s.uri}
                        >
                          {s.label} ({s.uri.split('/').pop() || s.uri})
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {result?.detected_top_concepts && result.detected_top_concepts.length > 0 && (
                  <div style={{ marginTop: 4, padding: 8, background: 'var(--bg-1, #fff)', border: '1px solid var(--line, #e5e7eb)', borderRadius: 6 }}>
                    <div className="lbl" style={{ fontSize: 11, marginBottom: 4 }}>{t('importDialog.detectedTopConcepts')}</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {result.detected_top_concepts.map(tc => (
                        <button
                          key={tc.uri}
                          type="button"
                          className="btn sm gh"
                          style={{ fontSize: 11 }}
                          onClick={() => setTopConcept(tc.uri)}
                          title={tc.uri}
                        >
                          {tc.label} ({tc.uri.split('/').pop() || tc.uri})
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <select className="fld" style={{ maxWidth: 220 }} value={strategy} onChange={event => setStrategy(event.target.value as 'append' | 'replace')}>
                <option value="append">{t('importDialog.strategyAppend')}</option>
                <option value="replace">{t('importDialog.strategyReplace')}</option>
              </select>
              <button type="button" className="btn" disabled={!file || busy} onClick={() => void runImport(true)}>
                {t('importDialog.dryRun')}
              </button>
              <button type="button" className="btn pri" disabled={!file || busy} onClick={() => void runImport(false)}>
                {busy ? t('importDialog.busy') : t('importDialog.execute')}
              </button>
              {onClose && (
                <button type="button" className="btn gh" style={{ marginLeft: 'auto' }} onClick={onClose}>
                  {t('close', 'Schließen')}
                </button>
              )}
            </div>

            {feedback && <div role="alert" style={{ marginTop: 8, color: '#b91c1c', fontSize: 12 }}>{feedback}</div>}

            {result && (
              <div style={{ marginTop: 12, fontSize: 12 }}>
                <div style={{ fontWeight: 500 }}>
                  {t('importDialog.resultSummary', {
                    mode: result.dry_run ? t('importDialog.dryRun') : t('importDialog.execute'),
                    total: result.total ?? (result.created + result.updated),
                    created: result.created,
                    updated: result.updated,
                    deleted: result.deleted,
                  })}
                </div>
                {result.errors.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div className="lbl" style={{ color: '#b91c1c', marginBottom: 4 }}>{t('importDialog.errorsHeading')}</div>
                    <ul role="alert" style={{ color: '#b91c1c', paddingLeft: 16, margin: 0 }}>
                      {result.errors.map((error, index) => (
                        <li key={`${error.row ?? 'x'}-${index}`}>
                          {error.row !== null && error.row !== undefined
                            ? t('importDialog.rowError', { row: error.row, message: error.message })
                            : t('importDialog.generalError', { message: error.message })}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
