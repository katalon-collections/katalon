import React, { useEffect, useReducer, useRef } from 'react'
import { importer, schema, subtypes as subtypesApi } from '../../../api/client'
import type { MappingEntry, UploadResult, XmlElementLevel, XmlSelector } from '../../../api/client'
import type { FieldDefinition, RecordSubtype } from '../../../types'
import {
  IMPORTER_STATE_KEY,
  type ImporterAction,
  type ImporterState,
  type ImportProfile,
  type PendingField,
  type PersistedImporterState,
  type ProfileApplyResult,
} from './types'
import { applyProfile, buildProfile, downloadProfile } from './profileUtils'

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
  const hasUploadId = !!persisted?.uploaded?.upload_id
  const needsReupload = !!persisted?.uploaded && !hasUploadId && (persisted?.step ?? 0) > 0
  return {
    step:           needsReupload ? 0 : (persisted?.step ?? 0),
    recordType:     persisted?.recordType    ?? 'object',
    subtype:        persisted?.subtype       ?? null,
    uploading:      false,
    uploadErr:      null,
    uploaded:       persisted?.uploaded      ?? null,
    sourceType:     null,
    xmlUploadId:    null,
    xmlElementLevels: null,
    xmlSelectorsLoading: false,
    xmlSelectors:   null,
    mapping:        persisted?.mapping       ?? {},
    idnoStrategy:   persisted?.idnoStrategy  ?? 'auto',
    idnoColumn:     persisted?.idnoColumn    ?? null,
    upsertStrategy: persisted?.upsertStrategy ?? 'skip',
    autoPublish:    persisted?.autoPublish   ?? false,
    pendingFields:  persisted?.pendingFields ?? [],
    dryResult:      persisted?.dryResult     ?? null,
    dryRunning:     false,
    taskId:         persisted?.taskId        ?? null,
    taskStatus:     null,
    needsReupload,
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
      return { ...buildInitialState(null), recordType: action.payload }

    case 'SET_SUBTYPE':
      return { ...state, subtype: action.payload }

    case 'UPLOAD_STARTED':
      return { ...state, uploading: true, uploadErr: null }

    case 'UPLOADED':
      return { ...state, uploading: false, uploaded: action.payload, sourceType: action.payload.source_type ?? 'csv', mapping: {}, step: 1, uploadErr: null, needsReupload: false }

    case 'UPLOAD_ERROR':
      return { ...state, uploading: false, uploadErr: action.payload }

    case 'XML_UPLOAD_DONE':
      return {
        ...state, uploading: false, uploadErr: null,
        sourceType: 'xml',
        xmlUploadId: action.payload.uploadId,
        xmlElementLevels: action.payload.elementLevels,
        step: 1, // XmlRecordSelector step
      }

    case 'XML_SELECTORS_LOADING':
      return { ...state, xmlSelectorsLoading: true }

    case 'XML_RECORD_XPATH_SET':
      return {
        ...state,
        xmlSelectorsLoading: false,
        xmlSelectors: action.payload.selectors,
        uploaded: action.payload.uploaded,
        mapping: {},
        step: 2, // Mapping step for XML
      }

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
      return { ...state, dryRunning: false, dryResult: action.payload, step: state.sourceType === 'xml' ? 3 : 2 }

    case 'IMPORT_STARTED':
      return { ...state, taskId: action.payload, taskStatus: { state: 'PENDING' }, step: state.sourceType === 'xml' ? 4 : 3 }

    case 'TASK_STATUS_UPDATED':
      return { ...state, taskStatus: action.payload }

    case 'STEP_SET':
      return { ...state, step: action.payload }

    case 'PROFILE_APPLIED': {
      const { mapping, pendingFields, upsertStrategy, autoPublish, idnoStrategy } = action.payload
      return { ...state, mapping, pendingFields, upsertStrategy, autoPublish, idnoStrategy, step: state.sourceType === 'xml' ? 2 : 1 }
    }

    case 'RESET':
      return buildInitialState(null)

    default:
      return state
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export interface ImporterStateAndHandlers {
  state: ImporterState
  needsReupload: boolean
  dispatch: React.Dispatch<ImporterAction>
  fields: FieldDefinition[]
  availableSubtypes: RecordSubtype[]
  mappedCount: number
  ignoredCount: number
  missingRequired: FieldDefinition[]
  idnoMissing: boolean
  profileWarnings: ProfileApplyResult | null
  handleFile: (file: File) => Promise<void>
  handleXmlRecordXpath: (clarkTag: string) => Promise<void>
  handleDryRun: () => Promise<void>
  handleImport: () => Promise<void>
  handleProfileLoaded: (profile: ImportProfile) => Promise<void>
  handleProfileExport: () => Promise<void>
}

export function useImporterState(): ImporterStateAndHandlers {
  const persisted = loadPersistedState()
  const [state, dispatch] = useReducer(importerReducer, persisted, buildInitialState)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [fields, setFields] = React.useState<FieldDefinition[]>([])
  const [availableSubtypes, setAvailableSubtypes] = React.useState<RecordSubtype[]>([])
  const [profileWarnings, setProfileWarnings] = React.useState<ProfileApplyResult | null>(null)

  // Persist to localStorage — rows are NOT saved (too large); on restore, user must re-upload
  useEffect(() => {
    const toSave: PersistedImporterState = {
      step: state.step, recordType: state.recordType, subtype: state.subtype,
      mapping: state.mapping, idnoStrategy: state.idnoStrategy, idnoColumn: state.idnoColumn,
      upsertStrategy: state.upsertStrategy, autoPublish: state.autoPublish,
      uploaded: state.uploaded ? { ...state.uploaded, upload_id: '' } : null,
      dryResult: state.dryResult, taskId: state.taskId,
      pendingFields: state.pendingFields,
    }
    localStorage.setItem(IMPORTER_STATE_KEY, JSON.stringify(toSave))
  }, [
    state.step, state.recordType, state.subtype, state.mapping, state.idnoStrategy,
    state.idnoColumn, state.upsertStrategy, state.autoPublish, state.uploaded,
    state.dryResult, state.taskId, state.pendingFields,
  ])

  // Load fields + subtypes
  useEffect(() => {
    schema.list(state.recordType, state.subtype ?? undefined).then(fs => {
      const virtuals = state.pendingFields.map((p): FieldDefinition => ({
        id: `__pending__${p.name}`, target_type: state.recordType, name: p.name,
        label: { de: p.label_de, en: p.label_en },
        field_type: p.field_type as FieldDefinition['field_type'],
        is_required: false, is_repeatable: p.is_repeatable, sort_order: 9999,
        settings: {}, target_subtype: null,
        show_in_detail: false, show_in_list: false, is_facet: false, is_searchable: false,
      }))
      setFields(fs.concat(virtuals))
    }).catch(() => setFields([]))
    subtypesApi.list(state.recordType).then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
  }, [state.recordType, state.subtype]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-merge pending fields when they change
  useEffect(() => {
    setFields(prev => {
      const base = prev.filter(f => !f.id.startsWith('__pending__'))
      return base.concat(state.pendingFields.map((p): FieldDefinition => ({
        id: `__pending__${p.name}`, target_type: state.recordType, name: p.name,
        label: { de: p.label_de, en: p.label_en },
        field_type: p.field_type as FieldDefinition['field_type'],
        is_required: false, is_repeatable: p.is_repeatable, sort_order: 9999,
        settings: {}, target_subtype: null,
        show_in_detail: false, show_in_list: false, is_facet: false, is_searchable: false,
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
        if (s.state === 'SUCCESS' || s.state === 'FAILURE') clearInterval(pollRef.current!)
      } catch {
        clearInterval(pollRef.current!)
      }
    }, 1500)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [state.taskId])

  // Derived
  const mappedCount = Object.values(state.mapping).filter(m => m.target && m.target !== '__idno__').length
  const uploaded = state.uploaded
  const ignoredCount = uploaded
    ? uploaded.headers.length - mappedCount - (state.idnoStrategy === 'column' && state.idnoColumn ? 1 : 0)
    : 0
  const mappedTargets = new Set(Object.values(state.mapping).map(m => m.target).filter(Boolean))
  const missingRequired = fields.filter(f => f.is_required && !mappedTargets.has(f.name))
  const idnoMissing = state.idnoStrategy === 'column' && !state.idnoColumn

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleFile(file: File) {
    dispatch({ type: 'UPLOAD_STARTED' })
    try {
      const raw = await importer.upload(file)
      const result = raw as UploadResult & { upload_id?: string; element_levels?: XmlElementLevel[] }

      if (result.source_type === 'xml' && result.upload_id) {
        dispatch({
          type: 'XML_UPLOAD_DONE',
          payload: { uploadId: result.upload_id, elementLevels: result.element_levels ?? [] },
        })
        return
      }

      // CSV/Excel: auto-map obvious column names
      const autoMap: Record<string, MappingEntry> = {}
      for (const col of (result.headers ?? [])) {
        const norm = col.toLowerCase().replace(/[\s\-]/g, '_')
        const match = fields.find(f => f.name === norm || f.label.de?.toLowerCase() === col.toLowerCase())
        if (match) autoMap[col] = { target: match.name }
      }
      dispatch({ type: 'UPLOADED', payload: result })
      dispatch({ type: 'MAPPING_CHANGED', payload: autoMap })
    } catch (e) {
      dispatch({ type: 'UPLOAD_ERROR', payload: (e as Error).message })
    }
  }

  async function handleXmlRecordXpath(clarkTag: string) {
    if (!state.xmlUploadId) return
    dispatch({ type: 'XML_SELECTORS_LOADING' })
    try {
      const result = await importer.xmlSelectors(state.xmlUploadId, clarkTag)
      dispatch({
        type: 'XML_RECORD_XPATH_SET',
        payload: {
          uploaded: {
            source_type: 'xml',
            upload_id: result.upload_id,
            headers: result.headers,
            row_count: result.row_count,
            preview: result.preview,
            suggestions: result.suggestions,
          },
          selectors: result.selectors,
        },
      })
    } catch (e) {
      alert((e as Error).message)
      dispatch({ type: 'XML_SELECTORS_LOADING' }) // clear loading state via reducer fallthrough
    }
  }

  async function handleDryRun() {
    if (!state.uploaded) return
    dispatch({ type: 'DRY_RUN_STARTED' })
    try {
      const result = await importer.dryRun(state.recordType, state.uploaded.upload_id, state.mapping, state.subtype)
      dispatch({ type: 'DRY_RUN_OK', payload: result })
    } catch (e) {
      dispatch({ type: 'OPTIONS_CHANGED', payload: {} })
      alert((e as Error).message)
    }
  }

  async function handleImport() {
    if (!state.uploaded) return
    try {
      const { task_id } = await importer.import(state.recordType, state.uploaded.upload_id, state.mapping, {
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

  async function handleProfileLoaded(profile: ImportProfile) {
    const fieldDefs = await schema.list(state.recordType, state.subtype ?? undefined).catch(() => [] as FieldDefinition[])
    const existingFieldNames = new Set(fieldDefs.filter(f => !f.id.startsWith('__pending__')).map(f => f.name))
    const availableSelectors = state.sourceType === 'xml' && state.xmlSelectors
      ? state.xmlSelectors.map(s => s.path)
      : (state.uploaded?.headers ?? [])
    const result = applyProfile(profile, availableSelectors, existingFieldNames)
    setProfileWarnings(result)
    dispatch({
      type: 'PROFILE_APPLIED',
      payload: {
        mapping: result.appliedMapping,
        pendingFields: result.newPendingFields,
        upsertStrategy: profile.upsertStrategy,
        autoPublish: profile.autoPublish,
        idnoStrategy: profile.idnoStrategy,
      },
    })
  }

  async function handleProfileExport() {
    const fieldDefs = await schema.list(state.recordType, state.subtype ?? undefined).catch(() => [] as FieldDefinition[])
    const profile = buildProfile(
      state.mapping,
      { record_type: state.recordType, idnoStrategy: state.idnoStrategy, upsertStrategy: state.upsertStrategy, autoPublish: state.autoPublish },
      fieldDefs,
    )
    downloadProfile(profile)
  }

  return {
    state, needsReupload: state.needsReupload, dispatch, fields, availableSubtypes,
    mappedCount, ignoredCount, missingRequired, idnoMissing,
    profileWarnings,
    handleFile, handleXmlRecordXpath, handleDryRun, handleImport,
    handleProfileLoaded, handleProfileExport,
  }
}
