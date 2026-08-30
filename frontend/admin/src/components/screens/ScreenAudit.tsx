import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { audit } from '../../api/client'
import type { AuditEntry } from '../../types'
import { Check, Edit, Trash, Globe, Upload, Link, Lightning } from '../ui/Icons'

const TYPE_ROUTES: Record<string, string> = {
  object: 'form', entity: 'entities-form', place: 'places-form', occurrence: 'occurrences-form', procedure: 'procedures-form',
}

function navigateToRecord(type: string, id: string) {
  const route = TYPE_ROUTES[type]
  if (!route) return
  window.history.pushState({ route, editId: id }, '', `#${route}/${id}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function RecordLink({ type, id, label }: { type: string; id: string; label: string }) {
  if (!TYPE_ROUTES[type]) return <b>{label}</b>
  return (
    <a
      href={`#${TYPE_ROUTES[type]}/${id}`}
      onClick={e => { e.preventDefault(); navigateToRecord(type, id) }}
      style={{ color: 'inherit', textDecoration: 'underline', textUnderlineOffset: 2, cursor: 'pointer' }}
    >
      <b>{label}</b>
    </a>
  )
}


const ACTION_ICON: Record<string, React.ReactNode> = {
  create:            <Check size={13} />,
  update:            <Edit size={13} />,
  delete:            <Trash size={13} />,
  publish:           <Globe size={13} />,
  media_add:         <Upload size={13} />,
  media_update:      <Edit size={13} />,
  media_delete:      <Trash size={13} />,
  relation_add:      <Link size={13} />,
  relation_update:   <Link size={13} />,
  relation_delete:   <Link size={13} />,
  ai_schema_assist:  <Lightning size={13} />,
}



type AiSchemaAssistFields = {
  target_type?: string
  target_subtype?: string | null
  model?: string
  input_tokens?: number
  output_tokens?: number
}

function aiSchemaAssistTitle(diff: AiSchemaAssistFields): string {
  const typeLabel = (diff.target_type && TYPE_SINGULAR_LABELS[diff.target_type]) || diff.target_type || 'Schema'
  return diff.target_subtype ? `${typeLabel} · ${diff.target_subtype}` : typeLabel
}

type ExtraFields = {
  filename?: string
  relation_type?: string
  relation_id?: string
  related_record_type?: string
  related_record_id?: string
  related_record_label?: string
}

function extraLines(diff: ExtraFields): string[] {
  const lines: string[] = []
  if (diff.filename) lines.push(t('extraFile', { filename: diff.filename }))
  if (diff.relation_type) lines.push(t('extraRelationType', { relationType: diff.relation_type }))
  return lines
}

function relatedRecordSuffix(diff: ExtraFields): string | null {
  if (!diff.related_record_type || !diff.related_record_id) return null
  return diff.related_record_label ?? diff.related_record_id.slice(-8)
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function userDisplay(entry: AuditEntry) {
  return entry.user_name ?? (entry.user_id ? entry.user_id.slice(-8) : '—')
}

function formatDiffValue(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  if (Array.isArray(v)) return v.map(formatDiffValue).join(', ')
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v)
    } catch {
      return String(v)
    }
  }
  return String(v)
}

const ACTIONS = ['all', 'create', 'update', 'delete', 'publish', 'media', 'relation']

type Props = { initialFilter?: string | null; onFilterChange?: (filter: string) => void }

