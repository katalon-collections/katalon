// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Fragment, useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { schema, vocabularies } from '../../api/client'
import type { FieldDefinition, RecordType, Vocabulary, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { AuthorityInput, type AuthorityEntry } from '../AuthorityInput'
import { ChevD, ChevR, Edit, Help, Plus, Tag, Trash, Upload, X } from '../ui/Icons'
import { LabelEditor } from '../ui/LabelEditor'
import { HelpPopover } from '../ui/HelpPopover'
import { VocabularyImport } from './VocabularyImport'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

const RECORD_TYPES: RecordType[] = ['object', 'entity', 'place', 'occurrence', 'procedure', 'collection', 'storage_location']

function recordTypeLabel(t: TFunction, rt: RecordType): string {
  return t(`recordTypes.${rt}`)
}

function AppliesCheckboxes({ value, onChange }: { value: RecordType[]; onChange: (v: RecordType[]) => void }) {
  const { t } = useTranslation('screenVocab')
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', fontSize: 12 }}>
      {RECORD_TYPES.map(rt => (
        <label key={rt} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={value.includes(rt)}
            onChange={e => onChange(e.target.checked ? [...value, rt] : value.filter(v => v !== rt))}
          />
          {recordTypeLabel(t, rt)}
        </label>
      ))}
      <span style={{ color: 'var(--fg-3)' }}>{t('appliesCheckboxes.noSelectionMeansAll')}</span>
    </div>
  )
}

function appliesLabel(t: TFunction, term: Pick<VocabularyTerm, 'applies_from' | 'applies_to'>): string {
  const from = (term.applies_from ?? []) as RecordType[]
  const to = (term.applies_to ?? []) as RecordType[]
  if (from.length === 0 && to.length === 0) return t('appliesLabel.all')
  const fmt = (arr: RecordType[]) => arr.length === 0 ? t('appliesLabel.all') : arr.map(r => recordTypeLabel(t, r)).join(', ')
  return `${fmt(from)} → ${fmt(to)}`
}

type TreeTerm = { term: VocabularyTerm; depth: number }

function flattenTerms(terms: VocabularyTerm[]): TreeTerm[] {
  const children = new Map<string, VocabularyTerm[]>()
  const byId = new Map(terms.map(term => [term.id, term]))
  const roots = terms.filter(term => !term.parent_id || !byId.has(term.parent_id))
  for (const term of terms) {
    if (term.parent_id && byId.has(term.parent_id)) {
      children.set(term.parent_id, [...(children.get(term.parent_id) ?? []), term])
    }
  }

  const flattened: TreeTerm[] = []
  const seen = new Set<string>()
  const visit = (term: VocabularyTerm, depth: number) => {
    if (seen.has(term.id)) return
    seen.add(term.id)
    flattened.push({ term, depth })
    children.get(term.id)?.forEach(child => visit(child, depth + 1))
  }
  roots.forEach(root => visit(root, 0))
  terms.forEach(term => visit(term, 0))
  return flattened
}

function descendantIds(terms: VocabularyTerm[], termId: string): Set<string> {
  const descendants = new Set<string>([termId])
  let changed = true
  while (changed) {
    changed = false
    for (const term of terms) {
      if (term.parent_id && descendants.has(term.parent_id) && !descendants.has(term.id)) {
        descendants.add(term.id)
        changed = true
      }
    }
  }
  return descendants
}

function AppliesPreview({ from, to }: { from: RecordType[]; to: RecordType[] }) {
  const { t } = useTranslation('screenVocab')
  return (
    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--fg-3)' }} aria-live="polite">
      {t('appliesPreview.appliesTo')}: <strong>{appliesLabel(t, { applies_from: from, applies_to: to })}</strong>
      <div>{t('appliesPreview.hint')}</div>
    </div>
  )
}

function typePreview(types: RecordType[]): string {
  const { t } = useTranslation('screenVocab')
  return types.length === 0 ? t('appliesLabel.all') : types.map(type => recordTypeLabel(t, type)).join(', ')
}

function RelationTypeOverview() {
  const { t } = useTranslation('screenVocab')
  return (
    <div
      style={{
        marginBottom: 16,
        padding: '10px 14px',
        background: 'var(--panel-2)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        fontSize: 12,
        color: 'var(--fg-2)',
      }}
    >
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', color: 'var(--fg)', fontWeight: 600 }}>
        <Help size={14} aria-hidden="true" />
        {t('relationTypeHelp.heading')}
      </div>
      <div style={{ marginTop: 4 }}>
        {t('relationTypeHelp.description', { source: t('relationTypeHelp.source'), target: t('relationTypeHelp.target') })}
      </div>
      <div style={{ marginTop: 4, color: 'var(--fg-3)' }}>
        {t('relationTypeHelp.example')}
      </div>
    </div>
  )
}

