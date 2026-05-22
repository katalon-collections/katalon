import type { UploadResult, DryRunResult, TaskStatus, MappingEntry } from '../../../api/client'

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
  | { type: 'MAPPING_CHANGED'; payload: Record<string, MappingEntry> }
  | { type: 'IDNO_STRATEGY_CHANGED'; payload: { strategy: string; column: string | null } }
  | { type: 'OPTIONS_CHANGED'; payload: Partial<Pick<ImporterState, 'upsertStrategy' | 'autoPublish'>> }
  | { type: 'PENDING_FIELDS_CHANGED'; payload: PendingField[] }
  | { type: 'DRY_RUN_STARTED' }
  | { type: 'DRY_RUN_OK'; payload: DryRunResult }
  | { type: 'IMPORT_STARTED'; payload: string }
  | { type: 'TASK_STATUS_UPDATED'; payload: TaskStatus }
  | { type: 'STEP_SET'; payload: number }
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

export const STEPS = ['Upload', 'Mapping', 'Probelauf', 'Import'] as const

export const IMPORTER_STATE_KEY = 'katalon_importer_state'
