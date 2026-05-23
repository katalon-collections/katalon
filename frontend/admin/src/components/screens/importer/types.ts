import type { UploadResult, DryRunResult, TaskStatus, MappingEntry, XmlElementLevel, XmlSelector } from '../../../api/client'

export interface ImportProfile {
  version: 1
  record_type: string
  idnoStrategy: string
  upsertStrategy: string
  autoPublish: boolean
  mapping: Record<string, MappingEntry>
  field_definitions: Record<string, {
    name: string
    field_type: string
    label: Record<string, string>
    is_required: boolean
    is_repeatable: boolean
    settings: Record<string, unknown>
  }>
}

export interface ProfileApplyResult {
  appliedMapping: Record<string, MappingEntry>
  newPendingFields: PendingField[]
  missedSelectors: string[]
  missingFieldNames: string[]
}

export interface PendingField {
  csvColumn: string
  name: string
  field_type: string
  label_de: string
  label_en: string
  is_repeatable: boolean
}

// ── Wizard state (managed by reducer) ─────────────────────────────────────────

export interface ImporterState {
  step: number
  recordType: string
  subtype: string | null
  // Upload
  uploading: boolean
  uploadErr: string | null
  uploaded: UploadResult | null
  // XML-specific upload state (step 0.5 between Upload and Mapping)
  sourceType: 'csv' | 'excel' | 'xml' | null
  xmlUploadId: string | null
  xmlElementLevels: XmlElementLevel[] | null
  xmlSelectorsLoading: boolean
  xmlSelectors: XmlSelector[] | null
  // Mapping
  mapping: Record<string, MappingEntry>
  idnoStrategy: string
  idnoColumn: string | null
  // Options
  upsertStrategy: string
  autoPublish: boolean
  pendingFields: PendingField[]
  // Dry run
  dryResult: DryRunResult | null
  dryRunning: boolean
  // Import
  taskId: string | null
  taskStatus: TaskStatus | null
}

export type ImporterAction =
  | { type: 'SET_RECORD_TYPE'; payload: string }
  | { type: 'SET_SUBTYPE'; payload: string | null }
  | { type: 'UPLOAD_STARTED' }
  | { type: 'UPLOADED'; payload: UploadResult }
  | { type: 'UPLOAD_ERROR'; payload: string }
  // XML two-step upload
  | { type: 'XML_UPLOAD_DONE'; payload: { uploadId: string; elementLevels: XmlElementLevel[] } }
  | { type: 'XML_SELECTORS_LOADING' }
  | { type: 'XML_RECORD_XPATH_SET'; payload: { uploaded: UploadResult; selectors: XmlSelector[] } }
  | { type: 'MAPPING_CHANGED'; payload: Record<string, MappingEntry> }
  | { type: 'IDNO_STRATEGY_CHANGED'; payload: { strategy: string; column: string | null } }
  | { type: 'OPTIONS_CHANGED'; payload: Partial<Pick<ImporterState, 'upsertStrategy' | 'autoPublish'>> }
  | { type: 'PENDING_FIELDS_CHANGED'; payload: PendingField[] }
  | { type: 'DRY_RUN_STARTED' }
  | { type: 'DRY_RUN_OK'; payload: DryRunResult }
  | { type: 'IMPORT_STARTED'; payload: string }
  | { type: 'TASK_STATUS_UPDATED'; payload: TaskStatus }
  | { type: 'STEP_SET'; payload: number }
  | { type: 'PROFILE_APPLIED'; payload: {
      mapping: Record<string, MappingEntry>
      pendingFields: PendingField[]
      upsertStrategy: string
      autoPublish: boolean
      idnoStrategy: string
    }}
  | { type: 'RESET' }

// ── localStorage ───────────────────────────────────────────────────────────────

export type PersistedImporterState = Pick<
  ImporterState,
  'step' | 'recordType' | 'subtype' | 'mapping' | 'idnoStrategy' | 'idnoColumn'
  | 'upsertStrategy' | 'autoPublish' | 'uploaded' | 'dryResult' | 'taskId' | 'pendingFields'
>

// ── Constants ──────────────────────────────────────────────────────────────────

export const RECORD_TYPES = [
  { id: 'object',     label: 'Objekte' },
  { id: 'entity',     label: 'Entitäten' },
  { id: 'place',      label: 'Orte' },
  { id: 'occurrence', label: 'Occurrences' },
] as const

export const UPSERT_STRATEGIES = [
  { id: 'skip',    label: 'Bestehende überspringen (nur neue anlegen)' },
  { id: 'merge',   label: 'Zusammenführen (neue Felder hinzufügen)' },
  { id: 'replace', label: 'Ersetzen (komplett überschreiben)' },
] as const

export const FIELD_TYPE_OPTIONS = [
  { id: 'text',     label: 'Text' },
  { id: 'number',   label: 'Zahl' },
  { id: 'date',     label: 'Datum' },
  { id: 'boolean',  label: 'Boolean' },
  { id: 'vocab',    label: 'Vokabular' },
  { id: 'relation', label: 'Relation' },
] as const

// Steps 0=Upload, 1=Mapping (CSV/Excel) or XmlRecordSelector (XML), 2=Mapping (XML only), 3=DryRun, 4=Import
// For CSV/Excel the wizard has 4 steps; XML adds one extra step between Upload and Mapping
export const STEPS = ['Upload', 'Mapping', 'Probelauf', 'Import'] as const
export const STEPS_XML = ['Upload', 'Element', 'Mapping', 'Probelauf', 'Import'] as const

export const IMPORTER_STATE_KEY = 'katalon_importer_state'