function RelationTypePreview({ label, inverseLabel, from, to }: {
  label: string
  inverseLabel: string
  from: RecordType[]
  to: RecordType[]
}) {
  const { t } = useTranslation('screenVocab')
  const source = typePreview(from)
  const target = typePreview(to)
  return (
    <div
      style={{
        marginTop: 8,
        padding: '8px 10px',
        background: 'var(--panel-2)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        fontSize: 12,
        color: 'var(--fg-2)',
      }}
    >
      <strong style={{ color: 'var(--fg)' }}>{t('relationTypeHelp.preview')}</strong>
      <div style={{ marginTop: 4, color: 'var(--fg)' }}>
        {source} — <em>{label || t('relationTypeHelp.labelFallback')}</em> → {target}
        <br />
        {target} — <em>{inverseLabel || t('relationTypeHelp.inverseFallback')}</em> → {source}
      </div>
    </div>
  )
}

function isSystemVocabulary(v: Vocabulary): boolean {
  return v.kind === 'relation' || v.name === 'relation_types' || v.name === 'media_types'
}

function fieldLabel(field: FieldDefinition): string {
  return field.label.de || field.label.en || field.name
}

function CustomFieldsEditor({ fields, value, onChange }: {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  onChange: (value: Record<string, unknown>) => void
}) {
  function set(name: string, fieldValue: unknown) {
    const next = { ...value }
    if (fieldValue === '' || fieldValue === null || (Array.isArray(fieldValue) && fieldValue.length === 0)) {
      delete next[name]
    } else {
      next[name] = fieldValue
    }
    onChange(next)
  }

  function renderSingle(field: FieldDefinition, current: unknown, update: (next: unknown) => void) {
    if (field.field_type === 'boolean') {
      return <input type="checkbox" className="ck" checked={current === true} onChange={e => update(e.target.checked)} />
    }
    if (field.field_type === 'authority') {
      return (
        <AuthorityInput
          source={String(field.settings.source ?? '')}
          value={(current as AuthorityEntry | null) ?? null}
          onChange={update}
        />
      )
    }
    return (
      <input
        className="fld"
        type={field.field_type === 'number' ? 'number' : 'text'}
        value={current == null ? '' : String(current)}
        onChange={e => update(field.field_type === 'number'
          ? (e.target.value === '' ? '' : Number(e.target.value))
          : e.target.value)}
      />
    )
  }

  return (
    <>
      {fields.map(field => {
        const current = value[field.name]
        const items = field.is_repeatable ? (Array.isArray(current) ? current : []) : []
        return (
          <div className="field" key={field.id}>
            <div className="lbl">{fieldLabel(field)}{field.is_required && <span className="req"> *</span>}</div>
            {field.is_repeatable ? (
              <>
                {items.map((item, index) => (
                  <div key={index} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ flex: 1 }}>{renderSingle(field, item, next => set(field.name, items.map((old, i) => i === index ? next : old)))}</div>
                    <button type="button" className="btn sm gh" onClick={() => set(field.name, items.filter((_, i) => i !== index))}><X size={12} /></button>
                  </div>
                ))}
                <button type="button" className="btn sm" onClick={() => set(field.name, [...items, field.field_type === 'boolean' ? false : null])}>
                  <Plus size={12} /> Wert
                </button>
              </>
            ) : renderSingle(field, current, next => set(field.name, next))}
          </div>
        )
      })}
    </>
  )
}

function MetadataSummary({ fields, metadata }: { fields: FieldDefinition[]; metadata: Record<string, unknown> }) {
  const values = fields.flatMap(field => {
    const raw = metadata[field.name]
    if (raw == null || raw === '' || (Array.isArray(raw) && raw.length === 0)) return []
    const items = Array.isArray(raw) ? raw : [raw]
    const text = items.map(item => {
      if (typeof item === 'object' && item && 'external_id' in item) {
        const authority = item as AuthorityEntry
        return authority.label || `${authority.source}:${authority.external_id}`
      }
      return item === true ? 'Ja' : item === false ? 'Nein' : String(item)
    }).join(', ')
    return [`${fieldLabel(field)}: ${text}`]
  })
  return values.length > 0
    ? <div style={{ marginTop: 4, color: 'var(--fg-3)', fontSize: 11 }}>{values.join(' · ')}</div>
    : null
}

interface ScreenVocabProps {
  initialVocab?: string | null
  onVocabSelect?: (name: string) => void
}

