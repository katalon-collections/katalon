// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
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

type ApplyResult = { name: string; status: 'ok' | 'error' | 'skip'; message?: string }

function substituteTmpIds(settings: Record<string, unknown>, idMap: Map<string, string>): Record<string, unknown> {
  const out = { ...(settings ?? {}) }
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

function FieldPreview({ field, depth = 0, selected, onToggle }: {
  field: SchemaAiFieldProposal
  depth?: number
  selected: Set<string>
  onToggle: (name: string) => void
}) {
  const isSelected = selected.has(field.name)
  return (
    <div style={{ marginLeft: depth * 16, padding: '6px 0', borderBottom: depth === 0 ? '1px solid var(--border-s)' : 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggle(field.name)}
          title={isSelected ? 'Feld vom Vorschlag ausschließen' : 'Feld in den Vorschlag aufnehmen'}
          style={{ accentColor: 'var(--accent)', flexShrink: 0 }}
        />
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 4, padding: '1px 5px' }}>NEU</span>
        <strong style={{ fontSize: 13, opacity: isSelected ? 1 : 0.45 }}>{displayLabel(field.label, field.name)}</strong>
        <span style={{ fontSize: 11, color: 'var(--fg-3)', opacity: isSelected ? 1 : 0.45 }}>({field.name})</span>
        <span style={{ fontSize: 11, color: 'var(--fg-3)', opacity: isSelected ? 1 : 0.45 }}>{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</span>
        {field.is_required && <span style={{ fontSize: 11, color: 'var(--fg-3)', opacity: isSelected ? 1 : 0.45 }}>Pflicht</span>}
        {field.is_repeatable && <span style={{ fontSize: 11, color: 'var(--fg-3)', opacity: isSelected ? 1 : 0.45 }}>Wiederholbar</span>}
      </div>
      {typeof field.settings?.validation_regex === 'string' && field.settings.validation_regex && (
        <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: "'IBM Plex Mono',monospace", opacity: isSelected ? 1 : 0.45 }}>{field.settings.validation_regex}</div>
      )}
      {field.children?.map(child => <FieldPreview key={child.name} field={child} depth={depth + 1} selected={selected} onToggle={onToggle} />)}
    </div>
  )
}

function ChatText({ content }: { content: string }) {
  const parts = content.split(/(https?:\/\/\S+)/g)
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a key={i} href={part} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'underline', wordBreak: 'break-all' }}>{part}</a>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  )
}

export function SchemaAiAssist({ targetType, targetTypeLabel, targetSubtype, existingFieldCount, onClose, onApplied }: Props) {
  const [messages, setMessages] = useState<SchemaAiChatMessage[]>([])
  const [proposal, setProposal] = useState<SchemaAiProposal | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [applyResults, setApplyResults] = useState<ApplyResult[] | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  // Reset selection to "alles übernehmen" whenever a new proposal arrives.
  useEffect(() => {
    if (!proposal) return
    const names = new Set<string>()
    for (const field of proposal.fields) {
      names.add(field.name)
      field.children?.forEach(child => names.add(child.name))
    }
    setSelected(names)
  }, [proposal])

  function toggleField(name: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

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
      show_in_list: false,
      is_facet: false,
      is_searchable: true,
      ...(parentId ? { parent_id: parentId } : {}),
    }
    const created = await schema.create(payload)
    const children = field.children?.filter(child => selected.has(child.name)) ?? []
    for (let i = 0; i < children.length; i++) {
      await createField(children[i], idMap, i, created.id)
    }
  }

  async function apply() {
    if (!proposal) return
    setApplying(true)
    const idMap = new Map<string, string>()
    const results: ApplyResult[] = []

    const selectedFields = proposal.fields.filter(field => selected.has(field.name))
    const referencedVocabTmpIds = new Set<string>()
    function collectVocabRefs(field: SchemaAiFieldProposal) {
      const settings = field.settings ?? {}
      for (const key of ['vocabulary_id', 'relation_type_vocab']) {
        const value = settings[key]
        if (typeof value === 'string' && value.startsWith('tmp:')) referencedVocabTmpIds.add(value.slice(4))
      }
      field.children?.forEach(collectVocabRefs)
    }
    selectedFields.forEach(collectVocabRefs)

    for (const vocab of proposal.vocabularies) {
      if (!referencedVocabTmpIds.has(vocab.tmp_id)) continue
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
    for (const field of selectedFields) {
      if (field.field_type === 'group' && field.children?.length) {
        const keptChildren = field.children.filter(child => selected.has(child.name))
        if (keptChildren.length === 0) {
          results.push({ name: displayLabel(field.label, field.name), status: 'skip', message: 'keine Unterfelder ausgewählt' })
          continue
        }
      }
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
            fragt bei Bedarf nach, verlinkt passende Quellen und ändert nie bestehende Felder. Einzelne Felder des Vorschlags können vor dem Übernehmen abgewählt werden.
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
                {m.role === 'user' ? m.content : <ChatText content={m.content} />}
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
              {proposal.fields.map(f => <FieldPreview key={f.name} field={f} selected={selected} onToggle={toggleField} />)}
              <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
                {(() => {
                  const selectedCount = proposal.fields.filter(f => selected.has(f.name)).length
                  return (
                    <>
                      <button className="btn pri" onClick={apply} disabled={applying}>
                        {applying ? 'Wird angelegt…' : selectedCount === proposal.fields.length ? 'Übernehmen' : `Übernehmen (${selectedCount} von ${proposal.fields.length})`}
                      </button>
                      {selectedCount < proposal.fields.length && (
                        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Nicht ausgewählte Felder werden übersprungen.</span>
                      )}
                    </>
                  )
                })()}
              </div>
            </div>
          )}

          {applyResults && (
            <div style={{ fontSize: 12 }}>
              {applyResults.map((r, i) => (
                <div key={i} style={{ color: r.status === 'error' ? '#b91c1c' : r.status === 'skip' ? 'var(--fg-3)' : 'var(--fg-2)' }}>
                  {r.status === 'ok' ? '✓' : r.status === 'skip' ? '–' : '✗'} {r.name}{r.message ? `: ${r.message}` : ''}
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
