import React, { useEffect, useReducer, useRef } from 'react'
import { importer, schema, subtypes as subtypesApi } from '../../../api/client'
import type { MappingEntry, UploadResult, XmlElementLevel } from '../../../api/client'
import type { FieldDefinition, RecordSubtype } from '../../../types'
import {
  IMPORTER_STATE_KEY,
  type ImporterAction,
  type ImporterState,
  type ImportProfile,
  type PersistedImporterState,
  type ProfileApplyResult,
} from './types'
import { applyProfile, buildProfile, downloadProfile } from './profileUtils'
// ── Auto-Mapping-Heuristik (Issue #199) ──────────────────────────────────────

// Statische Synonym-Tabelle: kanonischer Feldname → gängige CSV-/DC-Aliasnamen.
const FIELD_SYNONYMS: Record<string, string[]> = {
  title: ['titel', 'dc:title', 'name', 'bezeichnung', 'objektbezeichnung'],
  description: ['beschreibung', 'dc:description', 'notes', 'anmerkung', 'notizen'],
  creator: ['autor', 'author', 'dc:creator', 'urheber', 'hersteller', 'künstler'],
  date: ['datum', 'dc:date', 'jahr', 'year', 'entstehungsjahr', 'datierung'],
  type: ['typ', 'dc:type', 'art', 'gattung', 'objekttyp'],
  identifier: ['id', 'idno', 'dc:identifier', 'signatur', 'inventarnummer', 'inventar-nr'],
  rights: ['lizenz', 'license', 'dc:rights', 'rechte', 'rechteinhaber'],
  medium: ['material', 'technik', 'werkstoff', 'medium'],
  location: ['ort', 'place', 'dc:coverage', 'standort'],
  subject: ['schlagwort', 'dc:subject', 'keyword', 'thema'],
  language: ['sprache', 'dc:language'],
  publisher: ['verlag', 'dc:publisher', 'herausgeber'],
}

function levenshteinDistance(a: string, b: string): number {
  if (a === b) return 0
  const m = a.length
  const n = b.length
  if (m === 0) return n
  if (n === 0) return m
  let prev = Array.from({ length: n + 1 }, (_, i) => i)
  let curr = new Array<number>(n + 1).fill(0)
  for (let i = 1; i <= m; i++) {
    curr[0] = i
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
    }
    ;[prev, curr] = [curr, prev]
  }
  return prev[n]
}

function normalizedSimilarity(a: string, b: string): number {
  const maxLen = Math.max(a.length, b.length)
  if (maxLen === 0) return 1
  return 1 - levenshteinDistance(a, b) / maxLen
}

