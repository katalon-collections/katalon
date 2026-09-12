// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useRef, useCallback, useId, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { objects, entities, places, occurrences, procedures, collections, storageLocations, schema, media, vocabularies, relations as relationsApi, search as searchApi, pids, subtypes, idno as idnoApi, formSections, formVariants, PORTAL_URL, ai, getTokenUser, VersionConflictError, authorizedFetch, workingSets, presence, locks, preservationApi } from '../../api/client'
import type { MediaFile, ActivePresence, LockInfo } from '../../api/client'
import { AuthorityInput, GeoNamesMap, type AuthorityEntry } from '../AuthorityInput'
import type { AiProvenance, AnyRecord, AuditEntry, FieldDefinition, FormSection, FormVariant, KatalonCollection, ProcedureStatus, RecordSubtype, RecordType, Relation, SearchResult, Snapshot, Status, VocabularyTerm, VocabularyTermNode, WorkingSet } from '../../types'
import { getLabel } from '../../types'
import { resolveActiveVariant } from '../../lib/formVariants'
import { AlertCircle, Bookmark, Calendar, ChevD, ChevR, ListTree, Plus, Upload, X, Trash, Lightning, File, Music, Video, FileText, Box, Eye, Download } from '../ui/Icons'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'
import { TranslatableInput } from '../ui/TranslatableInput'
import { RichTextEditor } from '../ui/RichTextEditor'
import { MediaLightbox } from '../MediaLightbox'
import { HelpPopover } from '../ui/HelpPopover'
import { AddToWorkingSetModal } from './AddToWorkingSetModal'

const INVALID_DATE_MESSAGE = 'Ungültiges Datum'