export function ScreenAudit({ initialFilter, onFilterChange }: Props = {}) {
  const { t } = useTranslation('screenAudit')
  const [entries, setEntries] = useState<AuditEntry[]>([])

  const ACTION_LABELS: Record<string, string> = {
    create: t('actionLabels.create'), update: t('actionLabels.update'), delete: t('actionLabels.delete'), publish: t('actionLabels.publish'),
    media_add: t('actionLabels.media_add'), media_update: t('actionLabels.media_update'), media_delete: t('actionLabels.media_delete'),
    relation_add: t('actionLabels.relation_add'), relation_update: t('actionLabels.relation_update'), relation_delete: t('actionLabels.relation_delete'),
    ai_schema_assist: t('actionLabels.ai_schema_assist'),
  }
  const TYPE_SINGULAR_LABELS: Record<string, string> = {
    object: t('typeLabels.object'), entity: t('typeLabels.entity'), place: t('typeLabels.place'), occurrence: t('typeLabels.occurrence'), procedure: t('typeLabels.procedure'),
  }
  const [filter, setFilter] = useState(initialFilter && ACTIONS.includes(initialFilter) ? initialFilter : 'all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    audit.list({ limit: 200 })
      .then(setEntries)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = filter === 'all'
    ? entries
    : filter === 'media' || filter === 'relation'
      ? entries.filter(e => e.action.startsWith(`${filter}_`))
      : entries.filter(e => e.action === filter)

  // A relation change is logged once per endpoint it connects (so each record's
  // own history shows it); in this cross-record feed that'd render as two rows
  // for the same event, so keep only the first occurrence per relation+action.
  const seenRelations = new Set<string>()
  const items = filtered.filter(evt => {
    const relationId = (evt.changed_fields as ExtraFields)?.relation_id
    if (!relationId) return true
    const key = `${evt.action}:${relationId}`
    if (seenRelations.has(key)) return false
    seenRelations.add(key)
    return true
  })

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>{t('headline')}</h1><div className="sub">{t('subtitle')}</div></div>
      </div>

      <div className="toolbar">
        {ACTIONS.map(a => (
          <button key={a} className={`btn${filter === a ? ' pri' : ' gh'}`} onClick={() => { setFilter(a); onFilterChange?.(a) }}>
            {a === 'all' ? t('actionLabels.all') : a === 'media' ? t('actionLabels.media') : a === 'relation' ? t('actionLabels.relation') : ACTION_LABELS[a]}
          </button>
        ))}
      </div>

      {loading && <div className="empty" style={{ paddingTop: 40 }}>{t('loading')}</div>}
      {error && <div className="empty" style={{ paddingTop: 40, color: '#f87171' }}>{error}</div>}

      {!loading && !error && (
        <div className="timeline">
          {items.map(evt => {
            const diff = evt.changed_fields as { old?: Record<string, string>; new?: Record<string, string> } & ExtraFields
            const extras = extraLines(diff)
            const relatedRecord = relatedRecordSuffix(diff)
            return (
              <div key={evt.id} className={`evt ic-${evt.action}`}>
                <div className="when">{fmt(evt.created_at)}</div>
                <div className="ic">{ACTION_ICON[evt.action]}</div>
                <div className="body">
                  <div className="ti">
                    {ACTION_LABELS[evt.action] ?? evt.action}:{' '}
                    {evt.action === 'ai_schema_assist'
                      ? <b>{aiSchemaAssistTitle(diff as AiSchemaAssistFields)}</b>
                      : evt.action === 'delete'
                        ? <b>{evt.record_label ?? String(evt.record_id).slice(-8)}</b>
                        : <RecordLink type={evt.record_type} id={evt.record_id} label={evt.record_label ?? String(evt.record_id).slice(-8)} />}
                    {relatedRecord && (
                      <>
                        {' '}{'↔'}{' '}
                        {diff.related_record_type && evt.action !== 'relation_delete'
                          ? <RecordLink type={diff.related_record_type} id={diff.related_record_id!} label={relatedRecord} />
                          : <b>{relatedRecord}</b>}
                      </>
                    )}
                  </div>
                  {evt.action === 'ai_schema_assist' ? (
                    (() => {
                      const ai = diff as AiSchemaAssistFields
                      const tokens = (ai.input_tokens ?? 0) + (ai.output_tokens ?? 0)
                      return <div className="sub">{ai.model ?? '—'}{tokens > 0 ? ` · ${tokens} Tokens` : ''}</div>
                    })()
                  ) : (
                    <div className="sub">{evt.record_type} · {evt.record_id.slice(-8)}</div>
                  )}
                  {extras.length > 0 && (
                    <div className="sub" style={{ marginTop: 2 }}>{extras.join(' · ')}</div>
                  )}
                  {diff.old && (
                    <div className="diff">
                      {Object.entries(diff.old).map(([k, v]) => (
                        <div key={k} style={{ overflowWrap: 'anywhere' }}>
                          <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{k}: </span>
                          <span className="rem">{formatDiffValue(v)}</span>
                          {' → '}
                          <span className="add">{formatDiffValue((diff.new ?? {})[k])}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="who">
                  <div className="av">{(userDisplay(evt)[0] ?? '?').toUpperCase()}</div>
                  {userDisplay(evt)}
                </div>
              </div>
            )
          })}
          {items.length === 0 && <div className="empty">{t('empty')}</div>}
        </div>
      )}
    </div>
  )
}