function suggestTargetForColumn(col: string, fields: FieldDefinition[]): string | null {
  const lowerCol = col.trim().toLowerCase()
  const normalized = lowerCol.replace(/[\s-]+/g, '_')

  // 1. Exakter Treffer: interner Name oder DE-Label
  for (const f of fields) {
    if (f.name === normalized) return f.name
    const labelDe = (f.label.de ?? '').toLowerCase()
    if (labelDe && labelDe === lowerCol) return f.name
  }

  // 2. Synonym-Tabelle
  for (const f of fields) {
    const aliases = FIELD_SYNONYMS[f.name] ?? []
    if (aliases.includes(lowerCol) || aliases.includes(normalized)) return f.name
  }

  // 3. Fuzzy (Levenshtein) gegen internen Namen und DE-Label
  let best: { name: string; score: number } | null = null
  for (const f of fields) {
    const labelDe = f.label.de
    const candidates = labelDe ? [f.name, labelDe.toLowerCase()] : [f.name]
    for (const raw of candidates) {
      const cand = raw.replace(/[\s-]+/g, '_')
      const score = normalizedSimilarity(normalized, cand)
      if (score > (best?.score ?? -1)) best = { name: f.name, score }
    }
  }
  return best && best.score >= 0.8 ? best.name : null
}


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
    mediaSelector:  persisted?.recordType === 'object' ? (persisted.mediaSelector ?? null) : null,
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
      return {
        ...state,
        uploading: false,
        uploaded: action.payload,
        sourceType: action.payload.source_type ?? 'csv',
        mapping: {},
        mediaSelector: state.mediaSelector && action.payload.headers.includes(state.mediaSelector)
          ? state.mediaSelector
          : null,
        step: 1,
        uploadErr: null,
        needsReupload: false,
      }

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
        mediaSelector: state.mediaSelector && action.payload.uploaded.headers.includes(state.mediaSelector)
          ? state.mediaSelector
          : null,
        step: 2, // Mapping step for XML
      }

    case 'MAPPING_CHANGED':
      return { ...state, mapping: action.payload }

    case 'MEDIA_SELECTOR_CHANGED':
      return { ...state, mediaSelector: state.recordType === 'object' ? action.payload : null }

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
      const { mapping, mediaSelector, pendingFields, upsertStrategy, autoPublish, idnoStrategy } = action.payload
      return { ...state, mapping, mediaSelector: state.recordType === 'object' ? mediaSelector : null, pendingFields, upsertStrategy, autoPublish, idnoStrategy, step: state.sourceType === 'xml' ? 2 : 1 }
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
  handleFile: (files: File | File[]) => Promise<void>
  handleXmlRecordXpath: (clarkTag: string) => Promise<void>
  handleDryRun: () => Promise<void>
  applyVocabCluster: (field: string, canonical: string, variants: string[]) => Promise<void>
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

  useEffect(() => {
    setProfileWarnings(null)
  }, [state.recordType, state.uploaded?.upload_id])

  // Persist to localStorage — rows are NOT saved (too large); on restore, user must re-upload
  useEffect(() => {
    const toSave: PersistedImporterState = {
      step: state.step, recordType: state.recordType, subtype: state.subtype,
      mapping: state.mapping, idnoStrategy: state.idnoStrategy, idnoColumn: state.idnoColumn,
      mediaSelector: state.recordType === 'object' ? state.mediaSelector : null,
      upsertStrategy: state.upsertStrategy, autoPublish: state.autoPublish,
      uploaded: state.uploaded ? { ...state.uploaded, upload_id: '' } : null,
      dryResult: state.dryResult, taskId: state.taskId,
      pendingFields: state.pendingFields,
    }
    localStorage.setItem(IMPORTER_STATE_KEY, JSON.stringify(toSave))
  }, [
    state.step, state.recordType, state.subtype, state.mapping, state.mediaSelector, state.idnoStrategy,
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
        is_required: false, is_repeatable: p.is_repeatable, is_translatable: false, sort_order: 9999,
        settings: {}, target_subtype: null,
        show_in_detail: false, show_in_list: false, is_facet: false, is_searchable: false,
      }))
      setFields(fs.concat(virtuals))
    }).catch(() => setFields([]))
    subtypesApi.list(state.recordType).then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
  }, [state.recordType, state.subtype])

  // Re-merge pending fields when they change
  useEffect(() => {
    setFields(prev => {
      const base = prev.filter(f => !f.id.startsWith('__pending__'))
      return base.concat(state.pendingFields.map((p): FieldDefinition => ({
        id: `__pending__${p.name}`, target_type: state.recordType, name: p.name,
        label: { de: p.label_de, en: p.label_en },
        field_type: p.field_type as FieldDefinition['field_type'],
        is_required: false, is_repeatable: p.is_repeatable, is_translatable: false, sort_order: 9999,
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
  const mediaSelectorCountedSeparately = !!(
    uploaded
    && state.mediaSelector
    && uploaded.headers.includes(state.mediaSelector)
    && !state.mapping[state.mediaSelector]?.target
  )
  const ignoredCount = uploaded
    ? uploaded.headers.length
      - mappedCount
      - (state.idnoStrategy === 'column' && state.idnoColumn ? 1 : 0)
      - (mediaSelectorCountedSeparately ? 1 : 0)
    : 0
  const mappedTargets = new Set(Object.values(state.mapping).map(m => m.target).filter(Boolean))
  const missingRequired = fields.filter(f => f.is_required && !mappedTargets.has(f.name))
  const idnoMissing = state.idnoStrategy === 'column' && !state.idnoColumn

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleFile(files: File | File[]) {
    setProfileWarnings(null)
    dispatch({ type: 'UPLOAD_STARTED' })
    try {
      const raw = await importer.upload(files)
      const result = raw as UploadResult & { upload_id?: string; element_levels?: XmlElementLevel[] }

      if (result.source_type === 'xml' && result.upload_id) {
        dispatch({
          type: 'XML_UPLOAD_DONE',
          payload: { uploadId: result.upload_id, elementLevels: result.element_levels ?? [] },
        })
        return
      }

      // CSV/Excel: Auto-Mapping (exakt → Synonym → Levenshtein, #199)
      const autoMap: Record<string, MappingEntry> = {}
      for (const col of (result.headers ?? [])) {
        const target = suggestTargetForColumn(col, fields)
        if (target) autoMap[col] = { target }
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

  const pendingFieldsPayload = () => state.pendingFields.map(f => ({
    name: f.name, field_type: f.field_type,
    label_de: f.label_de, label_en: f.label_en, is_repeatable: f.is_repeatable,
  }))

  async function handleDryRun() {
    if (!state.uploaded) return
    dispatch({ type: 'DRY_RUN_STARTED' })
    try {
      const result = await importer.dryRun(state.recordType, state.uploaded.upload_id, state.mapping, state.subtype, pendingFieldsPayload(), state.mediaSelector)
      dispatch({ type: 'DRY_RUN_OK', payload: result })
    } catch (e) {
      dispatch({ type: 'OPTIONS_CHANGED', payload: {} })
      alert((e as Error).message)
    }
  }

  async function applyVocabCluster(field: string, canonical: string, variants: string[]) {
    if (!state.uploaded) return
    const nextMapping = { ...state.mapping }
    for (const [selector, entry] of Object.entries(nextMapping)) {
      if (entry.target !== field) continue
      const transforms = entry.transforms ? [...entry.transforms] : []
      const idx = transforms.findIndex(t => t.type === 'vocab_map')
      const vocabMap = idx >= 0 ? { ...(transforms[idx].vocab_map ?? {}) } : {}
      for (const v of variants) {
        if (v !== canonical) vocabMap[v] = canonical
      }
      if (idx >= 0) transforms[idx] = { ...transforms[idx], vocab_map: vocabMap }
      else transforms.push({ type: 'vocab_map', vocab_map: vocabMap, strict: false })
      nextMapping[selector] = { ...entry, transforms }
    }
    dispatch({ type: 'MAPPING_CHANGED', payload: nextMapping })
    dispatch({ type: 'DRY_RUN_STARTED' })
    try {
      const result = await importer.dryRun(state.recordType, state.uploaded.upload_id, nextMapping, state.subtype, pendingFieldsPayload(), state.mediaSelector)
      dispatch({ type: 'DRY_RUN_OK', payload: result })
    } catch (e) {
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
        fields_to_create: pendingFieldsPayload(),
        media_selector: state.mediaSelector,
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
        mediaSelector: result.mediaSelector,
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
      { record_type: state.recordType, mediaSelector: state.mediaSelector, idnoStrategy: state.idnoStrategy, upsertStrategy: state.upsertStrategy, autoPublish: state.autoPublish },
      fieldDefs,
    )
    downloadProfile(profile)
  }

  return {
    state, needsReupload: state.needsReupload, dispatch, fields, availableSubtypes,
    mappedCount, ignoredCount, missingRequired, idnoMissing,
    profileWarnings,
    handleFile, handleXmlRecordXpath, handleDryRun, applyVocabCluster, handleImport,
    handleProfileLoaded, handleProfileExport,
  }
}
