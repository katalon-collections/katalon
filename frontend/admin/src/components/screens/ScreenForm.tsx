import { useState, useEffect, useRef, useCallback } from 'react'
import { objects, entities, places, occurrences, procedures, schema, media, vocabularies, relations as relationsApi, search as searchApi, authority as authorityApi, pids, subtypes, idno as idnoApi, BASE, PORTAL_URL, ai, getTokenUser } from '../../api/client'
import type { AuthorityHit, MediaFile } from '../../api/client'
import type { AnyRecord, AuditEntry, FieldDefinition, ProcedureStatus, RecordSubtype, RecordType, Relation, SearchResult, Snapshot, Status, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { AlertCircle, ChevD, Plus, Upload, X, Trash, Image, Edit, Lightning } from '../ui/Icons'

function extractTitle(m: Record<string, unknown>, fallback: string): string {
  for (const key of ['label', 'title', 'titel', 'name', 'display_name', 'place_name', 'bezeichnung']) {
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

const STATUSES: Status[] = ['draft', 'internal', 'public']
const STATUS_LABELS: Record<Status, string> = { draft: 'Entwurf', internal: 'Intern', public: 'Öffentlich' }
const PROCEDURE_STATUSES: ProcedureStatus[] = ['draft', 'active', 'completed', 'cancelled']
const PROCEDURE_STATUS_LABELS: Record<ProcedureStatus, string> = { draft: 'Entwurf', active: 'Aktiv', completed: 'Abgeschlossen', cancelled: 'Abgebrochen' }
const MEDIA_LICENSES = [
  ['https://creativecommons.org/publicdomain/zero/1.0/', 'CC0 1.0'],
  ['https://creativecommons.org/publicdomain/mark/1.0/', 'Public Domain Mark 1.0'],
  ['https://creativecommons.org/licenses/by/4.0/', 'CC BY 4.0'],
  ['https://creativecommons.org/licenses/by-sa/4.0/', 'CC BY-SA 4.0'],
  ['https://rightsstatements.org/vocab/InC/1.0/', 'In Copyright'],
] as const
const PROCEDURE_TYPES = [
  { id: 'loan_out', label: 'Ausleihe ausgehend' },
  { id: 'loan_in', label: 'Ausleihe eingehend' },
  { id: 'acquisition', label: 'Erwerbung' },
  { id: 'conservation', label: 'Restaurierung' },
  { id: 'object_entry', label: 'Objekteingang' },
  { id: 'deaccession', label: 'Deakzession' },
]
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

const SUBTYPE_KEY: Partial<Record<RecordType, string>> = {
  object:     'object_type',
  entity:     'entity_type',
  place:      'place_type',
  occurrence: 'occurrence_type',
  procedure:  'procedure_type',
}

export type AuthorityEntry = { source: string; external_id: string; label: string }
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

function AuthorityInput({ source, value, onChange, disabled }: {
  source: string
  value: AuthorityEntry | null
  onChange: (v: AuthorityEntry | null) => void
  disabled?: boolean
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<AuthorityHit[]>([])
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
    if (q.trim().length < 2) { setResults([]); setOpen(false); return }
    timer.current = setTimeout(() => {
      setBusy(true)
      authorityApi.search(source, q.trim())
        .then(r => { setResults(r); setOpen(r.length > 0) })
        .catch(() => setResults([]))
        .finally(() => setBusy(false))
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, source])

  function pick(hit: AuthorityHit) {
    onChange({ source: hit.source, external_id: hit.external_id, label: hit.label })
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
          <span style={{ fontSize: 10, opacity: 0.6, fontFamily: 'var(--mono)' }}>
            {value.source}:{value.external_id}
          </span>
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
        placeholder={`${source.toUpperCase()} durchsuchen…`}
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
          {results.map(hit => (
            <button
              key={hit.external_id}
              onMouseDown={e => { e.preventDefault(); pick(hit) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)',
                background: 'none', cursor: 'pointer',
              }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{hit.label}</div>
              {hit.description && (
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{hit.description}</div>
              )}
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                {hit.source} · {hit.external_id}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function RelationInput({
  targetType,
  targetSubtype,
  relTypeVocabId,
  onAdd,
  disabled,
}: {
  targetType: string
  targetSubtype?: string
  relTypeVocabId?: string
  onAdd: (entry: RelationEntry) => void
  disabled?: boolean
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [picked, setPicked] = useState<SearchResult | null>(null)
  const [relType, setRelType] = useState('')
  const [relTypeTerms, setRelTypeTerms] = useState<VocabularyTerm[]>([])
  const [showDrop, setShowDrop] = useState(false)
  const [dropPos, setDropPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!relTypeVocabId) { setRelTypeTerms([]); return }
    vocabularies.listTerms(relTypeVocabId).then(setRelTypeTerms).catch(() => {})
  }, [relTypeVocabId])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (inputRef.current?.contains(e.target as Node) || dropRef.current?.contains(e.target as Node)) return
      setShowDrop(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    if (showDrop && inputRef.current) {
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
  }, [showDrop])

  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults([]); return }
    timer.current = setTimeout(() => {
      setSearching(true)
      searchApi.query(q.trim(), targetType as RecordType, 8)
        .then(r => {
          setResults(r.items)
          setShowDrop(r.items.length > 0)
        })
        .catch(() => setResults([]))
        .finally(() => setSearching(false))
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, targetType])

  function openSuggestions() {
    if (!targetType) return
    setSearching(true)
    searchApi.query(q.trim(), targetType as RecordType, 8)
      .then(r => {
        setResults(r.items)
        setShowDrop(r.items.length > 0)
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
    setRelType('')
  }

  function confirm() {
    if (!picked || !relType.trim()) return
    onAdd({ id: picked.id, label: picked.title, relation_type: relType.trim() })
    setPicked(null)
    setRelType('')
  }

  if (picked) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, color: 'var(--fg-2)', flex: 1 }}>{picked.title}</span>
          <button className="btn sm ico gh" onClick={() => setPicked(null)} title="Auswahl aufheben"><X size={12} /></button>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {relTypeTerms.length > 0 ? (
            <select className="fld" style={{ flex: 1 }} value={relType} onChange={e => setRelType(e.target.value)}>
              <option value="">— Relationstyp wählen —</option>
              {relTypeTerms.map(t => (
                <option key={t.id} value={t.term}>{getLabel(t, t.term)}</option>
              ))}
            </select>
          ) : (
            <input className="fld" style={{ flex: 1 }} value={relType}
              onChange={e => setRelType(e.target.value)}
              placeholder="Relationstyp (z.B. depicts, created_by)"
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); confirm() } }}
              autoFocus
            />
          )}
          <button className="btn pri sm" onClick={confirm} disabled={!relType.trim()}>Hinzufügen</button>
          <button className="btn gh sm" onClick={() => { setPicked(null); setRelType('') }}>Abbrechen</button>
        </div>
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
        placeholder={targetType ? `${targetType} suchen (mind. 2 Zeichen)…` : 'Kein Ziel-Typ konfiguriert'}
        disabled={disabled || !targetType}
      />
      {searching && (
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 11, color: 'var(--fg-3)' }}>
          Suche…
        </div>
      )}
      {showDrop && results.length > 0 && dropPos && (
        <div ref={dropRef} style={{
          position: 'fixed', top: dropPos.top, left: dropPos.left, width: dropPos.width, zIndex: 9999,
          background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,.18)', maxHeight: dropPos.maxHeight, overflowY: 'auto',
        }}>
          {results.map(r => (
            <button
              key={r.id}
              onMouseDown={e => { e.preventDefault(); pickRecord(r) }}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', border: 'none', borderBottom: '1px solid var(--border)', background: 'none', cursor: 'pointer' }}
              className="authority-hit"
            >
              <div style={{ fontWeight: 500, fontSize: 13 }}>{r.title}</div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{r.id.slice(0, 8)}…</div>
            </button>
          ))}
        </div>
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

interface Props {
  recordType: RecordType
  recordId?: string
  onBack?: () => void
  onSaved?: (id: string) => void
  onDirtyChange?: (dirty: boolean) => void
}

export function ScreenForm({ recordType, recordId, onBack, onSaved, onDirtyChange }: Props) {
  const isNew = !recordId || recordId === 'new'
  const currentId = isNew ? null : recordId!
  const api = getApi(recordType)
  const label = TYPE_LABELS[recordType]
  const subtypeKey = SUBTYPE_KEY[recordType]
  const showIdno  = true
  const showMedia = recordType === 'object'
  const showGeo   = recordType === 'place'
  const showProcedureFields = recordType === 'procedure'
  const showCollectionStatus = recordType === 'object'
  const user = getTokenUser()
  const canEditLocked = user?.role === 'admin' || user?.role === 'superuser'

  const [fields, setFields] = useState<FieldDefinition[]>([])
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
  const [mediaTypeTerms, setMediaTypeTerms] = useState<VocabularyTerm[]>([])
  const [uploadLicenseUri, setUploadLicenseUri] = useState('')
  const [uploadRightsName, setUploadRightsName] = useState('')
  const [uploadRightsUri, setUploadRightsUri] = useState('')
  const [relTypeTerms, setRelTypeTerms] = useState<VocabularyTerm[]>([])
  const [availableSubtypes, setAvailableSubtypes] = useState<RecordSubtype[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [savedId, setSavedId] = useState<string | null>(currentId)
  const [saveOk, setSaveOk]   = useState(false)
  const [saveNotice, setSaveNotice] = useState<string | null>(null)

  const [rels, setRels]           = useState<Relation[]>([])
  const [relTitles, setRelTitles] = useState<Record<string, string>>({})
  const [relMeta, setRelMeta]     = useState<Record<string, Record<string, unknown>>>({})
  const [objectStatuses, setObjectStatuses] = useState<Record<string, string>>({})
  const [addTargetType, setAddTargetType] = useState<RecordType>('object')
  const [addSearchQ, setAddSearchQ]       = useState('')
  const [addResults, setAddResults]       = useState<SearchResult[]>([])
  const [addSearching, setAddSearching]   = useState(false)
  const [addSelected, setAddSelected]     = useState<SearchResult | null>(null)
  const [addSaving, setAddSaving]         = useState(false)
  const [addProcedureOpen, setAddProcedureOpen] = useState(false)
  const [completionDialog, setCompletionDialog] = useState<{ count: number; status: string } | null>(null)
  const [aiBusyField, setAiBusyField] = useState<string | null>(null)

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
    api.snapshots.list(id).then(setSnapshots).catch(() => {})
  }, [api])

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
      const metaMap: Record<string, Record<string, unknown>> = {}
      const statusMap: Record<string, string> = {}
      await Promise.all(loaded.map(async r => {
        const isFrom = r.from_id === id
        const targetType = isFrom ? r.to_type : r.from_type
        const targetId = isFrom ? r.to_id : r.from_id
        const key = `${targetType}/${targetId}`
        try {
          const rec = await (getApi(targetType as RecordType).get as (id: string) => Promise<AnyRecord>)(targetId)
          const m = rec.metadata_ as Record<string, unknown>
          titleMap[key] = extractTitle(m, (rec as { idno?: string | null }).idno ?? targetId.slice(0, 8) + '…')
          metaMap[key] = m
          if (targetType === 'object') {
            statusMap[targetId] = (rec as { collection_status?: string | null }).collection_status ?? 'active'
          }
        } catch {
          titleMap[key] = targetId.slice(0, 8) + '…'
        }
      }))
      setRelTitles(titleMap)
      setRelMeta(metaMap)
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
    setSubtype('')
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
    setRelMeta({})
    setObjectStatuses({})
    setAddProcedureOpen(false)
    setCompletionDialog(null)

    // Load available subtypes for this record type
    if (subtypeKey) {
      subtypes.list(recordType).then(setAvailableSubtypes).catch(() => setAvailableSubtypes([]))
    } else {
      setAvailableSubtypes([])
    }

    const loadRecP = isNew ? Promise.resolve(null) : (api.get as (id: string) => Promise<AnyRecord>)(recordId!)

    loadRecP
      .then(async rec => {
        let recSubtype: string | undefined
        if (rec) {
          setStatus(rec.status as Status)
          setLoadedStatus(rec.status as Status)
          setValues(rec.metadata_)
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
        }
        const fieldDefs = await schema.list(recordType, recSubtype)
        setFields(fieldDefs)
        if (!rec) setValues(defaultsFor(fieldDefs))
      })
      .catch(e => setError(e.message))
      .finally(() => { setLoading(false); setIsDirty(false) })

    if (!isNew && currentId) loadRelations(currentId)
  }, [recordId, recordType, isNew])

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
    if (savedId) loadSnapshots(savedId)
  }, [savedId, loadSnapshots])

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
        if (rt) return vocabularies.listTerms(rt.id)
        return []
      })
      .then(setRelTypeTerms)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const searchOpen =
      (showProcedureFields && addTargetType === 'object') ||
      (showCollectionStatus && addProcedureOpen && addTargetType === 'procedure')
    if (!searchOpen || addSearchQ.trim().length < 2) { setAddResults([]); return }
    setAddSearching(true)
    const timer = setTimeout(() => {
      const q = addSearchQ.trim()
      const request = addTargetType === 'procedure'
        ? procedures.list({ q, page_size: 6 }).then(r => r.items.map(procedureSearchResult))
        : searchApi.query(q, addTargetType, 6).then(r => r.items)
      request
        .then(setAddResults)
        .catch(() => setAddResults([]))
        .finally(() => setAddSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [addSearchQ, addTargetType, showProcedureFields, showCollectionStatus, addProcedureOpen])

  async function handleAddObjectRelation(result: SearchResult) {
    if (!savedId) return
    setAddSaving(true)
    try {
      const created = await relationsApi.create({
        from_type: recordType, from_id: savedId,
        to_type: 'object', to_id: result.id,
        relation_type: relTypeTerms[0]?.term ?? 'concerns',
      })
      setRels(prev => [...prev, created])
      setRelTitles(prev => ({ ...prev, [`object/${created.to_id}`]: result.title }))
      objects.get(result.id).then(obj => {
        setObjectStatuses(prev => ({ ...prev, [result.id]: obj.collection_status ?? 'active' }))
      }).catch(() => {})
      setAddSearchQ('')
      setAddResults([])
    } catch (e) { alert((e as Error).message) }
    finally { setAddSaving(false) }
  }

  async function handleAddProcedureRelation(selected = addSelected) {
    if (!selected || !savedId) return
    setAddSaving(true)
    try {
      const created = await relationsApi.create({
        from_type: recordType, from_id: savedId,
        to_type: 'procedure', to_id: selected.id,
        relation_type: 'concerns',
      })
      setRels(prev => [...prev, created])
      setRelTitles(prev => ({ ...prev, [`procedure/${created.to_id}`]: selected.title }))
      setAddProcedureOpen(false); setAddSearchQ(''); setAddSelected(null); setAddResults([])
    } catch (e) { alert((e as Error).message) }
    finally { setAddSaving(false) }
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
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" className="ck" checked={Boolean(val)} onChange={e => onChange(e.target.checked)} disabled={disabled} />
            <span style={{ fontSize: 13 }}>{sf.label.de || sf.name}</span>
          </label>
        )
      case 'number':
        return <input className="fld" type="number" step="any" value={(val as string) ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={getLabel(sf, sf.name)} />
      case 'date':
        return <input className="fld" type="text" value={(val as string) ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder="YYYY, YYYY-MM oder YYYY-MM-DD" />
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
            targetType={(sf.settings?.target_type as string) ?? ''}
            onAdd={entry => onChange(entry)}
            disabled={disabled}
          />
        )
      default:
        return <input className="fld" value={(val as string) ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={getLabel(sf, sf.name)} />
    }
  }

  function addRelationEntry(name: string, entry: RelationEntry) {
    const cur = (values[name] as RelationEntry[] | undefined) ?? []
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
    // subtype is required when subtypes are configured
    if (subtypeKey && (availableSubtypes.length > 0 || showProcedureFields) && !subtype) {
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
            if (!/^\d{4}(-\d{2}(-\d{2})?)?$/.test(item)) {
              errors[f.name] = 'Ungültiges Datum. Erlaubte Formate: YYYY, YYYY-MM, YYYY-MM-DD'
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
        if (v && !/^\d{4}(-\d{2}(-\d{2})?)?$/.test(v)) {
          errors[f.name] = 'Ungültiges Datum. Erlaubte Formate: YYYY, YYYY-MM, YYYY-MM-DD'
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
      if (v && !/^\d{4}(-\d{2}(-\d{2})?)?$/.test(v)) {
        return { level: 'error', message: 'Ungültiges Datum. Erlaubte Formate: YYYY, YYYY-MM, YYYY-MM-DD' }
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
    if (hasValue && !window.confirm(`Vorhandenen Wert in "${getLabel(field, field.name)}" durch KI-Vorschlag ersetzen?`)) {
      return
    }
    setAiBusyField(field.name)
    setError(null)
    try {
      const result = await ai.complete({
        field_definition_id: field.id,
        record_type: recordType,
        record_id: targetId,
      })
      setValuesDirty(prev => ({ ...prev, [field.name]: result.value }))
      clearFieldFeedback(field.name)
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
        status: completingProcedure ? loadedStatus : status,
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
        await (api.update as (id: string, d: typeof payload) => Promise<AnyRecord>)(recordId!, payload)
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
      try {
        const updated = await media.patch(savedId, uploaded.id, {
          license_uri: uploadLicenseUri.trim() || null,
          rights_holder: buildRightsHolder(uploadRightsName.trim(), uploadRightsUri.trim()),
        })
        setMediaFiles(prev => prev.map(f => f.id === uploaded.id ? updated : f))
      } catch (e) {
        setUploadError(`Upload erfolgreich, Rechte konnten nicht gespeichert werden: ${(e as Error).message}`)
      }
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
  const showTwoCol   = showMedia || !isNew
  const objectRels = showProcedureFields ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) === 'object') : []
  const procedureRels = showCollectionStatus ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) === 'procedure') : []
  const otherRels = showProcedureFields
    ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) !== 'object')
    : showCollectionStatus
      ? rels.filter(r => (r.from_id === savedId ? r.to_type : r.from_type) !== 'procedure')
      : rels
  const linkedProcedureIds = new Set(procedureRels.map(r => r.from_id === savedId ? r.to_id : r.from_id))
  const visibleProcedureResults = addTargetType === 'procedure'
    ? addResults.filter(r => !linkedProcedureIds.has(r.id))
    : []
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ background: 'var(--panel)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', border: '1px solid var(--border-s)', borderRadius: 6, overflow: 'hidden' }}>
            {statusOptions.map(s => (
              <button key={s} onClick={() => { setStatus(s); setIsDirty(true) }}
                style={{ border: 0, padding: '5px 10px', fontSize: 12, fontWeight: 500, fontFamily: 'inherit', cursor: 'pointer',
                  background: status === s ? 'var(--accent)' : '#fff',
                  color: status === s ? '#fff' : 'var(--fg-2)',
                  borderLeft: s !== 'draft' ? '1px solid var(--border-s)' : undefined }}>
                {statusLabels[s]}
              </button>
            ))}
          </div>
          {!isNew && recordType !== 'procedure' && status === 'public' && (
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
            if (isDirty && !window.confirm('Du hast ungespeicherte Änderungen. Trotzdem verlassen?')) return
            onBack?.()
          }} disabled={saving}>
            {justCreated ? 'Zur Liste' : 'Verwerfen'}
          </button>
          {!justCreated && (
            <button className="btn pri" onClick={handleSave} disabled={saving}>
              {saving ? 'Speichert…' : 'Speichern'}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca', padding: '8px 24px', fontSize: 13, color: '#b91c1c', flexShrink: 0 }}>
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

      {justCreated && (
        <div style={{ background: '#f0fdf4', borderBottom: '1px solid #bbf7d0', padding: '8px 24px', fontSize: 13, color: '#166534', flexShrink: 0 }}>
          {label} gespeichert.{showMedia ? ' Bilder können jetzt hochgeladen werden.' : ''}
        </div>
      )}
      {saveOk && (
        <div style={{ background: saveNotice?.includes('Validierungshinweisen') ? '#fffbeb' : '#f0fdf4', borderBottom: saveNotice?.includes('Validierungshinweisen') ? '1px solid #fcd34d' : '1px solid #bbf7d0', padding: '8px 24px', fontSize: 13, color: saveNotice?.includes('Validierungshinweisen') ? '#92400e' : '#166534', flexShrink: 0 }}>
          {saveNotice ?? 'Änderungen gespeichert.'}
        </div>
      )}

      <div className="scroll">
        <div className={showTwoCol ? 'form-grid' : undefined} style={showTwoCol ? undefined : { padding: '20px 24px', maxWidth: 680 }}>
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

                {showProcedureFields && (
                  <div className="field">
                    <div className="lbl">Vorgangstyp</div>
                    <select
                      className="fld"
                      value={subtype}
                      onChange={e => { setSubtype(e.target.value); setIsDirty(true); clearFieldFeedback('__subtype') }}
                      disabled={justCreated}
                      style={getFeedbackStyle('__subtype')}
                    >
                      <option value="">— Vorgangstyp wählen —</option>
                      {PROCEDURE_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                    </select>
                    {(fieldErrors['__subtype'] || fieldWarnings['__subtype']) && (
                      <div style={{ fontSize: 11, color: fieldErrors['__subtype'] ? '#dc2626' : '#92400e', marginTop: 4 }}>
                        {fieldErrors['__subtype'] ?? fieldWarnings['__subtype']}
                      </div>
                    )}
                  </div>
                )}

                {subtypeKey && !showProcedureFields && availableSubtypes.length > 0 && (
                  <div className="field">
                    <div className="lbl">{recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : 'Occurrence-Typ'}</div>
                    <select
                      className="fld"
                      value={subtype}
                      onChange={e => { setSubtype(e.target.value); setIsDirty(true); clearFieldFeedback('__subtype') }}
                      disabled={justCreated}
                      style={getFeedbackStyle('__subtype')}
                    >
                      <option value="">— {recordType === 'entity' ? 'Entitätstyp' : recordType === 'place' ? 'Orts-Typ' : recordType === 'object' ? 'Objekt-Typ' : 'Occurrence-Typ'} wählen —</option>
                      {availableSubtypes.map(s => (
                        <option key={s.id} value={s.name}>{getLabel(s, s.name)}</option>
                      ))}
                    </select>
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
                    <div style={{ display: 'flex', gap: 8 }}>
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
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                        <input className="fld mono" type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Startdatum" />
                        <input className="fld mono" type="date" value={dueDate} onChange={e => { setDueDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Fälligkeitsdatum" />
                        <input className="fld mono" type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setIsDirty(true) }} disabled={justCreated} title="Enddatum" />
                      </div>
                    </div>
                  </>
                )}

                {fields.map(f => {
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
                    <fieldset key={f.id} className="field" disabled={Boolean(f.settings?.is_locked) && !canEditLocked} style={{ border: 0, padding: 0, margin: 0 }}>
                      <div className="lbl">
                        {getLabel(f, f.name)}
                        {f.is_required && <span className="req">*</span>}
                        {repeatable && <span className="h">wiederholbar</span>}
                        {Boolean(f.settings?.is_locked) && <span className="h">{canEditLocked ? 'gesperrt · Admin-Bearbeitung' : 'gesperrt'}</span>}
                        {getFieldAiConfig(f) && (
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

                      {f.field_type === 'vocab' ? (
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
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px', borderRadius: 4, background: 'var(--panel)', border: '1px solid var(--border-s)', fontSize: 13 }}>
                                  <span style={{ flex: 1 }}>{entry.label}</span>
                                  <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--mono)' }}>{entry.relation_type}</span>
                                  <button className="btn sm ico gh" onClick={() => removeRelationEntry(f.name, i)} disabled={justCreated}><X size={10} /></button>
                                </div>
                              ))}
                            </div>
                            <RelationInput
                              targetType={(f.settings?.target_type as string) ?? ''}
                              targetSubtype={f.settings?.target_subtype as string | undefined}
                              relTypeVocabId={f.settings?.relation_type_vocab as string | undefined}
                              onAdd={entry => addRelationEntry(f.name, entry)}
                              disabled={justCreated}
                            />
                          </>
                        ) : (
                          <>
                            {val && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, padding: '4px 8px', borderRadius: 4, background: 'var(--panel)', border: '1px solid var(--border-s)', fontSize: 13 }}>
                                <span style={{ flex: 1 }}>{(val as RelationEntry).label}</span>
                                <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--mono)' }}>{(val as RelationEntry).relation_type}</span>
                                <button className="btn sm ico gh" onClick={() => setField(f.name, undefined)} disabled={justCreated}><X size={10} /></button>
                              </div>
                            )}
                            {!val && (
                              <RelationInput
                                targetType={(f.settings?.target_type as string) ?? ''}
                                targetSubtype={f.settings?.target_subtype as string | undefined}
                                relTypeVocabId={f.settings?.relation_type_vocab as string | undefined}
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
                                  <div className="lbl">
                                    {getLabel(sf, sf.name)}
                                    {sf.is_required && <span className="req">*</span>}
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
                              <input className="fld" value={v}
                                type={f.field_type === 'number' ? 'number' : 'text'}
                                step={f.field_type === 'number' ? 'any' : undefined}
                                onChange={e => updateRepeat(f.name, i, e.target.value)}
                                placeholder={getLabel(f, f.name)}
                                disabled={justCreated} />
                              <button className="btn sm ico gh" onClick={() => removeRepeat(f.name, i)} disabled={justCreated}><X size={12} /></button>
                            </div>
                          ))}
                          <button className="btn sm gh" onClick={() => addRepeat(f.name)} disabled={justCreated}>
                            <Plus size={12} /> Weiteren Wert
                          </button>
                        </>
                      ) : f.field_type === 'boolean' ? (
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <input type="checkbox" className="ck"
                            checked={Boolean(val)}
                            onChange={e => setField(f.name, e.target.checked)}
                            disabled={justCreated} />
                          <span style={{ fontSize: 13 }}>{f.label.de}</span>
                        </label>
                      ) : f.field_type === 'date' ? (
                        <input className="fld"
                          type="text"
                          value={(val as string) ?? ''}
                          onChange={e => {
                            setField(f.name, e.target.value)
                            clearFieldFeedback(f.name)
                          }}
                          onBlur={() => handleFieldBlur(f)}
                          placeholder="YYYY, YYYY-MM oder YYYY-MM-DD"
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

                {fields.length === 0 && !showIdno && !subtypeKey && !showGeo && (
                  <div className="empty">Keine Felder definiert. Schema unter Konfiguration → Schemata anlegen.</div>
                )}
                {fields.length === 0 && (showIdno || subtypeKey || showGeo) && (
                  <div style={{ fontSize: 12, color: 'var(--fg-3)', paddingTop: 4 }}>
                    Keine weiteren dynamischen Felder. Schema unter Konfiguration → Schemata anlegen.
                  </div>
                )}
              </div>
            </div>
          </div>

          {showTwoCol && (
            <div>
              {showMedia && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Medien</span>
                    {mediaFiles.length > 0 && <span className="sub">{mediaFiles.length} Datei{mediaFiles.length !== 1 ? 'en' : ''}</span>}
                  </div>
                  <div className="bd">
                    {mediaFiles.length > 0 && (
                      <div style={{ marginBottom: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 10 }}>
                        {mediaFiles.map(f => (
                          <div key={f.id} style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border-s)', background: 'var(--bg-s)' }}>
                            <a href={`${BASE}/v1/objects/${savedId}/media/${f.id}/file`} target="_blank" rel="noreferrer" style={{ display: 'block', aspectRatio: '1', overflow: 'hidden' }}>
                              {f.status !== 'error' ? (
                                <img
                                  src={`${BASE}/v1/objects/${savedId}/media/${f.id}/file`}
                                  alt={f.filename}
                                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                                />
                              ) : null}
                              {f.status === 'error' && (
                                <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                                  <AlertCircle size={18} style={{ color: '#dc2626' }} />
                                  <span style={{ fontSize: 9, color: '#dc2626' }}>Fehler</span>
                                </div>
                              )}
                              {f.status !== 'ready' && f.status !== 'pending' && f.status !== 'error' && (
                                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <Image size={20} style={{ color: 'var(--fg-3)' }} />
                                </div>
                              )}
                            </a>
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
                              <option value="">— Typ —</option>
                              {mediaTypeTerms.map(t => (
                                <option key={t.id} value={t.term}>{getLabel(t, t.term)}</option>
                              ))}
                            </select>
                            <div style={{ padding: 6, display: 'grid', gap: 4, borderTop: '1px solid var(--border-s)' }}>
                              <input
                                className="fld"
                                style={{ fontSize: 10, padding: '3px 5px' }}
                                defaultValue={f.license_uri ?? ''}
                                data-media-rights="license_uri"
                                list="media-license-options"
                                placeholder="Lizenz-URI"
                                onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))}
                              />
                              <input
                                className="fld"
                                style={{ fontSize: 10, padding: '3px 5px' }}
                                defaultValue={f.rights_holder?.name ?? ''}
                                data-media-rights="rights_holder_name"
                                placeholder="Rechteinhaber"
                                onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))}
                              />
                              <input
                                className="fld"
                                style={{ fontSize: 10, padding: '3px 5px' }}
                                defaultValue={f.rights_holder?.uri ?? ''}
                                data-media-rights="rights_holder_uri"
                                placeholder="Rechteinhaber-URI"
                                onBlur={e => handleMediaRights(f.id, mediaRightsFromInputs(e.currentTarget.parentElement))}
                              />
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
                      <div className="fg-2" style={{ marginBottom: 10 }}>
                        <div className="field">
                          <div className="lbl">Lizenz für neue Uploads <span className="h">optional</span></div>
                          <input className="fld" list="media-license-options" value={uploadLicenseUri} onChange={e => setUploadLicenseUri(e.target.value)} placeholder="Lizenz-URI wählen oder eingeben" />
                          {!uploadLicenseUri && <div style={{ fontSize: 11, color: '#b45309', marginTop: 4 }}>Keine Lizenz angegeben. Upload bleibt möglich.</div>}
                        </div>
                        <div className="field">
                          <div className="lbl">Rechteinhaber für neue Uploads <span className="h">optional</span></div>
                          <input className="fld" value={uploadRightsName} onChange={e => setUploadRightsName(e.target.value)} placeholder="Name" />
                          <input className="fld" value={uploadRightsUri} onChange={e => setUploadRightsUri(e.target.value)} placeholder="URI (optional)" style={{ marginTop: 4 }} />
                        </div>
                      </div>
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
                            <label style={{ color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
                              &nbsp;auswählen
                              <input ref={fileInputRef} type="file" style={{ display: 'none' }} accept="image/jpeg,image/png,image/tiff,image/webp" onChange={onFileChange} />
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
                <div className="card" style={{ marginBottom: 14, overflow: addProcedureOpen ? 'visible' : undefined }}>
                  <div className="hd">
                    <span>Vorgänge</span>
                    {procedureRels.length > 0 && <span className="sub">{procedureRels.length}</span>}
                    <div className="grow" />
                    {!addProcedureOpen && hasSavedId && (
                      <button
                        className="btn sm gh"
                        onClick={() => {
                          setAddTargetType('procedure')
                          setAddProcedureOpen(true)
                          setAddSearchQ('')
                          setAddSelected(null)
                          setAddResults([])
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
                        <div className="field" style={{ marginBottom: 8 }}>
                          <div className="lbl">Vorgang suchen</div>
                          <div style={{ position: 'relative' }}>
                            <input
                              className="fld"
                              value={addTargetType === 'procedure' ? addSearchQ : ''}
                              onFocus={() => setAddTargetType('procedure')}
                              onChange={e => { setAddTargetType('procedure'); setAddSearchQ(e.target.value) }}
                              placeholder="Vorgang suchen…"
                              autoFocus
                              aria-label="Vorgang suchen"
                            />
                            {addTargetType === 'procedure' && addSearchQ.trim().length >= 2 && (
                              <div style={{ position: 'absolute', zIndex: 20, left: 0, right: 0, top: 'calc(100% + 4px)', border: '1px solid var(--border-s)', borderRadius: 6, background: '#fff', boxShadow: '0 10px 24px rgba(15, 23, 42, .12)', maxHeight: 180, overflowY: 'auto' }}>
                                {addSearching ? (
                                  <div style={{ padding: '8px 10px', fontSize: 12, color: 'var(--fg-3)' }}>Suche…</div>
                                ) : visibleProcedureResults.length > 0 ? (
                                  visibleProcedureResults.map(r => (
                                    <button key={r.id} className="btn gh" style={{ width: '100%', justifyContent: 'flex-start', border: 0, borderRadius: 0, borderBottom: '1px solid var(--border-s)', padding: '8px 10px', fontSize: 12 }} onClick={() => handleAddProcedureRelation(r)} disabled={addSaving}>
                                      {r.title}
                                    </button>
                                  ))
                                ) : addResults.length > 0 ? (
                                  <div style={{ padding: '8px 10px', fontSize: 12, color: 'var(--fg-3)' }}>Alle Treffer sind bereits verknüpft.</div>
                                ) : (
                                  <div style={{ padding: '8px 10px', fontSize: 12, color: 'var(--fg-3)' }}>Keine Ergebnisse.</div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn gh sm" onClick={() => { setAddProcedureOpen(false); setAddSearchQ(''); setAddSelected(null); setAddResults([]) }}>
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
                      <input
                        className="fld"
                        value={addTargetType === 'object' ? addSearchQ : ''}
                        onFocus={() => setAddTargetType('object')}
                        onChange={e => { setAddTargetType('object'); setAddSearchQ(e.target.value) }}
                        placeholder="Suchbegriff (mind. 2 Zeichen)…"
                      />
                      {addTargetType === 'object' && addSearching && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>Suche…</div>}
                      {addTargetType === 'object' && addResults.length > 0 && !addSearching && (
                        <div style={{ border: '1px solid var(--border-s)', borderRadius: 4, marginTop: 4, maxHeight: 160, overflowY: 'auto' }}>
                          {addResults.map(r => (
                            <button key={r.id} className="btn gh" style={{ width: '100%', justifyContent: 'flex-start', borderRadius: 0, border: 0, borderBottom: '1px solid var(--border-s)', fontSize: 12 }} onClick={() => handleAddObjectRelation(r)} disabled={addSaving}>
                              {r.title}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {!isNew && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="hd">
                    <span>Beziehungen</span>
                    {otherRels.length > 0 && <span className="sub">{otherRels.length}</span>}
                    <div className="grow" />
                  </div>
                  <div className="bd">
                    {otherRels.length > 0 && (
                      <div style={{ marginBottom: 0 }}>
                        {otherRels.map(r => {
                          const typeLabel: Record<string, string> = { object: 'Objekt', entity: 'Entität', place: 'Ort', occurrence: 'Occurrence', procedure: 'Vorgang' }
                          const relTypeTerm = relTypeTerms.find(t => t.term === r.relation_type)
                          const isFrom = r.from_id === savedId
                          const relTypeLabel = relTypeTerm
                            ? (isFrom
                              ? getLabel(relTypeTerm, r.relation_type)
                              : (relTypeTerm.inverse_label?.de ?? relTypeTerm.inverse_label?.en ?? getLabel(relTypeTerm, r.relation_type)))
                            : r.relation_type
                          const targetType = isFrom ? r.to_type : r.from_type
                          const targetId = isFrom ? r.to_id : r.from_id
                          const targetKey = `${targetType}/${targetId}`
                          const inheritedFieldNames = fields
                            .filter(f => f.field_type === 'relation' && (f.settings?.target_type as string) === targetType)
                            .flatMap(f => (f.settings?.inherited_fields as string[]) ?? [])
                          const inheritedMeta = relMeta[targetKey]
                          return (
                            <div key={r.id}>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-s)', fontSize: 12 }}>
                                <span style={{ color: 'var(--fg-2)' }} title={r.relation_type}>
                                  {!isFrom && <span style={{ color: 'var(--accent)', marginRight: 4 }}>←</span>}
                                  {relTypeLabel}
                                </span>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={`${targetType}: ${targetId}`}>
                                  <span style={{ fontSize: 10, color: 'var(--fg-4)', marginRight: 4 }}>{typeLabel[targetType] ?? targetType}</span>
                                  <a
                                    href={`#${TYPE_ROUTES[targetType] ?? targetType}/${targetId}`}
                                    onClick={e => { e.preventDefault(); navigateToRecord(targetType, targetId) }}
                                    style={{ color: 'inherit', textDecoration: 'none', cursor: 'pointer' }}
                                    onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                                    onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
                                  >
                                    {relTitles[targetKey] ?? targetId.slice(0, 8) + '…'}
                                  </a>
                                </span>
                              </div>
                              {inheritedMeta && inheritedFieldNames.length > 0 && (
                                <div style={{ padding: '3px 0 5px', borderBottom: '1px solid var(--border-s)', display: 'flex', flexWrap: 'wrap', gap: '2px 12px' }}>
                                  {inheritedFieldNames.map(fname => {
                                    const val = inheritedMeta[fname]
                                    if (val == null) return null
                                    let text: string | null = null
                                    if (typeof val === 'string') text = val || null
                                    else if (Array.isArray(val) && val.length > 0) {
                                      const first = val[0]
                                      text = typeof first === 'string' ? first : (typeof first === 'object' && first !== null ? String((first as Record<string,unknown>).value ?? '') || null : null)
                                    }
                                    if (!text) return null
                                    return <span key={fname} style={{ fontSize: 11, color: 'var(--fg-3)' }}>{fname}: {text}</span>
                                  })}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {otherRels.length === 0 && (
                      <div className="empty" style={{ padding: '16px 0' }}>Noch keine Relationen.</div>
                    )}
                  </div>
                </div>
              )}

              {!isNew && savedId && (
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
                              const snap = await api.snapshots.create(savedId, snapLabel.trim())
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
                                const restored = await api.snapshots.restore(savedId, snap.id)
                                setStatus(restored.status as Status)
                                setIdno(restored.idno ?? '')
                                setValues(restored.metadata_ as Record<string, unknown>)
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
    </div>
  )
}