function isHttpUrlString(s: unknown): s is string {
  if (typeof s !== 'string' || !s.trim()) return false
  try {
    const url = new URL(s.trim())
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

/** External resolver link for a stored PID value, if one is derivable. */
function pidHref(value: string): string | undefined {
  if (value.startsWith('urn:')) return `https://nbn-resolving.org/${value}`
  if (value.startsWith('ark:')) return `https://n2t.net/${value}`
  if (isHttpUrlString(value)) return value
  return undefined
}

/** Proleptic Gregorian leap rule; also correct for BCE years (year 0 = 1 v. Chr.). */
function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
}

function daysInMonth(year: number, month: number): number {
  return [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
}

/** Normalizes a single (unqualified) date: European dd.mm.yyyy → ISO, BCE year padding. */
function normalizeBareDate(value: string): string {
  const trimmed = value.trim()
  const european = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(trimmed)
  if (european) {
    const [, day, month, year] = european
    const iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
    const parsed = new Date(`${iso}T00:00:00Z`)
    if (parsed.getUTCFullYear() === Number(year) &&
      parsed.getUTCMonth() + 1 === Number(month) &&
      parsed.getUTCDate() === Number(day)) {
      return iso
    }
    return trimmed
  }
  // BCE years: pad the year to 4 digits, e.g. "-43" → "-0043" (44 v. Chr.)
  const bce = /^-(\d{1,4})(-\d{2}(-\d{2})?)?$/.exec(trimmed)
  if (bce) return `-${bce[1].padStart(4, '0')}${bce[2] ?? ''}`
  // CE years under 1000: pad the year to 4 digits, e.g. "100" → "0100"
  const ce = /^(\d{1,4})(-\d{2}(-\d{2})?)?$/.exec(trimmed)
  if (ce) return `${ce[1].padStart(4, '0')}${ce[2] ?? ''}`
  return trimmed
}

/**
 * Normalizes a single date with optional uncertainty qualifier into canonical
 * EDTF-lite form ("1900~" = circa, "1900?" = unsicher, "1900~?" = beides).
 * Accepts German words ("ca.", "um", "(unsicher)") as well as the symbols directly.
 */
function normalizeQualifiedDate(value: string): string {
  let s = value.trim()
  let circa = false
  let uncertain = false
  const unsicher = /^(.*?)\s*\(\s*unsicher\s*\)$/i.exec(s)
  if (unsicher) {
    uncertain = true
    s = unsicher[1].trim()
  }
  if (s.endsWith('?')) {
    uncertain = true
    s = s.slice(0, -1).trim()
  }
  if (s.endsWith('~')) {
    circa = true
    s = s.slice(0, -1).trim()
  }
  const ca = /^(ca\.?|um)\s+(.+)$/i.exec(s)
  if (ca) {
    circa = true
    s = ca[2].trim()
  }
  const bare = normalizeBareDate(s)
  const suffix = circa && uncertain ? '~?' : circa ? '~' : uncertain ? '?' : ''
  return `${bare}${suffix}`
}

/**
 * Normalizes date input into canonical storage form. Supports ranges via "START/END",
 * "START bis END", "vor END" (offener Anfang) and "nach START" (offenes Ende).
 */
function normalizeDateInput(value: string): string {
  const trimmed = value.trim()
  const bis = /^(.*?)\s+bis\s+(.*)$/i.exec(trimmed)
  if (bis) {
    const [, left, right] = bis
    return `${left.trim() ? normalizeQualifiedDate(left) : ''}/${right.trim() ? normalizeQualifiedDate(right) : ''}`
  }
  if (trimmed.split('/').length === 2) {
    const [left, right] = trimmed.split('/')
    return `${left.trim() ? normalizeQualifiedDate(left) : ''}/${right.trim() ? normalizeQualifiedDate(right) : ''}`
  }
  const vor = /^vor\s+(.+)$/i.exec(trimmed)
  if (vor) return `/${normalizeQualifiedDate(vor[1])}`
  const nach = /^nach\s+(.+)$/i.exec(trimmed)
  if (nach) return `${normalizeQualifiedDate(nach[1])}/`
  return normalizeQualifiedDate(trimmed)
}

function isValidDatePart(value: string): boolean {
  if (/^-?\d{4}$/.test(value)) return true
  if (/^-?\d{4}-(0[1-9]|1[0-2])$/.test(value)) return true
  const full = /^(-?\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!full) return false
  const year = Number(full[1])
  const month = Number(full[2])
  const day = Number(full[3])
  return day >= 1 && day <= daysInMonth(year, month)
}

function isValidQualifiedDate(value: string): boolean {
  for (const suffix of ['~?', '~', '?']) {
    if (value.endsWith(suffix)) return isValidDatePart(value.slice(0, -suffix.length))
  }
  return isValidDatePart(value)
}

function isValidDateInput(value: string): boolean {
  const normalized = normalizeDateInput(value)
  if (normalized.includes('/')) {
    const parts = normalized.split('/')
    if (parts.length !== 2) return false
    const [start, end] = parts
    if (!start && !end) return false
    return (start === '' || isValidQualifiedDate(start)) && (end === '' || isValidQualifiedDate(end))
  }
  return isValidQualifiedDate(normalized)
}

function DateInput({ value, onChange, onBlur, disabled, style }: {
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  disabled?: boolean
  style?: CSSProperties
}) {
  const { t } = useTranslation('screenForm')
  const pickerRef = useRef<HTMLInputElement>(null)
  const normalized = normalizeDateInput(value)
  const isPlainDate = /^\d{4}(-\d{2}(-\d{2})?)?$/.test(normalized)
  const pickerValue = /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized : ''
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <input className="fld" type="text" value={value}
        onChange={e => onChange(e.target.value)}
        onBlur={() => { const n = normalizeDateInput(value); if (n !== value) onChange(n); onBlur?.() }}
        placeholder={t('dateInput.placeholder')} disabled={disabled} style={{ flex: 1, ...style }} />
      <button type="button" className="btn sm ico gh" title={isPlainDate ? t('dateInput.pickerTitleEnabled') : t('dateInput.pickerTitleDisabled')}
        disabled={disabled || !isPlainDate} onClick={() => pickerRef.current?.showPicker()}>
        <Calendar size={14} />
      </button>
      <input ref={pickerRef} type="date" value={pickerValue} disabled={disabled}
        onChange={e => onChange(e.target.value)} aria-label={t('dateInput.pickerAriaLabel')}
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

function formatRecordLabel(m: Record<string, unknown>, idno: string | null | undefined, fallback: string): string {
  const label = extractTitle(m, '')
  if (!label) return idno || fallback
  return idno ? `${label} (${idno})` : label
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
  model: string
  group?: { name: string; index: number }
}

/** Disclosure badge for field values populated via the KI-Assistent (Katalon
 *  data-integrity requirement: AI involvement in a field value must be visible
 *  to catalogers, not just logged in the audit trail). */
function AiDisclosureBadge({ model, at }: { model: string; at: string }) {
  return (
    <span
      className="h"
      title={`KI-generiert (${model}) am ${new Date(at).toLocaleString('de')}`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 3, marginLeft: 6, color: 'var(--accent-ink)' }}
    >
      <Lightning size={11} /> KI
    </span>
  )
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
  object: 'objects', entity: 'entities', place: 'places', occurrence: 'occurrences', procedure: 'procedures', collection: 'collections', storage_location: 'storage-locations',
}

const TYPE_LABELS: Record<RecordType, string> = {
  object:     'Objekt',
  entity:     'Entität',
  place:      'Ort',
  occurrence: 'Occurrence',
  procedure:  'Vorgang',
  collection: 'Sammlung',
  storage_location: 'Lagerort',
}

const NEW_TYPE_LABELS: Record<RecordType, string> = {
  object:     'Neues Objekt',
  entity:     'Neue Entität',
  place:      'Neuer Ort',
  occurrence: 'Neue Occurrence',
  procedure:  'Neuer Vorgang',
  collection: 'Neue Sammlung',
  storage_location: 'Neuer Lagerort',
}

const TYPE_ROUTES: Record<string, string> = {
  object: 'form', entity: 'entities-form', place: 'places-form', occurrence: 'occurrences-form', procedure: 'procedures-form', collection: 'collections-form', storage_location: 'storage-locations',
}

function navigateToRecord(type: string, id: string) {
  const route = TYPE_ROUTES[type]
  if (!route) return
  window.history.pushState({ route, editId: id }, '', `#${route}/${id}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function procedureSearchResult(proc: AnyRecord): SearchResult {
  const idno = (proc as { idno?: string | null }).idno ?? null
  const label = extractTitle(proc.metadata_ as Record<string, unknown>, '') || idno || proc.id.slice(0, 8) + '…'
  return {
    id: proc.id,
    record_type: 'procedure',
    title: label,
    idno,
    status: (proc as { status?: string | null }).status ?? null,
    score: null,
  }
}

function recordSearchResult(recordType: RecordType, record: AnyRecord): SearchResult {
  const idno = (record as { idno?: string | null }).idno ?? null
  const label = extractTitle(record.metadata_ as Record<string, unknown>, '') || idno || record.id.slice(0, 8) + '…'
  return {
    id: record.id,
    record_type: recordType,
    title: label,
    idno,
    status: (record as { status?: string | null }).status ?? null,
    score: null,
  }
}

export async function searchRecords(targetType: RecordType, q: string, targetSubtype?: string): Promise<SearchResult[]> {
  const trimmed = q.trim()
  if (targetType === 'storage_location') {
    return (await storageLocations.list({ q: trimmed || undefined, storage_location_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
  }
  if (targetType === 'procedure') {
    return (await procedures.list({ q: trimmed || undefined, procedure_type: targetSubtype, page_size: 20 })).items.map(procedureSearchResult)
  }
  if (targetType === 'collection') {
    return (await collections.list({ q: trimmed || undefined, collection_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
  }
  if (!trimmed) {
    switch (targetType) {
      case 'object':
        return (await objects.list({ object_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
      case 'entity':
        return (await entities.list({ entity_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
      case 'place':
        return (await places.list({ place_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
      case 'occurrence':
        return (await occurrences.list({ occurrence_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
    }
  }
  if (!targetSubtype) {
    try {
      const searchRes = await searchApi.query(trimmed, targetType, 20)
      if (searchRes.items.length > 0) return searchRes.items
    } catch {
      // Fallback to direct DB list endpoint below
    }
  }
  switch (targetType) {
    case 'object':
      return (await objects.list({ q: trimmed || undefined, object_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
    case 'entity':
      return (await entities.list({ q: trimmed || undefined, entity_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
    case 'place':
      return (await places.list({ q: trimmed || undefined, place_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
    case 'occurrence':
      return (await occurrences.list({ q: trimmed || undefined, occurrence_type: targetSubtype, page_size: 20 })).items.map(r => recordSearchResult(targetType, r))
  }
}

const SUBTYPE_KEY: Partial<Record<RecordType, string>> = {
  object:     'object_type',
  entity:     'entity_type',
  place:      'place_type',
  occurrence: 'occurrence_type',
  procedure:  'procedure_type',
  collection: 'collection_type',
  storage_location: 'storage_location_type',
}

export type VocabEntry = { id: string; label: string }
export type RelationEntry = { id: string; label: string; relation_type: string }
type VocabSuggestion = { term: VocabularyTerm; depth: number }

function orderVocabSuggestions(terms: VocabularyTerm[]): VocabSuggestion[] {
  const byId = new Map(terms.map(term => [term.id, term]))
  const children = new Map<string, VocabularyTerm[]>()
  const roots = terms.filter(term => !term.parent_id || !byId.has(term.parent_id))
  for (const term of terms) {
    if (term.parent_id && byId.has(term.parent_id)) {
      children.set(term.parent_id, [...(children.get(term.parent_id) ?? []), term])
    }
  }

  const suggestions: VocabSuggestion[] = []
  const visit = (term: VocabularyTerm, depth: number) => {
    suggestions.push({ term, depth })
    children.get(term.id)?.forEach(child => visit(child, depth + 1))
  }
  roots.forEach(term => visit(term, 0))
  return suggestions
}

type VocabPickerMode = 'search' | 'tree'

/** Lazily loads and caches the vocabulary tree (browse mode of the vocab pickers). */
function useVocabTree(vocabId: string) {
  const [roots, setRoots] = useState<VocabularyTermNode[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const load = useCallback(() => {
    if (!vocabId || roots !== null || loading) return
    setLoading(true)
    vocabularies.tree(vocabId)
      .then(setRoots)
      .catch(() => setRoots([]))
      .finally(() => setLoading(false))
  }, [vocabId, roots, loading])
  useEffect(() => {
    setRoots(null)
    setExpanded(new Set())
  }, [vocabId])
  const toggle = useCallback((id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  return { roots, loading, load, expanded, toggle }
}

function VocabTreeRows({ nodes, depth, expanded, onToggle, onPick }: {
  nodes: VocabularyTermNode[]
  depth: number
  expanded: Set<string>
  onToggle: (id: string) => void
  onPick: (node: VocabularyTermNode) => void
}) {
  const { t } = useTranslation('screenForm')
  return (
    <>
      {nodes.map(node => (
        <div key={node.id}>
          <div className="authority-hit" style={{ display: 'flex', alignItems: 'center', gap: 2, paddingLeft: depth * 16, borderBottom: '1px solid var(--border)' }}>
            {node.children.length > 0 ? (
              <button
                type="button"
                onMouseDown={e => { e.preventDefault(); onToggle(node.id) }}
                aria-label={expanded.has(node.id) ? t('vocabPicker.collapse') : t('vocabPicker.expand')}
                aria-expanded={expanded.has(node.id)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                  display: 'inline-flex', color: 'var(--fg-3)',
                  transform: expanded.has(node.id) ? 'rotate(90deg)' : 'none', transition: 'transform .12s',
                }}
              >
                <ChevR size={12} />
              </button>
            ) : (
              <span style={{ width: 20 }} />
            )}
            <button
              type="button"
              onMouseDown={e => { e.preventDefault(); onPick(node) }}
              style={{ flex: 1, minWidth: 0, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: '6px 8px 6px 0' }}
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{getLabel(node)}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{node.term}</div>
            </button>
          </div>
          {expanded.has(node.id) && node.children.length > 0 && (
            <VocabTreeRows nodes={node.children} depth={depth + 1} expanded={expanded} onToggle={onToggle} onPick={onPick} />
          )}
        </div>
      ))}
    </>
  )
}

function VocabPickerTabs({ mode, onModeChange }: {
  mode: VocabPickerMode
  onModeChange: (m: VocabPickerMode) => void
}) {
  const { t } = useTranslation('screenForm')
  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 1, display: 'flex', gap: 2, padding: 4, background: 'var(--panel)', borderBottom: '1px solid var(--border)' }}>
      {(['search', 'tree'] as const).map(m => (
        <button
          key={m}
          type="button"
          onMouseDown={e => { e.preventDefault(); onModeChange(m) }}
          style={{
            flex: 1, padding: '4px 8px', fontSize: 12, borderRadius: 4, border: 'none', cursor: 'pointer',
            background: mode === m ? 'var(--accent-50)' : 'none',
            color: mode === m ? 'var(--accent-ink)' : 'var(--fg-3)',
            fontWeight: mode === m ? 600 : 400,
          }}
        >
          {m === 'search' ? t('vocabPicker.searchTab') : t('vocabPicker.treeTab')}
        </button>
      ))}
    </div>
  )
}

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

function VocabInput({ vocabId, value, onChange, disabled, autoFocus, onCancel }: {
  vocabId: string
  value: VocabEntry | null
  onChange: (v: VocabEntry | null) => void
  disabled?: boolean
  autoFocus?: boolean
  onCancel?: () => void
}) {
  const { t } = useTranslation('screenForm')
  const [q, setQ] = useState('')
  const [results, setResults] = useState<VocabSuggestion[]>([])
  const [ancestorPath, setAncestorPath] = useState('')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<VocabPickerMode>('search')
  const { roots, loading: treeLoading, load: loadTree, expanded, toggle: toggleExpand } = useVocabTree(vocabId)
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

  const updateDropPosition = useCallback(() => {
    if (!inputRef.current) return
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
  }, [])

  useEffect(() => {
    if (!open) return
    updateDropPosition()
    window.addEventListener('resize', updateDropPosition)
    window.addEventListener('scroll', updateDropPosition, true)
    return () => {
      window.removeEventListener('resize', updateDropPosition)
      window.removeEventListener('scroll', updateDropPosition, true)
    }
  }, [open, updateDropPosition])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!vocabId) { setResults([]); setOpen(false); return }
    if (mode === 'tree') return
    const isFocused = document.activeElement === inputRef.current
    if (!isFocused && !open) return
    timer.current = setTimeout(() => {
      setBusy(true)
      vocabularies.searchTerms(vocabId, q.trim())
        .then(r => {
          setResults(orderVocabSuggestions(r))
          updateDropPosition()
          if (document.activeElement === inputRef.current) {
            setOpen(r.length > 0)
          }
        })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [q, vocabId, open, mode, updateDropPosition])

  useEffect(() => {
    if (!value) {
      setAncestorPath('')
      return
    }
    let current = true
    vocabularies.ancestors(vocabId, value.id)
      .then(ancestors => { if (current) setAncestorPath(ancestors.map(term => getLabel(term)).join(' › ')) })
      .catch(() => { if (current) setAncestorPath('') })
    return () => { current = false }
  }, [value?.id, vocabId])

  function openSuggestions() {
    if (!vocabId) return
    updateDropPosition()
    setBusy(true)
    vocabularies.searchTerms(vocabId, q.trim())
      .then(r => {
        setResults(orderVocabSuggestions(r))
        updateDropPosition()
        if (document.activeElement === inputRef.current) {
          setOpen(r.length > 0)
        }
      })
      .catch(() => { setResults([]); setOpen(false) })
      .finally(() => setBusy(false))
  }
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus()
      openSuggestions()
    }
  }, [autoFocus])

  function openTree() {
    if (!vocabId) return
    setMode('tree')
    updateDropPosition()
    loadTree()
    setOpen(true)
  }

  function handleActivate() {
    if (mode === 'tree') openTree()
    else openSuggestions()
  }

  function handleModeChange(m: VocabPickerMode) {
    setMode(m)
    if (m === 'tree') loadTree()
    else if (results.length === 0) openSuggestions()
  }

  function pick(term: Pick<VocabularyTerm, 'id' | 'label'>) {
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
          {ancestorPath ? `${ancestorPath} › ${value.label}` : value.label}
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
      <div style={{ display: 'flex', gap: 4 }}>
        <input
          ref={inputRef}
          className="fld"
          style={{ flex: 1 }}
          value={q}
          onChange={e => { setQ(e.target.value); setMode('search') }}
          onFocus={handleActivate}
          onClick={handleActivate}
          onBlur={e => {
            if (dropRef.current?.contains(e.relatedTarget as Node)) return
            setOpen(false)
          }}
          onKeyDown={e => {
            if (e.key === 'Escape') {
              setOpen(false)
              setResults([])
              onCancel?.()
            }
          }}
          autoFocus={autoFocus}
          placeholder={vocabId ? 'Tippen zum Suchen…' : 'Kein Vokabular zugewiesen'}
          disabled={disabled || !vocabId}
        />
        <button
          type="button"
          className="btn sm ico gh"
          title={t('vocabPicker.browseTitle')}
          onMouseDown={e => { e.preventDefault(); openTree() }}
          disabled={disabled || !vocabId}
        >
          <ListTree size={14} />
        </button>
      </div>
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {open && dropPos && (mode === 'tree' || results.length > 0) && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          <VocabPickerTabs mode={mode} onModeChange={handleModeChange} />
          {mode === 'search' ? results.map(({ term, depth }) => (
            <button
              key={term.id}
              onMouseDown={e => { e.preventDefault(); pick(term) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: `8px 12px 8px ${12 + depth * 16}px`, border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{getLabel(term)}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{term.term}</div>
            </button>
          )) : roots === null ? (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--fg-3)' }}>{treeLoading ? t('vocabPicker.loading') : ''}</div>
          ) : roots.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--fg-3)' }}>{t('vocabPicker.empty')}</div>
          ) : (
            <VocabTreeRows nodes={roots} depth={0} expanded={expanded} onToggle={toggleExpand} onPick={pick} />
          )}
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
function VocabFreeInput({ vocabId, value, onChange, onAdd, disabled, placeholder, autoFocus, onCancel }: {
  vocabId: string
  value?: string
  onChange?: (v: string) => void
  onAdd?: (v: string) => void
  disabled?: boolean
  placeholder?: string
  autoFocus?: boolean
  onCancel?: () => void
}) {
  const { t } = useTranslation('screenForm')
  const [draft, setDraft] = useState(value ?? '')
  const [results, setResults] = useState<VocabSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<VocabPickerMode>('search')
  const { roots, loading: treeLoading, load: loadTree, expanded, toggle: toggleExpand } = useVocabTree(vocabId)
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
    if (!open) return
    updateDropPosition()
    window.addEventListener('resize', updateDropPosition)
    window.addEventListener('scroll', updateDropPosition, true)
    return () => {
      window.removeEventListener('resize', updateDropPosition)
      window.removeEventListener('scroll', updateDropPosition, true)
    }
  }, [open, updateDropPosition])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!vocabId) { setResults([]); setOpen(false); return }
    if (mode === 'tree') return
    const isFocused = document.activeElement === inputRef.current
    if (!isFocused && !open) return
    timer.current = setTimeout(() => {
      setBusy(true)
      vocabularies.searchTerms(vocabId, draft.trim())
        .then(r => {
          setResults(orderVocabSuggestions(r))
          updateDropPosition()
          if (document.activeElement === inputRef.current) {
            setOpen(r.length > 0)
          }
        })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [draft, vocabId, open, mode, updateDropPosition])

  function openSuggestions() {
    if (!vocabId) return
    updateDropPosition()
    setBusy(true)
    vocabularies.searchTerms(vocabId, draft.trim())
      .then(r => {
        setResults(orderVocabSuggestions(r))
        updateDropPosition()
        if (document.activeElement === inputRef.current) {
          setOpen(r.length > 0)
        }
      })
      .catch(() => { setResults([]); setOpen(false) })
      .finally(() => setBusy(false))
  }
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus()
      openSuggestions()
    }
  }, [autoFocus])


  function openTree() {
    if (!vocabId) return
    setMode('tree')
    updateDropPosition()
    loadTree()
    setOpen(true)
  }

  function handleActivate() {
    if (mode === 'tree') openTree()
    else openSuggestions()
  }

  function handleModeChange(m: VocabPickerMode) {
    setMode(m)
    if (m === 'tree') loadTree()
    else if (results.length === 0) openSuggestions()
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

  function pick(term: Pick<VocabularyTerm, 'label'>) {
    commit(getLabel(term))
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', gap: 4 }}>
        <input
          ref={inputRef}
          className="fld"
          style={{ flex: 1 }}
          value={draft}
          onChange={e => {
            setDraft(e.target.value)
            setMode('search')
            if (!onAdd) onChange?.(e.target.value)
          }}
          onFocus={handleActivate}
          onClick={handleActivate}
          onBlur={e => {
            if (dropRef.current?.contains(e.relatedTarget as Node)) return
            setOpen(false)
          }}
          onKeyDown={e => {
            if (e.key === 'Enter') { e.preventDefault(); commit(draft) }
            if (e.key === 'Escape') {
              setOpen(false)
              setResults([])
              onCancel?.()
            }
          }}
          autoFocus={autoFocus}
          placeholder={placeholder ?? (vocabId ? 'Tippen zum Suchen oder frei eingeben…' : 'Freitext eingeben')}
          disabled={disabled}
        />
        <button
          type="button"
          className="btn sm ico gh"
          title={t('vocabPicker.browseTitle')}
          onMouseDown={e => { e.preventDefault(); openTree() }}
          disabled={disabled || !vocabId}
        >
          <ListTree size={14} />
        </button>
      </div>
      {busy && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {open && dropPos && (mode === 'tree' || results.length > 0) && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          <VocabPickerTabs mode={mode} onModeChange={handleModeChange} />
          {mode === 'search' ? results.map(({ term, depth }) => (
            <button
              key={term.id}
              onMouseDown={e => { e.preventDefault(); pick(term) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: `8px 12px 8px ${12 + depth * 16}px`, border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{getLabel(term)}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{term.term}</div>
            </button>
          )) : roots === null ? (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--fg-3)' }}>{treeLoading ? t('vocabPicker.loading') : ''}</div>
          ) : roots.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--fg-3)' }}>{t('vocabPicker.empty')}</div>
          ) : (
            <VocabTreeRows nodes={roots} depth={0} expanded={expanded} onToggle={toggleExpand} onPick={pick} />
          )}
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
    window.addEventListener('scroll', updateDropPosition, true)
    return () => {
      window.removeEventListener('resize', updateDropPosition)
      window.removeEventListener('scroll', updateDropPosition, true)
    }
  }, [showDrop, updateDropPosition])

  useEffect(() => {
    if (!targetType) {
      setResults([])
      return
    }
    let active = true
    setSearching(true)
    searchRecords(targetType as RecordType, '', targetSubtype)
      .then(items => {
        if (active) setResults(items)
      })
      .catch(() => {
        if (active) setResults([])
      })
      .finally(() => {
        if (active) setSearching(false)
      })
    return () => { active = false }
  }, [targetType, targetSubtype])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!targetType) return
    const isFocused = document.activeElement === inputRef.current
    if (!isFocused && !showDrop) return
    timer.current = setTimeout(() => {
      setSearching(true)
      searchRecords(targetType as RecordType, q.trim(), targetSubtype)
        .then(items => {
          setResults(items)
          updateDropPosition()
          if (document.activeElement === inputRef.current) {
            setShowDrop(true)
          }
        })
        .catch(() => setResults([]))
        .finally(() => setSearching(false))
    }, 250)
    return () => clearTimeout(timer.current)
  }, [q, targetType, targetSubtype, showDrop, updateDropPosition])

  function openSuggestions() {
    if (!targetType) return
    updateDropPosition()
    if (document.activeElement === inputRef.current) {
      setShowDrop(true)
    }
    if (results.length === 0 && !searching) {
      setSearching(true)
      searchRecords(targetType as RecordType, q.trim(), targetSubtype)
        .then(items => {
          setResults(items)
          updateDropPosition()
          if (document.activeElement === inputRef.current) {
            setShowDrop(true)
          }
        })
        .catch(() => {
          setResults([])
        })
        .finally(() => setSearching(false))
    }
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
            onClick={openSuggestions}
            onBlur={e => {
              if (dropRef.current?.contains(e.relatedTarget as Node)) return
              setShowDrop(false)
            }}
            onKeyDown={e => { if (e.key === 'Escape') setShowDrop(false) }}
            placeholder={targetType ? `${TYPE_LABELS[targetType as RecordType] ?? targetType} suchen…` : 'Kein Ziel-Typ konfiguriert'}
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
                  {(() => {
                    const match = r.title.match(/^(.*?)\s+\(([^)]+)\)$/)
                    const displayTitle = match ? match[1] : r.title
                    const displayId = r.idno || (match ? match[2] : null)
                    return (
                      <>
                        <div style={{ fontWeight: 500, fontSize: 13 }}>{displayTitle}</div>
                        <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                          {displayId && displayId !== displayTitle ? displayId : `${r.id.slice(0, 8)}…`}
                        </div>
                      </>
                    )
                  })()}
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
    case 'collection': return collections
    case 'storage_location': return storageLocations
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
  initialParentId?: string | null
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

/** Thumbnails go through the auth-protected redirect endpoint, not a plain <img src> to Cantoloupe —
 * nginx gates /iiif/ behind the caller's identity, and a bare <img> tag can't send the bearer token. */
function ImageThumb({ objectId, mediaId, alt }: { objectId: string; mediaId: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    authorizedFetch(`/v1/objects/${objectId}/media/${mediaId}/thumbnail`)
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

  if (!url) return null
  return <img src={url} alt={alt} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
}

export function ScreenForm({ recordType, recordId, onBack, onSaved, onDirtyChange, variantHint, quickCreate = false, initialSubtype, lockSubtype = false, initialLabel, onCreated, initialParentId }: Props) {
  const { t } = useTranslation('screenForm')
  const isNew = !recordId || recordId === 'new'
  const currentId = isNew ? null : recordId!
  const api = getApi(recordType)
  const snapshotsApi = recordType === 'object' ? objects.snapshots
    : recordType === 'entity' ? entities.snapshots
    : recordType === 'place' ? places.snapshots
    : recordType === 'occurrence' ? occurrences.snapshots
    : recordType === 'collection' ? collections.snapshots
    : null
  const label = TYPE_LABELS[recordType]
  const subtypeKey = SUBTYPE_KEY[recordType]
  const showIdno  = true
  const showMedia = recordType === 'object' && !quickCreate
  const showGeo   = recordType === 'place'
  const showProcedureFields = recordType === 'procedure'
  const showSnapshotsForRecord = recordType !== 'procedure'
  const showCollectionStatus = recordType === 'object'
  const showParentCollection = recordType === 'collection'
  const [parentId, setParentId] = useState<string | null>(initialParentId ?? null)
  const [availableParents, setAvailableParents] = useState<Array<{ id: string; title: string }>>([])
  const [availableCollections, setAvailableCollections] = useState<Array<{ id: string; title: string }>>([])
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('')
  const user = getTokenUser()
  const features = user?.features ?? []
  const canEditLocked = user?.role === 'admin' || user?.role === 'superuser'
  const canManageContent = !user || user.role === 'viewer' ? false : features.includes('import') || user.role === 'admin' || user.role === 'superuser'

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [sections, setSections] = useState<FormSection[]>([])
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null)
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
  const [aiProvenance, setAiProvenance] = useState<AiProvenance>({})
  const languages = useSupportedLanguages()
  // Optimistic locking (#272): version loaded with the record + the metadata as
  // loaded (base), so a save conflict can be resolved field-by-field.
  const [version, setVersion] = useState<number | null>(null)
  const [baseValues, setBaseValues] = useState<Record<string, unknown>>({})
  // Presence Lock (#371): heartbeat while an existing record is open for editing.
  const [otherEditors, setOtherEditors] = useState<ActivePresence[]>([])
  // Manual Exclusive Lock (#371, Phase 2): persistent lock set by the user.
  const [manualLock, setManualLock] = useState<LockInfo | null>(null)
  const [lockLoading, setLockLoading] = useState(false)
  const [showLockModal, setShowLockModal] = useState(false)
  const [lockReason, setLockReason] = useState('')
  const [lockExpires, setLockExpires] = useState('')
  const [lockModalError, setLockModalError] = useState<string | null>(null)
  useEffect(() => {
    if (isNew || !recordId) return
    let cancelled = false
    const tick = () => {
      presence.heartbeat(recordType, recordId).then(others => {
        if (!cancelled) setOtherEditors(others)
      }).catch(() => {})
    }
    tick()
    const interval = window.setInterval(tick, 25000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
      setOtherEditors([])
      presence.release(recordType, recordId).catch(() => {})
    }
  }, [recordType, recordId, isNew])
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
  const [addingRepeatableField, setAddingRepeatableField] = useState<string | null>(null)
  const [title, setTitle]     = useState(isNew ? NEW_TYPE_LABELS[recordType] : '…')

  const [mediaFiles, setMediaFiles]     = useState<MediaFile[]>([])
  const [uploading, setUploading]       = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number; fraction: number; phase: 'sending' | 'processing' } | null>(null)
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

  const [assignedWorkingSets, setAssignedWorkingSets] = useState<WorkingSet[]>([])
  const [workingSetsDropdownOpen, setWorkingSetsDropdownOpen] = useState(false)
  const [addToWorkingSetOpen, setAddToWorkingSetOpen] = useState(false)
  const workingSetsDropdownRef = useRef<HTMLDivElement>(null)

  const loadAssignedWorkingSets = useCallback(async () => {
    if (isNew || !currentId) {
      setAssignedWorkingSets([])
      return
    }
    try {
      const sets = await workingSets.list({ record_id: currentId })
      setAssignedWorkingSets(sets)
    } catch {
      setAssignedWorkingSets([])
    }
  }, [isNew, currentId])

  useEffect(() => {
    loadAssignedWorkingSets()
  }, [loadAssignedWorkingSets])

  useEffect(() => {
    if (!workingSetsDropdownOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (workingSetsDropdownRef.current && !workingSetsDropdownRef.current.contains(e.target as Node)) {
        setWorkingSetsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [workingSetsDropdownOpen])

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
  const [hasStorageLocations, setHasStorageLocations] = useState(false)
  const [addLocationOpen, setAddLocationOpen] = useState(false)

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
      const objectIds: string[] = []
      for (const r of loaded) {
        const isFrom = r.from_id === id
        const targetType = isFrom ? r.to_type : r.from_type
        const targetId = isFrom ? r.to_id : r.from_id
        const label = isFrom ? r.to_label : r.from_label
        titleMap[`${targetType}/${targetId}`] = label ?? 'Nicht verfügbar'
        if (targetType === 'object') objectIds.push(targetId)
      }
      setRelTitles(titleMap)
      const statusMap: Record<string, string> = {}
      await Promise.all(objectIds.map(async targetId => {
        try {
          const rec = await objects.get(targetId)
          statusMap[targetId] = rec.collection_status ?? 'active'
        } catch {
          // target inaccessible — status badge just stays unset
        }
      }))
      setObjectStatuses(statusMap)
      if (recordType === 'object') {
        const colRel = fromRels.find(r => r.to_type === 'collection' && r.relation_type === 'member_of')
        setSelectedCollectionId(colRel ? colRel.to_id : '')
      }
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

    if (showParentCollection) {
      collections.list({ page_size: 100 }).then(res => {
        setAvailableParents(res.items.map(c => ({
          id: c.id,
          title: formatRecordLabel(c.metadata_ as Record<string, unknown>, c.idno, c.id.slice(0, 8) + '…'),
        })))
      }).catch(() => {})
    }

    if (recordType === 'object') {
      collections.list({ page_size: 100 }).then(res => {
        setAvailableCollections(res.items.map(c => ({
          id: c.id,
          title: formatRecordLabel(c.metadata_ as Record<string, unknown>, c.idno, c.id.slice(0, 8) + '…'),
        })))
      }).catch(() => {})
    }
    if (isNew && initialParentId) {
      setParentId(initialParentId)
    }

    const loadRecP = isNew ? Promise.resolve(null) : (api.get as (id: string) => Promise<AnyRecord>)(recordId!)

    loadRecP
      .then(async rec => {
        let recSubtype: string | undefined = isNew ? initialSubtype : undefined
        if (rec) {
          setStatus((rec as { status?: string }).status as Status)
          setLoadedStatus((rec as { status?: string }).status as Status)
          setValues(rec.metadata_)
          setAiProvenance('ai_provenance' in rec ? rec.ai_provenance : {})
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
          if (showParentCollection) {
            setParentId((rec as KatalonCollection).parent_id ?? null)
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
        // Load manual lock info after record data
        if (rec && !isNew) {
          locks.get(recordType, rec.id).then(setManualLock).catch(() => {})
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
        const resolved = resolveActiveVariant(variantList, user?.role ?? '', variantHint)
        setActiveVariantId(resolved?.id ?? null)
        const sectionList = await formSections.list(recordType, recSubtype).catch(() => [])
        setSections(sectionList)
        setActiveSectionId(sectionList[0]?.id ?? null)
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
      const resolved = resolveActiveVariant(variantList, user?.role ?? '', variantHint)
      setActiveVariantId(resolved?.id ?? null)
    }).catch(() => setVariants([]))
    formSections.list(recordType, subtype).then(sectionList => {
      setSections(sectionList)
      setActiveSectionId(sectionList[0]?.id ?? null)
    }).catch(() => { setSections([]); setActiveSectionId(null) })
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

  useEffect(() => {
    if (recordType !== 'object') return
    storageLocations.list({ page_size: 1 }).then(page => setHasStorageLocations(page.total > 0)).catch(() => {})
  }, [recordType])

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

  async function handleAddLocationRelation(entry: RelationEntry) {
    if (!savedId) return
    const duplicate = rels.some(r => {
      const isFrom = r.from_id === savedId
      return (isFrom ? r.to_type : r.from_type) === 'storage_location'
        && (isFrom ? r.to_id : r.from_id) === entry.id
        && r.relation_type === entry.relation_type
    })
    if (duplicate) throw new Error('Diese Beziehung besteht bereits.')
    const created = await relationsApi.create({
      from_type: recordType,
      from_id: savedId,
      to_type: 'storage_location',
      to_id: entry.id,
      relation_type: entry.relation_type,
    })
    setRels(prev => [...prev, created])
    setRelTitles(prev => ({ ...prev, [`storage_location/${entry.id}`]: entry.label }))
    setAddLocationOpen(false)
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

  async function handleLockToggle() {
    if (!currentId || lockLoading) return
    setLockLoading(true)
    try {
      if (manualLock) {
        if (manualLock.locked_by_email === user?.email) {
          await locks.release(recordType, currentId)
          setManualLock(null)
        } else if (user?.role === 'admin' || user?.role === 'superuser') {
          await locks.forceUnlock(recordType, currentId)
          setManualLock(null)
        }
      } else {
        setLockReason('')
        setLockExpires('')
        setLockModalError(null)
        setShowLockModal(true)
      }
    } catch (e) { setError((e as Error).message) }
    finally { setLockLoading(false) }
  }

  async function handleLockSubmit() {
    if (!currentId) return
    setLockLoading(true)
    setLockModalError(null)
    try {
      const lock = await locks.set(recordType, currentId, lockReason, lockExpires ? new Date(lockExpires + 'T23:59:59').toISOString() : undefined)
      setManualLock(lock)
      setShowLockModal(false)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Fehler beim Sperren'
      setLockModalError(msg)
    } finally {
      setLockLoading(false)
    }
  }

  // All user-triggered value mutations go through this wrapper to mark the form dirty
  const setValuesDirty: typeof setValues = (fn) => { setValues(fn); setIsDirty(true) }

  // Manual edits invalidate the KI-Assistent disclosure for that field path;
  // only the explicit AI-apply call sites re-add an entry (see markAiProvenance).
  function clearAiProvenance(path: string) {
    setAiProvenance(prev => {
      if (!(path in prev)) return prev
      const next = { ...prev }
      delete next[path]
      return next
    })
  }
  function markAiProvenance(path: string, model: string) {
    setAiProvenance(prev => ({ ...prev, [path]: { model, at: new Date().toISOString() } }))
  }
  function setField(name: string, value: unknown) { setValuesDirty(v => ({ ...v, [name]: value })); clearAiProvenance(name) }
  function addRepeat(name: string) {
    const cur = (values[name] as string[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, ''] }))
    clearAiProvenance(name)
  }
  function removeRepeat(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as string[]) ?? []).filter((_, i) => i !== idx) }))
    clearAiProvenance(name)
  }
  function updateRepeat(name: string, idx: number, val: string) {
    const cur = [...((values[name] as string[]) ?? [])]
    cur[idx] = val
    setValuesDirty(v => ({ ...v, [name]: cur }))
    clearAiProvenance(name)
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

  function addUrl(name: string) {
    const cur = (values[name] as PidEntry[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, { value: '', label: '' }] }))
  }
  function removeUrl(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as PidEntry[]) ?? []).filter((_, i) => i !== idx) }))
  }
  function updateUrl(name: string, idx: number, key: 'value' | 'label', val: string) {
    const cur = [...((values[name] as PidEntry[] | undefined) ?? [])]
    cur[idx] = { ...cur[idx], [key]: val }
    setValuesDirty(v => ({ ...v, [name]: cur }))
  }

  async function mintPid(fieldName: string, repeatable: boolean) {
    if (!savedId) return
    setRegisteringPidField(fieldName)
    try {
      const result = await pids.mint({
        record_type: recordType,
        record_id: savedId,
        field_name: fieldName,
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
    setAddingRepeatableField(null)
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
    setAddingRepeatableField(null)
  }
  function removeFreeVocab(name: string, idx: number) {
    setValuesDirty(v => ({ ...v, [name]: ((v[name] as string[]) ?? []).filter((_, i) => i !== idx) }))
  }

  function addVocab(name: string, val: VocabEntry) {
    const cur = (values[name] as VocabEntry[] | undefined) ?? []
    setValuesDirty(v => ({ ...v, [name]: [...cur, val] }))
    setAddingRepeatableField(null)
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
    clearAiProvenance(`${name}.${idx}.${subName}`)
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
    // A fixed relation subtype is structural in quick-create, so drafts must not bypass it.
    const validConfiguredSubtype = availableSubtypes.some(item => item.name === subtype)
    if (quickCreate && lockSubtype && !validConfiguredSubtype) {
      errors.__subtype = 'Der konfigurierte Subtyp ist ungültig.'
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
                `Feld '${getLabel(sf, sf.name)}' (Eintrag ${idx + 1}): Ungültiges Datum`
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
              errors[f.name] = INVALID_DATE_MESSAGE
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
          if (f.field_type === 'url' && item && typeof item === 'object' && !Array.isArray(item)) {
            if (!isHttpUrlString((item as PidEntry).value)) {
              errors[f.name] = 'Ungültige URL. Erlaubt sind vollständige http(s)-Adressen.'
              break
            }
          }
        }
        continue
      }

      // Non-repeatable field validation
      if (f.field_type === 'date') {
        const v = val as string
        if (v && !isValidDateInput(v)) {
          errors[f.name] = INVALID_DATE_MESSAGE
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
      if (f.field_type === 'url' && val && typeof val === 'object' && !Array.isArray(val)) {
        if (!isHttpUrlString((val as PidEntry).value)) {
          errors[f.name] = 'Ungültige URL. Erlaubt sind vollständige http(s)-Adressen.'
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
        return { level: 'error', message: INVALID_DATE_MESSAGE }
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
    if (field.field_type === 'url' && val && typeof val === 'object' && !Array.isArray(val)) {
      if (!isHttpUrlString((val as PidEntry).value)) {
        return { level: 'error', message: 'Ungültige URL. Erlaubt sind vollständige http(s)-Adressen.' }
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
      if (hasValue) setAiProposal({ field, currentValue, suggestedValue: result.value, model: result.model })
      else {
        setValuesDirty(prev => ({ ...prev, [field.name]: result.value }))
        markAiProvenance(field.name, result.model)
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
      if (isEmptyValue(currentValue)) {
        updateGroupSubField(group.name, groupIndex, field.name, result.value)
        markAiProvenance(`${group.name}.${groupIndex}.${field.name}`, result.model)
      } else {
        setAiProposal({ field, currentValue, suggestedValue: result.value, model: result.model, group: { name: group.name, index: groupIndex } })
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

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaveNotice(null)
    const validation = validateFields()
    if (Object.keys(validation.errors).length > 0) {
      console.log('[Katalon] Validierungsfehler beim Speichern:', validation.errors)
      setFieldErrors(validation.errors)
      setFieldWarnings(validation.warnings)
      selectSectionForField(Object.keys(validation.errors)[0].split(/[.:]/)[0])
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
        ai_provenance: aiProvenance,
      }
      if (showIdno)   payload.idno = idno || null
      if (subtypeKey) payload[subtypeKey] = subtype
      if (showCollectionStatus) payload.collection_status = collectionStatus
      if (showParentCollection) payload.parent_id = parentId || null
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
      async function syncCollectionMembership(objectId: string) {
        if (recordType !== 'object') return
        const existing = rels.find(r => r.from_id === objectId && r.to_type === 'collection' && r.relation_type === 'member_of')
        const existingTarget = existing?.to_id ?? null
        const desired = selectedCollectionId || null
        if (existingTarget === desired) return
        if (existing) await relationsApi.delete(existing.id)
        if (desired) {
          const created = await relationsApi.create({
            from_type: 'object', from_id: objectId,
            to_type: 'collection', to_id: desired,
            relation_type: 'member_of',
          })
          setRels(prev => [...prev.filter(r => r.id !== existing?.id), created])
        } else {
          setRels(prev => prev.filter(r => r.id !== existing?.id))
        }
      }


      if (isNew) {
        const created = await (api.create as (d: typeof payload) => Promise<AnyRecord>)(payload)
        if (quickCreate) {
          onCreated?.(created)
          return
        }
        setSavedId(created.id)
        setLoadedStatus((created as { status?: string }).status as Status)
        onSaved?.(created.id)
        if (showMedia) loadMedia(created.id)
        await syncCollectionMembership(created.id)
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
        await syncCollectionMembership(recordId!)
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
      setLoadedStatus((updated as { status?: string }).status as Status)
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

  async function handleUpload(files: File[]) {
    if (!savedId || files.length === 0) return
    setUploading(true)
    setUploadError(null)
    const errors: string[] = []
    for (let i = 0; i < files.length; i++) {
      setUploadProgress({ done: i, total: files.length, fraction: 0, phase: 'sending' })
      try {
        const uploaded = await media.upload(savedId, files[i], fraction =>
          setUploadProgress({ done: i, total: files.length, fraction, phase: fraction >= 1 ? 'processing' : 'sending' }))
        setMediaFiles(prev => [...prev, uploaded])
      } catch (e) {
        errors.push(`${files[i].name}: ${(e as Error).message}`)
      }
    }
    setUploadProgress(null)
    setUploading(false)
    if (errors.length > 0) setUploadError(errors.join('; '))
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

  async function handleDownloadPreservationBag() {
    if (!savedId) return
    try {
      await preservationApi.downloadBag(savedId)
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

  async function handleToggleMediaPublic(mediaId: string, isPublic: boolean) {
    if (!savedId) return
    try {
      const updated = await media.patch(savedId, mediaId, { is_public: isPublic })
      setMediaFiles(prev => prev.map(f => f.id === mediaId ? { ...f, is_public: updated.is_public } : f))
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
    const files = Array.from(e.target.files ?? [])
    if (files.length > 0) handleUpload(files)
    e.target.value = ''
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files ?? [])
    if (files.length > 0) handleUpload(files)
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
  const showStorageLocationCard = recordType === 'object' && hasStorageLocations
  const storageLocationRels = showStorageLocationCard ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) === 'storage_location') : []
  const otherRels = rels.filter(r => {
    const otherType = r.from_id === savedId ? r.to_type : r.from_type
    if (showProcedureFields && otherType === 'object') return false
    if (showCollectionStatus && otherType === 'procedure') return false
    if (showStorageLocationCard && otherType === 'storage_location') return false
    return true
  })
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
    const typeLabel: Record<string, string> = { object: 'Objekt', entity: 'Entität', place: 'Ort', occurrence: 'Occurrence', procedure: 'Vorgang', collection: 'Sammlung', storage_location: 'Lagerort' }
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
        <div style={{ display: 'grid', gridTemplateColumns: schemaBound ? '1fr 1fr' : '1fr 1fr auto', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
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
              {relTitles[targetKey] ?? '…'}
            </a>
          </span>
          {!schemaBound && canManageContent && (
            <button className="btn sm ico gh dn" title="Beziehung löschen" onClick={() => handleDeleteRelation(r.id)}><Trash size={11} /></button>
          )}
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

  const assignedFieldNames = new Set<string>()
  const sectionFields = sections.map(section => ({
    section,
    fields: section.field_names
      .map(name => displayFields.find(field => field.name === name))
      .filter((field): field is FieldDefinition => field != null && !assignedFieldNames.has(field.name))
      .map(field => { assignedFieldNames.add(field.name); return field }),
  })).filter(({ fields: sectionFields }) => sectionFields.length > 0)
  const unassignedFields = displayFields.filter(field => !assignedFieldNames.has(field.name))
  const activeSection = sectionFields.find(({ section }) => section.id === activeSectionId)
  const visibleFields = activeSection ? activeSection.fields : unassignedFields

  function sectionErrorCount(fieldNames: string[]) {
    return Object.keys(fieldErrors).filter(key => fieldNames.includes(key.split(/[.:]/)[0])).length
  }

  function selectSectionForField(fieldName: string) {
    const section = sectionFields.find(({ fields: sectionFields }) => sectionFields.some(field => field.name === fieldName))
    setActiveSectionId(section?.section.id ?? null)
  }

  function selectVariant(variantId: string | null) {
    setActiveVariantId(variantId)
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
          {!isNew && currentId && (
            <div ref={workingSetsDropdownRef} style={{ position: 'relative' }}>
              {assignedWorkingSets.length === 0 ? (
                <button
                  type="button"
                  className="btn gh"
                  onClick={() => setAddToWorkingSetOpen(true)}
                  title={t('workingSets.add')}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <Bookmark size={14} />
                  <span>{t('workingSets.add')}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="btn gh"
                  onClick={() => setWorkingSetsDropdownOpen((prev) => !prev)}
                  title={t('workingSets.inWorkingSets', { count: assignedWorkingSets.length })}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    background: '#eff6ff',
                    color: '#1d4ed8',
                    borderColor: '#bfdbfe',
                    fontWeight: 500,
                  }}
                >
                  <Bookmark size={14} style={{ fill: 'currentColor' }} />
                  <span>
                    {assignedWorkingSets.length === 1
                      ? t('workingSets.inWorkingSets_one')
                      : t('workingSets.inWorkingSets', { count: assignedWorkingSets.length })}
                  </span>
                  <span style={{ fontSize: 10, marginLeft: 2 }}>▾</span>
                </button>
              )}

              {workingSetsDropdownOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    zIndex: 200,
                    width: 280,
                    background: 'var(--panel, #fff)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    padding: '8px 0',
                    fontSize: 13,
                  }}
                >
                  <div
                    style={{
                      padding: '6px 14px 4px',
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--fg-3)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    {t('workingSets.containedTitle')}
                  </div>
                  {assignedWorkingSets.map((ws) => (
                    <a
                      key={ws.id}
                      href={`#working-sets/${ws.id}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '7px 14px',
                        color: 'var(--fg)',
                        textDecoration: 'none',
                      }}
                      className="link-hover"
                    >
                      <span
                        style={{
                          fontWeight: 500,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {ws.name}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          color: 'var(--fg-4)',
                          marginLeft: 8,
                          flexShrink: 0,
                        }}
                      >
                        {t('workingSets.openSet')} ↗
                      </span>
                    </a>
                  ))}
                  <div
                    style={{
                      borderTop: '1px solid var(--border)',
                      marginTop: 6,
                      paddingTop: 6,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setWorkingSetsDropdownOpen(false)
                        setAddToWorkingSetOpen(true)
                      }}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        background: 'none',
                        border: 'none',
                        padding: '6px 14px',
                        color: '#2563eb',
                        cursor: 'pointer',
                        fontSize: 12.5,
                        fontWeight: 500,
                      }}
                    >
                      {t('workingSets.addToAnother')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {!isNew && currentId && features.includes('manual_lock') && (
            !manualLock || manualLock.locked_by_email === user?.email || user?.role === 'admin' || user?.role === 'superuser'
              ? <button className="btn gh" onClick={handleLockToggle} disabled={lockLoading} style={{ minWidth: 90 }}>
                  {lockLoading ? '…' : manualLock ? 'Sperre aufheben' : 'Sperren'}
                </button>
              : null
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

      {otherEditors.length > 0 && (
        <div className="record-notice" style={{ background: '#fffbeb', borderBottom: '1px solid #fcd34d', color: '#92400e' }}>
          {t('presence.editingBy', { names: otherEditors.map(p => p.user_email).join(', ') })}
        </div>
      )}

      {manualLock && (
        <div className="record-notice" style={{ background: '#f3e8ff', borderBottom: '1px solid #d8b4fe', color: '#6b21a8' }}>
          {manualLock.locked_by_email === user?.email
            ? t('locks.youLocked', { reason: manualLock.reason || t('locks.noReason') })
            : t('locks.lockedBy', { name: manualLock.locked_by_email, reason: manualLock.reason || t('locks.noReason') })}
          {manualLock.expires_at && <span style={{ marginLeft: 8, fontSize: 11, opacity: 0.7 }}>{t('locks.expiresAt', { date: new Date(manualLock.expires_at).toLocaleString() })}</span>}
        </div>
      )}

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
            if (aiProposal.group) {
              updateGroupSubField(aiProposal.group.name, aiProposal.group.index, aiProposal.field.name, value)
              markAiProvenance(`${aiProposal.group.name}.${aiProposal.group.index}.${aiProposal.field.name}`, aiProposal.model)
            } else {
              setValuesDirty(previous => ({ ...previous, [aiProposal.field.name]: value }))
              markAiProvenance(aiProposal.field.name, aiProposal.model)
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
            {variants.length > 0 && (
              <label className="field" style={{ display: 'block', maxWidth: 300, margin: '0 0 14px' }}>
                <span className="lbl">{t('variants.label')}</span>
                <select className="fld" value={activeVariantId ?? ''} onChange={event => selectVariant(event.target.value || null)}>
                  <option value="">{t('variants.complete')}</option>
                  {variants.map(variant => <option key={variant.id} value={variant.id}>{getLabel(variant, variant.name)}</option>)}
                </select>
              </label>
            )}

            <div className="card">
              <div className="hd">{t('cards.system')}</div>
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
                    <div className="lbl">{recordType === 'procedure' ? 'Vorgangstyp' : recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : recordType === 'collection' ? 'Sammlungstyp' : 'Occurrence-Typ'} {recordType !== 'object' && <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span>}</div>
                    <select
                      className="fld"
                      value={subtype}
                      onChange={e => { setSubtype(e.target.value); setIsDirty(true); clearFieldFeedback('__subtype') }}
                      disabled={justCreated || lockSubtype}
                      style={getFeedbackStyle('__subtype')}
                    >
                      <option value="">— {recordType === 'procedure' ? 'Vorgangstyp' : recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : recordType === 'collection' ? 'Sammlungstyp' : 'Occurrence-Typ'} wählen —</option>
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
                    <div className="lbl">Bestandsstatus</div>
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

                {showParentCollection && (
                  <div className="field">
                    <div className="lbl">Übergeordnete Sammlung <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
                    <select
                      className="fld"
                      value={parentId ?? ''}
                      onChange={e => { setParentId(e.target.value || null); setIsDirty(true) }}
                      disabled={justCreated}
                    >
                      <option value="">— Keine (oberste Ebene) —</option>
                      {availableParents
                        .filter(p => p.id !== currentId)
                        .map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
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
              </div>
            </div>

            <div className="card">
              <div className="hd">{t('cards.metadata')}</div>
              <div className="bd">
                {sectionFields.length > 0 && (
                  <div className="tabs" style={{ marginBottom: 12 }} role="tablist" aria-label={t('sections.label')}>
                    {sectionFields.map(({ section, fields: sectionFields }) => {
                      const count = sectionErrorCount(sectionFields.map(field => field.name))
                      return (
                        <button key={section.id} className={`tab${activeSection?.section.id === section.id ? ' active' : ''}`} onClick={() => setActiveSectionId(section.id)} role="tab" aria-selected={activeSection?.section.id === section.id}>
                          {getLabel(section, section.id)}{count > 0 ? ` · ${count}` : ''}
                        </button>
                      )
                    })}
                    {unassignedFields.length > 0 && (
                      <button className={`tab${activeSection === undefined ? ' active' : ''}`} onClick={() => setActiveSectionId(null)} role="tab" aria-selected={activeSection === undefined}>
                        {t('sections.general')}{sectionErrorCount(unassignedFields.map(field => field.name)) > 0 ? ` · ${sectionErrorCount(unassignedFields.map(field => field.name))}` : ''}
                      </button>
                    )}
                  </div>
                )}

                {visibleFields.map(f => {
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
                      <div className="lbl" title={repeatable ? (t('repeatable.hint') || 'Wiederholbares Feld') : undefined}>
                        {getLabel(f, f.name)}
                        {f.is_required && <span className="req">*</span>}
                        {getLabel({ label: f.help_text }) && (
                          <HelpPopover content={<div>{getLabel({ label: f.help_text })}</div>} ariaLabel={t('helpTextAriaLabel') || 'Hilfe zu diesem Feld'} />
                        )}
                        {Boolean(f.settings?.is_locked) && <span className="h">{canEditLocked ? 'gesperrt · Admin-Bearbeitung' : 'gesperrt'}</span>}
                        {aiProvenance[f.name] && <AiDisclosureBadge {...aiProvenance[f.name]} />}
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
                          ((val as VocabEntry[] | undefined) ?? []).length === 0 ? (
                            <VocabInput
                              vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                              value={null}
                              onChange={v => { if (v) addVocab(f.name, v) }}
                              disabled={justCreated}
                            />
                          ) : (
                            <>
                              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
                                {((val as VocabEntry[] | undefined) ?? []).map((entry, i) => (
                                  <span key={i} style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 5,
                                    padding: '3px 8px', borderRadius: 4,
                                    background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
                                  }}>
                                    {entry.label}
                                    <button
                                      type="button"
                                      className="btn sm ico gh"
                                      style={{ marginLeft: 2, padding: 0 }}
                                      onClick={() => removeVocab(f.name, i)}
                                      disabled={justCreated}
                                      title="Entfernen"
                                    >
                                      <X size={10} />
                                    </button>
                                  </span>
                                ))}
                                {addingRepeatableField !== f.name && !justCreated && (
                                  <button
                                    type="button"
                                    className="btn sm gh"
                                    style={{ height: 26, padding: '0 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                    onClick={() => setAddingRepeatableField(f.name)}
                                    disabled={justCreated}
                                  >
                                    <Plus size={12} /> {t('repeatable.add')}
                                  </button>
                                )}
                              </div>
                              {addingRepeatableField === f.name && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                                  <div style={{ flex: 1 }}>
                                    <VocabInput
                                      vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                                      value={null}
                                      onChange={v => { if (v) addVocab(f.name, v) }}
                                      disabled={justCreated}
                                      autoFocus
                                      onCancel={() => setAddingRepeatableField(null)}
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    className="btn sm ico gh"
                                    onClick={() => setAddingRepeatableField(null)}
                                    title={t('repeatable.cancel')}
                                    aria-label={t('repeatable.cancel')}
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              )}
                            </>
                          )
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
                          ((val as string[] | undefined) ?? []).length === 0 ? (
                            <VocabFreeInput
                              vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                              onAdd={v => addFreeVocab(f.name, v)}
                              disabled={justCreated}
                              placeholder="Eingeben und Enter drücken oder Vorschlag wählen"
                            />
                          ) : (
                            <>
                              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
                                {((val as string[] | undefined) ?? []).map((entry, i) => (
                                  <span key={i} style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 5,
                                    padding: '3px 8px', borderRadius: 4,
                                    background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13,
                                  }}>
                                    {entry}
                                    <button
                                      type="button"
                                      className="btn sm ico gh"
                                      style={{ marginLeft: 2, padding: 0 }}
                                      onClick={() => removeFreeVocab(f.name, i)}
                                      disabled={justCreated}
                                      title="Entfernen"
                                    >
                                      <X size={10} />
                                    </button>
                                  </span>
                                ))}
                                {addingRepeatableField !== f.name && !justCreated && (
                                  <button
                                    type="button"
                                    className="btn sm gh"
                                    style={{ height: 26, padding: '0 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                    onClick={() => setAddingRepeatableField(f.name)}
                                    disabled={justCreated}
                                  >
                                    <Plus size={12} /> {t('repeatable.add')}
                                  </button>
                                )}
                              </div>
                              {addingRepeatableField === f.name && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                                  <div style={{ flex: 1 }}>
                                    <VocabFreeInput
                                      vocabId={(f.settings?.vocabulary_id as string) ?? ''}
                                      onAdd={v => addFreeVocab(f.name, v)}
                                      disabled={justCreated}
                                      placeholder="Eingeben und Enter drücken oder Vorschlag wählen"
                                      autoFocus
                                      onCancel={() => setAddingRepeatableField(null)}
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    className="btn sm ico gh"
                                    onClick={() => setAddingRepeatableField(null)}
                                    title={t('repeatable.cancel')}
                                    aria-label={t('repeatable.cancel')}
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              )}
                            </>
                          )
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
                          ((val as AuthorityEntry[] | undefined) ?? []).length === 0 ? (
                            <AuthorityInput
                              source={(f.settings?.source as string) ?? 'gnd'}
                              value={null}
                              onChange={v => { if (v) addAuthority(f.name, v) }}
                              disabled={justCreated}
                            />
                          ) : (
                            <>
                              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
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
                                      type="button"
                                      className="btn sm ico gh"
                                      style={{ marginLeft: 2, padding: 0 }}
                                      onClick={() => removeAuthority(f.name, i)}
                                      disabled={justCreated}
                                      title="Entfernen"
                                    >
                                      <X size={10} />
                                    </button>
                                  </span>
                                ))}
                                {addingRepeatableField !== f.name && !justCreated && (
                                  <button
                                    type="button"
                                    className="btn sm gh"
                                    style={{ height: 26, padding: '0 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                    onClick={() => setAddingRepeatableField(f.name)}
                                    disabled={justCreated}
                                  >
                                    <Plus size={12} /> {t('repeatable.add')}
                                  </button>
                                )}
                              </div>
                              {((val as AuthorityEntry[] | undefined) ?? []).map((entry, i) => (
                                <GeoNamesMap key={`${entry.external_id}-${i}`} value={entry} />
                              ))}
                              {addingRepeatableField === f.name && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                                  <div style={{ flex: 1 }}>
                                    <AuthorityInput
                                      source={(f.settings?.source as string) ?? 'gnd'}
                                      value={null}
                                      onChange={v => { if (v) addAuthority(f.name, v) }}
                                      disabled={justCreated}
                                      autoFocus
                                      onCancel={() => setAddingRepeatableField(null)}
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    className="btn sm ico gh"
                                    onClick={() => setAddingRepeatableField(null)}
                                    title={t('repeatable.cancel')}
                                    aria-label={t('repeatable.cancel')}
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              )}
                            </>
                          )
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
                          ((val as RelationEntry[] | undefined) ?? []).length === 0 ? (
                            <RelationInput
                              targetType={(f.settings?.target_type as RecordType) ?? ''}
                              targetSubtype={f.settings?.target_subtype as string | undefined}
                              relTypeVocabId={(f.settings?.relation_type_vocab as string | undefined) ?? relTypeVocabId}
                              fixedRelationType={f.settings?.fixed_relation_type as string | undefined}
                              fromType={recordType}
                              onAdd={entry => addRelationEntry(f.name, entry)}
                              disabled={justCreated}
                            />
                          ) : (
                            <>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 6 }}>
                                {((val as RelationEntry[] | undefined) ?? []).map((entry, i) => (
                                  <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 8px', borderRadius: 999, background: 'var(--accent-50)', color: 'var(--accent-ink)', fontSize: 13 }}>
                                    <span style={{ flex: 1 }}>{entry.label}</span>
                                    <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--mono)' }}>{entry.relation_type}</span>
                                    <button type="button" className="btn sm ico gh" onClick={() => removeRelationEntry(f.name, i)} disabled={justCreated} aria-label="Beziehung entfernen" title="Beziehung entfernen"><X size={10} /></button>
                                  </div>
                                ))}
                              </div>
                              {addingRepeatableField === f.name ? (
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 4 }}>
                                  <div style={{ flex: 1 }}>
                                    <RelationInput
                                      targetType={(f.settings?.target_type as RecordType) ?? ''}
                                      targetSubtype={f.settings?.target_subtype as string | undefined}
                                      relTypeVocabId={(f.settings?.relation_type_vocab as string | undefined) ?? relTypeVocabId}
                                      fixedRelationType={f.settings?.fixed_relation_type as string | undefined}
                                      fromType={recordType}
                                      onAdd={async entry => {
                                        await addRelationEntry(f.name, entry)
                                        setAddingRepeatableField(null)
                                      }}
                                      disabled={justCreated}
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    className="btn sm ico gh"
                                    onClick={() => setAddingRepeatableField(null)}
                                    title={t('repeatable.cancel')}
                                    aria-label={t('repeatable.cancel')}
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              ) : (
                                !justCreated && (
                                  <button
                                    type="button"
                                    className="btn sm gh"
                                    style={{ alignSelf: 'flex-start', marginTop: 4 }}
                                    onClick={() => setAddingRepeatableField(f.name)}
                                    disabled={justCreated}
                                  >
                                    <Plus size={12} /> {t('repeatable.addRelationship')}
                                  </button>
                                )
                              )}
                            </>
                          )
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
                                      {getLabel({ label: sf.help_text }) && (
                                        <HelpPopover content={<div>{getLabel({ label: sf.help_text })}</div>} ariaLabel={t('helpTextAriaLabel') || 'Hilfe zu diesem Feld'} />
                                      )}
                                    </div>
                                    {aiProvenance[`${f.name}.${i}.${sf.name}`] && <AiDisclosureBadge {...aiProvenance[`${f.name}.${i}.${sf.name}`]} />}
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
                          {(() => {
                            const groupInstances = (val as Record<string, unknown>[] | undefined) ?? []
                            const maxCount = f.settings?.max_count as number | undefined
                            const limitReached = typeof maxCount === 'number' && groupInstances.length >= maxCount
                            return (
                              <button className="btn sm gh" onClick={() => addGroupInstance(f.name)} disabled={justCreated || limitReached}>
                                <Plus size={12} /> Eintrag hinzufügen{limitReached ? ` (max. ${maxCount})` : ''}
                              </button>
                            )
                          })()}
                        </div>
                      ) : f.field_type === 'pid' ? (
                        (() => {
                          const provider = (f.settings?.pid_provider as string) ?? 'dnb_urn'
                          const isArk = provider === 'ark'
                          const mintLabel = isArk ? t('pid.mintArk') : t('pid.mintUrn')
                          const mintPending = isArk ? t('pid.mintArkPending') : t('pid.mintUrnPending')
                          const mintHint = !savedId ? t('pid.mintHint') : undefined
                          const href = (v: string) => pidHref(v)
                          return (
                        <div style={{ display: 'grid', gap: 6 }}>
                          {(!repeatable && pidSingle && pidSingle.value) ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, flex: 1, overflowWrap: 'anywhere' }}>
                                {href(pidSingle.value) ? (
                                  <a href={href(pidSingle.value)} target="_blank" rel="noreferrer">{pidSingle.value}</a>
                                ) : pidSingle.value}
                              </span>
                              <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{t('pid.systemManaged')}</span>
                            </div>
                          ) : (
                            <div>
                              <button
                                className="btn sm gh"
                                onClick={() => mintPid(f.name, repeatable)}
                                disabled={justCreated || !savedId || registeringPidField === f.name}
                                title={mintHint}
                              >
                                {registeringPidField === f.name ? mintPending : mintLabel}
                              </button>
                            </div>
                          )}
                          {repeatable && (pidEntries ?? []).length > 0 && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {(pidEntries ?? []).map((entry, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0' }}>
                                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12, flex: 1, overflowWrap: 'anywhere' }}>
                                    {href(entry.value) ? (
                                      <a href={href(entry.value)} target="_blank" rel="noreferrer">{entry.value}</a>
                                    ) : entry.value}
                                  </span>
                                  {entry.label && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{entry.label}</span>}
                                </div>
                              ))}
                              <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{t('pid.systemManaged')}</span>
                            </div>
                          )}
                          {repeatable && (
                            <div>
                              <button
                                className="btn sm gh"
                                onClick={() => mintPid(f.name, repeatable)}
                                disabled={justCreated || !savedId || registeringPidField === f.name}
                                title={mintHint}
                              >
                                {registeringPidField === f.name ? mintPending : mintLabel}
                              </button>
                            </div>
                          )}
                        </div>
                          )
                        })()
                      ) : f.field_type === 'url' ? (
                        repeatable ? (
                          <>
                            {(() => {
                              const urlEntries = ((val as PidEntry[] | undefined) ?? [])
                              const maxCount = f.settings?.max_count as number | undefined
                              const limitReached = typeof maxCount === 'number' && urlEntries.length >= maxCount
                              return (
                                <>
                                  {urlEntries.map((entry, i) => (
                                    <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                                      <input className="fld mono" value={entry.value}
                                        type="url"
                                        onChange={e => updateUrl(f.name, i, 'value', e.target.value)}
                                        placeholder="https://…"
                                        disabled={justCreated} style={{ flex: 2 }} />
                                      <input className="fld" value={entry.label}
                                        onChange={e => updateUrl(f.name, i, 'label', e.target.value)}
                                        placeholder={t('url.linkLabel')}
                                        disabled={justCreated} style={{ flex: 1 }} />
                                      <button className="btn sm ico gh" onClick={() => removeUrl(f.name, i)} disabled={justCreated}><X size={12} /></button>
                                    </div>
                                  ))}
                                  <button className="btn sm gh" onClick={() => addUrl(f.name)} disabled={justCreated || limitReached}>
                                    <Plus size={12} /> {t('url.add')}{limitReached ? ` (max. ${maxCount})` : ''}
                                  </button>
                                </>
                              )
                            })()}
                          </>
                        ) : (
                          (() => {
                            const entry = ((val as PidEntry | undefined) ?? { value: '', label: '' })
                            return (
                          <div style={{ display: 'flex', gap: 6 }}>
                            <input className="fld mono" value={entry.value}
                              type="url"
                              onChange={e => setField(f.name, { ...entry, value: e.target.value })}
                              placeholder="https://…"
                              disabled={justCreated} style={{ flex: 2 }} />
                            <input className="fld" value={entry.label}
                              onChange={e => setField(f.name, { ...entry, label: e.target.value })}
                              placeholder={t('url.linkLabel')}
                              disabled={justCreated} style={{ flex: 1 }} />
                          </div>
                            )
                          })()
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
                          {(() => {
                            const maxCount = f.settings?.max_count as number | undefined
                            const limitReached = typeof maxCount === 'number' && (vals?.length ?? 0) >= maxCount
                            return (
                              <button className="btn sm gh" onClick={() => addRepeat(f.name)} disabled={justCreated || limitReached}>
                                <Plus size={12} /> Weiteren Wert{limitReached ? ` (max. ${maxCount})` : ''}
                              </button>
                            )
                          })()}
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
                        <RichTextEditor
                          value={(val as string) ?? ''}
                          onChange={v => { setField(f.name, v); clearFieldFeedback(f.name) }}
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
              {recordType === 'object' && availableCollections.length > 0 && (
                <div className="card collection-card" style={{ marginBottom: 14 }}>
                  <div className="hd">Sammlung</div>
                  <div className="bd">
                    <div className="field">
                      <div className="lbl">Sammlung <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>(optional)</span></div>
                      <select
                        className="fld"
                        value={selectedCollectionId}
                        onChange={e => { setSelectedCollectionId(e.target.value); setIsDirty(true) }}
                        disabled={justCreated}
                      >
                        <option value="">— Keine —</option>
                        {availableCollections.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {showMedia && (
                <div className="card media-card" style={{ marginBottom: 14 }} data-tour="media-section">
                  <div className="hd">
                    <span>Medien</span>
                    {mediaFiles.length > 0 && <span className="sub">{mediaFiles.length} Datei{mediaFiles.length !== 1 ? 'en' : ''}</span>}
                    <span className="grow" />
                    {recordType === 'object' && savedId && features.includes('export') && (
                      <span className="right">
                        <button
                          type="button"
                          className="btn sm ico gh"
                          onClick={handleDownloadPreservationBag}
                          title={t('preservation.bagTitle')}
                        >
                          <Download size={12} />
                        </button>
                      </span>
                    )}
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
                              ) : f.status === 'pending' ? (
                                <div style={{ width: '100%', aspectRatio: '1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                                  <div style={{ width: 18, height: 18, border: '2px solid var(--border-s)', borderTopColor: 'var(--fg-3)', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
                                  <span style={{ fontSize: 9, color: 'var(--fg-3)' }}>Verarbeite…</span>
                                </div>
                              ) : f._links?.thumbnail ? (
                                <ImageThumb objectId={savedId!} mediaId={f.id} alt={f.filename} />
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
                              <button
                                className={`btn sm ico${f.is_public ? ' gh' : ' dn'}`}
                                style={{ padding: '1px 4px', flexShrink: 0 }}
                                onClick={() => handleToggleMediaPublic(f.id, !f.is_public)}
                                title={f.is_public ? 'Öffentlich sichtbar – zum Verbergen im Portal klicken' : 'Im Portal verborgen – zum Freigeben klicken'}
                              >
                                <Eye size={10} style={f.is_public ? undefined : { opacity: 0.35 }} />
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
                          {uploading
                            ? <div style={{ width: 24, height: 24, border: '2px solid var(--border-s)', borderTopColor: 'var(--fg-3)', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
                            : <Upload size={24} style={{ color: 'var(--fg-4)' }} />}
                        </div>
                        {uploading && uploadProgress ? (
                          <div>
                            <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                              {uploadProgress.phase === 'processing'
                                ? 'Verarbeite…'
                                : `Hochladen${uploadProgress.total > 1 ? ` (${uploadProgress.done + 1}/${uploadProgress.total})` : ''} ${Math.round(uploadProgress.fraction * 100)}%`}
                            </div>
                            <div style={{ marginTop: 6, height: 4, borderRadius: 2, background: 'var(--border-s)', overflow: 'hidden' }}>
                              <div style={uploadProgress.phase === 'processing'
                                ? { height: '100%', borderRadius: 2, background: 'var(--accent)', animation: 'progress-pulse 1.1s ease-in-out infinite' }
                                : {
                                  height: '100%', borderRadius: 2, background: 'var(--accent)',
                                  width: `${((uploadProgress.done + uploadProgress.fraction) / uploadProgress.total) * 100}%`,
                                  transition: 'width .15s ease',
                                }} />
                            </div>
                          </div>
                        ) : (
                          <>
                            <div style={{ fontSize: 12 }}>Hierher ziehen oder</div>
                            <label className="upload-control">
                              &nbsp;auswählen
                              <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} accept="image/jpeg,image/png,image/tiff,image/webp,application/pdf,audio/mpeg,audio/wav,audio/ogg,video/mp4,video/webm,model/gltf-binary,.glb" onChange={onFileChange} />
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

              {showStorageLocationCard && !isNew && (
                <div className="card storage-card" style={{ marginBottom: 14, overflow: addLocationOpen ? 'visible' : undefined }}>
                  <div className="hd">
                    <span>Zugeordnete Lagerorte</span>
                    {storageLocationRels.length > 0 && <span className="sub">{storageLocationRels.length}</span>}
                    <div className="grow" />
                    {!addLocationOpen && hasSavedId && canManageContent && (
                      <button className="btn sm gh" onClick={() => setAddLocationOpen(true)}>
                        <Plus size={12} /> Hinzufügen
                      </button>
                    )}
                  </div>
                  <div className="bd">
                    {storageLocationRels.length > 0 ? (
                      <div style={{ marginBottom: addLocationOpen ? 12 : 0 }}>
                        {storageLocationRels.map(r => renderRelation(r))}
                      </div>
                    ) : (
                      <div className="empty" style={{ padding: addLocationOpen ? '0 0 12px' : '8px 0' }}>Noch keinem Lagerort zugeordnet.</div>
                    )}
                    {addLocationOpen && (
                      <div style={{ borderTop: storageLocationRels.length > 0 ? '1px solid var(--border-s)' : undefined, paddingTop: storageLocationRels.length > 0 ? 12 : 0 }}>
                        <RelationInput
                          targetType="storage_location"
                          relTypeVocabId={relTypeVocabId}
                          fromType={recordType}
                          onAdd={handleAddLocationRelation}
                        />
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn gh sm" onClick={() => setAddLocationOpen(false)}>
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
                          fromType={recordType}
                          onAdd={handleAddGenericRelation}
                        />
                        <button className="btn gh sm" onClick={() => setGenericAddOpen(false)}>Abbrechen</button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!isNew && savedId && showSnapshotsForRecord && (
                <div className="card versions-card">
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
                                setAiProvenance({})
                                setVersion(restored.version)
                                if (showCollectionStatus) {
                                  setCollectionStatus((restored as { collection_status?: string | null }).collection_status ?? 'active')
                                }
                                if (showParentCollection && 'parent_id' in restored) {
                                  setParentId((restored as KatalonCollection).parent_id ?? null)
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
                <div className="card audit-card">
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
                          {(() => {
                            const cf = evt.changed_fields as { old?: Record<string, unknown>; new?: Record<string, unknown> } | undefined
                            const newVals = cf?.new
                            if (!newVals || Object.keys(newVals).length === 0) return null
                            const oldVals = cf?.old ?? {}
                            return (
                              <div style={{ marginTop: 4, display: 'grid', gap: 2 }}>
                                {Object.keys(newVals).map(field => (
                                  <div key={field} style={{ color: 'var(--fg-2)' }}>
                                    <span style={{ fontWeight: 600 }}>{field}</span>
                                    {field in oldVals && (
                                      <>: <span style={{ textDecoration: 'line-through', color: 'var(--fg-3)' }}>{String(oldVals[field] ?? '—')}</span> → </>
                                    )}
                                    {!(field in oldVals) && ': '}
                                    <span>{String(newVals[field] ?? '—')}</span>
                                  </div>
                                ))}
                              </div>
                            )
                          })()}
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
      {addToWorkingSetOpen && currentId && (
        <AddToWorkingSetModal
          recordType={recordType}
          recordIds={[currentId]}
          onClose={() => setAddToWorkingSetOpen(false)}
          onSuccess={() => {
            setAddToWorkingSetOpen(false)
            loadAssignedWorkingSets()
          }}
        />
      )}
      {showLockModal && (
        <div className="batch-modal-backdrop" onClick={() => setShowLockModal(false)} role="dialog" aria-modal="true">
          <div className="batch-modal" style={{ width: 480 }} onClick={e => e.stopPropagation()}>
            <div className="batch-modal-header">
              <h2>Datensatz sperren</h2>
              <button type="button" className="btn ico gh" onClick={() => setShowLockModal(false)} aria-label="Schließen"><X size={16} /></button>
            </div>
            <div className="batch-modal-body">
              {lockModalError && (
                <div style={{ marginBottom: 16, padding: 10, background: '#fee2e2', color: '#991b1b', borderRadius: 6, fontSize: 13 }}>
                  {lockModalError}
                </div>
              )}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>Grund (optional)</label>
                <textarea className="fld" rows={3} value={lockReason} onChange={e => setLockReason(e.target.value)} placeholder="z.B. Übernahme aus Altbestand, warte auf Rückmeldung…" style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--fg-2)' }}>Ablaufdatum (optional)</label>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input className="fld" type="date" value={lockExpires} onChange={e => setLockExpires(e.target.value)} min={new Date().toISOString().split('T')[0]} style={{ flex: 1, boxSizing: 'border-box' }} />
                  {lockExpires && (
                    <button type="button" className="btn ico gh" onClick={() => setLockExpires('')} aria-label="Datum entfernen" style={{ flexShrink: 0 }}><X size={14} /></button>
                  )}
                </div>
              </div>
            </div>
            <div className="batch-modal-footer">
              <button type="button" className="btn gh" onClick={() => setShowLockModal(false)} disabled={lockLoading}>Abbrechen</button>
              <button type="button" className="btn pri" onClick={handleLockSubmit} disabled={lockLoading}>{lockLoading ? 'Sperre setzen…' : 'Sperren'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
