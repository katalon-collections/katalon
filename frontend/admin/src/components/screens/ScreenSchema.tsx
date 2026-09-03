// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { adminConfig, authority, schema, subtypes, vocabularies } from '../../api/client'
import type { AuthoritySource, SchemaImportResult } from '../../api/client'
import type { FieldDefinition, RecordSubtype, Vocabulary, VocabularyTerm } from '../../types'
import { getLabel } from '../../types'
import { Edit, Grip, Lightning, Plus, Trash } from '../ui/Icons'
import { SchemaAiAssist } from './SchemaAiAssist'
import { LabelEditor } from '../ui/LabelEditor'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

const FIELD_TYPES = ['text', 'richtext', 'date', 'number', 'boolean', 'vocab', 'vocab_free', 'relation', 'geo', 'pid', 'url', 'authority', 'group'] as const
const VOCABULARY_TERM_FIELD_TYPES = ['text', 'number', 'boolean', 'authority'] as const
export { FIELD_TYPE_LABELS } from './schemaConstants'

// Field types allowed as sub-fields of a group (no recursion)
const SUB_FIELD_TYPES = ['text', 'date', 'number', 'boolean', 'vocab', 'vocab_free', 'relation', 'authority'] as const
type SubFieldType = typeof SUB_FIELD_TYPES[number]

type SubFieldFormState = {
  id?: string
  name: string
  label: Record<string, string>
  field_type: SubFieldType
  is_required: boolean
  is_public: boolean
  sort_order: number
  validation_regex: string
  vocabulary_id: string
  relation_target_type: string
  relation_type_vocab: string
  authority_source: string
  ai_enabled: boolean
  ai_mode: 'text' | 'vision'
  ai_prompt: string
  ai_include_fields: string[]
  ai_send_existing_value: boolean
}

type FieldFormState = {
  target_type: string
  target_subtype: string
  name: string
  label: Record<string, string>
  field_type: string
  is_required: boolean
  is_repeatable: boolean
  is_translatable: boolean
  sort_order: number
  validation_regex: string
  authority_source: string
  pid_provider: string
  show_in_detail: boolean
  show_in_list: boolean
  detail_slot: 'main' | 'sidebar'
  detail_role: 'none' | 'description'
  is_public: boolean
  is_facet: boolean
  is_searchable: boolean
  vocabulary_id: string
  relation_target_type: string
  relation_target_subtype: string
  relation_type_vocab: string
  fixed_relation_type: string
  inherited_fields: string[]
  default_value: unknown
  is_locked: boolean
  ai_enabled: boolean
  ai_mode: 'text' | 'vision'
  ai_prompt: string
  ai_include_fields: string[]
  ai_send_existing_value: boolean
  // sub-fields of this group field (populated when editing an existing group field)
  subFields?: FieldDefinition[]
}

function emptyForm(targetType: string, sortOrder: number, subtype: string): FieldFormState {
  return { target_type: targetType, target_subtype: subtype, name: '', label: {}, field_type: 'text', is_required: false, is_repeatable: false, is_translatable: false, sort_order: sortOrder, validation_regex: '', authority_source: 'gnd', pid_provider: 'dnb_urn', show_in_detail: true, show_in_list: false, detail_slot: 'sidebar', detail_role: 'none', is_public: true, is_facet: false, is_searchable: true, vocabulary_id: '', relation_target_type: 'entity', relation_target_subtype: '', relation_type_vocab: '', fixed_relation_type: '', inherited_fields: [], default_value: '', is_locked: false, ai_enabled: false, ai_mode: 'text', ai_prompt: '', ai_include_fields: [], ai_send_existing_value: false }
}

function fieldToForm(f: FieldDefinition): FieldFormState {
  return {
    target_type: f.target_type,
    target_subtype: f.target_subtype ?? '',
    name: f.name,
    label: { ...f.label },
    field_type: f.field_type,
    is_required: f.is_required,
    is_repeatable: f.is_repeatable,
    is_translatable: f.is_translatable ?? false,
    sort_order: f.sort_order,
    validation_regex: (f.settings?.validation_regex as string) ?? '',
    authority_source: (f.settings?.source as string) ?? 'gnd',
    pid_provider: (f.settings?.pid_provider as string) ?? 'dnb_urn',
    show_in_detail: f.show_in_detail ?? true,
    show_in_list: f.show_in_list ?? false,
    detail_slot: f.detail_slot ?? 'sidebar',
    detail_role: f.detail_role ?? 'none',
    is_public: f.is_public ?? true,
    is_facet: f.is_facet ?? false,
    is_searchable: f.is_searchable ?? true,
    vocabulary_id: (f.settings?.vocabulary_id as string) ?? '',
    relation_target_type: (f.settings?.target_type as string) ?? 'entity',
    relation_target_subtype: (f.settings?.target_subtype as string) ?? '',
    relation_type_vocab: (f.settings?.relation_type_vocab as string) ?? '',
    fixed_relation_type: (f.settings?.fixed_relation_type as string) ?? '',
    inherited_fields: (f.settings?.inherited_fields as string[]) ?? [],
    default_value: f.settings?.default_value ?? '',
    is_locked: Boolean(f.settings?.is_locked),
    ai_enabled: Boolean((f.settings?.ai_config as Record<string, unknown> | undefined)?.enabled),
    ai_mode: (((f.settings?.ai_config as Record<string, unknown> | undefined)?.mode as 'text' | 'vision' | undefined) ?? 'text'),
    ai_prompt: ((f.settings?.ai_config as Record<string, unknown> | undefined)?.prompt as string) ?? '',
    ai_include_fields: ((f.settings?.ai_config as Record<string, unknown> | undefined)?.include_fields as string[]) ?? [],
    ai_send_existing_value: Boolean((f.settings?.ai_config as Record<string, unknown> | undefined)?.send_existing_value),
    subFields: f.children ?? [],
  }
}

interface FieldDetailProps {
  form: FieldFormState
  availableFields: FieldDefinition[]
  fieldId: string | null   // null when creating a new field
  isNew: boolean
  saving: boolean
  error: string | null
  showSubtype: boolean
  authoritySources: AuthoritySource[]
  pidProviders: ('ark' | 'dnb_urn')[]
  onChange: (form: FieldFormState) => void
  onSave: () => void
  onDelete: () => void
  onClose: () => void
  onSubFieldChange: () => void  // reload field list after sub-field create/delete
}

