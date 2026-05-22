import { useEffect, useReducer, useRef } from 'react'
import { importer, schema, subtypes as subtypesApi } from '../../../api/client'
import type { MappingEntry, UploadResult } from '../../../api/client'
import type { FieldDefinition, RecordSubtype } from '../../../types'
import {
  IMPORTER_STATE_KEY,
  type ImporterAction,
  type ImporterState,
  type PendingField,
  type PersistedImporterState,
} from './types'

// ── Persistence helpers ───────────────────────────────────────────────────────

function migrateOldMapping(mapping: Record<string, unknown>): Record<string, MappingEntry> {
  const result: Record<string, MappingEntry> = {}
  for (const [col, entry] of Object.entries(mapping)) {
    if (!entry) continue
    if (typeof entry === 'string') {
      result[col] = { target: entry }
    } else if (typeof entry === 'object' && entry !== null && 'target' in entry) {
      const e = entry as Record<string, unknown>
      const transforms = (Array.isArray(e.transforms) ? e.transforms : []) as MappingEntry['transforms']
      if (e.delimiter && !transforms?.some(t => t.type === 'split')) {
        transforms?.push({ type: 'split', delimiter: e.delimiter as string, filter_empty: true })
      }
      result[col] = { target: e.target as string, transforms: transforms?.length ? transforms : undefined }
    }
  }
  return result
}

