// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { ReactNode } from 'react'
import { useEffect, useId, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type PortalFieldDefinition } from '../api/client'
import { typeLabel, useI18n } from '../i18n'
import {
  decodeAdvancedQuery,
  encodeAdvancedQuery,
  type AdvancedClause,
  type AdvancedFieldClause,
  type AdvancedGroup,
  type AdvancedQuery,
} from '../utils/advancedSearch'

const RECORD_TYPES = ['object', 'entity', 'place', 'occurrence'] as const
const SUPPORTED_TYPES = new Set([
  'text', 'richtext', 'date', 'number', 'boolean', 'vocab', 'vocab_free',
  'authority', 'pid', 'url', 'relation',
])

const OPERATORS: Record<string, Array<[string, string]>> = {
  text: [['contains', 'advanced.op.contains'], ['eq', 'advanced.op.eq'], ['not_contains', 'advanced.op.notContains'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  richtext: [['contains', 'advanced.op.contains'], ['eq', 'advanced.op.eq'], ['not_contains', 'advanced.op.notContains'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  number: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['lt', 'advanced.op.lt'], ['lte', 'advanced.op.lte'], ['gt', 'advanced.op.gt'], ['gte', 'advanced.op.gte'], ['between', 'advanced.op.between'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  date: [['before', 'advanced.op.before'], ['on', 'advanced.op.on'], ['after', 'advanced.op.after'], ['between', 'advanced.op.between'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  boolean: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  vocab: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  vocab_free: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  authority: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  pid: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
  url: [['eq', 'advanced.op.eq'], ['neq', 'advanced.op.neq'], ['exists', 'advanced.op.exists'], ['not_exists', 'advanced.op.notExists']],
}

function blankClause(): AdvancedFieldClause {
  return { kind: 'field', field: '', operator: 'contains', value: '' }
}

function fieldLabel(field: PortalFieldDefinition, locale: string): string {
  return field.label[locale] ?? field.label.de ?? field.label.en ?? field.name
}

function defaultOperator(fieldType: string): string {
  return OPERATORS[fieldType]?.[0]?.[0] ?? 'eq'
}

function operatorLabel(fieldType: string, operator: string, t: (key: string) => string): string {
  const key = OPERATORS[fieldType]?.find(([value]) => value === operator)?.[1]
  return key ? t(key) : operator
}

async function summarizeGroup(
  targetType: string,
  group: AdvancedGroup,
  locale: string,
  t: (key: string, params?: Record<string, string>) => string,
): Promise<ReactNode> {
  const fields = await api.portal.schema(targetType).catch(() => [])
  const parts = await Promise.all(group.clauses.map(async clause => {
    const field = fields.find(item => item.name === clause.field)
    if (!field) return clause.field
    if (clause.kind === 'relation') {
      const nestedTarget = String(field.settings.target_type ?? '')
      const nested = await summarizeGroup(nestedTarget, clause.group, locale, t)
      return <>{fieldLabel(field, locale)} → {typeLabel(nestedTarget)} ({nested})</>
    }
    if (clause.operator === 'exists') return <>{fieldLabel(field, locale)} <em>{t('advanced.exists')}</em></>
    if (clause.operator === 'not_exists') return <>{fieldLabel(field, locale)} <em>{t('advanced.notExists')}</em></>
    const value = await valueLabel(field, targetType, clause.value, locale, t)
    return <>{fieldLabel(field, locale)} <em>{operatorLabel(field.field_type, clause.operator, t)}</em> &quot;{value}&quot;</>
  }))
  const joinWord = t(group.mode === 'all' ? 'advanced.joinAll' : 'advanced.joinAny')
  return (
    <>
      {parts.map((part, i) => <span key={i}>{i > 0 ? ` ${joinWord} ` : ''}{part}</span>)}
    </>
  )
}

async function valueLabel(
  field: PortalFieldDefinition,
  targetType: string,
  value: unknown,
  locale: string,
  t: (key: string) => string,
): Promise<string> {
  if (value == null) return ''
  if (field.field_type === 'boolean') return t(value ? 'advanced.yes' : 'advanced.no')
  if (Array.isArray(value)) {
    const resolved = await Promise.all(value.map(v => valueLabel(field, targetType, v, locale, t)))
    return resolved.join(` ${t('advanced.and')} `)
  }
  if (['vocab', 'vocab_free', 'authority', 'pid'].includes(field.field_type)) {
    const terms = await api.portal.searchFieldTerms(targetType, field.name).catch(() => [])
    const term = terms.find(item => item.id === value)
    if (term) return term.label[locale] ?? term.label.de ?? term.label.en ?? term.term
  }
  return String(value)
}

export function QuerySummary({ query }: { query: AdvancedQuery }) {
  const { locale, t } = useI18n()
  const [summary, setSummary] = useState<ReactNode>(null)
  const key = JSON.stringify(query)

  useEffect(() => {
    let cancelled = false
    summarizeGroup(query.record_type, query.group, locale, t).then(text => { if (!cancelled) setSummary(text) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, locale])

  return <p className="advanced-query-summary">{summary}</p>
}

function ValueEditor({ clause, field, targetType, onChange }: {
  clause: AdvancedFieldClause
  field: PortalFieldDefinition
  targetType: string
  onChange: (clause: AdvancedFieldClause) => void
}) {
  const { locale, t } = useI18n()
  const [terms, setTerms] = useState<Awaited<ReturnType<typeof api.portal.searchFieldTerms>>>([])
  const listId = useId()

  useEffect(() => {
    if (!['vocab', 'vocab_free'].includes(field.field_type)) return
    let cancelled = false
    api.portal.searchFieldTerms(targetType, field.name)
      .then(result => { if (!cancelled) setTerms(result) })
      .catch(() => { if (!cancelled) setTerms([]) })
    return () => { cancelled = true }
  }, [field.field_type, field.name, targetType])

  if (clause.operator === 'exists' || clause.operator === 'not_exists') return null
  const termLabel = (term: (typeof terms)[number]) =>
    term.label[locale] ?? term.label.de ?? term.label.en ?? term.term
  if (field.field_type === 'vocab') {
    return (
      <select
        className="advanced-value"
        aria-label={t('advanced.value')}
        value={String(clause.value ?? '')}
        onChange={event => onChange({ ...clause, value: event.target.value })}
      >
        <option value="">{t('advanced.chooseValue')}</option>
        {terms.map(term => <option key={term.id} value={term.id}>{termLabel(term)}</option>)}
      </select>
    )
  }
  if (field.field_type === 'vocab_free') {
    return (
      <>
        <input
          className="advanced-value"
          aria-label={t('advanced.value')}
          list={listId}
          value={String(clause.value ?? '')}
          placeholder={t('advanced.value')}
          onChange={event => onChange({ ...clause, value: event.target.value })}
        />
        <datalist id={listId}>
          {terms.map(term => <option key={term.id} value={termLabel(term)} />)}
        </datalist>
      </>
    )
  }
  if (field.field_type === 'boolean') {
    return (
      <select
        className="advanced-value"
        aria-label={t('advanced.value')}
        value={String(clause.value ?? true)}
        onChange={event => onChange({ ...clause, value: event.target.value === 'true' })}
      >
        <option value="true">{t('advanced.yes')}</option>
        <option value="false">{t('advanced.no')}</option>
      </select>
    )
  }
  if (clause.operator === 'between') {
    const values = Array.isArray(clause.value) ? clause.value : ['', '']
    return (
      <div className="advanced-between">
        <input
          aria-label={t('advanced.from')}
          type={field.field_type === 'number' ? 'number' : 'text'}
          value={String(values[0] ?? '')}
          placeholder={t('advanced.from')}
          onChange={event => onChange({ ...clause, value: [event.target.value, values[1] ?? ''] })}
        />
        <span>{t('advanced.and')}</span>
        <input
          aria-label={t('advanced.to')}
          type={field.field_type === 'number' ? 'number' : 'text'}
          value={String(values[1] ?? '')}
          placeholder={t('advanced.to')}
          onChange={event => onChange({ ...clause, value: [values[0] ?? '', event.target.value] })}
        />
      </div>
    )
  }
  return (
    <input
      className="advanced-value"
      aria-label={t('advanced.value')}
      type={field.field_type === 'number' ? 'number' : 'text'}
      value={String(clause.value ?? '')}
      placeholder={field.field_type === 'date' ? t('advanced.datePlaceholder') : t('advanced.value')}
      onChange={event => onChange({ ...clause, value: event.target.value })}
    />
  )
}

function RuleGroupEditor({ targetType, group, depth, onChange }: {
  targetType: string
  group: AdvancedGroup
  depth: number
  onChange: (group: AdvancedGroup) => void
}) {
  const { locale, t } = useI18n()
  const [fields, setFields] = useState<PortalFieldDefinition[]>([])

  useEffect(() => {
    let cancelled = false
    api.portal.schema(targetType)
      .then(result => { if (!cancelled) setFields(result) })
      .catch(() => { if (!cancelled) setFields([]) })
    return () => { cancelled = true }
  }, [targetType])

  const available = useMemo(
    () => fields.filter(field => field.is_searchable && !field.parent_id
      && SUPPORTED_TYPES.has(field.field_type)
      && (depth < 2 || field.field_type !== 'relation')),
    [fields, depth],
  )

  function replace(index: number, clause: AdvancedClause) {
    onChange({ ...group, clauses: group.clauses.map((item, i) => i === index ? clause : item) })
  }

  function remove(index: number) {
    onChange({ ...group, clauses: group.clauses.filter((_, i) => i !== index) })
  }

  function selectField(index: number, name: string) {
    const field = available.find(item => item.name === name)
    if (!field) {
      replace(index, blankClause())
      return
    }
    if (field.field_type === 'relation') {
      replace(index, {
        kind: 'relation', field: field.name,
        group: { mode: 'all', clauses: [blankClause()] },
      })
      return
    }
    replace(index, {
      kind: 'field', field: field.name,
      operator: defaultOperator(field.field_type),
      value: field.field_type === 'boolean' ? true : '',
    })
  }

  return (
    <fieldset className={`advanced-group advanced-depth-${depth}`}>
      <legend>{depth === 0 ? t('advanced.rules') : t('advanced.relatedRules')}</legend>
      <label className="advanced-mode">
        <span>{t('advanced.match')}</span>
        <select
          value={group.mode}
          onChange={event => onChange({ ...group, mode: event.target.value as 'all' | 'any' })}
        >
          <option value="all">{t('advanced.all')}</option>
          <option value="any">{t('advanced.any')}</option>
        </select>
      </label>

      <div className="advanced-rules">
        {group.clauses.map((clause, index) => {
          const field = available.find(item => item.name === clause.field)
          const relationTarget = field?.field_type === 'relation'
            ? String(field.settings.target_type ?? '')
            : ''
          return (
            <div className="advanced-rule" key={`${index}-${clause.kind}`}>
              <div className="advanced-rule-row">
                <select
                  aria-label={t('advanced.field')}
                  value={clause.field}
                  onChange={event => selectField(index, event.target.value)}
                >
                  <option value="">{t('advanced.chooseField')}</option>
                  {available.map(item => (
                    <option key={item.name} value={item.name}>
                      {fieldLabel(item, locale)}{item.field_type === 'relation' ? ` → ${typeLabel(String(item.settings.target_type ?? ''))}` : ''}
                    </option>
                  ))}
                </select>

                {clause.kind === 'field' && field && field.field_type !== 'relation' && (
                  <>
                    <select
                      aria-label={t('advanced.operator')}
                      value={clause.operator}
                      onChange={event => replace(index, { ...clause, operator: event.target.value, value: event.target.value === 'between' ? ['', ''] : field.field_type === 'boolean' ? true : '' })}
                    >
                      {(OPERATORS[field.field_type] ?? []).map(([value, label]) => (
                        <option key={value} value={value}>{t(label)}</option>
                      ))}
                    </select>
                    <ValueEditor clause={clause} field={field} targetType={targetType} onChange={next => replace(index, next)} />
                  </>
                )}

                <button
                  className="advanced-remove"
                  type="button"
                  onClick={() => remove(index)}
                  aria-label={t('advanced.removeRule')}
                >
                  ×
                </button>
              </div>

              {clause.kind === 'relation' && relationTarget && (
                <div className="advanced-relation-target">
                  <div className="advanced-relation-label">
                    {t('advanced.relatedTarget', { type: typeLabel(relationTarget) })}
                  </div>
                  <RuleGroupEditor
                    targetType={relationTarget}
                    group={clause.group}
                    depth={depth + 1}
                    onChange={next => replace(index, { ...clause, group: next })}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      <button
        className="advanced-add"
        type="button"
        onClick={() => onChange({ ...group, clauses: [...group.clauses, blankClause()] })}
      >
        {t('advanced.addRule')}
      </button>
    </fieldset>
  )
}

function groupIsComplete(group: AdvancedGroup): boolean {
  if (group.clauses.length === 0) return false
  return group.clauses.every(clause => {
    if (!clause.field) return false
    if (clause.kind === 'relation') return groupIsComplete(clause.group)
    if (clause.operator === 'exists' || clause.operator === 'not_exists') return true
    if (clause.operator === 'between') {
      return Array.isArray(clause.value) && clause.value.length === 2 && clause.value.every(Boolean)
    }
    return clause.value !== '' && clause.value != null
  })
}

export function AdvancedSearchPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { t } = useI18n()
  const restored = decodeAdvancedQuery(params.get('aq'))
  const [query, setQuery] = useState<AdvancedQuery>(restored ?? {
    version: 1,
    record_type: 'object',
    group: { mode: 'all', clauses: [blankClause()] },
  })
  const [error, setError] = useState('')

  function changeType(recordType: AdvancedQuery['record_type']) {
    setQuery({ version: 1, record_type: recordType, group: { mode: 'all', clauses: [blankClause()] } })
    setError('')
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!groupIsComplete(query.group)) {
      setError(t('advanced.incomplete'))
      return
    }
    navigate(`/search?aq=${encodeURIComponent(encodeAdvancedQuery(query))}`)
  }

  return (
    <div className="container page advanced-page">
      <div className="bc"><Link to="/search">{t('common.search')}</Link><span className="sep">/</span><span>{t('advanced.title')}</span></div>
      <h1>{t('advanced.title')}</h1>
      <p className="advanced-intro">{t('advanced.intro')}</p>
      <form onSubmit={submit}>
        <label className="advanced-type">
          <span>{t('advanced.resultType')}</span>
          <select value={query.record_type} onChange={event => changeType(event.target.value as AdvancedQuery['record_type'])}>
            {RECORD_TYPES.map(type => <option value={type} key={type}>{typeLabel(type)}</option>)}
          </select>
        </label>
        <RuleGroupEditor
          targetType={query.record_type}
          group={query.group}
          depth={0}
          onChange={group => setQuery({ ...query, group })}
        />
        {error && <div className="advanced-error" role="alert">{error}</div>}
        <div className="advanced-actions">
          <button className="advanced-submit" type="submit">{t('advanced.showResults')}</button>
          <Link to="/search">{t('advanced.simpleSearch')}</Link>
        </div>
      </form>
    </div>
  )
}
