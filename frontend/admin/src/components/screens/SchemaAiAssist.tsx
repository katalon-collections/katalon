import { useRef, useState } from 'react'
import { schema, vocabularies } from '../../api/client'
import type { SchemaAiChatMessage, SchemaAiFieldProposal, SchemaAiProposal, SchemaAiVocabularyProposal } from '../../api/client'
import type { FieldDefinition } from '../../types'
import { getLabel } from '../../types'
import { Lightning } from '../ui/Icons'
import { FIELD_TYPE_LABELS } from './ScreenSchema'

type Props = {
  targetType: string
  targetTypeLabel: string
  targetSubtype: string
  existingFieldCount: number
  onClose: () => void
  onApplied: () => void
}

type ApplyResult = { name: string; status: 'ok' | 'error'; message?: string }

function substituteTmpIds(settings: Record<string, unknown>, idMap: Map<string, string>): Record<string, unknown> {
  const out = { ...settings }
  for (const key of ['vocabulary_id', 'relation_type_vocab']) {
    const value = out[key]
    if (typeof value === 'string' && value.startsWith('tmp:')) {
      const real = idMap.get(value.slice(4))
      if (real) out[key] = real
    }
  }
  return out
}

function displayLabel(label: Record<string, string>, name: string): string {
  const fromLabel = getLabel(label)
  if (fromLabel) return fromLabel
  const spaced = name.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function FieldPreview({ field, depth = 0 }: { field: SchemaAiFieldProposal; depth?: number }) {
  return (
    <div style={{ marginLeft: depth * 16, padding: '6px 0', borderBottom: depth === 0 ? '1px solid var(--border-s)' : 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 4, padding: '1px 5px' }}>NEU</span>
        <strong style={{ fontSize: 13 }}>{displayLabel(field.label, field.name)}</strong>
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>({field.name})</span>
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</span>
        {field.is_required && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Pflicht</span>}
        {field.is_repeatable && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Wiederholbar</span>}
      </div>
      {typeof field.settings.validation_regex === 'string' && field.settings.validation_regex && (
        <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: "'IBM Plex Mono',monospace" }}>{field.settings.validation_regex}</div>
      )}
      {field.children?.map(child => <FieldPreview key={child.name} field={child} depth={depth + 1} />)}
    </div>
  )
}

