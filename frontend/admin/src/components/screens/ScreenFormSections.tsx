// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formSections, schema } from '../../api/client'
import type { FieldDefinition, FormSection } from '../../types'
import { Edit, Plus, Trash } from '../ui/Icons'
import { ActionMenu } from '../ui/ActionMenu'
import { LabelEditor } from '../ui/LabelEditor'
import { useSupportedLanguages } from '../../hooks/useSupportedLanguages'

const inputStyle: React.CSSProperties = { width: '100%', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', fontSize: 13, background: 'var(--bg)', color: 'var(--fg)', boxSizing: 'border-box' }

type FormState = { target_type: string; target_subtype: string | null; label: Record<string, string>; field_names: string[]; sort_order: number }

function emptyForm(targetType: string, subtype: string): FormState {
  return { target_type: targetType, target_subtype: subtype || null, label: {}, field_names: [], sort_order: 0 }
}

function sectionToForm(section: FormSection): FormState {
  return { target_type: section.target_type, target_subtype: section.target_subtype, label: { ...section.label }, field_names: section.field_names, sort_order: section.sort_order }
}

type Props = { targetType: string; targetSubtype: string }

export function ScreenFormSections({ targetType, targetSubtype }: Props) {
  const { t } = useTranslation('screenFormSections')
  const languages = useSupportedLanguages()
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [sections, setSections] = useState<FormSection[]>([])
  const [form, setForm] = useState<FormState | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      formSections.list(targetType, targetSubtype || undefined),
      schema.list(targetType, targetSubtype || undefined),
    ]).then(([nextSections, nextFields]) => {
      setSections(nextSections)
      setFields(targetSubtype ? nextFields : nextFields.filter(field => field.target_subtype == null))
    }).catch(() => { setSections([]); setFields([]) }).finally(() => setLoading(false))
  }, [targetType, targetSubtype])

  useEffect(() => { load() }, [load])
  useEffect(() => { setForm(null); setEditId(null); setError(null) }, [targetType, targetSubtype])

  function toggleField(name: string) {
    setForm(current => current ? { ...current, field_names: current.field_names.includes(name) ? current.field_names.filter(item => item !== name) : [...current.field_names, name] } : current)
  }

  async function save() {
    if (!form || !Object.values(form.label).some(label => label.trim())) { setError(t('errorLabelRequired')); return }
    setSaving(true)
    setError(null)
    try {
      if (editId) await formSections.update(editId, form)
      else await formSections.create(form)
      setForm(null)
      setEditId(null)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('errorSave'))
    } finally {
      setSaving(false)
    }
  }

  async function del(section: FormSection) {
    if (!confirm(t('deleteConfirm'))) return
    await formSections.delete(section.id).catch(() => {})
    load()
  }

  return (
    <div className="settings-page">
      <div className="settings-head" style={{ marginBottom: 8 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>{t('heading')}</h2>
        <button onClick={() => { setForm(emptyForm(targetType, targetSubtype)); setEditId(null); setError(null) }} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
          <Plus size={14} /> {t('newSection')}
        </button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--fg-3)', marginBottom: 20 }}>{t('description')}</p>

      {form && <div className="settings-card">
        <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>{editId ? t('editHeading') : t('newHeading')}</h2>
        <div className="fg-2" style={{ marginBottom: 14 }}>
          <div><label>{t('displayNameLabel')}</label><LabelEditor languages={languages} value={form.label} onChange={(lang, value) => setForm(current => current ? { ...current, label: { ...current.label, [lang]: value } } : current)} /></div>
          <div><label>{t('sortOrderLabel')}</label><input type="number" style={inputStyle} value={form.sort_order} onChange={event => setForm(current => current ? { ...current, sort_order: Number(event.target.value) } : current)} /></div>
        </div>
        <div style={{ marginBottom: 16 }}><div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>{t('fieldListLabel')}</div>{fields.map(field => <label key={field.id} style={{ display: 'flex', gap: 8, padding: '5px 0', fontSize: 13 }}><input type="checkbox" checked={form.field_names.includes(field.name)} onChange={() => toggleField(field.name)} />{field.label.de || field.name}</label>)}</div>
        {error && <div className="err" style={{ marginBottom: 10 }}>{error}</div>}
        <div className="settings-actions"><button onClick={save} disabled={saving} className="btn pri">{saving ? t('saving') : t('save')}</button><button onClick={() => { setForm(null); setEditId(null); setError(null) }} className="btn">{t('cancel')}</button></div>
      </div>}

      {loading ? <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>{t('loading')}</div> : sections.length === 0 ? <div className="empty">{t('empty')}</div> : <div className="schema-list">{sections.map(section => <div key={section.id} className="item settings-list-item"><div><strong>{section.label.de || section.label.en || t('unnamed')}</strong><div style={{ color: 'var(--fg-3)', fontSize: 12 }}>{t('fieldsCount', { n: section.field_names.length })}</div></div><ActionMenu ariaLabel={t('actions')} items={[{ key: 'edit', label: t('edit'), icon: <Edit size={13} />, onClick: () => { setForm(sectionToForm(section)); setEditId(section.id); setError(null) } }, { key: 'delete', label: t('delete'), icon: <Trash size={13} />, danger: true, onClick: () => del(section) }]} /></div>)}</div>}
    </div>
  )
}
