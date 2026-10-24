// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { vocabularies } from '../../../api/client'
import type { RelationFacet, VocabularyTerm } from '../../../types'
import { X } from '../../ui/Icons'

const TARGET_TYPES: RelationFacet['target_type'][] = ['entity', 'place', 'occurrence', 'collection', 'object']
const KEY_PATTERN = /^[a-z0-9_]{1,48}$/

function labelOf(label: Record<string, string> | undefined, lang: string, fallback: string): string {
  return label?.[lang] || label?.de || label?.en || fallback
}

function suggestKey(label: string): string {
  return label
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/ß/g, 'ss')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48)
}

/** List + dialog for the relation facets of one record type. Relation types
 *  come from the "relation_types" vocabulary, filtered by source and target
 *  type (applies_from / applies_to). */
export function RelationFacetsEditor({ recordType, value, onChange, sortByKey, onSortChange }: {
  recordType: string
  value: RelationFacet[]
  onChange: (next: RelationFacet[]) => void
  sortByKey?: Record<string, 'count' | 'alpha'>
  onSortChange?: (facetName: string, sort: 'count' | 'alpha') => void
}) {
  const { t, i18n } = useTranslation('facetSettings')
  const { t: tSettings } = useTranslation('screenSettings')
  const [editing, setEditing] = useState<{ index: number | null; draft: RelationFacet } | null>(null)
  const [relationTerms, setRelationTerms] = useState<VocabularyTerm[]>([])
  const lang = i18n.language?.slice(0, 2) || 'de'

  useEffect(() => {
    vocabularies.list()
      .then(list => {
        const vocab = list.find(v => v.name === 'relation_types')
        return vocab ? vocabularies.listTerms(vocab.id) : []
      })
      .then(setRelationTerms)
      .catch(() => setRelationTerms([]))
  }, [])

  const typeLabel = (type: string) => tSettings(`recordTypes.${type}`, { defaultValue: type })
  const termLabel = (code: string) => labelOf(relationTerms.find(term => term.term === code)?.label, lang, code)

  function startNew() {
    setEditing({
      index: null,
      draft: { key: '', label: { de: '', en: '' }, target_type: 'entity', relation_types: [], target_subtypes: [], direction: 'outgoing' },
    })
  }

  return (
    <div>
      {value.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>{t('relations.empty')}</div>
      )}
      {value.map((facet, index) => (
        <div key={facet.key} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', fontSize: 13, borderBottom: '1px solid var(--border-s)' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 500 }}>{labelOf(facet.label, lang, facet.key)}</div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              {typeLabel(facet.target_type)} · {facet.relation_types.map(termLabel).join(', ')}
              {facet.target_subtypes.length > 0 && ` · ${facet.target_subtypes.join(', ')}`}
            </div>
          </div>
          <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>relfacet_{facet.key}</span>
          {onSortChange && (
            <select
              className="fld"
              aria-label={t('order.sortAria', { name: labelOf(facet.label, lang, facet.key) })}
              value={sortByKey?.[`relfacet_${facet.key}`] ?? 'count'}
              onChange={e => onSortChange(`relfacet_${facet.key}`, e.target.value as 'count' | 'alpha')}
              style={{ width: 'auto', height: 26, padding: '0 8px', fontSize: 12 }}
            >
              <option value="count">{t('order.sort.count')}</option>
              <option value="alpha">{t('order.sort.alpha')}</option>
            </select>
          )}
          <button type="button" className="btn sm" onClick={() => setEditing({ index, draft: { ...facet } })}>{t('relations.edit')}</button>
          <button type="button" className="btn sm gh" onClick={() => onChange(value.filter((_, i) => i !== index))}>{t('relations.remove')}</button>
        </div>
      ))}
      <button type="button" className="btn sm" style={{ marginTop: 10 }} onClick={startNew}>{t('relations.add')}</button>
      {editing && (
        <RelationFacetDialog
          recordType={recordType}
          initial={editing.draft}
          isNew={editing.index === null}
          takenKeys={value.filter((_, i) => i !== editing.index).map(facet => facet.key)}
          relationTerms={relationTerms}
          lang={lang}
          typeLabel={typeLabel}
          onCancel={() => setEditing(null)}
          onApply={draft => {
            const next = [...value]
            if (editing.index === null) next.push(draft)
            else next[editing.index] = draft
            onChange(next)
            setEditing(null)
          }}
        />
      )}
    </div>
  )
}

