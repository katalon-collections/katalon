// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { objects, entities, places, occurrences, procedures, search, vocabularies } from '../../api/client'
import type { BatchOperation, BatchOperationType, BatchRequest, BatchResponse, FieldDefinition, RecordType } from '../../types'
import { getLabel } from '../../types'
import { Alert, Check, X } from '../ui/Icons'

const API_MAP = {
  object: objects,
  entity: entities,
  place: places,
  occurrence: occurrences,
  procedure: procedures,
}

const STATUS_OPTIONS: Record<RecordType, string[]> = {
  object: ['draft', 'internal', 'public'],
  entity: ['draft', 'internal', 'public'],
  place: ['draft', 'internal', 'public'],
  occurrence: ['draft', 'internal', 'public'],
  procedure: ['draft', 'active', 'completed', 'cancelled'],
}

interface Props {
  recordType: RecordType
  fields: FieldDefinition[]
  selection: {
    mode: 'ids' | 'filters'
    ids: string[]
    filters: Record<string, unknown>
    count: number
  }
  onClose: () => void
  onSuccess: () => void
}

export function BatchEditModal({ recordType, fields, selection, onClose, onSuccess }: Props) {
  const { t } = useTranslation('batchEditModal')
  const TYPE_LABELS: Record<RecordType, string> = {
    object: t('types.object'),
    entity: t('types.entity'),
    place: t('types.place'),
    occurrence: t('types.occurrence'),
    procedure: t('types.procedure'),
  }
  const STATUS_LABELS: Record<string, string> = {
    draft: t('statuses.draft'),
    internal: t('statuses.internal'),
    public: t('statuses.public'),
    active: t('statuses.active'),
    completed: t('statuses.completed'),
    cancelled: t('statuses.cancelled'),
  }
  const [opType, setOpType] = useState<BatchOperationType>('set_status')
  const [statusValue, setStatusValue] = useState<string>(STATUS_OPTIONS[recordType][0])
  const [fieldName, setFieldName] = useState<string>('')
  const [fieldValue, setFieldValue] = useState<string>('')
  const [fieldValueList, setFieldValueList] = useState<string[]>([''])
  const [booleanValue, setBooleanValue] = useState<boolean>(false)
  const [dateValue, setDateValue] = useState<string>('')
  const [numberValue, setNumberValue] = useState<string>('')
  const [vocabId, setVocabId] = useState<string>('')
  const [vocabQuery, setVocabQuery] = useState<string>('')
  const [vocabResults, setVocabResults] = useState<{ id: string; label: string }[]>([])
  const [selectedTerm, setSelectedTerm] = useState<{ id: string; label: string } | null>(null)
  const [relationToType, setRelationToType] = useState<RecordType>('object')
  const [relationType, setRelationType] = useState<string>('')
  const [recordQuery, setRecordQuery] = useState<string>('')
  const [recordResults, setRecordResults] = useState<{ id: string; label: string }[]>([])
  const [selectedRecord, setSelectedRecord] = useState<{ id: string; label: string } | null>(null)
  const [acceptedWarning, setAcceptedWarning] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BatchResponse | null>(null)

  const batchableFields = useMemo(
    () => fields.filter(f => f.field_type !== 'group' && f.field_type !== 'pid' && f.field_type !== 'url' && f.field_type !== 'authority'),
    [fields]
  )

  const selectedField = useMemo(
    () => batchableFields.find(f => f.name === fieldName) || null,
    [batchableFields, fieldName]
  )

  useEffect(() => {
    if (batchableFields.length > 0 && !fieldName) {
      setFieldName(batchableFields[0].name)
    }
  }, [batchableFields, fieldName])

  useEffect(() => {
    if (!selectedField) return
    if (selectedField.field_type === 'vocab' || selectedField.field_type === 'vocab_free') {
      const id = (selectedField.settings?.vocabulary_id as string) || ''
      setVocabId(id)
    } else {
      setVocabId('')
      setSelectedTerm(null)
    }
  }, [selectedField])

  useEffect(() => {
    if (!vocabId || vocabQuery.length < 2) {
      setVocabResults([])
      return
    }
    const t = setTimeout(() => {
      vocabularies.searchTerms(vocabId, vocabQuery)
        .then(terms => setVocabResults(terms.map(t => ({ id: t.id, label: getLabel(t, t.term) }))))
        .catch(() => setVocabResults([]))
    }, 200)
    return () => clearTimeout(t)
  }, [vocabId, vocabQuery])

  useEffect(() => {
    if (recordQuery.length < 2) {
      setRecordResults([])
      return
    }
    const t = setTimeout(() => {
      search.query(recordQuery, relationToType, 10)
        .then(res => setRecordResults(res.items.map(i => ({ id: i.id, label: `${i.title || i.id} (${i.record_type})` }))))
        .catch(() => setRecordResults([]))
    }, 200)
    return () => clearTimeout(t)
  }, [recordQuery, relationToType])

  function buildOperation(): BatchOperation {
    switch (opType) {
      case 'set_status':
        return { type: 'set_status', value: statusValue }
      case 'set_field':
      case 'append_field':
        return { type: opType, field: fieldName, value: buildFieldValue() }
      case 'clear_field':
        return { type: 'clear_field', field: fieldName }
      case 'add_relation':
      case 'remove_relation':
        return {
          type: opType,
          relation_to_type: relationToType,
          relation_to_id: selectedRecord?.id || '',
          relation_type: relationType,
        }
      default:
        throw new Error(t('errors.unknownOperation'))
    }
  }

  function buildFieldValue(): unknown {
    if (!selectedField) return fieldValue
    const ft = selectedField.field_type
    if (ft === 'boolean') return booleanValue
    if (ft === 'number') {
      const n = Number(numberValue)
      return Number.isNaN(n) ? null : n
    }
    if (ft === 'date') return dateValue || null
    if (ft === 'geo') return fieldValue
    if (ft === 'vocab' || ft === 'vocab_free') {
      if (selectedTerm) return { term_id: selectedTerm.id, label: selectedTerm.label }
      return fieldValue
    }
    if (opType === 'set_field' && selectedField.is_repeatable) {
      return fieldValueList.filter(v => v.trim() !== '').map(value => ({ value }))
    }
    return fieldValue
  }

  function validate(): string | null {
    if (opType === 'set_field' || opType === 'append_field') {
      if (!fieldName) return t('errors.selectField')
      if (opType === 'append_field' && !selectedField?.is_repeatable) {
        return t('errors.appendOnlyRepeatable')
      }
      if ((selectedField?.field_type === 'vocab' || selectedField?.field_type === 'vocab_free') && !selectedTerm && !fieldValue.trim()) {
        return t('errors.enterValueOrTerm')
      }
    }
    if ((opType === 'add_relation' || opType === 'remove_relation')) {
      if (!selectedRecord) return t('errors.selectTargetRecord')
      if (!relationType.trim()) return t('errors.enterRelationType')
    }
    if (selection.count === 0) return t('errors.noRecordsSelected')
    if (selection.count > 50 && !acceptedWarning) return 'WARNUNG_BITTE_BESTÄTIGEN'
    return null
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const validation = validate()
    if (validation === 'WARNUNG_BITTE_BESTÄTIGEN') {
      setAcceptedWarning(true)
      return
    }
    if (validation) {
      setError(validation)
      return
    }

    const payload: BatchRequest = {
      operation: buildOperation(),
      ...(selection.mode === 'ids' ? { ids: selection.ids } : { filters: selection.filters }),
    }

    setLoading(true)
    try {
      const res = await API_MAP[recordType].batch(payload)
      setResult(res)
      if (res.errors.length === 0) {
        onSuccess()
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const needsWarning = selection.count > 50 && !acceptedWarning && !result

  return (
    <div className="batch-modal-backdrop" onClick={onClose}>
      <div className="batch-modal" onClick={e => e.stopPropagation()}>
        <div className="batch-modal-header">
          <h2>{t('title')}</h2>
          <button type="button" className="btn ico gh" onClick={onClose} aria-label={t('close')}><X size={16} /></button>
        </div>

        <div className="batch-modal-body">
          <div className="batch-summary">
            <strong>{selection.count.toLocaleString('de')} {TYPE_LABELS[recordType]}{selection.count === 1 ? '' : 'e'}</strong>
            {' '}{t('selected')}{selection.mode === 'filters' ? ` ${t('allSearchResults')}` : ''}
          </div>

          {needsWarning && (
            <div className="batch-warning">
              <Alert size={18} />
              <div>
                <strong>{t('warningTitle', { count: selection.count.toLocaleString('de') })}</strong>
                <p>{t('warningBody')}</p>
              </div>
              <label className="ck-hit">
                <input type="checkbox" className="ck" checked={acceptedWarning} onChange={e => setAcceptedWarning(e.target.checked)} />
                <span>{t('warningConfirm')}</span>
              </label>
            </div>
          )}

          {result && (
            <div className={`batch-result ${result.errors.length ? 'partial' : 'ok'}`}>
              <Check size={18} />
              <div>
                <strong>{t('recordsEdited', { count: result.affected.toLocaleString('de') })}</strong>
                {result.task_id && <p>{t('asyncJob', { taskId: result.task_id })}</p>}
                {result.errors.length > 0 && (
                  <details>
                    <summary>{t('errorCount', { count: result.errors.length })}</summary>
                    <ul>{result.errors.map((err, i) => <li key={i}>{err}</li>)}</ul>
                  </details>
                )}
              </div>
            </div>
          )}

          {error && <div className="batch-error">{error}</div>}

          <form id="batch-form" onSubmit={handleSubmit}>
            <div className="fld-row">
              <label>{t('operation')}</label>
              <select className="fld" value={opType} onChange={e => setOpType(e.target.value as BatchOperationType)}>
                <option value="set_status">{t('operations.setStatus')}</option>
                <option value="set_field">{t('operations.setField')}</option>
                <option value="append_field">{t('operations.appendField')}</option>
                <option value="clear_field">{t('operations.clearField')}</option>
                <option value="add_relation">{t('operations.addRelation')}</option>
                <option value="remove_relation">{t('operations.removeRelation')}</option>
              </select>
            </div>

            {opType === 'set_status' && (
              <div className="fld-row">
                <label>{t('newStatus')}</label>
                <select className="fld" value={statusValue} onChange={e => setStatusValue(e.target.value)}>
                  {STATUS_OPTIONS[recordType].map(s => (
                    <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>
                  ))}
                </select>
              </div>
            )}

            {(opType === 'set_field' || opType === 'append_field' || opType === 'clear_field') && (
              <>
                <div className="fld-row">
                  <label>{t('field')}</label>
                  <select className="fld" value={fieldName} onChange={e => setFieldName(e.target.value)}>
                    {batchableFields.map(f => (
                      <option key={f.name} value={f.name}>{getLabel(f, f.name)}</option>
                    ))}
                  </select>
                </div>

                {opType !== 'clear_field' && selectedField && (
                  <div className="fld-row">
                    <label>{t('value')}</label>
                    {selectedField.field_type === 'boolean' && (
                      <label className="ck-hit">
                        <input type="checkbox" className="ck" checked={booleanValue} onChange={e => setBooleanValue(e.target.checked)} />
                        <span>{t('active')}</span>
                      </label>
                    )}
                    {selectedField.field_type === 'number' && (
                      <input className="fld" type="number" value={numberValue} onChange={e => setNumberValue(e.target.value)} />
                    )}
                    {selectedField.field_type === 'date' && (
                      <input className="fld" type="date" value={dateValue} onChange={e => setDateValue(e.target.value)} />
                    )}
                    {(selectedField.field_type === 'text' || selectedField.field_type === 'richtext' || selectedField.field_type === 'geo') && !(
                      selectedField.is_repeatable && (selectedField.field_type === 'text' || selectedField.field_type === 'richtext') && opType === 'set_field'
                    ) && (
                      <input className="fld" type="text" value={fieldValue} onChange={e => setFieldValue(e.target.value)} />
                    )}
                    {(selectedField.field_type === 'vocab' || selectedField.field_type === 'vocab_free') && (
                      <div className="batch-vocab-search">
                        {!selectedTerm ? (
                          <>
                            <input
                              className="fld"
                              type="text"
                              placeholder={t('searchTermPlaceholder')}
                              value={vocabQuery}
                              onChange={e => setVocabQuery(e.target.value)}
                            />
                            {vocabResults.length > 0 && (
                              <ul className="batch-dropdown">
                                {vocabResults.map(vr => (
                                  <li key={vr.id} onClick={() => { setSelectedTerm(vr); setVocabQuery(vr.label); setVocabResults([]) }}>
                                    {vr.label}
                                  </li>
                                ))}
                              </ul>
                            )}
                            {selectedField.field_type === 'vocab_free' && (
                              <input
                                className="fld"
                                type="text"
                                placeholder={t('freeValuePlaceholder')}
                                value={fieldValue}
                                onChange={e => setFieldValue(e.target.value)}
                              />
                            )}
                          </>
                        ) : (
                          <div className="batch-selected">
                            {selectedTerm.label}
                            <button type="button" className="btn sm gh" onClick={() => { setSelectedTerm(null); setVocabQuery('') }}>{t('remove')}</button>
                          </div>
                        )}
                      </div>
                    )}
                    {selectedField.field_type === 'relation' && (
                      <input className="fld" type="text" placeholder={t('relatedRecordIdPlaceholder')} value={fieldValue} onChange={e => setFieldValue(e.target.value)} />
                    )}
                    {selectedField.is_repeatable && (selectedField.field_type === 'text' || selectedField.field_type === 'richtext') && opType === 'set_field' && (
                      <div className="batch-repeatable">
                        {fieldValueList.map((v, i) => (
                          <div key={i} className="batch-repeat-row">
                            <input className="fld" type="text" value={v} onChange={e => {
                              const next = [...fieldValueList]
                              next[i] = e.target.value
                              if (i === next.length - 1 && e.target.value.trim() !== '') next.push('')
                              setFieldValueList(next)
                            }} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {(opType === 'add_relation' || opType === 'remove_relation') && (
              <>
                <div className="fld-row">
                  <label>{t('targetType')}</label>
                  <select className="fld" value={relationToType} onChange={e => setRelationToType(e.target.value as RecordType)}>
                    <option value="object">{t('types.object')}</option>
                    <option value="entity">{t('types.entity')}</option>
                    <option value="place">{t('types.place')}</option>
                    <option value="occurrence">{t('types.occurrence')}</option>
                  </select>
                </div>
                <div className="fld-row">
                  <label>{t('targetRecord')}</label>
                  <div className="batch-record-search">
                    {!selectedRecord ? (
                      <>
                        <input
                          className="fld"
                          type="text"
                          placeholder={t('searchRecords')}
                          value={recordQuery}
                          onChange={e => setRecordQuery(e.target.value)}
                        />
                        {recordResults.length > 0 && (
                          <ul className="batch-dropdown">
                            {recordResults.map(r => (
                              <li key={r.id} onClick={() => { setSelectedRecord(r); setRecordQuery(r.label); setRecordResults([]) }}>
                                {r.label}
                              </li>
                            ))}
                          </ul>
                        )}
                      </>
                    ) : (
                      <div className="batch-selected">
                        {selectedRecord.label}
                        <button type="button" className="btn sm gh" onClick={() => { setSelectedRecord(null); setRecordQuery('') }}>{t('remove')}</button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="fld-row">
                  <label>{t('relationType')}</label>
                  <input className="fld" type="text" value={relationType} onChange={e => setRelationType(e.target.value)} placeholder={t('relationTypePlaceholder')} />
                </div>
              </>
            )}
          </form>
        </div>

        <div className="batch-modal-footer">
          <button type="button" className="btn gh" onClick={onClose} disabled={loading}>{t('cancel')}</button>
          <button type="submit" form="batch-form" className="btn pri" disabled={loading || (selection.count > 50 && !acceptedWarning)}>
            {loading ? t('executing') : t('executeButton')}
          </button>
        </div>
      </div>
    </div>
  )
}
