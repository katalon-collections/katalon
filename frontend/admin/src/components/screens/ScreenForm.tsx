import { useState, useEffect, useRef, useCallback, useId, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { objects, entities, places, occurrences, procedures, schema, media, vocabularies, relations as relationsApi, search as searchApi, pids, subtypes, idno as idnoApi, formVariants, BASE, PORTAL_URL, ai, getTokenUser, VersionConflictError, authorizedFetch } from '../../api/client'
import type { MediaFile } from '../../api/client'
import { AuthorityInput, type AuthorityEntry } from '../AuthorityInput'
import type { AnyRecord, AuditEntry, FieldDefinition, FormVariant, ProcedureStatus, RecordSubtype, RecordType, Relation, SearchResult, Snapshot, Status, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { FULL_SCHEMA_CHOICE, localVariantKey, resolveActiveVariant } from '../../lib/formVariants'
import { AlertCircle, Calendar, ChevD, Plus, Upload, X, Trash, Image, Lightning, File, Music, Video, FileText, Box } from '../ui/Icons'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'
import { TranslatableInput } from '../ui/TranslatableInput'
import { MediaLightbox } from '../MediaLightbox'

function normalizeDateInput(value: string): string {
  const trimmed = value.trim()
  const european = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(trimmed)
  if (!european) return trimmed
  const [, day, month, year] = european
  const iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  const parsed = new Date(`${iso}T00:00:00Z`)
  return parsed.getUTCFullYear() === Number(year) &&
    parsed.getUTCMonth() + 1 === Number(month) &&
    parsed.getUTCDate() === Number(day)
    ? iso
    : trimmed
}

function isValidDateInput(value: string): boolean {
  const normalized = normalizeDateInput(value)
  if (/^\d{4}$/.test(normalized)) return true
  if (/^\d{4}-(0[1-9]|1[0-2])$/.test(normalized)) return true
  if (!/^\d{4}-\d{2}-\d{2}$/.test(normalized)) return false
  const parsed = new Date(`${normalized}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === normalized
}

function DateInput({ value, onChange, onBlur, disabled, style }: {
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  disabled?: boolean
  style?: CSSProperties
}) {
  const pickerRef = useRef<HTMLInputElement>(null)
  const normalized = normalizeDateInput(value)
  const pickerValue = /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized : ''
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <input className="fld" type="text" value={value}
        onChange={e => onChange(e.target.value)}
        onBlur={() => { onChange(normalizeDateInput(value)); onBlur?.() }}
        placeholder="TT.MM.JJJJ oder JJJJ-MM-TT" disabled={disabled} style={{ flex: 1, ...style }} />
      <button type="button" className="btn sm ico gh" title="Datum aus Kalender auswählen"
        disabled={disabled} onClick={() => pickerRef.current?.showPicker()}>
        <Calendar size={14} />
      </button>
      <input ref={pickerRef} type="date" value={pickerValue} disabled={disabled}
        onChange={e => onChange(e.target.value)} aria-label="Datum aus Kalender auswählen"
        style={{ position: 'absolute', opacity: 0, width: 1, height: 1, pointerEvents: 'none' }} />
    </div>
  )
}

const TITLE_FIELD_NAMES = ['label', 'title', 'titel', 'name', 'display_name', 'place_name', 'bezeichnung']

function extractTitle(m: Record<string, unknown>, fallback: string): string {
  for (const key of TITLE_FIELD_NAMES) {
    const val = m[key]
    if (!val) continue
    if (typeof val === 'string') return val
    if (Array.isArray(val) && val.length > 0) {
      const first = val[0]
      if (typeof first === 'string') return first
      if (first && typeof first === 'object') return String((first as Record<string, unknown>).value ?? (first as Record<string, unknown>).label ?? '') || fallback
    }
  }
  return fallback
}

function defaultsFor(fields: FieldDefinition[]): Record<string, unknown> {
  return Object.fromEntries(
    fields
      .filter(f => f.settings?.default_value !== undefined)
      .map(f => [f.name, f.settings.default_value]),
  )
}

function getFieldAiConfig(field: FieldDefinition): { enabled: boolean; mode: 'text' | 'vision'; prompt: string } | null {
  const aiConfig = field.settings?.ai_config as Record<string, unknown> | undefined
  if (!aiConfig?.enabled) return null
  return {
    enabled: true,
    mode: (aiConfig.mode as 'text' | 'vision' | undefined) ?? 'text',
    prompt: String(aiConfig.prompt ?? ''),
  }
}

type AiProposal = {
  field: FieldDefinition
  currentValue: unknown
  suggestedValue: unknown
  group?: { name: string; index: number }
}

function aiValueToText(value: unknown): string {
  return Array.isArray(value) ? value.map(item => String(item)).join('\n') : String(value ?? '')
}

function aiTextToValue(field: FieldDefinition, value: string): unknown {
  const coerce = (item: string): string | number | boolean => {
    if (field.field_type === 'number') {
      const parsed = Number(item)
      return Number.isNaN(parsed) ? item : parsed
    }
    if (field.field_type === 'boolean') return item.trim().toLowerCase() === 'true'
    return item
  }
  return field.is_repeatable ? value.split('\n').map(item => item.trim()).filter(Boolean).map(coerce) : coerce(value)
}

function AiProposalDialog({ proposal, onCancel, onApply }: {
  proposal: AiProposal
  onCancel: () => void
  onApply: (value: unknown) => void
}) {
  const [suggestion, setSuggestion] = useState(() => aiValueToText(proposal.suggestedValue))
  const label = getLabel(proposal.field, proposal.field.name)
  return (
    <dialog open onCancel={event => { event.preventDefault(); onCancel() }} aria-labelledby="ai-proposal-title"
      style={{ position: 'fixed', inset: 0, margin: 'auto', width: 680, maxWidth: 'calc(100vw - 32px)', maxHeight: 'calc(100vh - 64px)', overflow: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 0, background: 'var(--bg)', color: 'var(--fg)', boxShadow: '0 24px 80px rgba(0,0,0,.24)', zIndex: 25 }}>
      <div id="ai-proposal-title" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-s)', fontWeight: 700 }}>KI-Vorschlag für {label}</div>
      <div style={{ padding: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
        <label className="field" style={{ margin: 0 }}>
          <span className="lbl">Aktueller Wert</span>
          <textarea className="fld" value={aiValueToText(proposal.currentValue)} readOnly rows={8} />
        </label>
        <label className="field" style={{ margin: 0 }}>
          <span className="lbl">KI-Vorschlag</span>
          <textarea className="fld" value={suggestion} onChange={event => setSuggestion(event.target.value)} rows={8} autoFocus />
        </label>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 16px', borderTop: '1px solid var(--border-s)' }}>
        <button className="btn gh" onClick={onCancel}>Verwerfen</button>
        <button className="btn pri" onClick={() => onApply(aiTextToValue(proposal.field, suggestion))}>Übernehmen</button>
      </div>
    </dialog>
  )
}

const STATUSES: Status[] = ['draft', 'internal', 'public']
const STATUS_LABELS: Record<Status, string> = { draft: 'Entwurf', internal: 'Intern', public: 'Öffentlich' }
const MEDIA_LICENSES = [
  ['https://creativecommons.org/publicdomain/zero/1.0/', 'CC0 1.0'],
  ['https://creativecommons.org/publicdomain/mark/1.0/', 'Public Domain Mark 1.0'],
  ['https://creativecommons.org/licenses/by/4.0/', 'CC BY 4.0'],
  ['https://creativecommons.org/licenses/by-sa/4.0/', 'CC BY-SA 4.0'],
  ['https://rightsstatements.org/vocab/InC/1.0/', 'In Copyright'],
] as const
const PROCEDURE_STATUSES: ProcedureStatus[] = ['draft', 'active', 'completed', 'cancelled']
const PROCEDURE_STATUS_LABELS: Record<ProcedureStatus, string> = { draft: 'Entwurf', active: 'Aktiv', completed: 'Abgeschlossen', cancelled: 'Abgebrochen' }
const PROCEDURE_COMPLETION_STATUS: Record<string, string | null> = {
  loan_out: 'active',
  loan_in: 'returned',
  acquisition: 'active',
  object_entry: 'active',
  deaccession: 'deaccessioned',
  conservation: null,
}
const COLLECTION_STATUSES = [
  { id: 'active', label: 'Aktiv' },
  { id: 'pending', label: 'In Bearbeitung' },
  { id: 'on_loan_out', label: 'Ausgeliehen' },
  { id: 'on_loan_in', label: 'Leihgabe' },
  { id: 'deaccessioned', label: 'Deakzessioniert' },
  { id: 'returned', label: 'Zurückgegeben' },
]

const PORTAL_PATH: Record<RecordType, string> = {
  object: 'objects', entity: 'entities', place: 'places', occurrence: 'occurrences', procedure: 'procedures',
}

const TYPE_LABELS: Record<RecordType, string> = {
  object:     'Objekt',
  entity:     'Entität',
  place:      'Ort',
  occurrence: 'Occurrence',
  procedure:  'Vorgang',
}

const NEW_TYPE_LABELS: Record<RecordType, string> = {
  object:     'Neues Objekt',
  entity:     'Neue Entität',
  place:      'Neuer Ort',
  occurrence: 'Neue Occurrence',
  procedure:  'Neuer Vorgang',
}

const TYPE_ROUTES: Record<string, string> = {
  object: 'form', entity: 'entities-form', place: 'places-form', occurrence: 'occurrences-form', procedure: 'procedures-form',
}

function navigateToRecord(type: string, id: string) {
  const route = TYPE_ROUTES[type]
  if (!route) return
  window.history.pushState({ route, editId: id }, '', `#${route}/${id}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function procedureSearchResult(proc: AnyRecord): SearchResult {
  const idno = (proc as { idno?: string | null }).idno
  return {
    id: proc.id,
    record_type: 'procedure',
    title: extractTitle(proc.metadata_ as Record<string, unknown>, idno ?? proc.id.slice(0, 8) + '…'),
    status: proc.status,
    score: null,
  }
}

function recordSearchResult(recordType: RecordType, record: AnyRecord): SearchResult {
  const idno = (record as { idno?: string | null }).idno
  return {
    id: record.id,
    record_type: recordType,
    title: extractTitle(record.metadata_ as Record<string, unknown>, idno ?? record.id.slice(0, 8) + '…'),
    status: record.status,
    score: null,
  }
}

async function searchRecords(targetType: RecordType, q: string, targetSubtype?: string): Promise<SearchResult[]> {
  if (!targetSubtype) {
    return (await searchApi.query(q, targetType, 8)).items
  }
  switch (targetType) {
    case 'object':
      return (await objects.list({ q, object_type: targetSubtype, page_size: 8 })).items.map(r => recordSearchResult(targetType, r))
    case 'entity':
      return (await entities.list({ q, entity_type: targetSubtype, page_size: 8 })).items.map(r => recordSearchResult(targetType, r))
    case 'place':
      return (await places.list({ q, place_type: targetSubtype, page_size: 8 })).items.map(r => recordSearchResult(targetType, r))
    case 'occurrence':
      return (await occurrences.list({ q, occurrence_type: targetSubtype, page_size: 8 })).items.map(r => recordSearchResult(targetType, r))
    case 'procedure':
      return (await procedures.list({ q, procedure_type: targetSubtype, page_size: 8 })).items.map(procedureSearchResult)
  }
}

const SUBTYPE_KEY: Partial<Record<RecordType, string>> = {
  object:     'object_type',
  entity:     'entity_type',
  place:      'place_type',
  occurrence: 'occurrence_type',
  procedure:  'procedure_type',
}

export type VocabEntry = { id: string; label: string }
export type RelationEntry = { id: string; label: string; relation_type: string }

function buildRightsHolder(name: string, uri: string): { name: string; uri?: string } | null {
  return name ? { name, ...(uri ? { uri } : {}) } : null
}

function mediaRightsFromInputs(root: ParentNode | null) {
  const value = (field: string) =>
    (root?.querySelector<HTMLInputElement>(`input[data-media-rights="${field}"]`)?.value ?? '').trim()
  const licenseUri = value('license_uri')
  const rightsName = value('rights_holder_name')
  const rightsUri = value('rights_holder_uri')
  return {
    license_uri: licenseUri || null,
    rights_holder: buildRightsHolder(rightsName, rightsUri),
  }
}

function VocabInput({ vocabId, value, onChange, disabled }: {
  vocabId: string
  value: VocabEntry | null
  onChange: (v: VocabEntry | null) => void
  disabled?: boolean
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<VocabularyTerm[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const t = e.target as Node
      if (inputRef.current?.contains(t) || dropRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    if (open && inputRef.current) {
      const r = inputRef.current.getBoundingClientRect()
      const spaceBelow = window.innerHeight - r.bottom - 8
      const spaceAbove = r.top - 8
      const showBelow = spaceBelow >= 120 || spaceBelow >= spaceAbove
      setDropPos({
        top: showBelow ? r.bottom + 2 : r.top - Math.min(280, spaceAbove) - 2,
        left: r.left,
        width: r.width,
        maxHeight: showBelow ? Math.min(280, spaceBelow) : Math.min(280, spaceAbove),
      })
    }
  }, [open])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!vocabId) { setResults([]); setOpen(false); return }
    if (q.trim().length < 1) { setResults([]); return }
    timer.current = setTimeout(() => {
      setBusy(true)
      vocabularies.searchTerms(vocabId, q.trim())
        .then(r => { setResults(r); setOpen(r.length > 0) })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [q, vocabId])

  function openSuggestions() {
    if (!vocabId) return
    setBusy(true)
    vocabularies.searchTerms(vocabId, q.trim())
      .then(r => { setResults(r); setOpen(r.length > 0) })
      .catch(() => { setResults([]); setOpen(false) })
      .finally(() => setBusy(false))
  }

  function pick(term: VocabularyTerm) {
    onChange({ id: term.id, label: getLabel(term) })
    setQ(''); setResults([]); setOpen(false)
  }

  if (value) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 8px', borderRadius: 4,
          background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
        }}>
          {value.label}
        </span>
        {!disabled && (
          <button className="btn sm ico gh" onClick={() => onChange(null)} title="Entfernen">
            <X size={12} />
          </button>
        )}
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        className="fld"
        value={q}
        onChange={e => setQ(e.target.value)}
        onFocus={openSuggestions}
        placeholder={vocabId ? 'Tippen zum Suchen…' : 'Kein Vokabular zugewiesen'}
        disabled={disabled || !vocabId}
      />
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {open && results.length > 0 && dropPos && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          {results.map(term => (
            <button
              key={term.id}
              onMouseDown={e => { e.preventDefault(); pick(term) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{getLabel(term)}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{term.term}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Text input with optional vocabulary suggestions.
 * - Non-repeatable: use `value` + `onChange` (live update on each keystroke).
 * - Repeatable: use `onAdd` (fires with committed text, then clears the input).
 */
function VocabFreeInput({ vocabId, value, onChange, onAdd, disabled, placeholder }: {
  vocabId: string
  value?: string
  onChange?: (v: string) => void
  onAdd?: (v: string) => void
  disabled?: boolean
  placeholder?: string
}) {
  const [draft, setDraft] = useState(value ?? '')
  const [results, setResults] = useState<VocabularyTerm[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  // Sync controlled value
  useEffect(() => { if (value !== undefined) setDraft(value) }, [value])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const t = e.target as Node
      if (inputRef.current?.contains(t) || dropRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    if (open && inputRef.current) {
      const r = inputRef.current.getBoundingClientRect()
      const spaceBelow = window.innerHeight - r.bottom - 8
      const spaceAbove = r.top - 8
      const showBelow = spaceBelow >= 120 || spaceBelow >= spaceAbove
      setDropPos({
        top: showBelow ? r.bottom + 2 : r.top - Math.min(280, spaceAbove) - 2,
        left: r.left, width: r.width,
        maxHeight: showBelow ? Math.min(280, spaceBelow) : Math.min(280, spaceAbove),
      })
    }
  }, [open])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!vocabId) { setResults([]); setOpen(false); return }
    if (draft.trim().length < 1) { setResults([]); return }
    timer.current = setTimeout(() => {
      setBusy(true)
      vocabularies.searchTerms(vocabId, draft.trim())
        .then(r => { setResults(r); setOpen(r.length > 0) })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [draft, vocabId])

  function openSuggestions() {
    if (!vocabId) return
    setBusy(true)
    vocabularies.searchTerms(vocabId, draft.trim())
      .then(r => { setResults(r); setOpen(r.length > 0) })
      .catch(() => { setResults([]); setOpen(false) })
      .finally(() => setBusy(false))
  }

  function commit(text: string) {
    if (!text.trim()) return
    if (onAdd) {
      onAdd(text.trim())
      setDraft('')
    } else {
      onChange?.(text)
    }
    setResults([]); setOpen(false)
  }

  function pick(term: VocabularyTerm) {
    commit(getLabel(term))
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        className="fld"
        value={draft}
        onChange={e => {
          setDraft(e.target.value)
          if (!onAdd) onChange?.(e.target.value)
        }}
        onFocus={openSuggestions}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); commit(draft) }
          if (e.key === 'Escape') { setOpen(false); setResults([]) }
        }}
        placeholder={placeholder ?? (vocabId ? 'Tippen zum Suchen oder frei eingeben…' : 'Freitext eingeben')}
        disabled={disabled}
      />
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {open && results.length > 0 && dropPos && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          {results.map(term => (
            <button
              key={term.id}
              onMouseDown={e => { e.preventDefault(); pick(term) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{getLabel(term)}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{term.term}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function QuickCreateDialog({
  targetType,
  targetSubtype,
  context,
  initialLabel,
  onCreated,
  onClose,
  onReturnFocus,
}: {
  targetType: RecordType
  targetSubtype?: string
  context?: string
  initialLabel?: string
  onCreated: (record: AnyRecord) => void
  onClose: () => void
  onReturnFocus?: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    dialogRef.current?.showModal()
  }, [])

  function close() {
    if (dirty && !window.confirm('Eingaben verwerfen und Schnellanlage schließen?')) return
    dialogRef.current?.close()
    onClose()
    requestAnimationFrame(() => onReturnFocus?.())
  }

  return createPortal(
    <dialog
      ref={dialogRef}
      className="quick-create-dialog"
      aria-labelledby={titleId}
      onCancel={e => { e.preventDefault(); close() }}
    >
      <div className="quick-create-head">
        <div>
          <h2 id={titleId}>{NEW_TYPE_LABELS[targetType]} anlegen</h2>
          {context && <div className="quick-create-context">{context}</div>}
        </div>
        <button className="btn ico gh quick-create-close" onClick={close} aria-label="Schnellanlage schließen"><X size={16} /></button>
      </div>
      <div className="quick-create-notice"><AlertCircle size={15} /> Wird als Entwurf gespeichert</div>
      <ScreenForm
        recordType={targetType}
        recordId="new"
        quickCreate
        initialSubtype={targetSubtype}
        lockSubtype={Boolean(targetSubtype)}
        initialLabel={initialLabel}
        onDirtyChange={setDirty}
        onBack={close}
        onCreated={record => {
          setDirty(false)
          dialogRef.current?.close()
          onCreated(record)
          onClose()
          requestAnimationFrame(() => onReturnFocus?.())
        }}
      />
    </dialog>
    , document.body,
  )
}

function RelationInput({
  targetType,
  targetSubtype,
  relTypeVocabId,
  fixedRelationType,
  fromType,
  onAdd,
  disabled,
  allowCreate = true,
}: {
  targetType: RecordType | ''
  targetSubtype?: string
  relTypeVocabId?: string
  fixedRelationType?: string
  fromType?: RecordType
  onAdd: (entry: RelationEntry) => void | Promise<void>
  disabled?: boolean
  allowCreate?: boolean
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [picked, setPicked] = useState<SearchResult | null>(null)
  const [relType, setRelType] = useState('')
  const [relTypeTerms, setRelTypeTerms] = useState<VocabularyTerm[]>([])
  const [showDrop, setShowDrop] = useState(false)
  const [quickCreateOpen, setQuickCreateOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [linkError, setLinkError] = useState<string | null>(null)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)
  const pickerRef = useRef<HTMLDivElement>(null)
  const createButtonRef = useRef<HTMLButtonElement>(null)
  const restoreFocusAfterConfirm = useRef(false)

  function focusPicker() {
    pickerRef.current?.querySelector<HTMLElement>('button.btn.pri:not(:disabled), input:not(:disabled), select:not(:disabled), button:not(:disabled)')?.focus()
  }

  useEffect(() => {
    if (!relTypeVocabId) { setRelTypeTerms([]); return }
    vocabularies.listTerms(relTypeVocabId, { from_type: fromType, to_type: targetType || undefined })
      .then(setRelTypeTerms).catch(() => {})
  }, [relTypeVocabId, fromType, targetType])

  // Stale relType vermeiden: bei Wechsel der Typkombination Auswahl zurücksetzen (#292)
  useEffect(() => { setRelType('') }, [relTypeVocabId, fromType, targetType])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (inputRef.current?.contains(e.target as Node) || dropRef.current?.contains(e.target as Node)) return
      setShowDrop(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const updateDropPosition = useCallback(() => {
    if (!inputRef.current) return
    const r = inputRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - r.bottom - 8
    const spaceAbove = r.top - 8
    const showBelow = spaceBelow >= 120 || spaceBelow >= spaceAbove
    setDropPos({
      top: showBelow ? r.bottom + 2 : r.top - Math.min(280, spaceAbove) - 2,
      left: r.left, width: r.width,
      maxHeight: showBelow ? Math.min(280, spaceBelow) : Math.min(280, spaceAbove),
    })
  }, [])

  useEffect(() => {
    if (!showDrop) return
    updateDropPosition()
    window.addEventListener('resize', updateDropPosition)
    return () => window.removeEventListener('resize', updateDropPosition)
  }, [showDrop, updateDropPosition])

  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults([]); setSearching(false); return }
    timer.current = setTimeout(() => {
      setSearching(true)
      searchRecords(targetType as RecordType, q.trim(), targetSubtype)
        .then(items => {
          setResults(items)
          setShowDrop(true)
        })
        .catch(() => setResults([]))
        .finally(() => setSearching(false))
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, targetType, targetSubtype])

  function openSuggestions() {
    if (!targetType) return
    if (q.trim().length < 2) { setSearching(false); return }
    setSearching(true)
    searchRecords(targetType as RecordType, q.trim(), targetSubtype)
      .then(items => {
        setResults(items)
        setShowDrop(true)
      })
      .catch(() => {
        setResults([])
        setShowDrop(false)
      })
      .finally(() => setSearching(false))
  }

  function pickRecord(r: SearchResult) {
    setPicked(r)
    setQ('')
    setResults([])
    setShowDrop(false)
    setLinkError(null)
  }

  async function confirm(record = picked) {
    const relationType = fixedRelationType ?? relType.trim()
    if (!record || !relationType) return
    setConfirming(true)
    setLinkError(null)
    try {
      await onAdd({ id: record.id, label: record.title, relation_type: relationType })
      setPicked(null)
      if (!fixedRelationType) setRelType('')
      if (restoreFocusAfterConfirm.current) {
        restoreFocusAfterConfirm.current = false
        requestAnimationFrame(focusPicker)
      }
    } catch (e) {
      setPicked(record)
      setLinkError((e as Error).message)
      if (restoreFocusAfterConfirm.current) requestAnimationFrame(focusPicker)
    } finally {
      setConfirming(false)
    }
  }

  if (picked) {
    return (
      <div ref={pickerRef} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, color: 'var(--fg-2)', flex: 1 }}>{picked.title}</span>
          <button className="btn sm ico gh" onClick={() => setPicked(null)} title="Auswahl aufheben"><X size={12} /></button>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {!fixedRelationType && relTypeTerms.length > 0 ? (
            <select className="fld" style={{ flex: 1 }} value={relType} onChange={e => setRelType(e.target.value)}>
              <option value="">— Relationstyp wählen —</option>
              {relTypeTerms.map(t => (
                <option key={t.id} value={t.term}>{getLabel(t, t.term)}</option>
              ))}
            </select>
          ) : !fixedRelationType && relTypeVocabId ? (
            <div className="help err" style={{ flex: 1 }}>Für diese Kombination ist kein Relationstyp konfiguriert.</div>
          ) : !fixedRelationType ? (
            <input className="fld" style={{ flex: 1 }} value={relType}
              onChange={e => setRelType(e.target.value)}
              placeholder="Relationstyp (z.B. depicts, created_by)"
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); confirm() } }}
              autoFocus
            />
          ) : null}
          <button className="btn pri sm" onClick={() => confirm()} disabled={confirming || !(fixedRelationType ?? relType.trim())}>{confirming ? 'Verknüpft…' : linkError ? 'Erneut verknüpfen' : 'Verknüpfen'}</button>
          <button className="btn gh sm" onClick={() => { setPicked(null); setRelType('') }}>Abbrechen</button>
        </div>
        {linkError && <div className="help err">Zieldatensatz wurde angelegt oder ausgewählt, aber nicht verknüpft: {linkError}</div>}
      </div>
    )
  }

  return (
    <div ref={pickerRef} className="relation-picker">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
        <div style={{ position: 'relative', flex: '1 1 280px' }}>
          <input
            ref={inputRef}
            className="fld"
            value={q}
            onChange={e => setQ(e.target.value)}
            onFocus={openSuggestions}
            placeholder={targetType ? `${targetType} suchen (mind. 2 Zeichen)…` : 'Kein Ziel-Typ konfiguriert'}
            disabled={disabled || !targetType}
          />
          {searching && (
            <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
              Suche…
            </div>
          )}
          {showDrop && dropPos && (
            <div ref={dropRef} style={{
              position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
              background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
              boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
            }}>
              {results.length > 0 ? results.map(r => (
                <button
                  key={r.id}
                  onMouseDown={e => { e.preventDefault(); pickRecord(r) }}
                  style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)', background: 'none', cursor: 'pointer' }}
                  className="authority-hit"
                >
                  <div style={{ fontWeight: 500, fontSize: 13 }}>{r.title}</div>
                  <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{r.id.slice(0, 8)}…</div>
                </button>
              )) : (
                <div className="relation-empty">
                  {allowCreate && !disabled && targetType && getTokenUser()?.role !== 'viewer' && (
                    <button
                      ref={createButtonRef}
                      type="button"
                      className="relation-create-option"
                      onMouseDown={e => e.preventDefault()}
                      onClick={() => setQuickCreateOpen(true)}
                    >
                      {NEW_TYPE_LABELS[targetType as RecordType]} „{q.trim()}“ anlegen
                    </button>
                  )}
                  <div>Keine passenden {TYPE_LABELS[targetType as RecordType] ?? 'Datensätze'} gefunden.</div>
                </div>
              )}
            </div>
          )}
        </div>
        {!fixedRelationType && (relTypeTerms.length > 0 ? (
          <select className="fld" style={{ flex: '0 1 240px' }} value={relType} onChange={e => setRelType(e.target.value)} aria-label="Relationstyp">
            <option value="">— Relationstyp wählen —</option>
            {relTypeTerms.map(t => <option key={t.id} value={t.term}>{getLabel(t, t.term)}</option>)}
          </select>
        ) : relTypeVocabId ? (
          <div className="help err" style={{ flex: '0 1 240px' }}>Für diese Kombination ist kein Relationstyp konfiguriert.</div>
        ) : null)}
      </div>
      {quickCreateOpen && targetType && (
        <QuickCreateDialog
          targetType={targetType}
          targetSubtype={targetSubtype}
          initialLabel={q.trim()}
          onClose={() => setQuickCreateOpen(false)}
          onReturnFocus={() => {
            if (createButtonRef.current?.isConnected) createButtonRef.current.focus()
            else focusPicker()
          }}
          onCreated={record => {
            const result = recordSearchResult(targetType, record)
            restoreFocusAfterConfirm.current = true
            setPicked(result)
            void confirm(result)
          }}
        />
      )}
    </div>
  )
}

function getApi(recordType: RecordType) {
  switch (recordType) {
    case 'object':     return objects
    case 'entity':     return entities
    case 'place':      return places
    case 'occurrence': return occurrences
    case 'procedure':  return procedures
  }
}

// --- Optimistic-locking conflict resolution (#272) ------------------------
type ConflictItem = { name: string; label: string; server: unknown; mine: unknown }
type ConflictState = {
  items: ConflictItem[]
  autoMerged: Record<string, unknown>   // fields resolved without asking the user
  serverVersion: number
  basePayload: Record<string, unknown>  // the payload B tried to save (scalars kept)
}

const valuesEqual = (a: unknown, b: unknown) =>
  JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

/** Compact, human-readable rendering of a metadata field value for the diff. */
function formatConflictValue(v: unknown): string {
  if (v == null || v === '') return '(leer)'
  if (Array.isArray(v)) {
    return v.map(el => {
      if (el && typeof el === 'object') {
        const o = el as Record<string, unknown>
        return String(o.value ?? o.label ?? o.entity_id ?? JSON.stringify(o))
      }
      return String(el)
    }).join(', ')
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function ConflictDialog({ conflict, saving, onCancel, onResolve }: {
  conflict: ConflictState
  saving: boolean
  onCancel: () => void
  onResolve: (mergedMetadata: Record<string, unknown>) => void
}) {
  const [choices, setChoices] = useState<Record<string, 'server' | 'mine'>>(
    () => Object.fromEntries(conflict.items.map(it => [it.name, 'mine' as const])),
  )
  const apply = () => {
    const merged: Record<string, unknown> = { ...conflict.autoMerged }
    for (const it of conflict.items) {
      merged[it.name] = choices[it.name] === 'server' ? it.server : it.mine
    }
    onResolve(merged)
  }
  return (
    <dialog open style={{ position: 'fixed', inset: 0, margin: 'auto', width: 560, maxWidth: 'calc(100vw - 32px)', maxHeight: 'calc(100vh - 64px)', overflow: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 0, background: 'var(--bg)', color: 'var(--fg)', boxShadow: '0 24px 80px rgba(0,0,0,.24)', zIndex: 25 }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-s)', fontWeight: 700 }}>Bearbeitungskonflikt</div>
      <div style={{ padding: 16, fontSize: 13, lineHeight: 1.5 }}>
        <p style={{ marginTop: 0 }}>
          Jemand anderes hat diesen Datensatz gespeichert, während du ihn bearbeitet hast.
          Für die folgenden Felder gibt es unterschiedliche Werte. Wähle je Feld, welcher gelten soll.
          Deine übrigen Änderungen bleiben erhalten.
        </p>
        {conflict.items.map(it => (
          <div key={it.name} className="field" style={{ borderTop: '1px solid var(--border-s)', paddingTop: 10, marginTop: 10 }}>
            <div className="lbl" style={{ fontWeight: 600 }}>{it.label}</div>
            <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer', marginTop: 6 }}>
              <input type="radio" name={`c-${it.name}`} checked={choices[it.name] === 'server'} onChange={() => setChoices(c => ({ ...c, [it.name]: 'server' }))} />
              <span><span style={{ color: 'var(--muted)' }}>Aktuell gespeichert (andere Person):</span> {formatConflictValue(it.server)}</span>
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer', marginTop: 4 }}>
              <input type="radio" name={`c-${it.name}`} checked={choices[it.name] === 'mine'} onChange={() => setChoices(c => ({ ...c, [it.name]: 'mine' }))} />
              <span><span style={{ color: 'var(--muted)' }}>Meine Änderung:</span> {formatConflictValue(it.mine)}</span>
            </label>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 16px', borderTop: '1px solid var(--border-s)' }}>
        <button className="btn gh" onClick={onCancel} disabled={saving}>Abbrechen</button>
        <button className="btn pri" onClick={apply} disabled={saving}>Auswahl übernehmen &amp; speichern</button>
      </div>
    </dialog>
  )
}

interface Props {
  recordType: RecordType
  recordId?: string
  onBack?: () => void
  onSaved?: (id: string) => void
  onDirtyChange?: (dirty: boolean) => void
  // Context override for form-variant resolution (#275), e.g. from a workflow
  // or quick-add entry point. Not yet set by any caller in this issue's scope.
  variantHint?: string
  quickCreate?: boolean
  initialSubtype?: string
  lockSubtype?: boolean
  initialLabel?: string
  onCreated?: (record: AnyRecord) => void
}

function VideoThumb({ objectId, mediaId }: { objectId: string; mediaId: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    authorizedFetch(`/v1/objects/${objectId}/media/${mediaId}/file`)
      .then(res => { if (!res.ok) throw new Error(); return res.blob() })
      .then(blob => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [objectId, mediaId])

  if (!url) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Video size={20} style={{ color: 'var(--fg-3)' }} />
      </div>
    )
  }
  return <video src={url} muted preload="metadata" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
}

export function ScreenForm({ recordType, recordId, onBack, onSaved, onDirtyChange, variantHint, quickCreate = false, initialSubtype, lockSubtype = false, initialLabel, onCreated }: Props) {
  const isNew = !recordId || recordId === 'new'
  const currentId = isNew ? null : recordId!
  const api = getApi(recordType)
  const snapshotsApi = recordType === 'object' ? objects.snapshots
    : recordType === 'entity' ? entities.snapshots
    : recordType === 'place' ? places.snapshots
    : recordType === 'occurrence' ? occurrences.snapshots
    : null
  const label = TYPE_LABELS[recordType]
  const subtypeKey = SUBTYPE_KEY[recordType]
  const showIdno  = true
  const showMedia = recordType === 'object' && !quickCreate
  const showGeo   = recordType === 'place'
  const showProcedureFields = recordType === 'procedure'
  const showSnapshotsForRecord = recordType !== 'procedure'
  const showCollectionStatus = recordType === 'object'
  const user = getTokenUser()
  const canEditLocked = user?.role === 'admin' || user?.role === 'superuser'
  const canManageContent = Boolean(user && user.role !== 'viewer')

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [variants, setVariants] = useState<FormVariant[]>([])
  const [activeVariantId, setActiveVariantId] = useState<string | null>(null)
  const [idno, setIdno]       = useState('')
  const [subtype, setSubtype] = useState('')
  const [lat, setLat]         = useState('')
  const [lon, setLon]         = useState('')
  const [status, setStatus]   = useState<Status | ProcedureStatus>('draft')
  const [loadedStatus, setLoadedStatus] = useState<Status | ProcedureStatus>('draft')
  const [collectionStatus, setCollectionStatus] = useState('active')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [referenceNumber, setReferenceNumber] = useState('')
  const [values, setValues]   = useState<Record<string, unknown>>({})
  const languages = useSupportedLanguages()
  // Optimistic locking (#272): version loaded with the record + the metadata as
  // loaded (base), so a save conflict can be resolved field-by-field.
  const [version, setVersion] = useState<number | null>(null)
  const [baseValues, setBaseValues] = useState<Record<string, unknown>>({})
  const [conflict, setConflict] = useState<ConflictState | null>(null)
  const [showAudit, setShowAudit] = useState(false)
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [fieldWarnings, setFieldWarnings] = useState<Record<string, string>>({})
  const [showSnapshots, setShowSnapshots] = useState(false)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [snapLabel, setSnapLabel] = useState('')
  const [snapCreating, setSnapCreating] = useState(false)
  const [snapRestoring, setSnapRestoring] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [isDirty, setIsDirty] = useState(false)
  useEffect(() => { onDirtyChange?.(isDirty) }, [isDirty])
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [registeringPidField, setRegisteringPidField] = useState<string | null>(null)
  const [title, setTitle]     = useState(isNew ? NEW_TYPE_LABELS[recordType] : '…')

  const [mediaFiles, setMediaFiles]     = useState<MediaFile[]>([])
  const [uploading, setUploading]       = useState(false)
  const [uploadError, setUploadError]   = useState<string | null>(null)
  const [dragOver, setDragOver]         = useState(false)
  const [lightboxMedia, setLightboxMedia] = useState<MediaFile | null>(null)
  const [mediaTypeTerms, setMediaTypeTerms] = useState<VocabularyTerm[]>([])
  const [relTypeTerms, setRelTypeTerms] = useState<VocabularyTerm[]>([])
  const [relTypeVocabId, setRelTypeVocabId] = useState<string | undefined>()
  const [availableSubtypes, setAvailableSubtypes] = useState<RecordSubtype[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [savedId, setSavedId] = useState<string | null>(currentId)
  const [saveOk, setSaveOk]   = useState(false)
  const [saveNotice, setSaveNotice] = useState<string | null>(null)

  const [rels, setRels]           = useState<Relation[]>([])
  const [relTitles, setRelTitles] = useState<Record<string, string>>({})
  const [objectStatuses, setObjectStatuses] = useState<Record<string, string>>({})
  const [addTargetType, setAddTargetType] = useState<RecordType>('object')
  const [addProcedureOpen, setAddProcedureOpen] = useState(false)
  const [genericAddOpen, setGenericAddOpen] = useState(false)
  const [completionDialog, setCompletionDialog] = useState<{ count: number; status: string } | null>(null)
  const [aiBusyField, setAiBusyField] = useState<string | null>(null)
  const [aiProposal, setAiProposal] = useState<AiProposal | null>(null)
  const [openRightsMediaId, setOpenRightsMediaId] = useState<string | null>(null)
  const [highlightedField, setHighlightedField] = useState<string | null>(null)

  function jumpToField(name: string) {
    document.getElementById(`field-${name}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedField(name)
    window.setTimeout(() => setHighlightedField(current => current === name ? null : current), 3000)
  }

  // Warn on browser tab close / reload
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => { if (isDirty && !isNew) e.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty, isNew])

  const loadMedia = useCallback((id: string) => {
    media.list(id).then(setMediaFiles).catch(() => {})
  }, [])


  const loadSnapshots = useCallback((id: string) => {
    snapshotsApi?.list(id).then(setSnapshots).catch(() => {})
  }, [snapshotsApi])

  const loadAudit = useCallback((id: string) => {
    setAuditLoading(true)
    api.audit(id).then(setAuditEntries).catch(() => {}).finally(() => setAuditLoading(false))
  }, [api])

  const loadRelations = useCallback(async (id: string) => {
    try {
      const [fromRels, toRels] = await Promise.all([
        relationsApi.list({ from_type: recordType, from_id: id }),
        relationsApi.list({ to_type: recordType, to_id: id }),
      ])
      const loaded = [...fromRels, ...toRels]
      setRels(loaded)
      const titleMap: Record<string, string> = {}
      const statusMap: Record<string, string> = {}
      await Promise.all(loaded.map(async r => {
        const isFrom = r.from_id === id
        const targetType = isFrom ? r.to_type : r.from_type
        const targetId = isFrom ? r.to_id : r.from_id
        const key = `${targetType}/${targetId}`
        try {
          const rec = await (getApi(targetType as RecordType).get as (id: string) => Promise<AnyRecord>)(targetId)
          titleMap[key] = extractTitle(rec.metadata_ as Record<string, unknown>, (rec as { idno?: string | null }).idno ?? targetId.slice(0, 8) + '…')
          if (targetType === 'object') {
            statusMap[targetId] = (rec as { collection_status?: string | null }).collection_status ?? 'active'
          }
        } catch {
          titleMap[key] = targetId.slice(0, 8) + '…'
        }
      }))
      setRelTitles(titleMap)
      setObjectStatuses(statusMap)
    } catch {
      // silently ignore
    }
  }, [recordType])

  useEffect(() => {
    setLoading(true)
    setTitle(isNew ? NEW_TYPE_LABELS[recordType] : '…')
    setSavedId(currentId)
    setIdno('')
    setSubtype(initialSubtype ?? '')
    setLat('')
    setLon('')
    setStartDate('')
    setEndDate('')
    setDueDate('')
    setReferenceNumber('')
    setStatus('draft')
    setLoadedStatus('draft')
    setCollectionStatus('active')
    setValues({})
    setMediaFiles([])
    setRels([])
    setRelTitles({})
    setObjectStatuses({})
    setAddProcedureOpen(false)
    setCompletionDialog(null)

    // Load available subtypes before resolving a new form's schema, so the
    // default and fixed subtype use the same schema key from the first load.
    const subtypeListP = subtypeKey
      ? subtypes.list(recordType).catch(() => [] as RecordSubtype[])
      : Promise.resolve([] as RecordSubtype[])
    subtypeListP.then(items => {
      setAvailableSubtypes(items)
      if (isNew) setSubtype(current => current || initialSubtype || items.find(item => item.is_default)?.name || '')
    })

    const loadRecP = isNew ? Promise.resolve(null) : (api.get as (id: string) => Promise<AnyRecord>)(recordId!)

    loadRecP
      .then(async rec => {
        let recSubtype: string | undefined = isNew ? initialSubtype : undefined
        if (rec) {
          setStatus(rec.status as Status)
          setLoadedStatus(rec.status as Status)
          setValues(rec.metadata_)
          setVersion(rec.version)
          setBaseValues(rec.metadata_ ?? {})
          const m = rec.metadata_ as Record<string, unknown>
          if (showIdno)  setIdno((rec as { idno?: string | null }).idno ?? '')
          if (subtypeKey) {
            recSubtype = String((rec as unknown as Record<string, unknown>)[subtypeKey] ?? '') || undefined
            setSubtype(recSubtype ?? '')
          }
          if (showGeo) {
            const p = rec as { lat?: number | null; lon?: number | null }
            setLat(p.lat != null ? String(p.lat) : '')
            setLon(p.lon != null ? String(p.lon) : '')
          }
          if (showCollectionStatus) {
            setCollectionStatus((rec as { collection_status?: string | null }).collection_status ?? 'active')
          }
          if (showProcedureFields) {
            const p = rec as { start_date?: string | null; end_date?: string | null; due_date?: string | null; reference_number?: string | null }
            setStartDate(p.start_date ?? '')
            setEndDate(p.end_date ?? '')
            setDueDate(p.due_date ?? '')
            setReferenceNumber(p.reference_number ?? '')
          }
          setTitle(extractTitle(m, (rec as { idno?: string | null }).idno ?? rec.id))
        } else if (subtypeKey) {
          const items = await subtypeListP
          recSubtype = initialSubtype || items.find(item => item.is_default)?.name || undefined
        }
        const fieldDefs = await schema.list(recordType, recSubtype)
        setFields(fieldDefs)
        if (!rec) {
          const defaults = defaultsFor(fieldDefs)
          if (initialLabel) {
            const labelField = fieldDefs.find(f => f.field_type === 'text' && TITLE_FIELD_NAMES.includes(f.name))
            if (labelField) defaults[labelField.name] = labelField.is_repeatable ? [initialLabel] : initialLabel
          }
          setValues(defaults)
        }

        const variantList = await formVariants.list(recordType, recSubtype).catch(() => [])
        setVariants(variantList)
        const remembered = localStorage.getItem(localVariantKey(recordType, recSubtype))
        const resolved = resolveActiveVariant(variantList, user?.role ?? '', remembered, variantHint)
        setActiveVariantId(resolved?.id ?? null)
      })
      .catch(e => setError(e.message))
      .finally(() => { setLoading(false); setIsDirty(false) })

    if (!isNew && currentId) loadRelations(currentId)
  }, [recordId, recordType, isNew, initialSubtype])

  useEffect(() => {
    if (!isNew) return
    idnoApi.next(recordType)
      .then(r => { if (r.next) setIdno(r.next) })
      .catch(() => {})
  }, [isNew, recordType])

  // Reload field definitions when subtype changes on new forms (values preserved in state)
  useEffect(() => {
    if (!isNew || !subtypeKey || !subtype) return
    schema.list(recordType, subtype).then(fieldDefs => {
      setFields(fieldDefs)
      setValues(prev => ({ ...defaultsFor(fieldDefs), ...prev }))
    }).catch(() => {})
    formVariants.list(recordType, subtype).then(variantList => {
      setVariants(variantList)
      const remembered = localStorage.getItem(localVariantKey(recordType, subtype))
      const resolved = resolveActiveVariant(variantList, user?.role ?? '', remembered, variantHint)
      setActiveVariantId(resolved?.id ?? null)
    }).catch(() => setVariants([]))
  }, [isNew, subtype, recordType, subtypeKey])

  useEffect(() => {
    if (savedId && showMedia) loadMedia(savedId)
  }, [savedId, showMedia, loadMedia])

  // Poll until all pending uploads are processed by the Celery worker
  const hasPendingMedia = mediaFiles.some(f => f.status === 'pending')
  useEffect(() => {
    if (!savedId || !showMedia || !hasPendingMedia) return
    const timer = setInterval(() => {
      media.list(savedId).then(setMediaFiles).catch(() => {})
    }, 2500)
    return () => clearInterval(timer)
  }, [savedId, showMedia, hasPendingMedia])

  useEffect(() => {
    if (savedId && showSnapshotsForRecord) loadSnapshots(savedId)
  }, [savedId, showSnapshotsForRecord, loadSnapshots])

  useEffect(() => {
    if (!showMedia) return
    vocabularies.list()
      .then(vocabs => {
        const mt = vocabs.find(v => v.name === 'media_types')
        if (mt) return vocabularies.listTerms(mt.id)
        return []
      })
      .then(setMediaTypeTerms)
      .catch(() => {})
  }, [showMedia])

  useEffect(() => {
    vocabularies.list()
      .then(vocabs => {
        const rt = vocabs.find(v => v.name === 'relation_types')
        if (rt) {
          setRelTypeVocabId(rt.id)
          return vocabularies.listTerms(rt.id)
        }
        return []
      })
      .then(setRelTypeTerms)
      .catch(() => {})
  }, [])

  async function handleAddObjectRelation(result: SearchResult) {
    if (!savedId) return
    const duplicate = rels.some(r => {
      const isFrom = r.from_id === savedId
      return (isFrom ? r.to_type : r.from_type) === 'object'
        && (isFrom ? r.to_id : r.from_id) === result.id
        && r.relation_type === 'concerns'
    })
    if (duplicate) throw new Error('Diese Beziehung besteht bereits.')
    const created = await relationsApi.create({
      from_type: recordType, from_id: savedId,
      to_type: 'object', to_id: result.id,
      relation_type: 'concerns',
    })
    setRels(prev => [...prev, created])
    setRelTitles(prev => ({ ...prev, [`object/${created.to_id}`]: result.title }))
    objects.get(result.id).then(obj => {
      setObjectStatuses(prev => ({ ...prev, [result.id]: obj.collection_status ?? 'active' }))
    }).catch(() => {})
  }

  async function handleAddProcedureRelation(selected: SearchResult) {
    if (!selected || !savedId) return
    const duplicate = rels.some(r => {
      const isFrom = r.from_id === savedId
      return (isFrom ? r.to_type : r.from_type) === 'procedure'
        && (isFrom ? r.to_id : r.from_id) === selected.id
        && r.relation_type === 'concerns'
    })
    if (duplicate) throw new Error('Diese Beziehung besteht bereits.')
    const created = await relationsApi.create({
      from_type: recordType, from_id: savedId,
      to_type: 'procedure', to_id: selected.id,
      relation_type: 'concerns',
    })
    setRels(prev => [...prev, created])
    setRelTitles(prev => ({ ...prev, [`procedure/${created.to_id}`]: selected.title }))
    setAddProcedureOpen(false)
  }

  async function handleAddGenericRelation(entry: RelationEntry) {
    if (!savedId) return
    const field = fields.find(f => f.field_type === 'relation'
      && f.settings?.target_type === addTargetType
      && f.settings?.fixed_relation_type === entry.relation_type)
    if (field) {
      throw new Error(`Diese Beziehung wird im Feld „${getLabel(field, field.name)}“ gepflegt.`)
    }
    const duplicate = rels.some(r => {
      const isFrom = r.from_id === savedId
      return (isFrom ? r.to_type : r.from_type) === addTargetType
        && (isFrom ? r.to_id : r.from_id) === entry.id
        && r.relation_type === entry.relation_type
    })
    if (duplicate) throw new Error('Diese Beziehung besteht bereits.')
    const created = await relationsApi.create({
      from_type: recordType,
      from_id: savedId,
      to_type: addTargetType,
      to_id: entry.id,
      relation_type: entry.relation_type,
    })
    setRels(prev => [...prev, created])
    setRelTitles(prev => ({ ...prev, [`${addTargetType}/${entry.id}`]: entry.label }))
    setGenericAddOpen(false)
  }

  async function handleDeleteRelation(id: string) {
    if (!window.confirm('Relation wirklich löschen?')) return
    try {
      await relationsApi.delete(id)
      const rel = rels.find(r => r.id === id)
      setRels(prev => prev.filter(r => r.id !== id))
      if (rel) {
        const targetId = rel.from_id === savedId ? rel.to_id : rel.from_id
        setObjectStatuses(prev => { const next = { ...prev }; delete next[targetId]; return next })
      }
    } catch (e) { alert((e as Error).message) }
  }

  // All user-triggered value mutations go through this wrapper to mark the form dirty
  const setValuesDirty: typeof setValues = (fn) => { setValues(fn); setIsDirty(true) }

  function setField(name: string, value: unknown) { setValuesDirty(v => ({ ...v, [name]: value })) }
  function addRepeat(name: string) {
    const cur = (values[name] as string[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, ''] }))
  }
  function removeRepeat(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as string[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updateRepeat(name: string, idx: number, val: string) {
    const cur = [...((values[name] as string[]) ?? [])]
    cur[idx] = val
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }
  function updateTranslatable(name: string, lang: string, val: string) {
    const cur = { ...((values[name] as Record<string, string>) ?? {}) }
    cur[lang] = val
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }
  function removeTranslatable(name: string, lang: string) {
    const cur = { ...((values[name] as Record<string, string>) ?? {}) }
    delete cur[lang]
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }

  type PidEntry = { value: string; label: string }
  function addPid(name: string) {
    const cur = (values[name] as PidEntry[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, { value: '', label: '' }] }))
  }
  function removePid(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as PidEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updatePid(name: string, idx: number, key: 'value' | 'label', val: string) {
    const cur = [...((values[name] as PidEntry[]) ?? [])]
    cur[idx] = { ...cur[idx], [key]: val }
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }

  async function registerUrn(fieldName: string, repeatable: boolean) {
    if (!savedId) return
    setRegisteringPidField(fieldName)
    try {
      const result = await pids.registerDnbUrn({
        record_type: recordType,
        record_id: savedId,
        field_name: fieldName,
        target_url: `${PORTAL_URL}/${PORTAL_PATH[recordType]}/${savedId}`,
        label: 'URN',
      })
      if (repeatable) {
        const cur = (values[fieldName] as PidEntry[] | undefined) ?? []
        setField(fieldName, [...cur, result.value])
      } else {
        setField(fieldName, result.value)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRegisteringPidField(null)
    }
  }

  function setAuthority(name: string, val: AuthorityEntry | null) {
    setValuesDirty(v => ({ ...v, [name]: val ?? undefined }))
  }
  function addAuthority(name: string, val: AuthorityEntry) {
    const cur = (values[name] as AuthorityEntry[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, val] }))
  }
  function removeAuthority(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as AuthorityEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }

  function setVocab(name: string, val: VocabEntry | null) {
    setValuesDirty(v => ({ ...v, [name]: val ?? undefined }))
  }
  function addFreeVocab(name: string, val: string) {
    if (!val.trim()) return
    const cur = (values[name] as string[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, val.trim()] }))
  }
  function removeFreeVocab(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as string[]) ?? []).filter((_, i) => i !== idx) }))
  }

  function addVocab(name: string, val: VocabEntry) {
    const cur = (values[name] as VocabEntry[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, val] }))
  }
  function removeVocab(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as VocabEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }

  type GroupInstance = Record<string, unknown>
  function addGroupInstance(name: string) {
    const cur = (values[name] as GroupInstance[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, {}] }))
  }
  function removeGroupInstance(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as GroupInstance[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updateGroupSubField(name: string, idx: number, subName: string, val: unknown) {
    const cur = [...((values[name] as GroupInstance[]) ?? [])]
    cur[idx] = { ...cur[idx], [subName]: val }
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }

  function renderSubFieldInput(sf: FieldDefinition, val: unknown, onChange: (v: unknown) => void, disabled: boolean) {
    switch (sf.field_type) {
      case 'boolean':
        return (
          <label className="form-checkbox">
            <input type="checkbox" className="ck" checked={Boolean(val)} onChange={e => onChange(e.target.checked)} disabled={disabled} />
            <span style={{ fontSize: 13 }}>{sf.label.de || sf.name}</span>
          </label>
        )
      case 'number':
        return <input className="fld" type="number" step="any" value={(val as string) ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={getLabel(sf, sf.name)} />
      case 'date':
        return <DateInput value={(val as string) ?? ''} onChange={onChange} disabled={disabled} />
      case 'vocab':
        return (
          <VocabInput
            vocabId={(sf.settings?.vocabulary_id as string) ?? ''}
            value={(val as VocabEntry | undefined) ?? null}
            onChange={v => onChange(v ?? undefined)}
            disabled={disabled}
          />
        )
      case 'vocab_free':
        return (
          <VocabFreeInput
            vocabId={(sf.settings?.vocabulary_id as string) ?? ''}
            value={(val as string) ?? ''}
            onChange={v => onChange(v)}
            disabled={disabled}
          />
        )
      case 'relation':
        return val ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ flex: 1 }}>{(val as RelationEntry).label}</span>
            <button className="btn sm ico gh" onClick={() => onChange(undefined)} disabled={disabled}><X size={10} /></button>
          </div>
        ) : (
          <RelationInput
            targetType={(sf.settings?.target_type as RecordType) ?? ''}
            targetSubtype={sf.settings?.target_subtype as string | undefined}
            relTypeVocabId={(sf.settings?.relation_type_vocab as string | undefined) ?? relTypeVocabId}
            fixedRelationType={sf.settings?.fixed_relation_type as string | undefined}
            fromType={recordType}
            onAdd={entry => onChange(entry)}
            disabled={disabled}
          />
        )
      case 'authority':
        return (
          <AuthorityInput
            source={(sf.settings?.source as string) ?? ''}
            value={(val as AuthorityEntry | undefined) ?? null}
            onChange={value => onChange(value ?? undefined)}
            disabled={disabled}
          />
        )
      default:
        return <input className="fld" value={(val as string) ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={getLabel(sf, sf.name)} />
    }
  }

  function addRelationEntry(name: string, entry: RelationEntry) {
    const cur = (values[name] as RelationEntry[] | undefined) ?? []
    if (cur.some(item => item.id === entry.id && item.relation_type === entry.relation_type)) {
      throw new Error('Diese Beziehung besteht bereits.')
    }
    setValuesDirty(v => ({ ...v, [name]: [...cur, entry] }))
  }
  function removeRelationEntry(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as RelationEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }

  function isEmptyValue(val: unknown): boolean {
    return val === null || val === undefined || val === '' ||
      (Array.isArray(val) && val.length === 0) ||
      (typeof val === 'object' && val !== null && Object.keys(val).length === 0)
  }

  function validateFields(): { errors: Record<string, string>; warnings: Record<string, string> } {
    const errors: Record<string, string> = {}
    const warnings: Record<string, string> = {}
    const addRequired = (key: string, message: string) => {
      if (isDraftStatus) warnings[key] = message
      else errors[key] = message
    }
    // idno is required for all record types
    if (!idno.trim()) {
      addRequired('__idno', 'ID-Nr. ist ein Pflichtfeld.')
    }
    // Entity subtype choice and fixed relation subtypes are structural in quick-create,
    // so drafts must not bypass them.
    const validConfiguredSubtype = availableSubtypes.some(item => item.name === subtype)
    if (quickCreate &&
        ((recordType === 'entity' && availableSubtypes.length > 0) || lockSubtype) &&
        !validConfiguredSubtype) {
      errors.__subtype = lockSubtype ? 'Der konfigurierte Subtyp ist ungültig.' : 'Subtyp ist ein Pflichtfeld.'
    } else if (subtypeKey && availableSubtypes.length > 0 && !subtype) {
      addRequired('__subtype', 'Subtyp ist ein Pflichtfeld.')
    }
    for (const f of fields) {
      const val = values[f.name]

      // Required field check (all types)
      if (f.is_required && isEmptyValue(val)) {
        addRequired(f.name, `Feld '${getLabel(f, f.name)}' ist ein Pflichtfeld.`)
        continue
      }

      if (val === undefined || val === null || val === '') continue

      // Group field validation
      if (f.field_type === 'group') {
        const instances = (val as Record<string, unknown>[] | undefined) ?? []
        if (f.is_required && instances.length === 0) {
          addRequired(f.name, `Feld '${getLabel(f, f.name)}' muss mindestens einen Eintrag haben.`)
          continue
        }
        for (let idx = 0; idx < instances.length; idx++) {
          const instance = instances[idx]
          for (const sf of (f.children ?? [])) {
            const sv = instance[sf.name]
            if (sf.is_required && isEmptyValue(sv)) {
              addRequired(
                `${f.name}.${sf.name}:${idx}`,
                `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}) ist ein Pflichtfeld.`
              )
            }
            if (sv !== undefined && sv !== null && sv !== '' &&
                sf.field_type === 'text' && sf.settings?.validation_regex) {
              const regex = sf.settings.validation_regex as string
              try {
                if (!new RegExp(regex).test(String(sv))) {
                  errors[`${f.name}.${sf.name}:${idx}`] =
                    `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}): Eingabe entspricht nicht dem erwarteten Format.`
                }
              } catch {
                // invalid regex on backend, ignore
              }
            }
            if (sf.field_type === 'date' && typeof sv === 'string' && sv && !isValidDateInput(sv)) {
              errors[`${f.name}.${sf.name}:${idx}`] =
                `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}): Ungültiges Datum.`
            }
            if (!isEmptyValue(sv) && sf.field_type === 'authority') {
              const entry = typeof sv === 'object' && sv !== null && !Array.isArray(sv)
                ? sv as Partial<AuthorityEntry>
                : null
              const key = `${f.name}.${sf.name}:${idx}`
              if (!entry?.source || !entry.external_id || !entry.label) {
                errors[key] = `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}) enthält keinen gültigen Normdateneintrag.`
              } else if (entry.source !== sf.settings?.source) {
                errors[key] = `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}) verwendet die falsche Normdaten-Quelle.`
              }
            }
          }
        }
        continue
      }

      // Repeatable fields: must be a non-empty list when required
      if (f.is_repeatable) {
        const arr = Array.isArray(val) ? val : []
        if (f.is_required && arr.length === 0) {
          addRequired(f.name, `Feld '${getLabel(f, f.name)}' muss mindestens einen Wert haben.`)
          continue
        }
        // Validate each item
        for (let i = 0; i < arr.length; i++) {
          const item = arr[i]
          if (f.field_type === 'date' && typeof item === 'string' && item) {
            if (!isValidDateInput(item)) {
              errors[f.name] = 'Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT oder TT.MM.JJJJ'
              break
            }
          }
          if (f.field_type === 'number' && typeof item === 'string' && item) {
            if (!/^-?\d+(\.\d+)?$/.test(item)) {
              errors[f.name] = 'Ungültige Zahl. Erlaubt: Ganze Zahlen und Dezimalzahlen (z.B. 42 oder 3.14)'
              break
            }
          }
          if (f.field_type === 'text' && f.settings?.validation_regex && typeof item === 'string' && item) {
            const regex = f.settings.validation_regex as string
            try {
              if (!new RegExp(regex).test(item)) {
                errors[f.name] = 'Eingabe entspricht nicht dem erwarteten Format.'
                break
              }
            } catch {
              // invalid regex on backend, ignore
            }
          }
        }
        continue
      }

      // Non-repeatable field validation
      if (f.field_type === 'date') {
        const v = val as string
        if (v && !isValidDateInput(v)) {
          errors[f.name] = 'Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT oder TT.MM.JJJJ'
        }
      }
      if (f.field_type === 'number') {
        const v = val as string
        if (v && !/^-?\d+(\.\d+)?$/.test(v)) {
          errors[f.name] = 'Ungültige Zahl. Erlaubt: Ganze Zahlen und Dezimalzahlen (z.B. 42 oder 3.14)'
        }
      }
      if (f.field_type === 'text' && f.settings?.validation_regex) {
        const regex = f.settings.validation_regex as string
        const v = val as string
        if (v) {
          try {
            if (!new RegExp(regex).test(v)) {
              errors[f.name] = 'Eingabe entspricht nicht dem erwarteten Format.'
            }
          } catch {
            // invalid regex on backend, ignore
          }
        }
      }
    }
    return { errors, warnings }
  }

  function validateSingleField(field: FieldDefinition): { level: 'error' | 'warning'; message: string } | null {
    const val = values[field.name]
    if (field.is_required && isEmptyValue(val)) {
      return {
        level: isDraftStatus ? 'warning' : 'error',
        message: `Feld '${getLabel(field, field.name)}' ist ein Pflichtfeld.`,
      }
    }
    if (val === undefined || val === null || val === '') return null
    if (field.field_type === 'date') {
      const v = val as string
      if (v && !isValidDateInput(v)) {
        return { level: 'error', message: 'Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT oder TT.MM.JJJJ' }
      }
    }
    if (field.field_type === 'number') {
      const v = val as string
      if (v && !/^-?\d+(\.\d+)?$/.test(v)) {
        return { level: 'error', message: 'Ungültige Zahl. Erlaubt: Ganze Zahlen und Dezimalzahlen (z.B. 42 oder 3.14)' }
      }
    }
    if (field.field_type === 'text' && field.settings?.validation_regex) {
      const regex = field.settings.validation_regex as string
      const v = val as string
      if (v) {
        try {
          if (!new RegExp(regex).test(v)) {
            return { level: 'error', message: 'Eingabe entspricht nicht dem erwarteten Format.' }
          }
        } catch {
          // ignore
        }
      }
    }
    return null
  }

  function handleFieldBlur(field: FieldDefinition) {
    const result = validateSingleField(field)
    setFieldErrors(prev => {
      const next = { ...prev }
      if (result?.level === 'error') next[field.name] = result.message
      else delete next[field.name]
      return next
    })
    setFieldWarnings(prev => {
      const next = { ...prev }
      if (result?.level === 'warning') next[field.name] = result.message
      else delete next[field.name]
      return next
    })
  }

  async function runAIForField(field: FieldDefinition) {
    const aiConfig = getFieldAiConfig(field)
    const targetId = savedId ?? currentId
    if (!aiConfig || !targetId) return
    const currentValue = values[field.name]
    const hasValue = !isEmptyValue(currentValue)
    setAiBusyField(field.name)
    setError(null)
    try {
      const result = await ai.complete({
        field_definition_id: field.id,
        record_type: recordType,
        record_id: targetId,
      })
      if (hasValue) setAiProposal({ field, currentValue, suggestedValue: result.value })
      else {
        setValuesDirty(prev => ({ ...prev, [field.name]: result.value }))
        clearFieldFeedback(field.name)
      }
      if (result.warning) {
        setError(`KI-Hinweis für ${getLabel(field, field.name)}: ${result.warning}`)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAiBusyField(null)
    }
  }

  async function runAIForGroupSubField(group: FieldDefinition, field: FieldDefinition, groupIndex: number) {
    const aiConfig = getFieldAiConfig(field)
    const targetId = savedId ?? currentId
    if (!aiConfig || !targetId) return
    const instance = ((values[group.name] as GroupInstance[] | undefined) ?? [])[groupIndex]
    const currentValue = instance?.[field.name]
    const busyKey = `${group.name}:${groupIndex}:${field.name}`
    setAiBusyField(busyKey)
    setError(null)
    try {
      const result = await ai.complete({
        field_definition_id: field.id,
        record_type: recordType,
        record_id: targetId,
        group_index: groupIndex,
        group_instance: instance,
      })
      if (isEmptyValue(currentValue)) updateGroupSubField(group.name, groupIndex, field.name, result.value)
      else setAiProposal({ field, currentValue, suggestedValue: result.value, group: { name: group.name, index: groupIndex } })
      if (result.warning) {
        setError(`KI-Hinweis für ${getLabel(field, field.name)}: ${result.warning}`)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAiBusyField(null)
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaveNotice(null)
    const validation = validateFields()
    if (Object.keys(validation.errors).length > 0) {
      console.log('[Katalon] Validierungsfehler beim Speichern:', validation.errors)
      setFieldErrors(validation.errors)
      setFieldWarnings(validation.warnings)
      setSaving(false)
      setError('Bitte korrigieren Sie die markierten Felder.')
      return
    }
    setFieldErrors({})
    setFieldWarnings(validation.warnings)
    try {
      const completingProcedure = showProcedureFields && !isNew && loadedStatus !== 'completed' && status === 'completed'
      const payload: Record<string, unknown> = {
        status: quickCreate ? 'draft' : completingProcedure ? loadedStatus : status,
        metadata_: values,
      }
      if (showIdno)   payload.idno = idno || null
      if (subtypeKey) payload[subtypeKey] = subtype
      if (showCollectionStatus) payload.collection_status = collectionStatus
      if (showGeo) {
        payload.lat = lat ? parseFloat(lat) : null
        payload.lon = lon ? parseFloat(lon) : null
      }
      if (showProcedureFields) {
        payload.start_date = startDate || null
        payload.end_date = endDate || null
        payload.due_date = dueDate || null
        payload.reference_number = referenceNumber || null
      }

      if (isNew) {
        const created = await (api.create as (d: typeof payload) => Promise<AnyRecord>)(payload)
        if (quickCreate) {
          onCreated?.(created)
          return
        }
        setSavedId(created.id)
        setLoadedStatus(created.status as Status)
        onSaved?.(created.id)
        if (showMedia) loadMedia(created.id)
        setIsDirty(false)
        setSaveOk(true)
        setSaveNotice(
          Object.keys(validation.warnings).length > 0
            ? 'Entwurf gespeichert mit Validierungshinweisen.'
            : `${label} gespeichert.${showMedia ? ' Bilder können jetzt hochgeladen werden.' : ''}`
        )
        setTimeout(() => setSaveOk(false), 3000)
      } else {
        try {
          const updated = await (api.update as (id: string, d: typeof payload, v?: number) => Promise<AnyRecord>)(recordId!, payload, version ?? undefined)
          setVersion(updated.version)
          setBaseValues(payload.metadata_ as Record<string, unknown>)
        } catch (e) {
          if (e instanceof VersionConflictError) {
            await resolveConflict(payload)
            return
          }
          throw e
        }
        if (completingProcedure) {
          const objectCount = rels.filter(r => {
            const targetType = r.from_id === recordId ? r.to_type : r.from_type
            return targetType === 'object'
          }).length
          const suggested = PROCEDURE_COMPLETION_STATUS[subtype] ?? null
          if (objectCount > 0 && suggested) {
            setCompletionDialog({ count: objectCount, status: suggested })
          } else {
            await completeProcedure(null)
          }
        } else {
          setLoadedStatus(status)
        }
        setIsDirty(false)
        setSaveOk(true)
        setSaveNotice(
          Object.keys(validation.warnings).length > 0
            ? 'Entwurf gespeichert mit Validierungshinweisen.'
            : 'Änderungen gespeichert.'
        )
        setTimeout(() => setSaveOk(false), 3000)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  // Save hit a 409: fetch the current server state and do a 3-way merge
  // (base = as loaded, server = A's change, mine = B's edits) per metadata field.
  // Only genuine both-sides-changed fields are shown to the user.
  async function resolveConflict(payload: Record<string, unknown>) {
    const server = await (api.get as (id: string) => Promise<AnyRecord>)(recordId!)
    const serverMeta = (server.metadata_ ?? {}) as Record<string, unknown>
    const merged: Record<string, unknown> = {}
    const items: ConflictItem[] = []
    const names = new Set<string>([
      ...Object.keys(baseValues),
      ...Object.keys(serverMeta),
      ...Object.keys(values),
    ])
    for (const name of names) {
      const base = baseValues[name]
      const srv = serverMeta[name]
      const mine = values[name]
      if (valuesEqual(mine, srv)) { merged[name] = mine; continue }   // both agree
      if (valuesEqual(mine, base)) { merged[name] = srv; continue }   // only A changed
      if (valuesEqual(srv, base)) { merged[name] = mine; continue }   // only B changed
      const f = fields.find(fd => fd.name === name)
      items.push({ name, label: f ? getLabel(f.label) : name, server: srv, mine })
    }
    if (items.length === 0) {
      await commitMerge(payload, merged, server.version)
      return
    }
    setConflict({ items, autoMerged: merged, serverVersion: server.version, basePayload: payload })
  }

  async function commitMerge(
    payload: Record<string, unknown>,
    mergedMetadata: Record<string, unknown>,
    serverVersion: number,
  ) {
    setSaving(true)
    setError(null)
    try {
      const finalPayload = { ...payload, metadata_: mergedMetadata }
      const updated = await (api.update as (id: string, d: typeof finalPayload, v?: number) => Promise<AnyRecord>)(recordId!, finalPayload, serverVersion)
      setValues(mergedMetadata)
      setBaseValues(mergedMetadata)
      setVersion(updated.version)
      setLoadedStatus(updated.status as Status)
      setConflict(null)
      setIsDirty(false)
      setSaveOk(true)
      setSaveNotice('Konflikt gelöst – Änderungen gespeichert.')
      setTimeout(() => setSaveOk(false), 3000)
    } catch (e) {
      if (e instanceof VersionConflictError) {
        // Yet another save landed in between — recompute against the newest state.
        await resolveConflict(payload)
        return
      }
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function completeProcedure(collectionStatus: string | null) {
    if (!recordId) return
    setSaving(true)
    setError(null)
    try {
      await procedures.complete(recordId, collectionStatus)
      setStatus('completed')
      setLoadedStatus('completed')
      setCompletionDialog(null)
      setIsDirty(false)
      setSaveOk(true)
      setTimeout(() => setSaveOk(false), 3000)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleUpload(file: File) {
    if (!savedId) return
    setUploading(true)
    setUploadError(null)
    try {
      const uploaded = await media.upload(savedId, file)
      setMediaFiles(prev => [...prev, uploaded])
    } catch (e) {
      setUploadError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function handleMediaRights(mediaId: string, data: { license_uri?: string | null; rights_holder?: { name: string; uri?: string } | null }) {
    if (!savedId) return
    try {
      const updated = await media.patch(savedId, mediaId, data)
      setMediaFiles(prev => prev.map(f => f.id === mediaId ? updated : f))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleDeleteMedia(mediaId: string) {
    if (!savedId || !window.confirm('Medium wirklich löschen?')) return
    try {
      await media.delete(savedId, mediaId)
      setMediaFiles(prev => prev.filter(f => f.id !== mediaId))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleSetPrimary(mediaId: string) {
    if (!savedId) return
    try {
      await media.patch(savedId, mediaId, { is_primary: true })
      setMediaFiles(prev => prev.map(f => ({ ...f, is_primary: f.id === mediaId })))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  async function handleSetMediaType(mediaId: string, mediaType: string | null) {
    if (!savedId) return
    try {
      const updated = await media.patch(savedId, mediaId, { media_type: mediaType })
      setMediaFiles(prev => prev.map(f => f.id === mediaId ? { ...f, media_type: updated.media_type } : f))
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  const hasSavedId   = Boolean(savedId)
  const justCreated  = isNew && hasSavedId
  const showTwoCol   = !quickCreate && (showMedia || !isNew)
  const objectRels = showProcedureFields ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) === 'object') : []
  const procedureRels = showCollectionStatus ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) === 'procedure') : []
  const otherRels = showProcedureFields
    ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) !== 'object')
    : showCollectionStatus
      ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) !== 'procedure')
      : rels
  const schemaRels = otherRels.filter(r => r.is_schema_derived)
  const freeRels = otherRels.filter(r => !r.is_schema_derived)
  const statusOptions = recordType === 'procedure' ? PROCEDURE_STATUSES : STATUSES
  const statusLabels: Record<string, string> = recordType === 'procedure' ? PROCEDURE_STATUS_LABELS : STATUS_LABELS
  const isDraftStatus = status === 'draft'

  function clearFieldFeedback(name: string) {
    setFieldErrors(prev => {
      if (!(name in prev)) return prev
      const next = { ...prev }
      delete next[name]
      return next
    })
    setFieldWarnings(prev => {
      if (!(name in prev)) return prev
      const next = { ...prev }
      delete next[name]
      return next
    })
  }

  function getFeedbackStyle(name: string) {
    if (fieldErrors[name]) return { borderColor: '#dc2626', background: '#fef2f2' }
    if (fieldWarnings[name]) return { borderColor: '#f59e0b', background: '#fffbeb' }
    return undefined
  }

  function renderRelation(r: Relation, schemaBound = false) {
    const typeLabel: Record<string, string> = { object: 'Objekt', entity: 'Entität', place: 'Ort', occurrence: 'Occurrence', procedure: 'Vorgang' }
    const relTypeTerm = relTypeTerms.find(t => t.term === r.relation_type)
    const isFrom = r.from_id === savedId
    const relTypeLabel = relTypeTerm
      ? (isFrom ? getLabel(relTypeTerm, r.relation_type) : (relTypeTerm.inverse_label?.de ?? relTypeTerm.inverse_label?.en ?? getLabel(relTypeTerm, r.relation_type)))
      : r.relation_type
    const targetType = isFrom ? r.to_type : r.from_type
    const targetId = isFrom ? r.to_id : r.from_id
    const targetKey = `${targetType}/${targetId}`
    const sourceField = r.metadata_?.source_field as string | undefined
    const sourceLabel = sourceField ? getLabel(fields.find(f => f.name === sourceField), sourceField) : undefined
    return (
      <div key={r.id}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
          <span style={{ color: 'var(--fg-2)' }} title={r.relation_type}>
            {!isFrom && <span style={{ color: 'var(--accent)', marginRight: 4 }}>←</span>}
            {relTypeLabel}
            {schemaBound && sourceLabel && sourceField && (isFrom ? (
              <button
                type="button"
                onClick={() => jumpToField(sourceField)}
                style={{ display: 'block', padding: 0, border: 0, background: 'none', fontSize: 11, color: 'var(--accent)', textDecoration: 'underline' }}
              >
                Zum Feld: {sourceLabel}
              </button>
            ) : (
              <span style={{ display: 'block', fontSize: 10, color: 'var(--fg-4)' }}>
                Feld im verknüpften Datensatz: {sourceLabel}
              </span>
            ))}
          </span>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={`${targetType}: ${targetId}`}>
            <span style={{ fontSize: 10, color: 'var(--fg-4)', marginRight: 4 }}>{typeLabel[targetType] ?? targetType}</span>
            <a href={`#${TYPE_ROUTES[targetType] ?? targetType}/${targetId}`} onClick={e => { e.preventDefault(); navigateToRecord(targetType, targetId) }} style={{ color: 'inherit', textDecoration: 'none', cursor: 'pointer' }} onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')} onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
              {relTitles[targetKey] ?? targetId.slice(0, 8) + '…'}
            </a>
          </span>
        </div>
      </div>
    )
  }

  // Form variants (#275): a variant filters+reorders the already-loaded field
  // definitions; no variant selected falls back to the full schema (fields as-is).
  const activeVariant = variants.find(v => v.id === activeVariantId) ?? null
  const displayFields = activeVariant
    ? activeVariant.field_names.map(name => fields.find(f => f.name === name)).filter((f): f is FieldDefinition => f != null)
    : fields

  function selectVariant(variantId: string | null) {
    setActiveVariantId(variantId)
    localStorage.setItem(localVariantKey(recordType, subtype), variantId ?? FULL_SCHEMA_CHOICE)
  }

  return (
    <div className={quickCreate ? 'quick-create-form' : undefined} style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className={`record-toolbar${quickCreate ? ' quick-create-toolbar' : ''}`}>
        {!quickCreate && <div className="record-title">{title}</div>}
        <div className="record-actions">
          {!quickCreate && <div className="record-status" role="group" aria-label="Status" data-tour="record-status">
            {statusOptions.map(s => (
              <button key={s} onClick={() => { setStatus(s); setIsDirty(true) }}
                aria-pressed={status === s}
                disabled={justCreated}
                style={{ background: status === s ? 'var(--accent)' : '#fff',
                  color: status === s ? '#fff' : 'var(--fg-2)',
                  borderLeft: s !== 'draft' ? '1px solid var(--border-s)' : undefined }}>
                {statusLabels[s]}
              </button>
            ))}
          </div>}
          {!isNew && recordType !== 'procedure' && loadedStatus === 'public' && (
            <a
              className="btn gh"
              href={`${PORTAL_URL}/${PORTAL_PATH[recordType]}/${recordId}`}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: 'none' }}
            >
              Im Portal ansehen ↗
            </a>
          )}
          <button className="btn gh" onClick={() => {
            if (quickCreate) { onBack?.(); return }
            if (isDirty && !window.confirm('Du hast ungespeicherte Änderungen. Trotzdem verlassen?')) return
            onBack?.()
          }} disabled={saving}>
            {quickCreate ? 'Abbrechen' : justCreated ? 'Zur Liste' : 'Verwerfen'}
          </button>
          {!justCreated && (
            <button className="btn pri" onClick={handleSave} disabled={saving}>
              {saving ? 'Speichert…' : quickCreate ? 'Entwurf anlegen und verknüpfen' : 'Speichern'}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="record-notice" style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca', color: '#b91c1c' }}>
          {error}
          {Object.keys(fieldErrors).length > 0 && (
            <ul style={{ margin: '4px 0 0', paddingLeft: 18, lineHeight: 1.6 }}>
              {Object.values(fieldErrors).map((msg, i) => <li key={i}>{msg}</li>)}
            </ul>
          )}
        </div>
      )}

      {completionDialog && (
        <dialog open style={{ position: 'fixed', inset: 0, margin: 'auto', width: 420, maxWidth: 'calc(100vw - 32px)', border: '1px solid var(--border)', borderRadius: 8, padding: 0, background: 'var(--bg)', color: 'var(--fg)', boxShadow: '0 24px 80px rgba(0,0,0,.24)', zIndex: 20 }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-s)', fontWeight: 700 }}>Vorgang abschließen</div>
          <div style={{ padding: 16, fontSize: 13, lineHeight: 1.5 }}>
            {completionDialog.count} verknüpfte Objekt(e) gefunden. Sammlungsstatus auf <span className="mono">{completionDialog.status}</span> setzen?
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 16px', borderTop: '1px solid var(--border-s)' }}>
            <button className="btn gh" onClick={() => completeProcedure(null)} disabled={saving}>Ohne Statuswechsel</button>
            <button className="btn pri" onClick={() => completeProcedure(completionDialog.status)} disabled={saving}>Status setzen</button>
          </div>
        </dialog>
      )}

      {aiProposal && (
        <AiProposalDialog
          proposal={aiProposal}
          onCancel={() => setAiProposal(null)}
          onApply={value => {
            if (aiProposal.group) updateGroupSubField(aiProposal.group.name, aiProposal.group.index, aiProposal.field.name, value)
            else {
              setValuesDirty(previous => ({ ...previous, [aiProposal.field.name]: value }))
              clearFieldFeedback(aiProposal.field.name)
            }
            setAiProposal(null)
          }}
        />
      )}

      {conflict && (
        <ConflictDialog
          conflict={conflict}
          saving={saving}
          onCancel={() => setConflict(null)}
          onResolve={merged => commitMerge(conflict.basePayload, merged, conflict.serverVersion)}
        />
      )}

      {justCreated && (
        <div className="record-notice" style={{ background: '#f0fdf4', borderBottom: '1px solid #bbf7d0', color: '#166534' }}>
          {label} gespeichert.{showMedia ? ' Bilder können jetzt hochgeladen werden.' : ''}
        </div>
      )}
      {saveOk && (
        <div className="record-notice" style={{ background: saveNotice?.includes('Validierungshinweisen') ? '#fffbeb' : '#f0fdf4', borderBottom: saveNotice?.includes('Validierungshinweisen') ? '1px solid #fcd34d' : '1px solid #bbf7d0', color: saveNotice?.includes('Validierungshinweisen') ? '#92400e' : '#166534' }}>
          {saveNotice ?? 'Änderungen gespeichert.'}
        </div>
      )}

      <div className="scroll">
        <div className={showTwoCol ? 'form-grid' : 'form-single'}>
          <div>
            <div className="card">
              <div className="hd">Metadaten</div>
              <div className="bd">
                {showIdno && (
                  <div className="field">
                    <div className="lbl">ID-Nr. <span className="req">*</span></div>
                    <input
                      className="fld mono"
                      value={idno}
                      onChange={e => { setIdno(e.target.value); setIsDirty(true) }}
                      onBlur={() => {
                        if (!idno.trim()) {
                          if (isDraftStatus) setFieldWarnings(err => ({ ...err, __idno: 'ID-Nr. ist ein Pflichtfeld.' }))
                          else setFieldErrors(err => ({ ...err, __idno: 'ID-Nr. ist ein Pflichtfeld.' }))
                        } else {
                          clearFieldFeedback('__idno')
                        }
                      }}
                      placeholder="z.B. FOT.1958.0412"
                      disabled={justCreated}
                      style={getFeedbackStyle('__idno')}
                    />
                    {(fieldErrors['__idno'] || fieldWarnings['__idno']) && (
                      <div style={{ fontSize: 11, color: fieldErrors['__idno'] ? '#dc2626' : '#92400e', marginTop: 4 }}>
                        {fieldErrors['__idno'] ?? fieldWarnings['__idno']}
                      </div>
                    )}
                  </div>
                )}

                {subtypeKey && availableSubtypes.length > 0 && (
                  <div className="field">
                    <div className="lbl">{recordType === 'procedure' ? 'Vorgangstyp' : recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : 'Occurrence-Typ'}</div>
                    <select
                      className="fld"
                      value={subtype}
                      onChange={e => { setSubtype(e.target.value); setIsDirty(true); clearFieldFeedback('__subtype') }}
                      disabled={justCreated || lockSubtype}
                      style={getFeedbackStyle('__subtype')}
                    >
                      <option value="">— {recordType === 'procedure' ? 'Vorgangstyp' : recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : 'Occurrence-Typ'} wählen —</option>
                      {availableSubtypes.map(s => (
                        <option key={s.id} value={s.name}>{getLabel(s, s.name)}</option>
                      ))}
                    </select>
                    {recordType === 'procedure' && availableSubtypes.find(s => s.name === subtype)?.description.trim() && (
                      <div style={{ color: 'var(--fg-3)', fontSize: 12, lineHeight: 1.4, marginTop: 4 }}>
                        {availableSubtypes.find(s => s.name === subtype)?.description}
                      </div>
                    )}
                    {(fieldErrors['__subtype'] || fieldWarnings['__subtype']) && (
                      <div style={{ fontSize: 11, color: fieldErrors['__subtype'] ? '#dc2626' : '#92400e', marginTop: 4 }}>
                        {fieldErrors['__subtype'] ?? fieldWarnings['__subtype']}
                      </div>
                    )}
                  </div>
                )}

                {showCollectionStatus && (
                  <div className="field">
                    <div className="lbl">Sammlungsstatus</div>
                    <select
                      className="fld"
                      value={collectionStatus}
                      onChange={e => { setCollectionStatus(e.target.value); setIsDirty(true) }}
                      disabled={justCreated}
                    >
                      {COLLECTION_STATUSES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                    </select>
                  </div>
                )}

                {showGeo && (
                  <div className="field">
                    <div className="lbl">Koordinaten</div>
                    <div className="fg-2">
                      <input className="fld mono" value={lat} onChange={e => { setLat(e.target.value); setIsDirty(true) }} placeholder="Breite (lat)" disabled={justCreated} />
                      <input className="fld mono" value={lon} onChange={e => { setLon(e.target.value); setIsDirty(true) }} placeholder="Länge (lon)" disabled={justCreated} />
                    </div>
                  </div>
                )}

                {showProcedureFields && (
                  <>
                    <div className="field">
                      <div className="lbl">Referenznummer</div>
                      <input className="fld mono" value={referenceNumber} onChange={e => { setReferenceNumber(e.target.value); setIsDirty(true) }} disabled={justCreated} />
                    </div>
                    <div className="field">
                      <div className="lbl">Daten</div>
                      <div className="fg-3">
                        <input className="fld mono" type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Startdatum" aria-label="Startdatum" />
                        <input className="fld mono" type="date" value={dueDate} onChange={e => { setDueDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Fälligkeitsdatum" aria-label="Fälligkeitsdatum" />
                        <input className="fld mono" type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Enddatum" aria-label="Enddatum" />
                      </div>
                    </div>
                  </>
                )}

                {variants.length > 0 && (
                  <div className="tabs" style={{ marginBottom: 12 }}>
                    <button className={`tab${activeVariant === null ? ' active' : ''}`} onClick={() => selectVariant(null)}>
                      Vollständig
                    </button>
                    {variants.map(v => (
                      <button key={v.id} className={`tab${activeVariantId === v.id ? ' active' : ''}`} onClick={() => selectVariant(v.id)}>
                        {v.label.de || v.name}
                      </button>
                    ))}
                  </div>
                )}

                {displayFields.map(f => {
                  const val = values[f.name]
                  const repeatable = f.is_repeatable
                  const vals = repeatable ? ((val as string[] | undefined) ?? []) : undefined

                  const pidEntries = f.field_type === 'pid' && repeatable
                    ? ((val as PidEntry[] | undefined) ?? [])
                    : undefined
                  const pidSingle = f.field_type === 'pid' && !repeatable
                    ? ((val as PidEntry | undefined) ?? { value: '', label: '' })
                    : undefined

                  return (
                    <fieldset id={`field-${f.name}`} key={f.id} className="field" disabled={Boolean(f.settings?.is_locked) && !canEditLocked} style={{ border: 0, padding: '6px 8px', margin: '0 -8px', borderRadius: 4, transition: 'background .2s', background: highlightedField === f.name ? 'rgba(30, 58, 138, .10)' : undefined }}>
                      <div className="lbl">
                        {getLabel(f, f.name)}
                        {f.is_required && <span className="req">*</span>}
                        {repeatable && <span className="h">wiederholbar</span>}
                        {Boolean(f.settings?.is_locked) && <span className="h">{canEditLocked ? 'gesperrt · Admin-Bearbeitung' : 'gesperrt'}</span>}
                        {getFieldAiConfig(f) && !f.is_translatable && (
                          <button
                            type="button"
                            className="btn sm gh"
                            style={{ marginLeft: 8, padding: '2px 8px', height: 24 }}
                            onClick={() => runAIForField(f)}
                            disabled={justCreated || !savedId || aiBusyField !== null}
                            title={!savedId ? 'Datensatz zuerst speichern.' : undefined}
                          >
                            <Lightning size={12} /> {aiBusyField === f.name ? 'KI läuft…' : 'KI'}
                          </button>
                        )}
                      </div>

                      {f.is_translatable ? (
                        <TranslatableInput
                          languages={languages}
                          value={(val as Record<string, string> | undefined) ?? {}}
                          onChange={(lang, v) => updateTranslatable(f.name, lang, v)}
                          onRemove={lang => removeTranslatable(f.name, lang)}
                          richtext={f.field_type === 'richtext'}
                          labels={f.label}
                          placeholder={getLabel(f, f.name)}
                          disabled={justCreated}
                          style={getFeedbackStyle(f.name)}
                        />
                      ) : f.field_type === 'vocab' ? (
                        repeatable ? (
                          <>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                              {((val as VocabEntry[] | undefined) ?? []).map((entry, i) => (
                                <span key={i} style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 5,
                                  padding: '3px 8px', borderRadius: 4,
                                  background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
                                }}>
                                  {entry.label}
                                  <button
                                    className="btn sm ico gh"
                                    style={{ marginLeft: 2, padding: 0 }}
                                    onClick={() => removeVocab(f.name, i)}
                                    disabled={justCreated}
                                  >
                                    <X size={10} />
                                  </button>
                                </span>
                              ))}
                            </div>
                            <VocabInput
                              vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                              value={null}
                              onChange={v => { if (v) addVocab(f.name, v) }}
                              disabled={justCreated}
                            />
                          </>
                        ) : (
                          <VocabInput
                            vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                            value={(val as VocabEntry | undefined) ?? null}
                            onChange={v => setVocab(f.name, v)}
                            disabled={justCreated}
                          />
                        )
                      ) : f.field_type === 'vocab_free' ? (
                        repeatable ? (
                          <>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                              {((val as string[] | undefined) ?? []).map((entry, i) => (
                                <span key={i} style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 5,
                                  padding: '3px 8px', borderRadius: 4,
                                  background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
                                }}>
                                  {entry}
                                  <button
                                    className="btn sm ico gh"
                                    style={{ marginLeft: 2, padding: 0 }}
                                    onClick={() => removeFreeVocab(f.name, i)}
                                    disabled={justCreated}
                                  >
                                    <X size={10} />
                                  </button>
                                </span>
                              ))}
                            </div>
                            <VocabFreeInput
                              vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                              onAdd={v => addFreeVocab(f.name, v)}
                              disabled={justCreated}
                              placeholder="Eingeben und Enter drücken oder Vorschlag wählen"
                            />
                          </>
                        ) : (
                          <VocabFreeInput
                            vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                            value={(val as string | undefined) ?? ''}
                            onChange={v => setValues(prev => ({ ...prev, [f.name]: v }))}
                            disabled={justCreated}
                          />
                        )
                      ) : f.field_type === 'authority' ? (
                        repeatable ? (
                          <>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                              {((val as AuthorityEntry[] | undefined) ?? []).map((entry, i) => (
                                <span key={i} style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 5,
                                  padding: '3px 8px', borderRadius: 4,
                                  background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
                                }}>
                                  {entry.label}
                                  <span style={{ fontSize: 10, opacity: 0.6, fontFamily: 'var(--mono)' }}>
                                    {entry.external_id}
                                  </span>
                                  <button
                                    className="btn sm ico gh"
                                    style={{ marginLeft: 2, padding: 0 }}
                                    onClick={() => removeAuthority(f.name, i)}
                                    disabled={justCreated}
                                  >
                                    <X size={10} />
                                  </button>
                                </span>
                              ))}
                            </div>
                            <AuthorityInput
                              source={(f.settings?.source as string) ?? 'gnd'}
                              value={null}
                              onChange={v => { if (v) addAuthority(f.name, v) }}
                              disabled={justCreated}
                            />
                          </>
                        ) : (
                          <AuthorityInput
                            source={(f.settings?.source as string) ?? 'gnd'}
                            value={(val as AuthorityEntry | undefined) ?? null}
                            onChange={v => setAuthority(f.name, v)}
                            disabled={justCreated}
                          />
                        )
                      ) : f.field_type === 'relation' ? (
                        repeatable ? (
                          <>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 6 }}>
                              {((val as RelationEntry[] | undefined) ?? []).map((entry, i) => (
                                <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 8px', borderRadius: 999, background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13 }}>
                                  <span style={{ flex: 1 }}>{entry.label}</span>
                                  <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--mono)' }}>{entry.relation_type}</span>
                                  <button className="btn sm ico gh" onClick={() => removeRelationEntry(f.name, i)} disabled={justCreated} aria-label="Beziehung entfernen" title="Beziehung entfernen"><X size={10} /></button>
                                </div>
                              ))}
                            </div>
                            <RelationInput
                              targetType={(f.settings?.target_type as RecordType) ?? ''}
                              targetSubtype={f.settings?.target_subtype as string | undefined}
                              relTypeVocabId={(f.settings?.relation_type_vocab as string | undefined) ?? relTypeVocabId}
                              fixedRelationType={f.settings?.fixed_relation_type as string | undefined}
                              fromType={recordType}
                              onAdd={entry => addRelationEntry(f.name, entry)}
                              disabled={justCreated}
                            />
                          </>
                        ) : (
                          <>
                            {val && (
                              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 6, padding: '3px 8px', borderRadius: 999, background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13 }}>
                                <span style={{ flex: 1 }}>{(val as RelationEntry).label}</span>
                                <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--mono)' }}>{(val as RelationEntry).relation_type}</span>
                                <button className="btn sm ico gh" onClick={() => setField(f.name, undefined)} disabled={justCreated} aria-label="Beziehung entfernen" title="Beziehung entfernen"><X size={10} /></button>
                              </div>
                            )}
                            {!val && (
                              <RelationInput
                                targetType={(f.settings?.target_type as RecordType) ?? ''}
                                targetSubtype={f.settings?.target_subtype as string | undefined}
                                relTypeVocabId={(f.settings?.relation_type_vocab as string | undefined) ?? relTypeVocabId}
                                fixedRelationType={f.settings?.fixed_relation_type as string | undefined}
                                fromType={recordType}
                                onAdd={entry => setField(f.name, entry)}
                                disabled={justCreated}
                              />
                            )}
                          </>
                        )
                      ) : f.field_type === 'group' ? (
                        <div>
                          {((val as Record<string, unknown>[] | undefined) ?? []).map((instance, i) => (
                            <div key={i} style={{ border: '1px solid var(--border-s)', borderRadius: 6, padding: '10px 12px', marginBottom: 8, position: 'relative', background: 'var(--panel)' }}>
                              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
                                <button className="btn sm ico gh dn" onClick={() => removeGroupInstance(f.name, i)} disabled={justCreated}><X size={12} /></button>
                              </div>
                              {(f.children ?? []).map(sf => (
                                <div key={sf.id} className="field">
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                                    <div className="lbl" style={{ marginBottom: 0, flex: 1 }}>
                                      {getLabel(sf, sf.name)}
                                      {sf.is_required && <span className="req">*</span>}
                                    </div>
                                    {getFieldAiConfig(sf) && (
                                      <button
                                        type="button"
                                        className="btn sm gh"
                                        onClick={() => runAIForGroupSubField(f, sf, i)}
                                        disabled={justCreated || !savedId || aiBusyField !== null}
                                        title={!savedId ? 'Datensatz zuerst speichern, dann KI-Vorschlag erzeugen.' : undefined}
                                      >
                                        <Lightning size={12} /> {aiBusyField === `${f.name}:${i}:${sf.name}` ? 'KI läuft…' : 'KI'}
                                      </button>
                                    )}
                                  </div>
                                  {renderSubFieldInput(sf, instance[sf.name], v => updateGroupSubField(f.name, i, sf.name, v), justCreated)}
                                </div>
                              ))}
                              {(f.children ?? []).length === 0 && (
                                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Keine Sub-Felder definiert.</div>
                              )}
                            </div>
                          ))}
                          <button className="btn sm gh" onClick={() => addGroupInstance(f.name)} disabled={justCreated}>
                            <Plus size={12} /> Eintrag hinzufügen
                          </button>
                        </div>
                      ) : f.field_type === 'pid' ? (
                        repeatable ? (
                          <>
                            <div style={{ marginBottom: 6 }}>
                              <button
                                className="btn sm gh"
                                onClick={() => registerUrn(f.name, true)}
                                disabled={justCreated || !savedId || registeringPidField === f.name}
                                title={!savedId ? 'Datensatz zuerst speichern, dann URN registrieren.' : undefined}
                              >
                                {registeringPidField === f.name ? 'Registriert…' : 'URN registrieren'}
                              </button>
                            </div>
                            {(pidEntries ?? []).map((entry, i) => (
                              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                                <input className="fld mono" value={entry.value}
                                  onChange={e => updatePid(f.name, i, 'value', e.target.value)}
                                  placeholder="URI / ID (z.B. https://d-nb.info/…)"
                                  disabled={justCreated} style={{ flex: 2 }} />
                                <input className="fld" value={entry.label}
                                  onChange={e => updatePid(f.name, i, 'label', e.target.value)}
                                  placeholder="Anzeigebezeichnung"
                                  disabled={justCreated} style={{ flex: 1 }} />
                                <button className="btn sm ico gh" onClick={() => removePid(f.name, i)} disabled={justCreated}><X size={12} /></button>
                              </div>
                            ))}
                            <button className="btn sm gh" onClick={() => addPid(f.name)} disabled={justCreated}>
                              <Plus size={12} /> PID hinzufügen
                            </button>
                          </>
                        ) : (
                          <div style={{ display: 'grid', gap: 6 }}>
                            <div>
                              <button
                                className="btn sm gh"
                                onClick={() => registerUrn(f.name, false)}
                                disabled={justCreated || !savedId || registeringPidField === f.name}
                                title={!savedId ? 'Datensatz zuerst speichern, dann URN registrieren.' : undefined}
                              >
                                {registeringPidField === f.name ? 'Registriert…' : 'URN registrieren'}
                              </button>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <input className="fld mono" value={pidSingle!.value}
                                onChange={e => setField(f.name, { ...pidSingle!, value: e.target.value })}
                                placeholder="URI / ID (z.B. https://d-nb.info/…)"
                                disabled={justCreated} style={{ flex: 2 }} />
                              <input className="fld" value={pidSingle!.label}
                                onChange={e => setField(f.name, { ...pidSingle!, label: e.target.value })}
                                placeholder="Anzeigebezeichnung"
                                disabled={justCreated} style={{ flex: 1 }} />
                            </div>
                          </div>
                        )
                      ) : repeatable ? (
                        <>
                          {(vals ?? []).map((v, i) => (
                            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                              {f.field_type === 'date' ? (
                                <DateInput value={String(v)} onChange={value => updateRepeat(f.name, i, value)} disabled={justCreated} />
                              ) : (
                                <input className="fld" value={v}
                                  type={f.field_type === 'number' ? 'number' : 'text'}
                                  step={f.field_type === 'number' ? 'any' : undefined}
                                  onChange={e => updateRepeat(f.name, i, e.target.value)}
                                  placeholder={getLabel(f, f.name)}
                                  disabled={justCreated} />
                              )}
                              <button className="btn sm ico gh" onClick={() => removeRepeat(f.name, i)} disabled={justCreated}><X size={12} /></button>
                            </div>
                          ))}
                          <button className="btn sm gh" onClick={() => addRepeat(f.name)} disabled={justCreated}>
                            <Plus size={12} /> Weiteren Wert
                          </button>
                        </>
                      ) : f.field_type === 'boolean' ? (
                        <label className="form-checkbox">
                          <input type="checkbox" className="ck"
                            checked={Boolean(val)}
                            onChange={e => setField(f.name, e.target.checked)}
                            disabled={justCreated} />
                          <span style={{ fontSize: 13 }}>{f.label.de}</span>
                        </label>
                      ) : f.field_type === 'date' ? (
                        <DateInput value={(val as string) ?? ''}
                          onChange={value => {
                            setField(f.name, value)
                            clearFieldFeedback(f.name)
                          }}
                          onBlur={() => handleFieldBlur(f)}
                          disabled={justCreated}
                          style={getFeedbackStyle(f.name)} />
                      ) : f.field_type === 'number' ? (
                        <input className="fld"
                          type="number"
                          step="any"
                          value={(val as string) ?? ''}
                          onChange={e => {
                            setField(f.name, e.target.value)
                            clearFieldFeedback(f.name)
                          }}
                          onBlur={() => handleFieldBlur(f)}
                          placeholder={getLabel(f, f.name)}
                          disabled={justCreated}
                          style={getFeedbackStyle(f.name)} />
                      ) : f.field_type === 'richtext' ? (
                        <textarea className="fld" rows={4}
                          value={(val as string) ?? ''}
                          onChange={e => { setField(f.name, e.target.value); clearFieldFeedback(f.name) }}
                          placeholder={getLabel(f, f.name)}
                          disabled={justCreated}
                          style={getFeedbackStyle(f.name)} />
                      ) : (
                        <input className="fld"
                          value={(val as string) ?? ''}
                          onChange={e => {
                            setField(f.name, e.target.value)
                            clearFieldFeedback(f.name)
                          }}
                          onBlur={() => handleFieldBlur(f)}
                          placeholder={getLabel(f, f.name)}
                          disabled={justCreated}
                          style={getFeedbackStyle(f.name)} />
                      )}
                      {(fieldErrors[f.name] || fieldWarnings[f.name]) && (
                        <div style={{ fontSize: 11, color: fieldErrors[f.name] ? '#dc2626' : '#92400e', marginTop: 4 }}>
                          {fieldErrors[f.name] ?? fieldWarnings[f.name]}
                        </div>
                      )}
                    </fieldset>
                  )
                })}

                {displayFields.length === 0 && !showIdno && !subtypeKey && !showGeo && (
                  <div className="empty">Keine Felder definiert. Schema unter Konfiguration → Schemata anlegen.</div>
                )}
                {displayFields.length === 0 && (showIdno || subtypeKey || showGeo) && (
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', paddingTop: 4 }}>
                    Keine weiteren dynamischen Felder. Schema unter Konfiguration → Schemata anlegen.
                  </div>
                )}
              </div>
            </div>
          </div>

          {showTwoCol && (
            <div className="form-side">
              {showMedia && (
                <div className="card media-card" style={{ marginBottom: 14 }} data-tour="media-section">
                  <div className="hd">
                    <span>Medien</span>
                    {mediaFiles.length > 0 && <span className="sub">{mediaFiles.length} Datei{mediaFiles.length !== 1 ? 'en' : ''}</span>}
                  </div>
                  <div className="bd">
                    {mediaFiles.length > 0 && (
                      <div style={{ marginBottom: 12, display: 'grid', gap: 10 }}>
                        {mediaFiles.map(f => (
                          <div key={f.id} style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border-s)', background: 'var(--bg-s)' }}>
                            <button type="button" onClick={() => setLightboxMedia(f)} style={{ display: 'block', width: '100%', overflow: 'hidden', padding: 0, border: 0, cursor: 'zoom-in', background: 'transparent', ...(f.category !== 'audio' ? { aspectRatio: '1' } : {}) }}>
                              {f.status === 'error' ? (
                                <div style={{ width: '100%', aspectRatio: '1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                                  <AlertCircle size={18} style={{ color: '#dc2626' }} />
                                  <span style={{ fontSize: 9, color: '#dc2626' }}>Fehler</span>
                                </div>
                              ) : f._links?.thumbnail ? (
                                <img
                                  src={f._links.thumbnail.href}
                                  alt={f.filename}
                                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                                />
                              ) : f.category === 'video' ? (
                                <div style={{ width: '100%', aspectRatio: '1' }}>
                                  <VideoThumb objectId={savedId!} mediaId={f.id} />
                                </div>
                              ) : f.category === 'audio' ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px' }}>
                                  <Music size={16} style={{ color: 'var(--fg-3)' }} />
                                  <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>Audio</span>
                                </div>
                              ) : f.category === 'pdf' ? (
                                <div style={{ width: '100%', aspectRatio: '1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                                  <FileText size={20} style={{ color: 'var(--fg-3)' }} />
                                  <span style={{ fontSize: 9, color: 'var(--fg-3)' }}>PDF</span>
                                </div>
                              ) : f.category === 'model' ? (
                                <div style={{ width: '100%', aspectRatio: '1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                                  <Box size={20} style={{ color: 'var(--fg-3)' }} />
                                  <span style={{ fontSize: 9, color: 'var(--fg-3)' }}>3D</span>
                                </div>
                              ) : (
                                <div style={{ width: '100%', aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <File size={20} style={{ color: 'var(--fg-3)' }} />
                                </div>
                              )}
                            </button>
                            <div style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={f.filename}>{f.filename}</span>
                              <button
                                className={`btn sm${f.is_primary ? ' pri' : ' gh'}`}
                                style={{ fontSize: 10, padding: '1px 4px', flexShrink: 0 }}
                                onClick={() => handleSetPrimary(f.id)}
                                title={f.is_primary ? 'Primärbild' : 'Als Primärbild setzen'}
                                disabled={f.is_primary}
                              >
                                {f.is_primary ? '★' : '☆'}
                              </button>
                              <button className="btn sm ico gh dn" style={{ padding: '1px 4px' }} onClick={() => handleDeleteMedia(f.id)} title="Löschen"><Trash size={10} /></button>
                            </div>
                            <select
                              className="fld"
                              style={{ fontSize: 10, padding: '2px 4px', height: 22, borderRadius: 0, border: '0 solid var(--border-s)', borderTopWidth: 1 }}
                              value={f.media_type ?? ''}
                              onChange={e => handleSetMediaType(f.id, e.target.value || null)}
                            >
                              <option value="">Typ: —</option>
                              {mediaTypeTerms.map(t => (
                                <option key={t.id} value={t.term}>Typ: {getLabel(t, t.term)}</option>
                              ))}
                            </select>
                            <div style={{ borderTop: '1px solid var(--border-s)' }}>
                              <button type="button" onClick={() => setOpenRightsMediaId(current => current === f.id ? null : f.id)} style={{ width: '100%', padding: '5px 8px', border: 0, background: 'none', textAlign: 'left', fontSize: 10, color: 'var(--fg)' }}>
                                Rechteangaben {openRightsMediaId === f.id ? '⌃' : '⌄'}
                              </button>
                              {(f.license_uri || f.rights_holder?.name) && <div style={{ padding: '0 8px 5px', fontSize: 10, color: 'var(--fg)' }}>{[f.license_uri, f.rights_holder?.name].filter(Boolean).join(' · ')}</div>}
                              {openRightsMediaId === f.id && <div style={{ padding: '0 6px 6px', display: 'grid', gap: 4 }}>
                                <input className="fld" style={{ fontSize: 10, padding: '3px 5px' }} defaultValue={f.license_uri ?? ''} data-media-rights="license_uri" list="media-license-options" placeholder="Lizenz-URI" onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))} />
                                <input className="fld" style={{ fontSize: 10, padding: '3px 5px' }} defaultValue={f.rights_holder?.name ?? ''} data-media-rights="rights_holder_name" placeholder="Rechteinhaber" onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))} />
                                <input className="fld" style={{ fontSize: 10, padding: '3px 5px' }} defaultValue={f.rights_holder?.uri ?? ''} data-media-rights="rights_holder_uri" placeholder="Rechteinhaber-URI" onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))} />
                              </div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {hasSavedId ? (
                      <>
                      <datalist id="media-license-options">
                        {MEDIA_LICENSES.map(([uri, label]) => <option key={uri} value={uri}>{label}</option>)}
                      </datalist>
                      <div
                        className="dz"
                        style={{ padding: '20px 16px', opacity: uploading ? 0.5 : 1, border: dragOver ? '2px dashed var(--accent)' : undefined }}
                        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={onDrop}
                      >
                        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
                          <Upload size={24} style={{ color: 'var(--fg-4)' }} />
                        </div>
                        {uploading ? (
                          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Hochladen…</div>
                        ) : (
                          <>
                            <div style={{ fontSize: 12 }}>Hierher ziehen oder</div>
                            <label className="upload-control">
                              &nbsp;auswählen
                              <input ref={fileInputRef} type="file" style={{ display: 'none' }} accept="image/jpeg,image/png,image/tiff,image/webp,application/pdf,audio/mpeg,audio/wav,audio/ogg,video/mp4,video/webm,model/gltf-binary,.glb" onChange={onFileChange} />
                            </label>
                          </>
                        )}
                        {uploadError && <div style={{ fontSize: 11, color: '#dc2626', marginTop: 6 }}>{uploadError}</div>}
                      </div>
                      </>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--fg-3)', textAlign: 'center', padding: '16px 0' }}>
                        Objekt zuerst speichern, dann Bilder hochladen.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {showCollectionStatus && !isNew && (
                <div className="card procedure-card" style={{ marginBottom: 14, overflow: addProcedureOpen ? 'visible' : undefined }}>
                  <div className="hd">
                    <span>Verknüpfte Vorgänge</span>
                    {procedureRels.length > 0 && <span className="sub">{procedureRels.length}</span>}
                    <div className="grow" />
                    {!addProcedureOpen && hasSavedId && (
                      <button
                        className="btn sm gh"
                        onClick={() => {
                          setAddTargetType('procedure')
                          setAddProcedureOpen(true)
                        }}
                      >
                        <Plus size={12} /> Hinzufügen
                      </button>
                    )}
                  </div>
                  <div className="bd">
                    {procedureRels.length > 0 ? (
                      <div style={{ marginBottom: addProcedureOpen ? 12 : 0 }}>
                        {procedureRels.map(r => {
                          const targetId = r.from_id === savedId ? r.to_id : r.from_id
                          return (
                            <div key={r.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
                              <a
                                href={`#procedures-form/${targetId}`}
                                onClick={e => { e.preventDefault(); navigateToRecord('procedure', targetId) }}
                                style={{ color: 'inherit', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                title={targetId}
                              >
                                {relTitles[`procedure/${targetId}`] ?? targetId.slice(0, 8) + '…'}
                              </a>
                              <button className="btn sm ico gh dn" onClick={() => handleDeleteRelation(r.id)}><Trash size={11} /></button>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="empty" style={{ padding: addProcedureOpen ? '0 0 12px' : '8px 0' }}>Noch keine Vorgänge verknüpft.</div>
                    )}
                    {addProcedureOpen && (
                      <div style={{ borderTop: procedureRels.length > 0 ? '1px solid var(--border-s)' : undefined, paddingTop: procedureRels.length > 0 ? 12 : 0 }}>
                        <RelationInput
                          targetType="procedure"
                          fixedRelationType="concerns"
                          onAdd={entry => handleAddProcedureRelation({ id: entry.id, title: entry.label, record_type: 'procedure', status: 'draft', score: null })}
                        />
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn gh sm" onClick={() => setAddProcedureOpen(false)}>
                            Abbrechen
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {showProcedureFields && !isNew && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Objekte im Vorgang</span>
                    {objectRels.length > 0 && <span className="sub">{objectRels.length}</span>}
                  </div>
                  <div className="bd">
                    {objectRels.length > 0 ? (
                      <div style={{ marginBottom: 12 }}>
                        {objectRels.map(r => {
                          const targetId = r.from_id === savedId ? r.to_id : r.from_id
                          return (
                            <div key={r.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
                              <a
                                href={`#form/${targetId}`}
                                onClick={e => { e.preventDefault(); navigateToRecord('object', targetId) }}
                                style={{ color: 'inherit', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                title={targetId}
                              >
                                {relTitles[`object/${targetId}`] ?? targetId.slice(0, 8) + '…'}
                              </a>
                              <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>{objectStatuses[targetId] || '—'}</span>
                              <button className="btn sm ico gh dn" onClick={() => handleDeleteRelation(r.id)}><Trash size={11} /></button>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="empty" style={{ padding: '8px 0 14px' }}>Noch keine Objekte verknüpft.</div>
                    )}
                    <div className="field" style={{ marginBottom: 0 }}>
                      <div className="lbl">Objekt hinzufügen</div>
                      <RelationInput
                        targetType="object"
                        fixedRelationType="concerns"
                        onAdd={entry => handleAddObjectRelation({ id: entry.id, title: entry.label, record_type: 'object', status: 'draft', score: null })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {!isNew && (
                <div className="card relations-card" style={{ marginBottom: 14 }} data-tour="relations-section">
                  <div className="hd">
                    <span>Beziehungen</span>
                    {otherRels.length > 0 && <span className="sub">{otherRels.length}</span>}
                  </div>
                  <div className="bd">
                    {canManageContent && !genericAddOpen && savedId && (
                      <button className="btn sm gh" style={{ marginBottom: 12 }} onClick={() => setGenericAddOpen(true)}><Plus size={12} /> Freie Beziehung zu anderen Haupttypen hinzufügen</button>
                    )}
                    {schemaRels.length > 0 && (
                      <section style={{ marginBottom: freeRels.length ? 14 : 0 }}>
                        <div className="lbl">Feldgebundene Beziehungen</div>
                        <div className="help" style={{ marginBottom: 6 }}>Diese Beziehungen werden in den entsprechenden Formularfeldern gepflegt.</div>
                        {schemaRels.map(r => renderRelation(r, true))}
                      </section>
                    )}
                    {freeRels.length > 0 && (
                      <section>
                        {schemaRels.length > 0 && <div className="lbl">Weitere Beziehungen</div>}
                        {freeRels.map(r => renderRelation(r))}
                      </section>
                    )}
                    {otherRels.length === 0 && (
                      <div className="empty" style={{ padding: '16px 0' }}>Noch keine Relationen.</div>
                    )}
                    {genericAddOpen && (
                      <div className="generic-relation-picker">
                        <div className="lbl">1&nbsp; Zieltyp</div>
                        <select
                          className="fld"
                          value={addTargetType}
                          onChange={e => setAddTargetType(e.target.value as RecordType)}
                          aria-label="Zieltyp"
                        >
                          {(Object.keys(TYPE_LABELS) as RecordType[]).map(type => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}
                        </select>
                        <div className="lbl" style={{ marginTop: 10 }}>2–3&nbsp; Relationstyp und Datensatz</div>
                        <RelationInput
                          key={addTargetType}
                          targetType={addTargetType}
                          relTypeVocabId={relTypeVocabId}
                          onAdd={handleAddGenericRelation}
                        />
                        <button className="btn gh sm" onClick={() => setGenericAddOpen(false)}>Abbrechen</button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!isNew && savedId && showSnapshotsForRecord && (
                <div className="card">
                  <div className="hd" style={{ cursor: 'pointer' }} onClick={() => setShowSnapshots(s => !s)}>
                    <span>Versionen ({snapshots.length})</span>
                    <div className="grow" />
                    <ChevD size={14} style={{ transform: showSnapshots ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                  </div>
                  {showSnapshots && (
                    <div className="bd" style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <input
                          style={{ flex: 1, fontSize: 12, padding: '4px 8px', border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg)', color: 'var(--fg)' }}
                          placeholder="Bezeichnung (z.B. 'vor Bearbeitung')"
                          value={snapLabel}
                          onChange={e => setSnapLabel(e.target.value)}
                        />
                        <button
                          style={{ fontSize: 12, padding: '4px 10px', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 4, cursor: 'pointer' }}
                          disabled={snapCreating || !snapLabel.trim()}
                          onClick={async () => {
                            if (!snapLabel.trim() || !savedId) return
                            setSnapCreating(true)
                            try {
                              if (!snapshotsApi) return
                              const snap = await snapshotsApi.create(savedId, snapLabel.trim())
                              setSnapshots(s => [snap, ...s])
                              setSnapLabel('')
                            } finally {
                              setSnapCreating(false)
                            }
                          }}
                        >
                          {snapCreating ? '…' : 'Speichern'}
                        </button>
                      </div>
                      {snapshots.length === 0 && (
                        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Noch keine Versionen.</div>
                      )}
                      {snapshots.map(snap => (
                        <div key={snap.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 600 }}>{snap.label}</div>
                            <div style={{ color: 'var(--fg-3)' }}>{new Date(snap.created_at).toLocaleString('de')}</div>
                          </div>
                          <button
                            style={{ fontSize: 11, padding: '3px 8px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer' }}
                            disabled={snapRestoring === snap.id}
                            onClick={async () => {
                              if (!savedId || !window.confirm(`Version „${snap.label}" wiederherstellen?`)) return
                              setSnapRestoring(snap.id)
                              try {
                                if (!snapshotsApi) return
                                const restored = await snapshotsApi.restore(savedId, snap.id, version ?? undefined)
                                setStatus(restored.status as Status)
                                setIdno(restored.idno ?? '')
                                setValues(restored.metadata_ as Record<string, unknown>)
                                setVersion(restored.version)
                                if (showCollectionStatus) {
                                  setCollectionStatus((restored as { collection_status?: string | null }).collection_status ?? 'active')
                                }
                                setBaseValues(restored.metadata_ as Record<string, unknown>)
                                setIsDirty(false)
                              } catch (e) {
                                setError((e as Error).message)
                              } finally {
                                setSnapRestoring(null)
                              }
                            }}
                          >
                            {snapRestoring === snap.id ? '…' : 'Wiederherstellen'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {!isNew && (
                <div className="card">
                  <div className="hd" style={{ cursor: 'pointer' }} onClick={() => {
                    if (!showAudit && savedId) loadAudit(savedId)
                    setShowAudit(a => !a)
                  }}>
                    <span>Audit-Log</span>
                    <div className="grow" />
                    <ChevD size={14} style={{ transform: showAudit ? undefined : 'rotate(-90deg)', transition: 'transform .15s' }} />
                  </div>
                  {showAudit && (
                    <div className="bd" style={{ padding: '8px 0' }}>
                      {auditLoading && <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>Lade…</div>}
                      {!auditLoading && auditEntries.length === 0 && (
                        <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--fg-3)' }}>Keine Einträge.</div>
                      )}
                      {!auditLoading && auditEntries.map(evt => (
                        <div key={evt.id} style={{ padding: '6px 16px', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontWeight: 600 }}>{evt.action}</span>
                            <span style={{ color: 'var(--fg-3)' }}>{new Date(evt.created_at).toLocaleString('de-CH')}</span>
                          </div>
                          <div style={{ color: 'var(--fg-2)' }}>von {evt.user_name ?? evt.user_id ?? '—'}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      {lightboxMedia && savedId && (
        <MediaLightbox objectId={savedId} media={lightboxMedia} onClose={() => setLightboxMedia(null)} />
      )}
    </div>
  )
}