export function SchemaAiAssist({ targetType, targetTypeLabel, targetSubtype, existingFieldCount, onClose, onApplied }: Props) {
  const [messages, setMessages] = useState<SchemaAiChatMessage[]>([])
  const [proposal, setProposal] = useState<SchemaAiProposal | null>(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [applyResults, setApplyResults] = useState<ApplyResult[] | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  async function send() {
    const text = input.trim()
    if (!text || busy) return
    const nextMessages = [...messages, { role: 'user' as const, content: text }]
    setMessages(nextMessages)
    setInput('')
    setBusy(true)
    setError(null)
    try {
      const res = await schema.aiAssist(targetType, targetSubtype || null, nextMessages)
      setMessages(res.reply.trim() ? [...nextMessages, { role: 'assistant', content: res.reply }] : nextMessages)
      setProposal(res.proposal)
      setApplyResults(null)
      requestAnimationFrame(() => logRef.current?.scrollTo({ top: logRef.current.scrollHeight }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function createField(field: SchemaAiFieldProposal, idMap: Map<string, string>, sortOrder: number, parentId?: string): Promise<void> {
    const payload: Omit<FieldDefinition, 'id'> = {
      target_type: targetType,
      target_subtype: targetSubtype || null,
      name: field.name,
      label: field.label,
      field_type: field.field_type,
      is_required: field.is_required,
      is_repeatable: field.field_type === 'group' ? field.is_repeatable : (parentId ? false : field.is_repeatable),
      is_translatable: parentId ? false : field.is_translatable,
      sort_order: sortOrder,
      settings: substituteTmpIds(field.settings, idMap),
      show_in_detail: true,
      show_in_list: true,
      is_facet: false,
      is_searchable: true,
      ...(parentId ? { parent_id: parentId } : {}),
    }
    const created = await schema.create(payload)
    if (field.children?.length) {
      for (let i = 0; i < field.children.length; i++) {
        await createField(field.children[i], idMap, i, created.id)
      }
    }
  }

  async function apply() {
    if (!proposal) return
    setApplying(true)
    const idMap = new Map<string, string>()
    const results: ApplyResult[] = []

    for (const vocab of proposal.vocabularies) {
      try {
        const created = await vocabularies.create({ name: vocab.name, kind: vocab.kind, is_hierarchical: vocab.is_hierarchical })
        idMap.set(vocab.tmp_id, created.id)
        for (const term of vocab.terms) {
          await vocabularies.createTerm(created.id, {
            vocabulary_id: created.id,
            term: term.term,
            label: term.label,
            inverse_label: {},
            metadata_: {},
            parent_id: null,
            applies_from: [],
            applies_to: [],
          })
        }
        results.push({ name: `Vokabular: ${vocab.name}`, status: 'ok' })
      } catch (e) {
        results.push({ name: `Vokabular: ${vocab.name}`, status: 'error', message: (e as Error).message })
      }
    }

    let sortOrder = existingFieldCount
    for (const field of proposal.fields) {
      try {
        await createField(field, idMap, sortOrder)
        results.push({ name: displayLabel(field.label, field.name), status: 'ok' })
      } catch (e) {
        results.push({ name: displayLabel(field.label, field.name), status: 'error', message: (e as Error).message })
      }
      sortOrder += 1
    }

    setApplyResults(results)
    setApplying(false)
    setProposal(null)
    onApplied()
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 640, maxWidth: '92vw', maxHeight: '86vh', display: 'flex', flexDirection: 'column' }}>
        <div className="hd">
          <span><Lightning size={13} /> KI-Assistent für Felder</span>
          <div className="grow" />
          <button className="btn sm" onClick={onClose}>Schließen</button>
        </div>
        <div ref={logRef} className="bd" style={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--fg-3)', margin: 0 }}>
            Beschreibe, was erfasst werden soll. Der Assistent schlägt neue Felder für <strong>{targetTypeLabel}{targetSubtype ? ` / ${targetSubtype}` : ''}</strong> vor,
            fragt bei Bedarf nach und ändert nie bestehende Felder.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {messages.map((m, i) => (
              <div key={i} style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                background: m.role === 'user' ? 'var(--accent)' : 'var(--panel)',
                color: m.role === 'user' ? '#fff' : 'var(--fg-1)',
                borderRadius: 8, padding: '10px 14px', maxWidth: '85%', fontSize: 13,
                lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {m.content}
              </div>
            ))}
            {busy && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--fg-3)' }}>
                <span style={{
                  display: 'inline-block', width: 12, height: 12, flexShrink: 0,
                  border: '2px solid var(--border-s)', borderTopColor: 'var(--fg-3)',
                  borderRadius: '50%', animation: 'spin .7s linear infinite',
                }} />
                KI denkt nach…
              </div>
            )}
          </div>

          {error && <div style={{ fontSize: 13, color: '#b91c1c' }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <textarea
              className="fld"
              rows={3}
              style={{ flex: 1, resize: 'vertical' }}
              placeholder={messages.length === 0 ? "z.B. Ich will historische Postkarten erfassen: Karten haben Absende- und Empfangsort, Datierungen, sind frankiert/unfrankiert und brauchen eine Bildbeschreibung." : undefined}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send() }}
            />
            <button className="btn pri" onClick={send} disabled={busy || !input.trim()}>Senden</button>
          </div>

          {proposal && (proposal.vocabularies.length > 0 || proposal.fields.length > 0) && (
            <div style={{ border: '1px solid var(--border-s)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Vorschlag</div>
              {proposal.vocabularies.map(v => (
                <VocabPreview key={v.tmp_id} vocab={v} />
              ))}
              {proposal.fields.map(f => <FieldPreview key={f.name} field={f} />)}
              <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                <button className="btn pri" onClick={apply} disabled={applying}>{applying ? 'Wird angelegt…' : 'Übernehmen'}</button>
              </div>
            </div>
          )}

          {applyResults && (
            <div style={{ fontSize: 12 }}>
              {applyResults.map((r, i) => (
                <div key={i} style={{ color: r.status === 'ok' ? 'var(--fg-2)' : '#b91c1c' }}>
                  {r.status === 'ok' ? '✓' : '✗'} {r.name}{r.message ? `: ${r.message}` : ''}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function VocabPreview({ vocab }: { vocab: SchemaAiVocabularyProposal }) {
  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid var(--border-s)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 4, padding: '1px 5px' }}>NEUES VOKABULAR</span>
        <strong style={{ fontSize: 13 }}>{vocab.name}</strong>
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{vocab.terms.length} Terme</span>
      </div>
    </div>
  )
}