function toSlug(label: string): string {
  return label
    .toLowerCase()
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function emptySubFieldForm(sortOrder: number, authoritySource: string): SubFieldFormState {
  return { name: '', label: {}, field_type: 'text', is_required: false, is_public: true, sort_order: sortOrder, validation_regex: '', vocabulary_id: '', relation_target_type: 'entity', relation_type_vocab: '', authority_source: authoritySource, ai_enabled: false, ai_mode: 'text', ai_prompt: '', ai_include_fields: [], ai_send_existing_value: false }
}

function FieldDetail({ form, availableFields, fieldId, isNew, saving, error, showSubtype, authoritySources, pidProviders, onChange, onSave, onDelete, onClose, onSubFieldChange }: FieldDetailProps) {
  const { t } = useTranslation('screenSchema')
  const [nameManuallyEdited, setNameManuallyEdited] = useState(false)
  const languages = useSupportedLanguages()
  const primaryLang = languages[0] ?? 'de'

  // Sub-field editing state (only relevant when form.field_type === 'group')
  const [subFieldEditing, setSubFieldEditing] = useState<'new' | string | null>(null)
  const [subFieldForm, setSubFieldForm] = useState<SubFieldFormState | null>(null)
  const [subFieldSaving, setSubFieldSaving] = useState(false)
  const [subFieldError, setSubFieldError] = useState<string | null>(null)
  const [subNameManual, setSubNameManual] = useState(false)

  function openNewSubField() {
    setSubFieldEditing('new')
    setSubFieldForm(emptySubFieldForm(
      form.subFields?.length ?? 0,
      authoritySources.find(source => source.is_enabled)?.id ?? '',
    ))
    setSubFieldError(null)
    setSubNameManual(false)
  }

  function openEditSubField(sf: FieldDefinition) {
    setSubFieldEditing(sf.id)
    setSubFieldForm({
      id: sf.id,
      name: sf.name,
      label: { ...sf.label },
      field_type: sf.field_type as SubFieldType,
      is_required: sf.is_required,
      is_public: sf.is_public ?? true,
      sort_order: sf.sort_order,
      validation_regex: (sf.settings?.validation_regex as string) ?? '',
      vocabulary_id: (sf.settings?.vocabulary_id as string) ?? '',
      relation_target_type: (sf.settings?.target_type as string) ?? 'entity',
      relation_type_vocab: (sf.settings?.relation_type_vocab as string) ?? '',
      authority_source: (sf.settings?.source as string) ?? '',
      ai_enabled: Boolean((sf.settings?.ai_config as Record<string, unknown> | undefined)?.enabled),
      ai_mode: (((sf.settings?.ai_config as Record<string, unknown> | undefined)?.mode as 'text' | 'vision' | undefined) ?? 'text'),
      ai_prompt: ((sf.settings?.ai_config as Record<string, unknown> | undefined)?.prompt as string) ?? '',
      ai_include_fields: ((sf.settings?.ai_config as Record<string, unknown> | undefined)?.include_fields as string[]) ?? [],
      ai_send_existing_value: Boolean((sf.settings?.ai_config as Record<string, unknown> | undefined)?.send_existing_value),
    })
    setSubFieldError(null)
    setSubNameManual(true)
  }

  async function handleSubFieldSave() {
    if (!subFieldForm || !fieldId) return
    if (!subFieldForm.name.trim()) { setSubFieldError(t('fieldDetail.subFieldErrorNameEmpty')); return }
    if (subFieldForm.field_type === 'relation' && !subFieldForm.relation_type_vocab) {
      setSubFieldError(t('fieldDetail.subFieldErrorRelationVocab'))
      return
    }
    if (subFieldForm.field_type === 'authority' && !authoritySources.some(source => source.is_enabled && source.id === subFieldForm.authority_source)) {
      setSubFieldError(t('fieldDetail.subFieldErrorAuthoritySource'))
      return
    }
    setSubFieldSaving(true)
    setSubFieldError(null)
    const data = {
      target_type: form.target_type,
      target_subtype: form.target_subtype || null,
      name: subFieldForm.name,
      label: subFieldForm.label,
      field_type: subFieldForm.field_type,
      is_required: subFieldForm.is_required,
      is_repeatable: false,
      is_translatable: false,
      sort_order: subFieldForm.sort_order,
      show_in_detail: true,
      show_in_list: false,
      is_public: subFieldForm.is_public,
      is_facet: false,
      is_searchable: true,
      settings: {
        ...(subFieldForm.validation_regex.trim() ? { validation_regex: subFieldForm.validation_regex.trim() } : {}),
        ...((subFieldForm.field_type === 'vocab' || subFieldForm.field_type === 'vocab_free') && subFieldForm.vocabulary_id ? { vocabulary_id: subFieldForm.vocabulary_id } : {}),
        ...(subFieldForm.field_type === 'relation' ? {
          target_type: subFieldForm.relation_target_type,
          relation_type_vocab: subFieldForm.relation_type_vocab,
        } : {}),
        ...(subFieldForm.field_type === 'authority' ? { source: subFieldForm.authority_source } : {}),
        ...(subFieldForm.ai_enabled ? {
          ai_config: {
            enabled: true,
            mode: subFieldForm.ai_mode,
            prompt: subFieldForm.ai_prompt.trim(),
            include_fields: subFieldForm.ai_include_fields,
            send_existing_value: subFieldForm.ai_send_existing_value,
          },
        } : {}),
      },
      parent_id: fieldId,
    }
    try {
      if (subFieldEditing === 'new') {
        await schema.create(data)
      } else {
        await schema.update(subFieldEditing!, { ...data, parent_id: fieldId })
      }
      setSubFieldEditing(null)
      setSubFieldForm(null)
      onSubFieldChange()
    } catch (e) {
      setSubFieldError((e as Error).message)
    } finally {
      setSubFieldSaving(false)
    }
  }

  async function handleSubFieldDelete(sfId: string) {
    if (!window.confirm(t('fieldDetail.subFieldDeleteConfirm'))) return
    try {
      await schema.delete(sfId)
      onSubFieldChange()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  function set<K extends keyof FieldFormState>(key: K, value: FieldFormState[K]) {
    onChange({ ...form, [key]: value })
  }

  const [allVocabs, setAllVocabs] = useState<Vocabulary[]>([])
  const [defaultTerms, setDefaultTerms] = useState<VocabularyTerm[]>([])
  useEffect(() => {
    vocabularies.list().then(setAllVocabs).catch(() => {})
  }, [])
  useEffect(() => {
    if (form.field_type !== 'vocab' || !form.vocabulary_id) {
      setDefaultTerms([])
      return
    }
    vocabularies.listTerms(form.vocabulary_id).then(setDefaultTerms).catch(() => setDefaultTerms([]))
  }, [form.field_type, form.vocabulary_id])

  const [availableSubtypes, setAvailableSubtypes] = useState<RecordSubtype[]>([])
  useEffect(() => {
    if (!showSubtype) return
    subtypes.list(form.target_type).then(setAvailableSubtypes).catch(() => {})
  }, [showSubtype, form.target_type])

  const [targetTypeFields, setTargetTypeFields] = useState<FieldDefinition[]>([])
  useEffect(() => {
    if (form.field_type !== 'relation') { setTargetTypeFields([]); return }
    schema.list(form.relation_target_type).then(setTargetTypeFields).catch(() => setTargetTypeFields([]))
  }, [form.field_type, form.relation_target_type])

  const [relationTypeTerms, setRelationTypeTerms] = useState<VocabularyTerm[]>([])
  useEffect(() => {
    if (form.field_type !== 'relation' || !form.relation_type_vocab) {
      setRelationTypeTerms([])
      return
    }
    vocabularies.listTerms(form.relation_type_vocab, {
      from_type: form.target_type,
      to_type: form.relation_target_type,
    }).then(setRelationTypeTerms).catch(() => setRelationTypeTerms([]))
  }, [form.field_type, form.relation_type_vocab, form.relation_target_type, form.target_type])

  const isVocabularyTerm = form.target_type === 'vocabulary_term'
  const fieldTypes = (isVocabularyTerm ? VOCABULARY_TERM_FIELD_TYPES : FIELD_TYPES)
    .filter(type => type !== 'pid' || pidProviders.length > 0 || form.field_type === 'pid')
  const aiEligible = !isVocabularyTerm && ['text', 'richtext', 'vocab_free', 'date', 'number', 'boolean'].includes(form.field_type)
  useEffect(() => {
    if (!isNew || form.field_type !== 'authority') return
    const enabled = authoritySources.filter(source => source.is_enabled)
    if (!enabled.some(source => source.id === form.authority_source) && enabled[0]) {
      onChange({ ...form, authority_source: enabled[0].id })
    }
  }, [authoritySources, form, isNew, onChange])

  return (
    <div className="card" style={{ margin: '18px 24px' }}>
      <div className="hd">
        <span>{isNew ? t('fieldDetail.newField') : (getLabel({ label: form.label }, form.name))}</span>
        {!isNew && <span className="sub">{form.name}</span>}
        <div className="grow" />
        <button className="btn sm" onClick={onClose}>{t('fieldDetail.close')}</button>
      </div>
      <div className="bd">
        {error && <div style={{ marginBottom: 10, color: '#b91c1c', fontSize: 13 }}>{error}</div>}
        <div className="fg-2">
          <LabelEditor
            languages={languages}
            value={form.label}
            onChange={(lang, val) => {
              const nextLabel = { ...form.label, [lang]: val }
              if (isNew && !nameManuallyEdited && lang === primaryLang) {
                onChange({ ...form, label: nextLabel, name: toSlug(val) })
              } else {
                onChange({ ...form, label: nextLabel })
              }
            }}
          />
        </div>
        <div className="fg-2">
          <div className="field">
            <div className="lbl">{t('fieldDetail.internalName')}</div>
            <input className="fld mono" value={form.name} onChange={e => {
              setNameManuallyEdited(true)
              set('name', e.target.value)
            }} disabled={!isNew} />
          </div>
          <div className="field" data-tour="field-type-select">
            <div className="lbl">{t('fieldDetail.fieldType')}</div>
            <select className="fld" value={form.field_type} onChange={e => {
              const fieldType = e.target.value
              onChange({ ...form, field_type: fieldType, ...(fieldType === 'pid' && !pidProviders.includes(form.pid_provider as 'ark' | 'dnb_urn') ? { pid_provider: pidProviders[0] ?? '' } : {}) })
            }}>
              {fieldTypes.map(k => <option key={k} value={k}>{t(`fieldTypes.${k}`)}</option>)}
            </select>
          </div>
        </div>
        {showSubtype && (
          <div className="field">
            <div className="lbl">{t('fieldDetail.subtype')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.subtypeHint')}</span></div>
            <select className="fld" value={form.target_subtype} onChange={e => set('target_subtype', e.target.value)} disabled={!isNew}>
              <option value="">{t('fieldDetail.subtypeAll')}</option>
              {availableSubtypes.map(s => (
                <option key={s.id} value={s.name}>{s.label.de || s.name}</option>
              ))}
            </select>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" checked={form.is_required} onChange={e => set('is_required', e.target.checked)} />
              <span style={{ fontSize: 13 }}>{t('fieldDetail.required')}</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" checked={form.is_repeatable} onChange={e => set('is_repeatable', e.target.checked)} />
              <span style={{ fontSize: 13 }}>{t('fieldDetail.repeatable')}</span>
            </label>
            {!isVocabularyTerm && (form.field_type === 'text' || form.field_type === 'richtext') && !form.is_repeatable && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" className="ck" checked={form.is_translatable} onChange={e => set('is_translatable', e.target.checked)} />
                <span style={{ fontSize: 13 }}>{t('fieldDetail.translatable')}</span>
              </label>
            )}
            {!isVocabularyTerm && !((form.field_type === 'text' || form.field_type === 'richtext') && !form.is_repeatable) && (
              <span style={{ fontSize: 11, color: 'var(--fg-3)', alignSelf: 'center' }}>{t('fieldDetail.notTranslatableHint')}</span>
            )}
        </div>
        {form.field_type === 'authority' && (
          <div className="field">
            <div className="lbl">{t('fieldDetail.authoritySource')}</div>
            <select className="fld" value={form.authority_source} onChange={e => set('authority_source', e.target.value)}>
              {authoritySources
                .filter(source => source.is_enabled || source.id === form.authority_source)
                .map(source => (
                  <option key={source.id} value={source.id} disabled={!source.is_enabled}>
                    {source.label}{source.is_enabled ? '' : t('fieldDetail.authorityDisabled')}
                  </option>
                ))}
            </select>
            {!isNew && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('fieldDetail.authorityChangeWarning')}</div>}
          </div>
        )}
        {form.field_type === 'pid' && !isVocabularyTerm && (
          <div className="field">
            <div className="lbl">{t('fieldDetail.pidProvider')}</div>
            <select className="fld" value={form.pid_provider} onChange={e => set('pid_provider', e.target.value)}>
              {(['dnb_urn', 'ark'] as const).filter(provider => pidProviders.includes(provider) || provider === form.pid_provider).map(provider => (
                <option key={provider} value={provider} disabled={!pidProviders.includes(provider)}>
                  {provider === 'ark' ? t('fieldDetail.pidProviderArk') : t('fieldDetail.pidProviderDnbUrn')}
                </option>
              ))}
            </select>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('fieldDetail.pidProviderHint')}</div>
          </div>
        )}
        {(form.field_type === 'vocab' || form.field_type === 'vocab_free') && (
          <div className="field">
            <div className="lbl">
              {t('fieldDetail.vocabLabel')} {form.field_type === 'vocab' && <span className="req">*</span>}
              {form.field_type === 'vocab_free' && <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 4 }}>{t('fieldDetail.vocabFreeHint')}</span>}
            </div>
            <select className="fld" value={form.vocabulary_id} onChange={e => set('vocabulary_id', e.target.value)}>
              <option value="">{t('fieldDetail.vocabPlaceholder')}</option>
              {allVocabs.filter(v => v.kind === 'term').map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
        )}
        <details style={{ marginBottom: 16 }}>
          <summary style={{ cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>{t('fieldDetail.advancedOptions')}</summary>
          <div style={{ marginTop: 14 }}>
            <div className="field">
              <div className="lbl">{t('fieldDetail.sortOrder')}</div>
              <input className="fld mono" type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} />
            </div>
            {!isVocabularyTerm && (
              <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={form.show_in_detail} onChange={e => set('show_in_detail', e.target.checked)} />
                  <span style={{ fontSize: 13 }}>{t('fieldDetail.showInDetail')}</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={form.show_in_list} onChange={e => set('show_in_list', e.target.checked)} />
                  <span style={{ fontSize: 13 }}>{t('fieldDetail.showInList')}</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={form.is_public} onChange={e => set('is_public', e.target.checked)} />
                  <span style={{ fontSize: 13 }}>{t('fieldDetail.isPublic')}</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={form.is_facet} onChange={e => set('is_facet', e.target.checked)} />
                  <span style={{ fontSize: 13 }}>{t('fieldDetail.isFacet')}</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={form.is_searchable} onChange={e => set('is_searchable', e.target.checked)} />
                  <span style={{ fontSize: 13 }}>{t('fieldDetail.isSearchable')}</span>
                </label>
              </div>
            )}
          {!isVocabularyTerm && form.show_in_detail && (
            <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: 16, paddingTop: 12 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13 }}>{t('fieldDetail.detailSlot')}</span>
                <select className="fld" style={{ width: 'auto' }} value={form.detail_slot} onChange={e => set('detail_slot', e.target.value as 'main' | 'sidebar')}>
                  <option value="sidebar">{t('fieldDetail.detailSlotSidebar')}</option>
                  <option value="main">{t('fieldDetail.detailSlotMain')}</option>
                </select>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13 }}>{t('fieldDetail.detailRole')}</span>
                <select className="fld" style={{ width: 'auto' }} value={form.detail_role} onChange={e => set('detail_role', e.target.value as 'none' | 'description')}>
                  <option value="none">{t('fieldDetail.detailRoleNone')}</option>
                  <option value="description">{t('fieldDetail.detailRoleDescription')}</option>
                </select>
              </label>
            </div>
          )}
            {form.field_type === 'text' && (
              <div className="field">
                <div className="lbl">{t('fieldDetail.validationRegex')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.validationRegexHint')}</span></div>
                <input className="fld mono" value={form.validation_regex} onChange={e => set('validation_regex', e.target.value)}
                  placeholder="^97[89]-[0-9]{10}$" />
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('fieldDetail.validationExamples')}</div>
              </div>
            )}
        {!isVocabularyTerm && ['text', 'vocab', 'vocab_free', 'date', 'number'].includes(form.field_type) && (
          <div className="field">
            <div className="lbl">{t('fieldDetail.defaultValue')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.defaultValueHint')}</span></div>
            {form.field_type === 'vocab' ? (
              <select className="fld" value={(form.default_value as { id?: string })?.id ?? ''} onChange={e => {
                const term = defaultTerms.find(t => t.id === e.target.value)
                set('default_value', term ? { id: term.id, label: getLabel(term) } : '')
              }}>
                <option value="">{t('fieldDetail.defaultValueNone')}</option>
                {defaultTerms.map(t => <option key={t.id} value={t.id}>{getLabel(t, t.term)}</option>)}
              </select>
            ) : (
              <input className="fld" type={form.field_type === 'number' ? 'number' : 'text'} value={String(form.default_value ?? '')} onChange={e => set('default_value', e.target.value)} />
            )}
          </div>
        )}
        {!isVocabularyTerm && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <input type="checkbox" className="ck" checked={form.is_locked} onChange={e => set('is_locked', e.target.checked)} />
            <span style={{ fontSize: 13 }}>{t('fieldDetail.locked')}</span>
          </label>
        )}
        {aiEligible && (
          <div style={{ marginBottom: 16, padding: '12px 14px', border: '1px solid var(--border)', borderRadius: 6, background: 'var(--panel)' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 10 }}>
              <input type="checkbox" className="ck" checked={form.ai_enabled} onChange={e => set('ai_enabled', e.target.checked)} />
              {t('fieldDetail.aiEnable')}
            </label>
            {form.ai_enabled && (
              <>
                <div className="field">
                  <div className="lbl">{t('fieldDetail.aiMode')}</div>
                  <select className="fld" value={form.ai_mode} onChange={e => set('ai_mode', e.target.value as 'text' | 'vision')}>
                    <option value="text">{t('fieldDetail.aiModeText')}</option>
                    <option value="vision">{t('fieldDetail.aiModeVision')}</option>
                  </select>
                </div>
                <div className="field">
                  <div className="lbl">{t('fieldDetail.aiPrompt')}</div>
                  <textarea className="fld" value={form.ai_prompt} onChange={e => set('ai_prompt', e.target.value)} rows={5} placeholder={t('fieldDetail.aiPromptPlaceholder')} />
                </div>
                <div className="field">
                  <div className="lbl">{t('fieldDetail.aiContextFields')}</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
                    {availableFields
                      .filter(f => f.id !== fieldId && f.parent_id == null)
                      .map(f => (
                        <label key={f.id} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
                          <input
                            type="checkbox"
                            checked={form.ai_include_fields.includes(f.name)}
                            onChange={e => set('ai_include_fields', e.target.checked
                              ? [...form.ai_include_fields, f.name]
                              : form.ai_include_fields.filter(name => name !== f.name)
                            )}
                          />
                          <span>{getLabel(f, f.name)}</span>
                          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{f.name}</span>
                        </label>
                      ))}
                  </div>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" className="ck" checked={form.ai_send_existing_value} onChange={e => set('ai_send_existing_value', e.target.checked)} />
                  {t('fieldDetail.aiSendExisting')}
                </label>
              </>
            )}
          </div>
        )}
          </div>
        </details>
        {form.field_type === 'relation' && (
          <>
            <div className="fg-2">
              <div className="field">
                <div className="lbl">{t('fieldDetail.relationTargetType')} <span className="req">*</span></div>
                <select className="fld" value={form.relation_target_type} onChange={e => set('relation_target_type', e.target.value)}>
                  <option value="object">{t('fieldDetail.relationTargetTypeOptions.object')}</option>
                  <option value="entity">{t('fieldDetail.relationTargetTypeOptions.entity')}</option>
                  <option value="place">{t('fieldDetail.relationTargetTypeOptions.place')}</option>
                  <option value="occurrence">{t('fieldDetail.relationTargetTypeOptions.occurrence')}</option>
                  <option value="procedure">{t('fieldDetail.relationTargetTypeOptions.procedure')}</option>
                  <option value="collection">{t('fieldDetail.relationTargetTypeOptions.collection')}</option>
                  <option value="storage_location">{t('fieldDetail.relationTargetTypeOptions.storage_location')}</option>
                </select>
              </div>
              <div className="field">
                <div className="lbl">{t('fieldDetail.relationTargetSubtype')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.relationTargetSubtypeHint')}</span></div>
                <input className="fld" value={form.relation_target_subtype} onChange={e => set('relation_target_subtype', e.target.value)}
                  placeholder={t('fieldDetail.relationTargetSubtypePlaceholder')} />
              </div>
            </div>
            <div className="field">
              <div className="lbl">{t('fieldDetail.relationTypeVocab')} <span className="req">*</span></div>
              <select className="fld" value={form.relation_type_vocab} onChange={e => onChange({ ...form, relation_type_vocab: e.target.value, fixed_relation_type: '' })}>
                <option value="">{t('fieldDetail.relationTypeVocabPlaceholder')}</option>
                {allVocabs.filter(v => v.kind === 'relation').map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            {form.relation_type_vocab && (
              <div className="field">
                <div className="lbl">{t('fieldDetail.fixedRelationType')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.fixedRelationTypeHint')}</span></div>
                <select className="fld" value={form.fixed_relation_type} onChange={e => set('fixed_relation_type', e.target.value)}>
                  <option value="">{t('fieldDetail.fixedRelationTypeAll')}</option>
                  {relationTypeTerms.map(term => <option key={term.id} value={term.term}>{getLabel(term, term.term)}</option>)}
                </select>
              </div>
            )}
            {targetTypeFields.filter(f => f.field_type !== 'relation').length > 0 && (
              <div className="field">
                <div className="lbl">{t('fieldDetail.inheritedFields')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.inheritedFieldsHint')}</span></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                  {targetTypeFields.filter(f => f.field_type !== 'relation').map(f => (
                    <label key={f.name} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={form.inherited_fields.includes(f.name)}
                        onChange={e => set('inherited_fields', e.target.checked
                          ? [...form.inherited_fields, f.name]
                          : form.inherited_fields.filter(n => n !== f.name)
                        )}
                      />
                      {f.label?.de ?? f.label?.en ?? f.name}
                      <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{f.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn pri" onClick={onSave} disabled={saving}>
            {saving ? t('fieldDetail.saving') : t('fieldDetail.save')}
          </button>
          {!isNew && (
            <button className="btn dn" onClick={onDelete} disabled={saving}>{t('fieldDetail.delete')}</button>
          )}
        </div>

        {/* Sub-field management — only for saved group fields */}
        {form.field_type === 'group' && !isNew && fieldId && (
          <div style={{ marginTop: 20, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{t('fieldDetail.subFields')}</span>
              <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--fg-3)' }}>
                {t('fieldDetail.subFieldsDefined', { count: form.subFields?.length ?? 0 })}
              </span>
              <div style={{ flex: 1 }} />
              {subFieldEditing === null && (
                <button className="btn sm gh" onClick={openNewSubField}>
                  <Plus size={12} /> {t('fieldDetail.addSubField')}
                </button>
              )}
            </div>

            {/* Existing sub-fields */}
            {(form.subFields ?? []).map(sf => (
              <div key={sf.id} style={{ fontSize: 13 }}>
                {subFieldEditing === sf.id ? (
                  <SubFieldFormPanel
                    sf={subFieldForm!}
                    allVocabs={allVocabs}
                    availableFields={availableFields}
                    authoritySources={authoritySources}
                    nameManual={subNameManual}
                    saving={subFieldSaving}
                    error={subFieldError}
                    onChange={setSubFieldForm}
                    onNameManual={() => setSubNameManual(true)}
                    onSave={handleSubFieldSave}
                    onCancel={() => { setSubFieldEditing(null); setSubFieldForm(null) }}
                  />
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-s)' }}>
                    <span style={{ flex: 1, fontWeight: 500 }}>{getLabel(sf, sf.name)}</span>
                    <span className="key" style={{ fontSize: 11 }}>{sf.name}</span>
                    <span className="typ">{t(`fieldTypes.${sf.field_type}`)}</span>
                    {sf.is_required && <span className="req-mark">{t('fieldDetail.subFieldRequired')}</span>}
                    <button className="btn sm ico gh" onClick={() => openEditSubField(sf)}><Edit size={12} /></button>
                    <button className="btn sm ico gh dn" onClick={() => handleSubFieldDelete(sf.id)}><Trash size={12} /></button>
                  </div>
                )}
              </div>
            ))}

            {/* New sub-field form */}
            {subFieldEditing === 'new' && (
              <div style={{ marginTop: 8 }}>
                <SubFieldFormPanel
                  sf={subFieldForm!}
                  allVocabs={allVocabs}
                  availableFields={availableFields}
                  authoritySources={authoritySources}
                  nameManual={subNameManual}
                  saving={subFieldSaving}
                  error={subFieldError}
                  onChange={setSubFieldForm}
                  onNameManual={() => setSubNameManual(true)}
                  onSave={handleSubFieldSave}
                  onCancel={() => { setSubFieldEditing(null); setSubFieldForm(null) }}
                />
              </div>
            )}

            {(form.subFields?.length ?? 0) === 0 && subFieldEditing === null && (
              <div style={{ fontSize: 12, color: 'var(--fg-3)', paddingBottom: 4 }}>
                {t('fieldDetail.noSubFields')}
              </div>
            )}
          </div>
        )}
        {form.field_type === 'group' && isNew && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--accent-50)', borderRadius: 6, fontSize: 12, color: 'var(--fg-2)' }}>
            {t('fieldDetail.groupSaveHint')}
          </div>
        )}
      </div>
    </div>
  )
}

interface SubFieldFormPanelProps {
  sf: SubFieldFormState
  allVocabs: Vocabulary[]
  availableFields: FieldDefinition[]
  authoritySources: AuthoritySource[]
  nameManual: boolean
  saving: boolean
  error: string | null
  onChange: (sf: SubFieldFormState) => void
  onNameManual: () => void
  onSave: () => void
  onCancel: () => void
}

function SubFieldFormPanel({ sf, allVocabs, availableFields, authoritySources, nameManual, saving, error, onChange, onNameManual, onSave, onCancel }: SubFieldFormPanelProps) {
  const { t } = useTranslation('screenSchema')
  function set<K extends keyof SubFieldFormState>(k: K, v: SubFieldFormState[K]) { onChange({ ...sf, [k]: v }) }
  const languages = useSupportedLanguages()
  const primaryLang = languages[0] ?? 'de'
  const aiEligible = ['text', 'vocab_free', 'date', 'number', 'boolean'].includes(sf.field_type)
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', marginBottom: 8, background: 'var(--panel)' }}>
      {error && <div style={{ fontSize: 12, color: '#b91c1c', marginBottom: 8 }}>{error}</div>}
      <div className="fg-2">
        <LabelEditor
          languages={languages}
          value={sf.label}
          onChange={(lang, val) => {
            const nextLabel = { ...sf.label, [lang]: val }
            if (!nameManual && lang === primaryLang) {
              onChange({ ...sf, label: nextLabel, name: toSlug(val) })
            } else {
              onChange({ ...sf, label: nextLabel })
            }
          }}
        />
      </div>
      <div className="fg-2">
        <div className="field">
          <div className="lbl">{t('subFieldForm.internalName')}</div>
          <input className="fld mono" value={sf.name} onChange={e => { onNameManual(); set('name', e.target.value) }} disabled={Boolean(sf.id)} />
        </div>
        <div className="field">
          <div className="lbl">{t('subFieldForm.fieldType')}</div>
          <select className="fld" value={sf.field_type} onChange={e => set('field_type', e.target.value as SubFieldType)}>
            {SUB_FIELD_TYPES.map(k => <option key={k} value={k}>{t(`fieldTypes.${k}`)}</option>)}
          </select>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 8 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" className="ck" checked={sf.is_required} onChange={e => set('is_required', e.target.checked)} />
          {t('subFieldForm.required')}
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" className="ck" checked={sf.is_public} onChange={e => set('is_public', e.target.checked)} />
          {t('subFieldForm.isPublic')}
        </label>
      </div>
      {sf.field_type === 'text' && (
        <div className="field">
          <div className="lbl">{t('subFieldForm.validationRegex')} <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t('fieldDetail.validationRegexHint')}</span></div>
          <input className="fld mono" value={sf.validation_regex} onChange={e => set('validation_regex', e.target.value)} placeholder={t('subFieldForm.validationRegexPlaceholder')} />
        </div>
      )}
      {(sf.field_type === 'vocab' || sf.field_type === 'vocab_free') && (
        <div className="field">
          <div className="lbl">{t('subFieldForm.vocabLabel')}</div>
          <select className="fld" value={sf.vocabulary_id} onChange={e => set('vocabulary_id', e.target.value)}>
            <option value="">{t('subFieldForm.vocabPlaceholder')}</option>
            {allVocabs.filter(v => v.kind === 'term').map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </div>
      )}
      {sf.field_type === 'relation' && (
        <>
          <div className="field">
            <div className="lbl">{t('subFieldForm.targetType')}</div>
            <select className="fld" value={sf.relation_target_type} onChange={e => set('relation_target_type', e.target.value)}>
              <option value="object">{t('fieldDetail.relationTargetTypeOptions.object')}</option>
              <option value="entity">{t('fieldDetail.relationTargetTypeOptions.entity')}</option>
              <option value="place">{t('fieldDetail.relationTargetTypeOptions.place')}</option>
              <option value="occurrence">{t('fieldDetail.relationTargetTypeOptions.occurrence')}</option>
              <option value="collection">{t('fieldDetail.relationTargetTypeOptions.collection')}</option>
              <option value="storage_location">{t('fieldDetail.relationTargetTypeOptions.storage_location')}</option>
            </select>
          </div>
          <div className="field">
            <div className="lbl">{t('subFieldForm.relationTypeVocab')} <span className="req">*</span></div>
            <select className="fld" value={sf.relation_type_vocab} onChange={e => set('relation_type_vocab', e.target.value)}>
              <option value="">{t('subFieldForm.relationTypeVocabPlaceholder')}</option>
              {allVocabs.filter(v => v.kind === 'relation').map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
        </>
      )}
      {sf.field_type === 'authority' && (
        <div className="field">
          <div className="lbl">{t('subFieldForm.authoritySource')}</div>
          <select className="fld" value={sf.authority_source} onChange={e => set('authority_source', e.target.value)}>
            {authoritySources
              .filter(source => source.is_enabled || source.id === sf.authority_source)
              .map(source => (
                <option key={source.id} value={source.id} disabled={!source.is_enabled}>
                  {source.label}{source.is_enabled ? '' : t('subFieldForm.authorityDisabled')}
                </option>
              ))}
          </select>
          {sf.id && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('subFieldForm.authorityChangeWarning')}</div>}
        </div>
      )}
      {aiEligible && (
        <div style={{ marginBottom: 12, padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 6 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 10 }}>
            <input type="checkbox" className="ck" checked={sf.ai_enabled} onChange={e => set('ai_enabled', e.target.checked)} />
            {t('subFieldForm.aiEnable')}
          </label>
          {sf.ai_enabled && (
            <>
              <div className="field">
                <div className="lbl">{t('fieldDetail.aiMode')}</div>
                <select className="fld" value={sf.ai_mode} onChange={e => set('ai_mode', e.target.value as 'text' | 'vision')}>
                  <option value="text">{t('fieldDetail.aiModeText')}</option>
                  <option value="vision">{t('fieldDetail.aiModeVision')}</option>
                </select>
              </div>
              <div className="field">
                <div className="lbl">{t('subFieldForm.aiPrompt')}</div>
                <textarea className="fld" value={sf.ai_prompt} onChange={e => set('ai_prompt', e.target.value)} rows={4} />
              </div>
              <div className="field">
                <div className="lbl">{t('subFieldForm.aiContextFields')}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 140, overflowY: 'auto' }}>
                  {availableFields.filter(f => f.parent_id == null).map(f => (
                    <label key={f.id} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={sf.ai_include_fields.includes(f.name)}
                        onChange={e => set('ai_include_fields', e.target.checked
                          ? [...sf.ai_include_fields, f.name]
                          : sf.ai_include_fields.filter(name => name !== f.name)
                        )}
                      />
                      <span>{getLabel(f, f.name)}</span>
                    </label>
                  ))}
                </div>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
                <input type="checkbox" className="ck" checked={sf.ai_send_existing_value} onChange={e => set('ai_send_existing_value', e.target.checked)} />
                {t('subFieldForm.aiSendExisting')}
              </label>
              <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{t('subFieldForm.aiAutoContextHint')}</div>
            </>
          )}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button className="btn pri sm" onClick={onSave} disabled={saving}>{saving ? '…' : t('subFieldForm.save')}</button>
        <button className="btn gh sm" onClick={onCancel}>{t('subFieldForm.cancel')}</button>
      </div>
    </div>
  )
}

function ImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation('screenSchema')
  const fileRef = useRef<HTMLInputElement>(null)
  const [dryRun, setDryRun] = useState(true)
  const [overwrite, setOverwrite] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SchemaImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleImport() {
    const file = fileRef.current?.files?.[0]
    if (!file) { setError(t('importModal.errorNoFile')); return }
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await schema.import(file, { dryRun, overwrite })
      setResult(res)
      if (!dryRun) onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 480, maxWidth: '90vw' }}>
        <div className="hd">
          <span>{t('importModal.headline')}</span>
          <div className="grow" />
          <button className="btn sm" onClick={onClose}>{t('importModal.close')}</button>
        </div>
        <div className="bd">
          <p style={{ fontSize: 13, color: 'var(--fg-2)', margin: '0 0 12px' }}>
            {t('importModal.description')}
          </p>
          <details style={{ marginBottom: 12, fontSize: 12 }}>
            <summary style={{ cursor: 'pointer', color: 'var(--fg-3)', userSelect: 'none' }}>{t('importModal.formatHelp')}</summary>
            <pre style={{ margin: '8px 0 0', padding: '10px 12px', background: 'var(--panel)', borderRadius: 6, overflowX: 'auto', lineHeight: 1.5, fontSize: 11 }}>{`target_type: object   # object | entity | place | occurrence
fields:
  - name: title
    label:
      de: Titel
      en: Title
    field_type: text   # text | date | number | geo | vocab | relation | boolean
    is_required: true
    is_repeatable: false
    sort_order: 0
    settings: {}

  - name: material
    label: {de: Material}
    field_type: vocab
    settings:
      vocabulary: materials`}</pre>
          </details>
          <div className="field">
            <div className="lbl">{t('importModal.fileLabel')}</div>
            <input ref={fileRef} type="file" accept=".yaml,.yml,.json" className="fld" />
          </div>
          <div className="field" style={{ display: 'flex', gap: 16, flexDirection: 'row', paddingTop: 4 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" className="ck" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
              {t('importModal.dryRun')}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" className="ck" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />
              {t('importModal.overwrite')}
            </label>
          </div>
          {error && <div style={{ fontSize: 12, color: '#dc2626', margin: '8px 0' }}>{error}</div>}
          {result && (
            <div style={{ fontSize: 12, background: 'var(--accent-50)', borderRadius: 6, padding: '10px 12px', margin: '8px 0' }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{dryRun ? t('importModal.resultPreview') : t('importModal.resultDone')}</div>
              <div>{t('importModal.resultLine', { created: result.created, updated: result.updated, skipped: result.skipped })}</div>
              {result.errors.length > 0 && (
                <div style={{ color: '#b91c1c', marginTop: 4 }}>
                  {t('importModal.errorLabel')} {result.errors.map((e, i) => <div key={i}>{e}</div>)}
                </div>
              )}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn pri" onClick={handleImport} disabled={busy}>
              {busy ? t('importModal.importBusy') : dryRun ? t('importModal.importPreview') : t('importModal.import')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const TYPE_IDS = ['object', 'entity', 'place', 'occurrence', 'procedure', 'vocabulary_term']

function parseInitial(editId?: string | null): { type: string; subtype: string } {
  if (!editId) return { type: 'object', subtype: '' }
  const [type, subtype = ''] = editId.split('.')
  return TYPE_IDS.includes(type) ? { type, subtype } : { type: 'object', subtype: '' }
}

type Props = { initialPath?: string | null; onPathChange?: (path: string) => void }

export function ScreenSchema({ initialPath, onPathChange }: Props = {}) {
  const { t } = useTranslation('screenSchema')
  const initial = parseInitial(initialPath)
  const [activeType, setActiveType] = useState(initial.type)
  const [activeSubtype, setActiveSubtype] = useState(initial.subtype)
  const skipResetRef = useRef(true)
  const [subtypesList, setSubtypesList] = useState<RecordSubtype[]>([])
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<FieldFormState | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [showAiAssist, setShowAiAssist] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)
  const [pidProviders, setPidProviders] = useState<('ark' | 'dnb_urn')[]>([])
  const [authoritySources, setAuthoritySources] = useState<AuthoritySource[]>([])
  const [dragId, setDragId] = useState<string | null>(null)

  const TYPES = [
    { id: 'object',      label: t('typeLabels.object'),     key: 'object' },
    { id: 'entity',      label: t('typeLabels.entity'),     key: 'entity' },
    { id: 'place',       label: t('typeLabels.place'),      key: 'place' },
    { id: 'occurrence',  label: t('typeLabels.occurrence'), key: 'occurrence' },
    { id: 'procedure',   label: t('typeLabels.procedure'),  key: 'procedure' },
    { id: 'collection',  label: t('typeLabels.collection'), key: 'collection' },
    { id: 'storage_location', label: t('typeLabels.storage_location'), key: 'storage_location' },
    { id: 'vocabulary_term', label: t('typeLabels.vocabulary_term'), key: 'vocabulary_term' },
  ]

  const activeFieldIdRef = useRef<string | null>(null)
  activeFieldIdRef.current = activeFieldId

  const hasSubtypes = subtypesList.length > 0

  useEffect(() => {
    const request = activeType === 'vocabulary_term'
      ? vocabularies.list().then(list => list.map(v => ({
          id: v.id,
          name: v.id,
          label: { de: v.name },
          description: '',
          primary_type: 'vocabulary_term',
          sort_order: 0,
          is_default: false,
        })))
      : subtypes.list(activeType)
    request
      .then(list => {
        setSubtypesList(list)
        if (activeSubtype && !list.find(s => s.name === activeSubtype)) {
          setActiveSubtype('')
        }
      })
      .catch(() => setSubtypesList([]))
  }, [activeType])

  useEffect(() => {
    authority.list().then(setAuthoritySources).catch(() => setAuthoritySources([]))
    adminConfig.get().then(c => {
      setAiEnabled(c.ai_enabled)
      setPidProviders(c.pid_providers)
    }).catch(() => {
      setAiEnabled(false)
      setPidProviders([])
    })
  }, [])

  const loadFields = useCallback(() => {
    setLoading(true)
    schema.list(activeType, activeSubtype || undefined)
      .then(loaded => {
        setFields(loaded)
        // Sync sub-fields into open group field form
        setForm(prev => {
          if (!prev || prev.field_type !== 'group') return prev
          const current = loaded.find(f => f.id === activeFieldIdRef.current)
          if (current) return { ...prev, subFields: current.children ?? [] }
          return prev
        })
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [activeType, activeSubtype])

  useEffect(() => {
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
    loadFields()
  }, [loadFields])

  useEffect(() => {
    if (skipResetRef.current) { skipResetRef.current = false; return }
    setActiveSubtype('')
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
  }, [activeType])

  function openNew() {
    setIsNew(true)
    setActiveFieldId(null)
    const next = emptyForm(activeType, fields.length, activeSubtype)
    if (pidProviders.length) next.pid_provider = pidProviders[0]
    setForm(next)
    setSaveError(null)
  }

  function openExisting(f: FieldDefinition) {
    setIsNew(false)
    setActiveFieldId(f.id)
    setForm(fieldToForm(f))
    setSaveError(null)
  }

  function closeDetail() {
    setActiveFieldId(null)
    setIsNew(false)
    setForm(null)
  }

  async function handleSave() {
    if (!form) return
    if (!form.name.trim()) {
      setSaveError(t('errorInternalNameEmpty'))
      return
    }
    if (form.field_type === 'relation' && !form.relation_type_vocab) {
      setSaveError(t('errorRelationVocabEmpty'))
      return
    }
    if (form.field_type === 'authority' && !authoritySources.some(source => source.is_enabled && source.id === form.authority_source)) {
      setSaveError(t('errorAuthoritySourceEmpty'))
      return
    }
    setSaving(true)
    setSaveError(null)
    const data = {
      target_type: form.target_type,
      target_subtype: form.target_subtype.trim() || null,
      name: form.name,
      label: form.label,
      field_type: form.field_type as FieldDefinition['field_type'],
      is_required: form.is_required,
      is_repeatable: form.is_repeatable,
      is_translatable: form.is_translatable,
      sort_order: form.sort_order,
      show_in_detail: form.show_in_detail,
      show_in_list: form.show_in_list ?? false,
      detail_slot: form.detail_slot,
      detail_role: form.detail_role,
      is_public: form.is_public,
      is_facet: form.is_facet ?? false,
      is_searchable: form.is_searchable,
      settings: {
        ...(form.validation_regex.trim() ? { validation_regex: form.validation_regex.trim() } : {}),
        ...(form.field_type === 'authority' ? { source: form.authority_source } : {}),
        ...(form.field_type === 'pid' && form.target_type !== 'vocabulary_term' ? { pid_provider: form.pid_provider } : {}),
        ...((form.field_type === 'vocab' || form.field_type === 'vocab_free') && form.vocabulary_id ? { vocabulary_id: form.vocabulary_id } : {}),
        ...(form.field_type === 'relation' ? {
          target_type: form.relation_target_type,
          ...(form.relation_target_subtype.trim() ? { target_subtype: form.relation_target_subtype.trim() } : {}),
          relation_type_vocab: form.relation_type_vocab,
          ...(form.relation_type_vocab && form.fixed_relation_type ? { fixed_relation_type: form.fixed_relation_type } : {}),
          ...(form.inherited_fields.length ? { inherited_fields: form.inherited_fields } : {}),
        } : {}),
        ...(['text', 'vocab', 'vocab_free', 'date', 'number'].includes(form.field_type) && form.default_value !== '' ? { default_value: form.default_value } : {}),
        ...(form.is_locked ? { is_locked: true } : {}),
        ...(form.ai_enabled ? {
          ai_config: {
            enabled: true,
            mode: form.ai_mode,
            prompt: form.ai_prompt.trim(),
            include_fields: form.ai_include_fields,
            send_existing_value: form.ai_send_existing_value,
          },
        } : {}),
      },
    }
    try {
      if (isNew) {
        const created = await schema.create(data)
        closeDetail()
        loadFields()
        // Immediately open the new group field so user can add sub-fields
        if (data.field_type === 'group') {
          setTimeout(() => {
            setIsNew(false)
            setActiveFieldId(created.id)
            setForm({ ...fieldToForm(created as FieldDefinition), subFields: [] })
          }, 100)
          return
        }
      } else {
        await schema.update(activeFieldId!, data)
        loadFields()
        // Keep group field open with updated form but preserve subFields
        if (data.field_type === 'group') {
          setForm(prev => prev ? { ...prev, ...data as Partial<FieldFormState> } : prev)
          return
        }
        closeDetail()
      }
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleReorder(draggedId: string, targetId: string) {
    if (draggedId === targetId) return
    const from = fields.findIndex(f => f.id === draggedId)
    const to = fields.findIndex(f => f.id === targetId)
    if (from === -1 || to === -1) return
    const reordered = [...fields]
    const [moved] = reordered.splice(from, 1)
    reordered.splice(to, 0, moved)
    setFields(reordered)
    const changed = reordered.filter((f, i) => f.sort_order !== i)
    try {
      await Promise.all(changed.map(f => {
        const newOrder = reordered.indexOf(f)
        return schema.update(f.id, {
          target_type: f.target_type,
          target_subtype: f.target_subtype,
          name: f.name,
          label: f.label,
          field_type: f.field_type,
          is_required: f.is_required,
          is_repeatable: f.is_repeatable,
          is_translatable: f.is_translatable,
          is_searchable: f.is_searchable,
          sort_order: newOrder,
          settings: f.settings,
          show_in_detail: f.show_in_detail,
          show_in_list: f.show_in_list,
          detail_slot: f.detail_slot,
          detail_role: f.detail_role,
          is_public: f.is_public,
          is_facet: f.is_facet,
          parent_id: f.parent_id ?? null,
        })
      }))
      loadFields()
    } catch (e) {
      alert((e as Error).message)
      loadFields()
    }
  }

  async function handleDelete() {
    if (!activeFieldId || !window.confirm(t('deleteConfirm', { name: form?.name ?? '' }))) return
    setSaving(true)
    try {
      await schema.delete(activeFieldId)
      closeDetail()
      loadFields()
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const showDetail = form !== null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onDone={() => { setShowImport(false); loadFields() }} />
      )}
      {showAiAssist && (
        <SchemaAiAssist
          targetType={activeType}
          targetTypeLabel={TYPES.find(t => t.id === activeType)?.label ?? activeType}
          targetSubtype={activeSubtype}
          existingFieldCount={fields.length}
          onClose={() => setShowAiAssist(false)}
          onApplied={() => loadFields()}
        />
      )}
      <div className="ph">
        <div><h1>{t('headline')}</h1><div className="sub">{t('headlineSub')}</div></div>
        <div className="right">
          {aiEnabled && (
            <button className="btn gh" onClick={() => setShowAiAssist(true)} disabled={activeType === 'vocabulary_term'} title={t('aiAssistTitle')}><Lightning size={13} /> {t('aiAssist')}</button>
          )}
          <button className="btn gh" onClick={() => setShowImport(true)}>{t('import')}</button>
          <button className="btn pri" onClick={openNew} disabled={activeType === 'vocabulary_term' && !activeSubtype}><Plus size={13} /> {t('addField')}</button>
        </div>
      </div>

      <div className="tabs">
        {TYPES.map(t => (
          <button
            key={t.id}
            className={`tab${activeType === t.id ? ' active' : ''}`}
            onClick={() => { setActiveType(t.id); onPathChange?.(t.id) }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="schema-workspace" style={{ gridTemplateColumns: hasSubtypes ? '220px 1fr' : '1fr' }}>
        {hasSubtypes && (
          <div className="schema-subtype-panel">
            <div style={{ padding: '14px 12px 6px', fontFamily: "'IBM Plex Mono',monospace", fontSize: '10px', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--fg-4)', fontWeight: 500 }}>
              {t('subtypes.headline')}
            </div>
            {(activeType === 'vocabulary_term' ? subtypesList : [{ id: '', name: '', label: { de: t('subtypes.allGlobal') } }, ...subtypesList]).map(s => (
              <button
                key={s.id}
                className={`panel-it${activeSubtype === s.name ? ' active' : ''}`}
                onClick={() => { setActiveSubtype(s.name); onPathChange?.(s.name ? `${activeType}.${s.name}` : activeType) }}
              >
                <span>{s.label?.de || s.name || t('subtypes.allGlobal')}</span>
                {s.name && <span className="ct">{fields.filter(f => f.target_subtype === s.name).length}</span>}
              </button>
            ))}
          </div>
        )}

        <div style={{ overflowY: 'auto', minHeight: 0 }}>
          {hasSubtypes && (
            <div className="schema-subtype-select field">
              <label className="lbl" htmlFor="schema-subtype">
                {activeType === 'vocabulary_term' ? t('subtypes.filterLabelVocab') : t('subtypes.filterLabel')}
              </label>
              <select
                id="schema-subtype"
                className="fld"
                value={activeSubtype}
                onChange={e => setActiveSubtype(e.target.value)}
              >
                {activeType === 'vocabulary_term' && <option value="">{t('subtypes.pleaseSelect')}</option>}
                {activeType !== 'vocabulary_term' && <option value="">{t('subtypes.allGlobal')}</option>}
                {subtypesList.map(s => (
                  <option key={s.id} value={s.name}>{s.label?.de || s.name}</option>
                ))}
              </select>
            </div>
          )}
          {showDetail ? (
            <FieldDetail
              form={form!}
              availableFields={fields}
              fieldId={activeFieldId}
              isNew={isNew}
              saving={saving}
              error={saveError}
              showSubtype={hasSubtypes && activeType !== 'vocabulary_term'}
              authoritySources={authoritySources}
              pidProviders={pidProviders}
              onChange={setForm}
              onSave={handleSave}
              onDelete={handleDelete}
              onClose={closeDetail}
              onSubFieldChange={loadFields}
            />
          ) : (
            <>
              {loading ? (
                <div className="empty" style={{ paddingTop: 40 }}>{t('loading')}</div>
              ) : (
                <>
                  <div style={{ margin: '12px 24px 4px', color: 'var(--fg-3)', fontSize: 12 }}>
                    {t('fieldCount', { count: fields.length })}
                    {activeSubtype && (
                      <span>{t('forSubtype', { subtype: activeSubtype })}</span>
                    )}
                  </div>
                  {fields.map(f => {
                    const fieldLabel = getLabel(f, f.name)
                    return (
                      <div
                        key={f.id}
                        className={`field-row${dragId === f.id ? ' dragging' : ''}`}
                        draggable
                        onDragStart={() => setDragId(f.id)}
                        onDragEnd={() => setDragId(null)}
                        onDragOver={e => e.preventDefault()}
                        onDrop={e => {
                          e.preventDefault()
                          if (dragId) handleReorder(dragId, f.id)
                          setDragId(null)
                        }}
                      >
                        <button className="field-row-main" onClick={() => openExisting(f)}>
                          <span className="gp" aria-hidden="true"><Grip size={14} /></span>
                          <span className="nm">{fieldLabel}</span>
                          <span className="key">{f.name}</span>
                          {f.target_subtype && (
                            <span className="typ target-subtype" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{f.target_subtype}</span>
                          )}
                          <span className="typ">{t(`fieldTypes.${f.field_type}`)}</span>
                          {f.field_type === 'group' && <span className="typ" style={{ background: 'var(--fg-5)', color: 'var(--fg-3)' }}>{f.children?.length ?? 0} Sub-Felder</span>}
                          {f.is_required && <span className="req-mark">{t('fieldDetail.subFieldRequired')}</span>}
                          {f.is_repeatable && <span className="typ" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>×n</span>}
                        </button>
                        <div className="actions">
                          <button className="btn sm ico gh dn" aria-label={`Feld ${fieldLabel} löschen`} onClick={async () => {
                            if (!window.confirm(t('deleteConfirm', { name: fieldLabel }))) return
                            try {
                              await schema.delete(f.id)
                              loadFields()
                            } catch (err) {
                              alert((err as Error).message)
                            }
                          }}><Trash size={12} /></button>
                        </div>
                      </div>
                    )
                  })}
                  {fields.length === 0 && <div className="empty">{t('noFields')}</div>}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