export function ScreenVocab({ initialVocab, onVocabSelect }: ScreenVocabProps = {}) {
  const { t } = useTranslation('screenVocab')
  const requiredBadge = t('requiredBadge')
  const uriLabel = t('uri')
  const uriPlaceholder = t('uriPlaceholder')
  const exactMatchUrisLabel = t('exactMatchUris')
  const exactMatchUrisHelp = t('exactMatchUrisHelp')
  const uriHelpTitle = t('uriHelpPopover.title')
  const uriHelpDesc = t('uriHelpPopover.description')
  const uriHelpExample = t('uriHelpPopover.example')
  const uriHelpExportNote = t('uriHelpPopover.exportNote')
  const exactMatchUrisHelpTitle = t('exactMatchUrisHelpPopover.title')
  const exactMatchUrisHelpDesc = t('exactMatchUrisHelpPopover.description')
  const exactMatchUrisHelpExample = t('exactMatchUrisHelpPopover.example')
  const exactMatchUrisHelpSeparatorNote = t('exactMatchUrisHelpPopover.separatorNote')
  const [vocabs, setVocabs] = useState<Vocabulary[]>([])
  const [terms, setTerms] = useState<VocabularyTerm[]>([])
  const [activeVocab, setActiveVocab] = useState<string | null>(null)
  const [expandedVocab, setExpandedVocab] = useState<string | null>(null)
  const [selectedTermId, setSelectedTermId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [termsLoading, setTermsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // new vocab form
  const [showNewVocab, setShowNewVocab] = useState(false)
  const [newVocabName, setNewVocabName] = useState('')
  const [newVocabHierarchical, setNewVocabHierarchical] = useState(false)
  const [newVocabKind, setNewVocabKind] = useState<'term' | 'relation'>('term')
  const [newVocabCanonicalUri, setNewVocabCanonicalUri] = useState('')
  const [savingVocab, setSavingVocab] = useState(false)

  // new term form
  const [showNewTerm, setShowNewTerm] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [newTermTerm, setNewTermTerm] = useState('')
  const [newTermLabel, setNewTermLabel] = useState<Record<string, string>>({})
  const [newTermInverseLabel, setNewTermInverseLabel] = useState<Record<string, string>>({})
  const [newTermAppliesFrom, setNewTermAppliesFrom] = useState<RecordType[]>([])
  const [newTermAppliesTo, setNewTermAppliesTo] = useState<RecordType[]>([])
  const [savingTerm, setSavingTerm] = useState(false)
  const [newTermMetadata, setNewTermMetadata] = useState<Record<string, unknown>>({})
  const [newTermParentId, setNewTermParentId] = useState('')
  const [newTermUri, setNewTermUri] = useState('')
  const [newTermExactMatchUris, setNewTermExactMatchUris] = useState('')
  // edit term inline
  const [editTermId, setEditTermId] = useState<string | null>(null)
  const [editTermTerm, setEditTermTerm] = useState('')
  const [editTermLabel, setEditTermLabel] = useState<Record<string, string>>({})
  const [editTermInverseLabel, setEditTermInverseLabel] = useState<Record<string, string>>({})
  const [editTermAppliesFrom, setEditTermAppliesFrom] = useState<RecordType[]>([])
  const [editTermAppliesTo, setEditTermAppliesTo] = useState<RecordType[]>([])
  const [savingEditTerm, setSavingEditTerm] = useState(false)
  const [editTermMetadata, setEditTermMetadata] = useState<Record<string, unknown>>({})
  const [editTermParentId, setEditTermParentId] = useState('')
  const [editTermUri, setEditTermUri] = useState('')
  const [editTermExactMatchUris, setEditTermExactMatchUris] = useState('')
  const [termFields, setTermFields] = useState<FieldDefinition[]>([])
  const languages = useSupportedLanguages()

  const loadVocabs = useCallback(() => {
    setLoading(true)
    vocabularies.list()
      .then(data => {
        setVocabs(data)
        if (data.length > 0 && !activeVocab) {
          const target = initialVocab ? data.find(v => v.name === initialVocab) : null
          setActiveVocab(target ? target.id : data[0].id)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeVocab, initialVocab])

  useEffect(() => { loadVocabs() }, [])

  const loadTerms = useCallback(() => {
    if (!activeVocab) return
    setTermsLoading(true)
    vocabularies.listTerms(activeVocab)
      .then(setTerms)
      .catch(console.error)
      .finally(() => setTermsLoading(false))
  }, [activeVocab])

  useEffect(() => { loadTerms() }, [loadTerms])
  useEffect(() => {
    if (!activeVocab) {
      setTermFields([])
      return
    }
    schema.list('vocabulary_term', activeVocab)
      .then(setTermFields)
      .catch(() => setTermFields([]))
    setNewTermMetadata({})
    setNewTermParentId('')
    setEditTermId(null)
    setShowImport(false)
  }, [activeVocab])

  async function createVocab() {
    if (!newVocabName.trim()) return
    setSavingVocab(true)
    try {
      const v = await vocabularies.create({
        name: newVocabName.trim(),
        is_hierarchical: newVocabKind === 'relation' ? false : newVocabHierarchical,
        kind: newVocabKind,
        canonical_uri: newVocabCanonicalUri.trim() || undefined,
      })
      setVocabs(prev => [...prev, v])
      setActiveVocab(v.id)
      onVocabSelect?.(v.name)
      setNewVocabName('')
      setNewVocabCanonicalUri('')
      setNewVocabHierarchical(false)
      setNewVocabKind('term')
      setShowNewVocab(false)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingVocab(false)
    }
  }

  async function createTerm() {
    if (!activeVocab || !newTermTerm.trim()) return
    setError(null)
    setSavingTerm(true)
    try {
      await vocabularies.createTerm(activeVocab, {
        vocabulary_id: activeVocab,
        term: newTermTerm.trim(),
        label: newTermLabel,
        inverse_label: vocab?.kind === 'relation' ? newTermInverseLabel : {},
        metadata_: newTermMetadata,
        parent_id: vocab?.is_hierarchical ? newTermParentId || null : null,
        applies_from: vocab?.kind === 'relation' ? newTermAppliesFrom : [],
        applies_to: vocab?.kind === 'relation' ? newTermAppliesTo : [],
        uri: newTermUri.trim() || null,
        exact_match_uris: newTermExactMatchUris.split(/[\n,]+/).map(s => s.trim()).filter(Boolean),
      })
      setNewTermTerm('')
      setNewTermLabel({})
      setNewTermInverseLabel({})
      setNewTermAppliesFrom([])
      setNewTermAppliesTo([])
      setNewTermUri('')
      setNewTermExactMatchUris('')
      setNewTermMetadata({})
      setNewTermParentId('')
      setShowNewTerm(false)
      loadTerms()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSavingTerm(false)
    }
  }

  function startEditTerm(t: VocabularyTerm) {
    setEditTermId(t.id)
    setEditTermTerm(t.term)
    setEditTermLabel(t.label ?? {})
    setEditTermInverseLabel(t.inverse_label ?? {})
    setEditTermAppliesFrom((t.applies_from ?? []) as RecordType[])
    setEditTermAppliesTo((t.applies_to ?? []) as RecordType[])
    setEditTermMetadata({ ...(t.metadata_ ?? {}) })
    setEditTermParentId(t.parent_id ?? '')
    setEditTermUri(t.uri ?? '')
    setEditTermExactMatchUris((t.exact_match_uris ?? []).join(', '))
  }

  async function saveEditTerm(t: VocabularyTerm) {
    setError(null)
    setSavingEditTerm(true)
    try {
      await vocabularies.updateTerm(t.id, {
        vocabulary_id: activeVocab!,
        term: editTermTerm.trim(),
        label: editTermLabel,
        inverse_label: vocab?.kind === 'relation' ? editTermInverseLabel : {},
        metadata_: editTermMetadata,
        parent_id: vocab?.is_hierarchical ? editTermParentId || null : null,
        applies_from: vocab?.kind === 'relation' ? editTermAppliesFrom : [],
        applies_to: vocab?.kind === 'relation' ? editTermAppliesTo : [],
        uri: editTermUri.trim() || null,
        exact_match_uris: editTermExactMatchUris.split(/[\n,]+/).map(s => s.trim()).filter(Boolean),
      })
      setEditTermId(null)
      loadTerms()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSavingEditTerm(false)
    }
  }

  async function deleteTerm(id: string) {
    const childCount = terms.filter(term => term.parent_id === id).length
    const message = childCount
      ? `Term wirklich löschen? ${childCount} direkte Unterterm${childCount === 1 ? '' : 'e'} werden zu Haupttermen.`
      : 'Term wirklich löschen?'
    if (!window.confirm(message)) return
    setError(null)
    try {
      await vocabularies.deleteTerm(id)
      loadTerms()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const vocab = vocabs.find(v => v.id === activeVocab)
  const isHierarchical = vocab?.is_hierarchical === true
  const displayTerms = isHierarchical ? flattenTerms(terms) : terms.map(term => ({ term, depth: 0 }))
  const parentOptions = (termId?: string) => {
    const excluded = termId ? descendantIds(terms, termId) : new Set<string>()
    return flattenTerms(terms).filter(({ term }) => !excluded.has(term.id))
  }
  const tableColumnCount = vocab?.kind === 'relation' ? 5 : isHierarchical ? 4 : 3

  function startNewChild(parent: VocabularyTerm) {
    setNewTermTerm('')
    setNewTermLabel({})
    setNewTermInverseLabel({})
    setNewTermAppliesFrom([])
    setNewTermAppliesTo([])
    setNewTermMetadata({})
    setNewTermParentId(parent.id)
    setShowNewTerm(true)
  }

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>{t('headline')}</h1><div className="sub">{t('headlineSub')}</div></div>
        <div className="right">
          <button className="btn" onClick={() => setShowNewVocab(v => !v)}><Plus size={13} /> Neues Vokabular</button>
        </div>
      </div>

      {error && <div role="alert" style={{ padding: '8px 24px', color: '#b91c1c', fontSize: 13 }}>{error}</div>}

      {showNewVocab && (
        <div className="card" style={{ margin: '0 24px 12px', flexShrink: 0 }}>
          <div className="bd">
            <div className="fg-2">
              <div className="field">
                <div className="lbl">Name</div>
                <input className="fld" value={newVocabName} onChange={e => setNewVocabName(e.target.value)} placeholder="Vokabular-Name" autoFocus />
              </div>
              <div className="field">
                <div className="lbl">Art</div>
                <select className="fld" value={newVocabKind} onChange={e => setNewVocabKind(e.target.value as 'term' | 'relation')}>
                  <option value="term">Termvokabular</option>
                  <option value="relation">Relationsvokabular</option>
                </select>
              </div>
              {newVocabKind === 'term' && <div className="field" style={{ paddingTop: 20 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={newVocabHierarchical} onChange={e => setNewVocabHierarchical(e.target.checked)} />
                  <span style={{ fontSize: 13 }}>Hierarchisch</span>
                </label>
              </div>}
              <div className="field">
                <div className="lbl" style={{ display: 'flex', alignItems: 'center' }}>
                  {t('canonicalUri')}
                  <HelpPopover
                    title={t('canonicalUriHelpPopover.title')}
                    content={<div>{t('canonicalUriHelpPopover.description')}</div>}
                  />
                </div>
                <input className="fld mono" value={newVocabCanonicalUri} onChange={e => setNewVocabCanonicalUri(e.target.value)} placeholder={t('canonicalUriPlaceholder')} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn pri" onClick={createVocab} disabled={savingVocab}>Anlegen</button>
              <button className="btn gh" onClick={() => setShowNewVocab(false)}><X size={12} /></button>
            </div>
          </div>
        </div>
      )}

      <div className="vocab-grid" style={{ flex: 1, minHeight: 0 }}>
        <div className="vocab-tree">
          {vocabs.map(v => (
            <div key={v.id}>
              <div className={`tree-it${activeVocab === v.id ? ' active' : ''}`} onClick={() => { setActiveVocab(v.id); onVocabSelect?.(v.name) }}>
                <button
                  className="caret"
                  type="button"
                  aria-label={`${v.name} ${expandedVocab === v.id ? 'zuklappen' : 'aufklappen'}`}
                  aria-expanded={expandedVocab === v.id}
                  onClick={event => {
                    event.stopPropagation()
                    setActiveVocab(v.id)
                    setExpandedVocab(current => current === v.id ? null : v.id)
                    onVocabSelect?.(v.name)
                  }}
                  style={{ border: 0, background: 'none', padding: 0, cursor: v.is_hierarchical ? 'pointer' : 'default' }}
                  disabled={!v.is_hierarchical}
                >
                  {v.is_hierarchical ? (expandedVocab === v.id ? <ChevD size={12} /> : <ChevR size={12} />) : null}
                </button>
                <Tag size={13} className="ic" />
                <span style={{ flex: 1 }}>{v.name}</span>
                {isSystemVocabulary(v) && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 5px',
                      borderRadius: 3,
                      background: 'var(--panel-2)',
                      color: 'var(--fg-3)',
                      border: '1px solid var(--border-s)',
                      marginRight: 6,
                    }}
                  >
                    {t('systemVocabBadge')}
                  </span>
                )}
                {activeVocab === v.id && !termsLoading && <span className="ct">{terms.length}</span>}
              </div>
              {activeVocab === v.id && expandedVocab === v.id && !termsLoading && (
                <div aria-label={`${v.name}-Hierarchie`}>
                  {displayTerms.map(({ term, depth }) => (
                    <button
                      key={term.id}
                      type="button"
                      onClick={() => setSelectedTermId(term.id)}
                      aria-pressed={selectedTermId === term.id}
                      style={{ display: 'block', width: '100%', border: 0, background: selectedTermId === term.id ? 'var(--accent-50)' : 'none', padding: `4px 6px 4px ${30 + depth * 16}px`, textAlign: 'left', color: 'var(--fg-2)', cursor: 'pointer', fontSize: 12 }}
                    >
                      {getLabel(term, term.term)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {vocabs.length === 0 && <div className="empty" style={{ padding: 12, fontSize: 12 }}>Keine Vokabulare.</div>}
        </div>

        <div className="vocab-detail">
          {vocab && (
            <>
              <div className="vocab-detail-head">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>{vocab.name}</span>
                    {isSystemVocabulary(vocab) && (
                      <span
                        className="badge"
                        style={{
                          fontSize: 11,
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: 'var(--panel-2)',
                          color: 'var(--fg-3)',
                          border: '1px solid var(--border-s)',
                          fontWeight: 500,
                        }}
                      >
                        {t('systemVocabBadge')}
                      </span>
                    )}
                  </div>
                  <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>
                    {t('vocabMeta.termsCount', { count: terms.length })} · {vocab.is_hierarchical ? t('vocabMeta.hierarchical') : t('vocabMeta.flat')} · {vocab.kind === 'relation' ? t('vocabMeta.relation') : t('vocabMeta.picklist')}
                  </div>
                  {vocab.canonical_uri && (
                    <div style={{ color: 'var(--fg-3)', fontSize: 11, fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                      <a href={vocab.canonical_uri} target="_blank" rel="noreferrer" style={{ color: 'var(--fg-3)', textDecoration: 'underline' }}>
                        {vocab.canonical_uri}
                      </a>
                    </div>
                  )}
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                  <button type="button" className="btn" onClick={() => setShowImport(true)}>
                    <Upload size={13} /> {t('importButton')}
                  </button>
                  <button className="btn pri" onClick={() => { setNewTermParentId(''); setShowNewTerm(v => !v) }}><Plus size={13} /> Neuer Term</button>
                </div>
              </div>
              {vocab.kind === 'relation' && <RelationTypeOverview />}


              {showNewTerm && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <div className="bd">
                    <div className="fg-2">
                      <div className="field">
                        <div className="lbl">ID (intern) <span style={{ color: '#dc2626', fontSize: 11 }}>{t('requiredBadge')}</span></div>
                        <input className="fld mono" value={newTermTerm} onChange={e => setNewTermTerm(e.target.value)} placeholder="z.B. silbergelatine" autoFocus />
                      </div>
                      <LabelEditor
                        languages={languages}
                        value={newTermLabel}
                        onChange={(lang, val) => setNewTermLabel({ ...newTermLabel, [lang]: val })}
                      />
                      {isHierarchical && (
                        <div className="field">
                          <label className="lbl" htmlFor="new-term-parent">Übergeordneter Term</label>
                          <select id="new-term-parent" className="fld" value={newTermParentId} onChange={e => setNewTermParentId(e.target.value)}>
                            <option value="">Kein übergeordneter Term</option>
                            {parentOptions().map(({ term, depth }) => (
                              <option key={term.id} value={term.id}>{`${'— '.repeat(depth)}${getLabel(term, term.term)} (${term.term})`}</option>
                            ))}
                          </select>
                        </div>
                      )}
                      {vocab.kind === 'relation' && (
                        <LabelEditor
                          languages={languages}
                          value={newTermInverseLabel}
                          onChange={(lang, val) => setNewTermInverseLabel({ ...newTermInverseLabel, [lang]: val })}
                          labelPrefix={t('inverseLabelPrefix')}
                        />
                      )}
                      <div className="field">
                        <div className="lbl" style={{ display: 'flex', alignItems: 'center' }}>
                          {t('uri')}
                          <HelpPopover
                            title={t('uriHelpPopover.title')}
                            content={(
                              <div>
                                <div>{t('uriHelpPopover.description')}</div>
                                <div style={{ marginTop: 4, color: 'var(--fg-3)', fontFamily: 'monospace', fontSize: 11 }}>
                                  {t('uriHelpPopover.example')}
                                </div>
                                <div style={{ marginTop: 4, fontSize: 11 }}>
                                  {t('uriHelpPopover.exportNote')}
                                </div>
                              </div>
                            )}
                          />
                        </div>
                        <input className="fld mono" value={newTermUri} onChange={e => setNewTermUri(e.target.value)} placeholder={t('uriPlaceholder')} />
                      </div>
                      <div className="field">
                        <div className="lbl" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                          <span>{t('exactMatchUris')}</span>
                          <span style={{ color: 'var(--fg-3)', fontSize: 11, fontWeight: 'normal' }}>({t('exactMatchUrisHelp')})</span>
                          <HelpPopover
                            title={t('exactMatchUrisHelpPopover.title')}
                            content={(
                              <div>
                                <div>{t('exactMatchUrisHelpPopover.description')}</div>
                                <div style={{ marginTop: 4, color: 'var(--fg-3)', fontFamily: 'monospace', fontSize: 11 }}>
                                  {t('exactMatchUrisHelpPopover.example')}
                                </div>
                                <div style={{ marginTop: 4, fontSize: 11 }}>
                                  {t('exactMatchUrisHelpPopover.separatorNote')}
                                </div>
                              </div>
                            )}
                          />
                        </div>
                        <input className="fld mono" value={newTermExactMatchUris} onChange={e => setNewTermExactMatchUris(e.target.value)} placeholder="https://d-nb.info/gnd/..., http://id.loc.gov/..." />
                      </div>
                    </div>
                    {vocab.kind === 'relation' && (
                      <>
                        <RelationTypePreview
                          label={getLabel({ label: newTermLabel }, '')}
                          inverseLabel={getLabel({ label: newTermInverseLabel }, '')}
                          from={newTermAppliesFrom}
                          to={newTermAppliesTo}
                        />
                        <div className="fg-2" style={{ marginTop: 8 }}>
                          <div className="field">
                            <div className="lbl">{t('relationFields.sourceTypes')}</div>
                            <AppliesCheckboxes value={newTermAppliesFrom} onChange={setNewTermAppliesFrom} />
                          </div>
                          <div className="field">
                            <div className="lbl">{t('relationFields.targetTypes')}</div>
                            <AppliesCheckboxes value={newTermAppliesTo} onChange={setNewTermAppliesTo} />
                          </div>
                        </div>
                        <AppliesPreview from={newTermAppliesFrom} to={newTermAppliesTo} />
                      </>
                    )}
                    <CustomFieldsEditor fields={termFields} value={newTermMetadata} onChange={setNewTermMetadata} />
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button className="btn pri" onClick={createTerm} disabled={savingTerm}>Anlegen</button>
                      <button className="btn gh" onClick={() => setShowNewTerm(false)}><X size={12} /></button>
                    </div>
                  </div>
                </div>
              )}

              <div className="tw">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th style={{ minWidth: 160 }}>ID</th>
                      <th>Label</th>
                      {vocab.kind === 'relation' && <th>{t('tableHeaders.inverse')}</th>}
                      {vocab.kind === 'relation' && <th>{t('tableHeaders.types')}</th>}
                      {isHierarchical && <th>{t('tableHeaders.parent')}</th>}
                      <th className="col-act" />
                    </tr>
                  </thead>
                  <tbody>
                    {termsLoading && <tr><td colSpan={tableColumnCount} className="empty">Lade…</td></tr>}
                    {!termsLoading && terms.length === 0 && (
                      <tr><td colSpan={tableColumnCount} className="empty">Keine Terme.</td></tr>
                    )}
                    {!termsLoading && displayTerms.map(({ term: termItem, depth }) => (
                      editTermId === termItem.id ? (
                        <Fragment key={termItem.id}>
                          <tr>
                            <td colSpan={tableColumnCount} style={{ background: 'var(--panel)' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, alignItems: 'end', padding: '8px 0' }}>
                                <div className="field">
                                  <div className="lbl">ID <span style={{ color: '#dc2626', fontSize: 11 }}>{requiredBadge}</span></div>
                                  <input className="fld mono" value={editTermTerm} onChange={e => setEditTermTerm(e.target.value)} />
                                </div>
                                <LabelEditor languages={languages} value={editTermLabel} onChange={(lang, val) => setEditTermLabel({ ...editTermLabel, [lang]: val })} />
                                {vocab.kind === 'relation' && <LabelEditor languages={languages} value={editTermInverseLabel} onChange={(lang, val) => setEditTermInverseLabel({ ...editTermInverseLabel, [lang]: val })} labelPrefix={t('inverseLabelPrefix')} />}
                                {isHierarchical && <div className="field">
                                  <label className="lbl" htmlFor={`edit-term-parent-${termItem.id}`}>Übergeordneter Term</label>
                                  <select id={`edit-term-parent-${termItem.id}`} className="fld" value={editTermParentId} onChange={e => setEditTermParentId(e.target.value)}>
                                    <option value="">Kein übergeordneter Term</option>
                                    {parentOptions(termItem.id).map(({ term, depth: parentDepth }) => (
                                      <option key={term.id} value={term.id}>{`${'— '.repeat(parentDepth)}${getLabel(term, term.term)} (${term.term})`}</option>
                                    ))}
                                  </select>
                                </div>}
                                <div className="field">
                                <div className="lbl" style={{ display: 'flex', alignItems: 'center' }}>
                                  {uriLabel}
                                  <HelpPopover
                                    title={uriHelpTitle}
                                    content={(
                                      <div>
                                        <div>{uriHelpDesc}</div>
                                        <div style={{ marginTop: 4, color: 'var(--fg-3)', fontFamily: 'monospace', fontSize: 11 }}>
                                          {uriHelpExample}
                                        </div>
                                        <div style={{ marginTop: 4, fontSize: 11 }}>
                                          {uriHelpExportNote}
                                        </div>
                                      </div>
                                    )}
                                  />
                                </div>
                                <input className="fld mono" value={editTermUri} onChange={e => setEditTermUri(e.target.value)} placeholder={uriPlaceholder} />
                              </div>
                              <div className="field">
                                <div className="lbl" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                                  <span>{exactMatchUrisLabel}</span>
                                  <span style={{ color: 'var(--fg-3)', fontSize: 11, fontWeight: 'normal' }}>({exactMatchUrisHelp})</span>
                                  <HelpPopover
                                    title={exactMatchUrisHelpTitle}
                                    content={(
                                      <div>
                                        <div>{exactMatchUrisHelpDesc}</div>
                                        <div style={{ marginTop: 4, color: 'var(--fg-3)', fontFamily: 'monospace', fontSize: 11 }}>
                                          {exactMatchUrisHelpExample}
                                        </div>
                                        <div style={{ marginTop: 4, fontSize: 11 }}>
                                          {exactMatchUrisHelpSeparatorNote}
                                        </div>
                                      </div>
                                    )}
                                  />
                                </div>
                                <input className="fld mono" value={editTermExactMatchUris} onChange={e => setEditTermExactMatchUris(e.target.value)} placeholder="https://d-nb.info/gnd/..., http://id.loc.gov/..." />
                              </div>
                                <div style={{ display: 'flex', gap: 8 }}>
                                  <button className="btn pri" onClick={() => saveEditTerm(termItem)} disabled={savingEditTerm}>Speichern</button>
                                  <button className="btn gh" onClick={() => setEditTermId(null)}><X size={12} /> Abbrechen</button>
                                </div>
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td colSpan={tableColumnCount} style={{ background: 'var(--panel)' }}>
                              {vocab.kind === 'relation' && (
                                <>
                                  <RelationTypePreview
                                    label={getLabel({ label: editTermLabel }, '')}
                                    inverseLabel={getLabel({ label: editTermInverseLabel }, '')}
                                    from={editTermAppliesFrom}
                                    to={editTermAppliesTo}
                                  />
                                  <div className="fg-2" style={{ marginBottom: 8 }}>
                                    <div className="field">
                                      <div className="lbl">{t('relationFields.sourceTypes')}</div>
                                      <AppliesCheckboxes value={editTermAppliesFrom} onChange={setEditTermAppliesFrom} />
                                    </div>
                                    <div className="field">
                                      <div className="lbl">{t('relationFields.targetTypes')}</div>
                                      <AppliesCheckboxes value={editTermAppliesTo} onChange={setEditTermAppliesTo} />
                                    </div>
                                  </div>
                                  <AppliesPreview from={editTermAppliesFrom} to={editTermAppliesTo} />
                                </>
                              )}
                              <CustomFieldsEditor fields={termFields} value={editTermMetadata} onChange={setEditTermMetadata} />
                            </td>
                          </tr>
                        </Fragment>
                      ) : (
                        <tr key={termItem.id} style={selectedTermId === termItem.id ? { background: 'var(--accent-50)' } : undefined}>
                          <td className="mono" style={{ minWidth: 160, width: 160, paddingLeft: 12 + depth * 16 }}>
                            <div>{termItem.term}</div>
                            {termItem.uri && (
                              <div style={{ fontSize: 11, color: 'var(--fg-3)', wordBreak: 'break-all', marginTop: 2 }}>
                                <a href={termItem.uri} target="_blank" rel="noreferrer" title={termItem.uri} style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                                  {termItem.uri}
                                </a>
                              </div>
                            )}
                            {termItem.exact_match_uris && termItem.exact_match_uris.length > 0 && (
                              <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 2, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                {termItem.exact_match_uris.map((u, i) => (
                                  <a key={i} href={u} target="_blank" rel="noreferrer" title={u} style={{ color: 'var(--fg-3)', textDecoration: 'underline' }}>
                                    ≡ {u.replace(/^https?:\/\//, '').split('/').filter(Boolean).slice(-1)[0] || u}
                                  </a>
                                ))}
                              </div>
                            )}
                          </td>
                          <td style={{ maxWidth: 220 }}>
                            {getLabel(termItem, '—')}
                            <MetadataSummary fields={termFields} metadata={termItem.metadata_ ?? {}} />
                          </td>
                          {vocab.kind === 'relation' && <td style={{ color: 'var(--fg-3)', maxWidth: 220 }}>{getLabel({ label: termItem.inverse_label }, '—')}</td>}
                          {vocab.kind === 'relation' && <td style={{ color: 'var(--fg-3)', maxWidth: 220, fontSize: 12 }}>{appliesLabel(t, termItem)}</td>}
                          {isHierarchical && <td style={{ color: 'var(--fg-3)', maxWidth: 160 }}>{termItem.parent_id ? getLabel(terms.find(term => term.id === termItem.parent_id) ?? termItem, '—') : '—'}</td>}
                          <td className="col-act">
                            <div className="row-actions">
                              <button className="btn sm ico gh" onClick={() => startEditTerm(termItem)}><Edit size={12} /></button>
                              {isHierarchical && <button className="btn sm gh" onClick={() => startNewChild(termItem)}><Plus size={12} /> Unterterm</button>}
                              <button className="btn sm ico gh dn" onClick={() => deleteTerm(termItem.id)}><Trash size={12} /></button>
                            </div>
                          </td>
                        </tr>
                      )
                    ))}
                  </tbody>
                </table>
              </div>
              {showImport && (
                <div className="batch-modal-backdrop" onClick={() => setShowImport(false)} role="dialog" aria-modal="true">
                  <div className="batch-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
                    <div className="batch-modal-header">
                      <h2>{t('importDialog.title', { name: vocab.name })}</h2>
                      <button type="button" className="btn ico gh" onClick={() => setShowImport(false)} aria-label="Schließen">
                        <X size={16} />
                      </button>
                    </div>
                    <div className="batch-modal-body">
                      <VocabularyImport
                        initialVocabId={vocab.id}
                        onImportComplete={() => {
                          loadTerms()
                          setShowImport(false)
                        }}
                        onClose={() => setShowImport(false)}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>

          )}
          {!vocab && vocabs.length > 0 && (
            <div className="empty">Vokabular auswählen.</div>
          )}
        </div>
      </div>
    </div>
  )
}