function RelationFacetDialog({ recordType, initial, isNew, takenKeys, relationTerms, lang, typeLabel, onCancel, onApply }: {
  recordType: string
  initial: RelationFacet
  isNew: boolean
  takenKeys: string[]
  relationTerms: VocabularyTerm[]
  lang: string
  typeLabel: (type: string) => string
  onCancel: () => void
  onApply: (facet: RelationFacet) => void
}) {
  const { t } = useTranslation('facetSettings')
  const [draft, setDraft] = useState<RelationFacet>(initial)
  const [keyTouched, setKeyTouched] = useState(!isNew)
  const [subtypes, setSubtypes] = useState(initial.target_subtypes.join(', '))
  const [error, setError] = useState<string | null>(null)

  // Terms applicable between the two types in the chosen direction; empty
  // applies_from/applies_to means unrestricted.
  const [from, to] = draft.direction === 'incoming' ? [draft.target_type, recordType] : [recordType, draft.target_type]
  const applicable = relationTerms.filter(term =>
    (draft.direction === 'both' || ((term.applies_from?.length ? term.applies_from.includes(from) : true)
      && (term.applies_to?.length ? term.applies_to.includes(to) : true))))
  const options = [...applicable, ...relationTerms.filter(term => draft.relation_types.includes(term.term) && !applicable.includes(term))]

  function apply() {
    const key = draft.key.trim()
    if (!KEY_PATTERN.test(key) || takenKeys.includes(key)) { setError(t('relations.errorKey')); return }
    if (draft.relation_types.length === 0) { setError(t('relations.errorTypes')); return }
    onApply({
      ...draft,
      key,
      target_subtypes: subtypes.split(',').map(value => value.trim()).filter(Boolean),
    })
  }

  return (
    <div className="batch-modal-backdrop" onClick={onCancel} role="dialog" aria-modal="true" aria-labelledby="relation-facet-dialog-title">
      <div className="batch-modal" style={{ width: 560 }} onClick={e => e.stopPropagation()}>
        <div className="batch-modal-header">
          <h2 id="relation-facet-dialog-title">{t(isNew ? 'relations.dialogTitleNew' : 'relations.dialogTitleEdit')}</h2>
          <button type="button" className="btn sm ico gh" onClick={onCancel} aria-label={t('relations.cancel')}><X size={16} /></button>
        </div>
        <div className="batch-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              {t('relations.labelDe')}
              <input
                className="fld"
                autoFocus
                value={draft.label.de ?? ''}
                onChange={e => {
                  const de = e.target.value
                  setDraft(d => ({ ...d, label: { ...d.label, de }, key: keyTouched ? d.key : suggestKey(de) }))
                }}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              {t('relations.labelEn')}
              <input className="fld" value={draft.label.en ?? ''} onChange={e => setDraft(d => ({ ...d, label: { ...d.label, en: e.target.value } }))} />
            </label>
          </div>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
            {t('relations.key')}
            <input
              className="fld mono"
              value={draft.key}
              onChange={e => { setKeyTouched(true); setDraft(d => ({ ...d, key: e.target.value })) }}
              aria-describedby="relation-facet-key-hint"
            />
            <span id="relation-facet-key-hint" style={{ fontSize: 11, color: 'var(--fg-4)' }}>{t('relations.keyHint')}</span>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              {t('relations.targetType')}
              <select className="fld" value={draft.target_type} onChange={e => setDraft(d => ({ ...d, target_type: e.target.value as RelationFacet['target_type'] }))}>
                {TARGET_TYPES.map(type => <option key={type} value={type}>{typeLabel(type)}</option>)}
              </select>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              {t('relations.direction')}
              <select className="fld" value={draft.direction} onChange={e => setDraft(d => ({ ...d, direction: e.target.value as RelationFacet['direction'] }))}>
                <option value="outgoing">{t('relations.directionOutgoing')}</option>
                <option value="incoming">{t('relations.directionIncoming')}</option>
                <option value="both">{t('relations.directionBoth')}</option>
              </select>
            </label>
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ fontSize: 13, marginBottom: 4 }}>{t('relations.relationTypes')}</legend>
            <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid var(--border-s)', borderRadius: 6, padding: '4px 10px' }}>
              {options.length === 0 && <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '6px 0' }}>{t('relations.relationTypesEmpty')}</div>}
              {options.map(term => (
                <label key={term.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    className="ck"
                    checked={draft.relation_types.includes(term.term)}
                    onChange={() => setDraft(d => ({
                      ...d,
                      relation_types: d.relation_types.includes(term.term)
                        ? d.relation_types.filter(code => code !== term.term)
                        : [...d.relation_types, term.term],
                    }))}
                  />
                  <span style={{ flex: 1 }}>{labelOf(term.label, lang, term.term)}</span>
                  <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--fg-4)' }}>{term.term}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
            {t('relations.subtypes')}
            <input className="fld mono" value={subtypes} onChange={e => setSubtypes(e.target.value)} />
          </label>
          {error && <div role="alert" style={{ fontSize: 12, color: 'var(--danger, #b91c1c)' }}>{error}</div>}
        </div>
        <div className="batch-modal-footer">
          <button type="button" className="btn" onClick={onCancel}>{t('relations.cancel')}</button>
          <button type="button" className="btn pri" onClick={apply}>{t('relations.apply')}</button>
        </div>
      </div>
    </div>
  )
}