function loadPersistedState(): PersistedImporterState | null {
  try {
    const raw = localStorage.getItem(IMPORTER_STATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (typeof parsed.recordType === 'string' && typeof parsed.step === 'number') {
      if (parsed.mapping) parsed.mapping = migrateOldMapping(parsed.mapping)
      if (!parsed.pendingFields) parsed.pendingFields = []
      if (!('subtype' in parsed)) parsed.subtype = null
      if (!('idnoColumn' in parsed)) parsed.idnoColumn = null
      return parsed as PersistedImporterState
    }
  } catch { /* ignore corrupt state */ }
  return null
}

// ── Initial state ─────────────────────────────────────────────────────────────

function buildInitialState(persisted: PersistedImporterState | null): ImporterState {
  return {
    step:          persisted?.step          ?? 0,
    recordType:    persisted?.recordType    ?? 'object',
    subtype:       persisted?.subtype       ?? null,
    uploading:     false,
    uploadErr:     null,
    uploaded:      persisted?.uploaded      ?? null,
    mapping:       persisted?.mapping       ?? {},
    idnoStrategy:  persisted?.idnoStrategy  ?? 'auto',
    idnoColumn:    persisted?.idnoColumn    ?? null,
    upsertStrategy: persisted?.upsertStrategy ?? 'skip',
    autoPublish:   persisted?.autoPublish   ?? false,
    pendingFields: persisted?.pendingFields ?? [],
    dryResult:     persisted?.dryResult     ?? null,
    dryRunning:    false,
    taskId:        persisted?.taskId        ?? null,
    taskStatus:    null,
  }
}

// ── Reducer ───────────────────────────────────────────────────────────────────

function removeIdnoFromMapping(m: Record<string, MappingEntry>): Record<string, MappingEntry> {
  const next = { ...m }
  for (const [k, v] of Object.entries(next)) {
    if (v.target === '__idno__') delete next[k]
  }
  return next
}

function importerReducer(state: ImporterState, action: ImporterAction): ImporterState {
  switch (action.type) {
    case 'SET_RECORD_TYPE':
      return buildInitialState(null) // full reset on type change
        && { ...buildInitialState(null), recordType: action.payload }

    case 'SET_SUBTYPE':
      return { ...state, subtype: action.payload }

    case 'UPLOAD_STARTED':
      return { ...state, uploading: true, uploadErr: null }

    case 'UPLOADED': {
      const result = action.payload
      const autoMap: Record<string, MappingEntry> = {}
      // Auto-map obvious column names (will be refined by step components)
      return { ...state, uploading: false, uploaded: result, mapping: autoMap, step: 1, uploadErr: null }
    }

    case 'UPLOAD_ERROR':
      return { ...state, uploading: false, uploadErr: action.payload }

    case 'MAPPING_CHANGED':
      return { ...state, mapping: action.payload }

    case 'IDNO_STRATEGY_CHANGED': {
      const { strategy, column } = action.payload
      const mapping = strategy !== 'column'
        ? removeIdnoFromMapping(state.mapping)
        : column
          ? { ...removeIdnoFromMapping(state.mapping), [column]: { target: '__idno__' } }
          : removeIdnoFromMapping(state.mapping)
      return { ...state, idnoStrategy: strategy, idnoColumn: column, mapping }
    }

    case 'OPTIONS_CHANGED':
      return { ...state, ...action.payload }

    case 'PENDING_FIELDS_CHANGED':
      return { ...state, pendingFields: action.payload }

    case 'DRY_RUN_STARTED':
      return { ...state, dryRunning: true }

    case 'DRY_RUN_OK':
      return { ...state, dryRunning: false, dryResult: action.payload, step: 2 }

    case 'IMPORT_STARTED':
      return { ...state, taskId: action.payload, taskStatus: { state: 'PENDING' }, step: 3 }

    case 'TASK_STATUS_UPDATED':
      return { ...state, taskStatus: action.payload }

    case 'STEP_SET':
      return { ...state, step: action.payload }

    case 'RESET':
      return buildInitialState(null)

    default:
      return state
  }
}

// Workaround: SET_RECORD_TYPE resets all state then sets the type
function patchedReducer(state: ImporterState, action: ImporterAction): ImporterState {
  if (action.type === 'SET_RECORD_TYPE') {
    return { ...buildInitialState(null), recordType: action.payload }
  }
  return importerReducer(state, action)
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export interface ImporterStateAndHandlers {
  state: ImporterState
  dispatch: React.Dispatch<ImporterAction>
  fields: FieldDefinition[]
  availableSubtypes: RecordSubtype[]
  // Derived
  mappedCount: number
  ignoredCount: number
  missingRequired: FieldDefinition[]
  idnoMissing: boolean
  // Async handlers
  handleFile: (file: File) => Promise<void>
  handleDryRun: () => Promise<void>
  handleImport: () => Promise<void>
}

export function useImporterState(): ImporterStateAndHandlers {
  const persisted = loadPersistedState()
  const [state, dispatch] = useReducer(patchedReducer, persisted, buildInitialState)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [fields, setFields] = React.useState<FieldDefinition[]>([])
  const [availableSubtypes, setAvailableSubtypes] = React.useState<RecordSubtype[]>([])

  // Persist to localStorage
  useEffect(() => {
    const toSave: PersistedImporterState = {
      step: state.step, recordType: state.recordType, subtype: state.subtype,
      mapping: state.mapping, idnoStrategy: state.idnoStrategy, idnoColumn: state.idnoColumn,
      upsertStrategy: state.upsertStrategy, autoPublish: state.autoPublish,
      uploaded: state.uploaded, dryResult: state.dryResult, taskId: state.taskId,
      pendingFields: state.pendingFields,
    }
    localStorage.setItem(IMPORTER_STATE_KEY, JSON.stringify(toSave))
  }, [
    state.step, state.recordType, state.subtype, state.mapping, state.idnoStrategy,
    state.idnoColumn, state.upsertStrategy, state.autoPublish, state.uploaded,
    state.dryResult, state.taskId, state.pendingFields,
  ])

  // Load fields + subtypes when recordType or subtype changes
  useEffect(() => {
    schema.list(state.recordType, state.subtype ?? undefined).then(fs => {
      setFields(fs.concat(state.pendingFields.map((p): FieldDefinition => ({
        id: `__pending__${p.name}`,
        target_type: state.recordType,
        name: p.name,
        label: { de: p.label_de, en: p.label_en },
        field_type: p.field_type as FieldDefinition['field_type'],
        is_required: false,
        is_repeatable: p.is_repeatable,
        sort_order: 9999,
        settings: {},
        target_subtype: null,
        show_in_detail: false,
        show_in_list: false,
        is_facet: false,
        is_searchable: false,
      }))))
    }).catch(() => setFields([]))
    subtypesApi.list(state.recordType).then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
  }, [state.recordType, state.subtype]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-merge pending fields into fields list when pendingFields changes
  useEffect(() => {
    setFields(prev => {
      const base = prev.filter(f => !f.id.startsWith('__pending__'))
      return base.concat(state.pendingFields.map((p): FieldDefinition => ({
        id: `__pending__${p.name}`,
        target_type: state.recordType,
        name: p.name,
        label: { de: p.label_de, en: p.label_en },
        field_type: p.field_type as FieldDefinition['field_type'],
        is_required: false,
        is_repeatable: p.is_repeatable,
        sort_order: 9999,
        settings: {},
        target_subtype: null,
        show_in_detail: false,
        show_in_list: false,
        is_facet: false,
        is_searchable: false,
      })))
    })
  }, [state.pendingFields, state.recordType])

  // Poll task status
  useEffect(() => {
    if (!state.taskId) return
    pollRef.current = setInterval(async () => {
      try {
        const s = await importer.taskStatus(state.taskId!)
        dispatch({ type: 'TASK_STATUS_UPDATED', payload: s })
        if (s.state === 'SUCCESS' || s.state === 'FAILURE') {
          clearInterval(pollRef.current!)
        }
      } catch {
        clearInterval(pollRef.current!)
      }
    }, 1500)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [state.taskId])

  // Derived
  const mappedCount = Object.values(state.mapping).filter(m => m.target && m.target !== '__idno__').length
  const ignoredCount = state.uploaded
    ? state.uploaded.headers.length - mappedCount - (state.idnoStrategy === 'column' && state.idnoColumn ? 1 : 0)
    : 0
  const mappedTargets = new Set(Object.values(state.mapping).map(m => m.target).filter(Boolean))
  const missingRequired = fields.filter(f => f.is_required && !mappedTargets.has(f.name))
  const idnoMissing = state.idnoStrategy === 'column' && !state.idnoColumn

  // Async handlers
  async function handleFile(file: File) {
    dispatch({ type: 'UPLOAD_STARTED' })
    try {
      const result = await importer.upload(file) as UploadResult
      // Auto-map obvious columns
      const currentFields = fields
      const autoMap: Record<string, MappingEntry> = {}
      for (const col of (result.headers ?? [])) {
        const norm = col.toLowerCase().replace(/[\s\-]/g, '_')
        const match = currentFields.find(f => f.name === norm || f.label.de?.toLowerCase() === col.toLowerCase())
        if (match) autoMap[col] = { target: match.name }
      }
      dispatch({ type: 'UPLOADED', payload: { ...result, } })
      // Override auto-map with actual computed one
      dispatch({ type: 'MAPPING_CHANGED', payload: autoMap })
    } catch (e) {
      dispatch({ type: 'UPLOAD_ERROR', payload: (e as Error).message })
    }
  }

  async function handleDryRun() {
    if (!state.uploaded) return
    dispatch({ type: 'DRY_RUN_STARTED' })
    try {
      const result = await importer.dryRun(state.recordType, state.uploaded.rows, state.mapping, state.subtype)
      dispatch({ type: 'DRY_RUN_OK', payload: result })
    } catch (e) {
      dispatch({ type: 'OPTIONS_CHANGED', payload: {} }) // clear dryRunning
      alert((e as Error).message)
    }
  }

  async function handleImport() {
    if (!state.uploaded) return
    try {
      const { task_id } = await importer.import(state.recordType, state.uploaded.rows, state.mapping, {
        idno_strategy: state.idnoStrategy,
        upsert_strategy: state.upsertStrategy,
        auto_publish: state.autoPublish,
        subtype: state.subtype,
        fields_to_create: state.pendingFields.map(f => ({
          name: f.name, field_type: f.field_type,
          label_de: f.label_de, label_en: f.label_en, is_repeatable: f.is_repeatable,
        })),
      })
      dispatch({ type: 'IMPORT_STARTED', payload: task_id })
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return {
    state, dispatch, fields, availableSubtypes,
    mappedCount, ignoredCount, missingRequired, idnoMissing,
    handleFile, handleDryRun, handleImport,
  }
}

// React needs to be in scope for JSX in this file
import React from 'react'
