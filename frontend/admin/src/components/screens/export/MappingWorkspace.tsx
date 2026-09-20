// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportMappingSets, schema, vocabularies } from '../../../api/client'
import type {
  ExportMappingRule,
  ExportMappingSet,
  ExportProfileCapabilities,
  ExportTargetCapability,
  FieldDefinition,
  LidoEventConfig,
  MappingDiagnostic,
  SourceKind,
} from '../../../types'
import { ChevD, ChevL, ChevU, Plus, Trash, X } from '../../ui/Icons'
import { ExportGuidance } from './ExportGuidance'
import { ExportPreview } from './ExportPreview'
import { PublishMapping } from './PublishMapping'
import { RuleEditor } from './RuleEditor'
import { SourcePicker, type SourceDraft } from './SourcePicker'
import { TargetNavigator } from './TargetNavigator'
import { ValidationPanel } from './ValidationPanel'

export interface MappingWorkspaceProps {
  recordType: string
  profile: ExportProfileCapabilities
  onBack: () => void
}

const DEFAULT_LIDO_EVENTS: LidoEventConfig[] = [
  {
    id: 'production',
    type: 'Herstellung',
    label: { de: 'Herstellung / Entstehung', en: 'Production / Creation' },
    is_preset: true,
  },
]

const LIDO_LEGACY_TARGET_ALIAS: Record<string, string> = {
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term': 'lido:events/production/type',
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate': 'lido:events/production/date',
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate': 'lido:events/production/earliest_date',
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue': 'lido:events/production/actor',
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventPlace/lido:displayPlace': 'lido:events/production/place',
  'lido:eventWrap/lido:eventSet/lido:event/lido:eventMaterialsTech/lido:displayMaterialsTech': 'lido:events/production/materials_tech',
}

function buildLidoEventTargets(
  event: LidoEventConfig,
  t: (key: string, options?: Record<string, unknown>) => string,
): ExportTargetCapability[] {
  const { id, label } = event
  return [
    {
      key: `lido:events/${id}/actor`,
      group: 'events',
      label: { de: `${label.de}: ${t('eventActorLabel')}`, en: `${label.en}: ${t('eventActorLabel')}` },
      help: { de: t('eventActorHelp'), en: t('eventActorHelp') },
      source_kinds: ['field', 'relation'],
      accepted_field_types: ['text', 'relation'],
      cardinality: 'many',
      required: false,
      editor_kind: 'default',
      settings_schema: {},
    },
    {
      key: `lido:events/${id}/materials_tech`,
      group: 'events',
      label: { de: `${label.de}: ${t('eventMaterialsTechLabel')}`, en: `${label.en}: ${t('eventMaterialsTechLabel')}` },
      help: { de: t('eventMaterialsTechHelp'), en: t('eventMaterialsTechHelp') },
      source_kinds: ['field', 'constant'],
      accepted_field_types: ['text'],
      cardinality: 'many',
      required: false,
      editor_kind: 'default',
      settings_schema: {},
    },
    {
      key: `lido:events/${id}/date`,
      group: 'events',
      label: { de: `${label.de}: ${t('eventDateLabel')}`, en: `${label.en}: ${t('eventDateLabel')}` },
      help: { de: t('eventDateHelp'), en: t('eventDateHelp') },
      source_kinds: ['field'],
      accepted_field_types: ['text', 'date'],
      cardinality: 'one',
      required: false,
      editor_kind: 'default',
      settings_schema: {},
    },
    {
      key: `lido:events/${id}/earliest_date`,
      group: 'events',
      label: { de: `${label.de}: ${t('eventEarliestDateLabel')}`, en: `${label.en}: ${t('eventEarliestDateLabel')}` },
      help: { de: t('eventEarliestDateHelp'), en: t('eventEarliestDateHelp') },
      source_kinds: ['field'],
      accepted_field_types: ['text', 'date'],
      cardinality: 'one',
      required: false,
      editor_kind: 'default',
      settings_schema: {},
    },
    {
      key: `lido:events/${id}/place`,
      group: 'events',
      label: { de: `${label.de}: ${t('eventPlaceLabel')}`, en: `${label.en}: ${t('eventPlaceLabel')}` },
      help: { de: t('eventPlaceHelp'), en: t('eventPlaceHelp') },
      source_kinds: ['field', 'relation'],
      accepted_field_types: ['text', 'geo', 'relation'],
      cardinality: 'many',
      required: false,
      editor_kind: 'default',
      settings_schema: {},
    },
  ]
}

function InstitutionConfigEditor({ config, busy, isLido, isMetsMods = false, onSave }: {
  config: Record<string, unknown>
  busy: boolean
  isLido: boolean
  isMetsMods?: boolean
  onSave: (config: Record<string, unknown>) => Promise<boolean>
}) {
  const { t } = useTranslation('screenExport')

  const STANDARD_KEYS = useMemo<Record<string, true>>(
    () => ({
      institution_name: true,
      repository_name: true,
      isil: true,
      website: true,
      repository_url: true,
      location: true,
      repository_location: true,
      portal_host: true,
      record_rights: true,
      lido_events: true,
      mods_elements: true,
    }),
    []
  )

  const [institutionName, setInstitutionName] = useState<string>(
    () => String(config.institution_name ?? config.repository_name ?? '')
  )
  const [isil, setIsil] = useState<string>(
    () => String(config.isil ?? '')
  )
  const [website, setWebsite] = useState<string>(
    () => String(config.website ?? config.repository_url ?? '')
  )
  const [location, setLocation] = useState<string>(
    () => String(config.location ?? config.repository_location ?? '')
  )
  const [portalHost, setPortalHost] = useState<string>(() => String(config.portal_host ?? ''))
  const [recordRights, setRecordRights] = useState<string>(
    () => String(config.record_rights ?? 'https://creativecommons.org/publicdomain/zero/1.0/')
  )

  const [customRows, setCustomRows] = useState<{ key: string; value: string }[]>(() =>
    Object.entries(config)
      .filter(([key]) => !STANDARD_KEYS[key])
      .map(([key, value]) => ({ key, value: String(value ?? '') }))
  )
  const [showCustom, setShowCustom] = useState(() => customRows.length > 0)
  const [dirty, setDirty] = useState(false)
  const [open, setOpen] = useState(() => !institutionName.trim())
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setInstitutionName(String(config.institution_name ?? config.repository_name ?? ''))
    setIsil(String(config.isil ?? ''))
    setWebsite(String(config.website ?? config.repository_url ?? ''))
    setLocation(String(config.location ?? config.repository_location ?? ''))
    setPortalHost(String(config.portal_host ?? ''))
    setRecordRights(String(config.record_rights ?? 'https://creativecommons.org/publicdomain/zero/1.0/'))
    const nextCustom = Object.entries(config)
      .filter(([key]) => !STANDARD_KEYS[key])
      .map(([key, value]) => ({ key, value: String(value ?? '') }))
    setCustomRows(nextCustom)
    setShowCustom(nextCustom.length > 0)
    setDirty(false)
  }, [config, STANDARD_KEYS])

  function updateCustomRow(i: number, patch: Partial<{ key: string; value: string }>) {
    setCustomRows(r => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)))
    setDirty(true)
  }
  function addCustomRow() {
    setCustomRows(r => [...r, { key: '', value: '' }])
    setShowCustom(true)
    setDirty(true)
  }
  function removeCustomRow(i: number) {
    setCustomRows(r => r.filter((_, idx) => idx !== i))
    setDirty(true)
  }

  async function save() {
    const next: Record<string, unknown> = {}
    if (config.lido_events) {
      next.lido_events = config.lido_events
    }
    if (config.mods_elements) {
      next.mods_elements = config.mods_elements
    }
    if (institutionName.trim()) next.institution_name = institutionName.trim()
    if (isil.trim()) next.isil = isil.trim()
    if (website.trim()) next.website = website.trim()
    if (location.trim()) next.location = location.trim()
    if ((isLido || isMetsMods) && portalHost.trim()) next.portal_host = portalHost.trim()
    if ((isLido || isMetsMods) && recordRights.trim()) next.record_rights = recordRights.trim()

    for (const row of customRows) {
      if (row.key.trim()) {
        next[row.key.trim()] = row.value
      }
    }
    if (await onSave(next)) {
      setDirty(false)
      setSaved(true)
      if (institutionName.trim()) setOpen(false)
      window.setTimeout(() => setSaved(false), 2000)
    }
  }

  return (
    <div className="settings-card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{t('institutionConfigHeadline')}</h3>
        <button
          type="button"
          className="btn sm ico gh"
          aria-label={open ? t('collapseLabel') : t('expandLabel')}
          title={open ? t('collapseLabel') : t('expandLabel')}
          disabled={open && (!institutionName.trim() || dirty)}
          onClick={() => setOpen(current => !current)}
        >
          {open ? <ChevU size={13} /> : <ChevD size={13} />}
        </button>
      </div>
      {saved && <div role="status" style={{ color: '#16a34a', fontSize: 12, marginBottom: 8 }}>{t('institutionConfigSaved')}</div>}
      {open && <>
        <p style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 0, marginBottom: 16 }}>
          {t('institutionConfigHelp')}
        </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16 }}>
        {/* Name der Institution (Pflicht) */}
        <div>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
            {t('institutionNameLabel')}{' '}
            <span style={{ color: '#dc2626', fontSize: 11, fontWeight: 700 }}>* {t('requiredMarker')}</span>
          </label>
          <input
            className="fld"
            style={{ width: '100%' }}
            placeholder={t('institutionNamePlaceholder')}
            value={institutionName}
            onChange={e => {
              setInstitutionName(e.target.value)
              setDirty(true)
            }}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('institutionNameHelp')}</div>
        </div>

        {/* ISIL (Empfohlen) */}
        <div>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
            {t('isilLabel')}{' '}
            <span style={{ color: 'var(--fg-3)', fontSize: 11, fontWeight: 400 }}>({t('recommendedMarker')})</span>
          </label>
          <input
            className="fld"
            style={{ width: '100%' }}
            placeholder={t('isilPlaceholder')}
            value={isil}
            onChange={e => {
              setIsil(e.target.value)
              setDirty(true)
            }}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('isilHelp')}</div>
        </div>

        {/* Webseite / URL */}
        <div>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
            {t('websiteLabel')}
          </label>
          <input
            className="fld"
            style={{ width: '100%' }}
            placeholder={t('websitePlaceholder')}
            value={website}
            onChange={e => {
              setWebsite(e.target.value)
              setDirty(true)
            }}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('websiteHelp')}</div>
        </div>

        {/* Standort / Ort */}
        <div>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
            {t('locationLabel')}
          </label>
          <input
            className="fld"
            style={{ width: '100%' }}
            placeholder={t('locationPlaceholder')}
            value={location}
            onChange={e => {
              setLocation(e.target.value)
              setDirty(true)
            }}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('locationHelp')}</div>
        </div>

        {(isLido || isMetsMods) && (
          <>
            {isLido && (
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
                  {t('portalHostLabel')}
                </label>
                <input
                  className="fld"
                  style={{ width: '100%' }}
                  placeholder={t('portalHostPlaceholder')}
                  value={portalHost}
                  onChange={e => {
                    setPortalHost(e.target.value)
                    setDirty(true)
                  }}
                />
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('portalHostHelp')}</div>
              </div>
            )}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', marginBottom: 4 }}>
                {t('recordRightsLabel')}
              </label>
              <input
                className="fld"
                style={{ width: '100%' }}
                placeholder={t('recordRightsPlaceholder')}
                value={recordRights}
                onChange={e => {
                  setRecordRights(e.target.value)
                  setDirty(true)
                }}
              />
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{t('recordRightsHelp')}</div>
            </div>
          </>
        )}
      </div>

      {/* Custom parameters section */}
      <div style={{ borderTop: '1px solid var(--border-s)', paddingTop: 12, marginBottom: 16 }}>
        <button
          type="button"
          className="btn sm gh"
          onClick={() => {
            if (!showCustom && customRows.length === 0) {
              addCustomRow()
            } else {
              setShowCustom(v => !v)
            }
          }}
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 8px' }}
        >
          <Plus size={12} /> {t('customParamsToggle')} {customRows.length > 0 ? `(${customRows.length})` : ''}
        </button>

        {showCustom && (
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {customRows.map((row, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  className="fld sm"
                  style={{ width: 200 }}
                  placeholder={t('institutionConfigKey')}
                  aria-label={t('institutionConfigKey')}
                  value={row.key}
                  onChange={e => updateCustomRow(i, { key: e.target.value })}
                />
                <input
                  className="fld sm"
                  style={{ flex: 1 }}
                  placeholder={t('institutionConfigValue')}
                  aria-label={t('institutionConfigValue')}
                  value={row.value}
                  onChange={e => updateCustomRow(i, { value: e.target.value })}
                />
                <button
                  type="button"
                  className="btn sm ico gh"
                  aria-label={t('ruleDeleteLabel')}
                  title={t('ruleDeleteLabel')}
                  onClick={() => removeCustomRow(i)}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
            <div>
              <button
                type="button"
                className="btn sm gh"
                onClick={addCustomRow}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}
              >
                <Plus size={12} /> {t('addCustomParam')}
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          className="btn sm pri"
          disabled={!dirty || busy}
          onClick={save}
        >
          {t('institutionConfigSave')}
        </button>
      </div>
      </>}
    </div>
  )
}


export function MappingWorkspace({ recordType, profile, onBack }: MappingWorkspaceProps) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'
  const compact = profile.format_key === 'oai_dc'
  const isLido = profile.format_key === 'lido'
  const isMetsMods = profile.format_key === 'mets_mods'

  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [publishedSet, setPublishedSet] = useState<ExportMappingSet | null>(null)
  const [draftSet, setDraftSet] = useState<ExportMappingSet | null>(null)
  const [selectedTargetKey, setSelectedTargetKey] = useState<string | null>(null)
  const [diagnostics, setDiagnostics] = useState<MappingDiagnostic[]>([])
  const [validated, setValidated] = useState(false)
  const [busy, setBusy] = useState(false)
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [importStatus, setImportStatus] = useState<{ message: string; type: 'success' | 'error'; warnings?: string[] } | null>(null)
  const [relationTypeOptions, setRelationTypeOptions] = useState<{ term: string; label: Record<string, string> }[]>([])

  const lidoEvents: LidoEventConfig[] = useMemo(() => {
    if (!isLido) return []
    const configured = draftSet?.institution_config?.lido_events
    if (Array.isArray(configured) && configured.length > 0) {
      return configured as LidoEventConfig[]
    }
    return DEFAULT_LIDO_EVENTS
  }, [isLido, draftSet?.institution_config])

  const configuredModsElements = useMemo<string[]>(() => {
    if (!isMetsMods) return []
    const raw = draftSet?.institution_config?.mods_elements
    return Array.isArray(raw) ? (raw as string[]) : []
  }, [isMetsMods, draftSet?.institution_config])

  const effectiveTargets = useMemo(() => {
    if (isLido) {
      const nonEventTargets = profile.targets.filter(trg => trg.group !== 'events')
      const eventTargets: ExportTargetCapability[] = []
      for (const ev of lidoEvents) {
        eventTargets.push(...buildLidoEventTargets(ev, t))
      }
      return [...nonEventTargets, ...eventTargets]
    }
    if (isMetsMods) {
      const baseNoteTarget = profile.targets.find(t => t.key === 'mods:note')
      const rules = draftSet?.rules ?? []

      const noteKeysSet = new Set<string>()
      for (const k of configuredModsElements) {
        if (k === 'mods:note' || k.startsWith('mods:note/')) {
          noteKeysSet.add(k)
        }
      }
      for (const r of rules) {
        if (r.target_key === 'mods:note' || r.target_key.startsWith('mods:note/')) {
          noteKeysSet.add(r.target_key)
        }
      }

      const noteKeys = Array.from(noteKeysSet)

      const noteTargets: ExportTargetCapability[] = noteKeys.map((key, idx) => {
        const matchingRule = rules.find(r => r.target_key === key)
        const noteType = (matchingRule?.settings?.type as string | undefined)?.trim()
        const baseDe = t('noteTargetBaseName', 'Anmerkung')
        const baseEn = t('noteTargetBaseName', 'Note')
        const deLabel = noteType
          ? `${baseDe} (${noteType})`
          : noteKeys.length > 1
            ? `${baseDe} ${idx + 1}`
            : (baseNoteTarget?.label.de ?? 'Anmerkung / Note')
        const enLabel = noteType
          ? `${baseEn} (${noteType})`
          : noteKeys.length > 1
            ? `${baseEn} ${idx + 1}`
            : (baseNoteTarget?.label.en ?? 'Note')

        return {
          ...(baseNoteTarget ?? {
            key,
            group: 'description',
            label: { de: deLabel, en: enLabel },
            help: { de: 'Anmerkung oder Hinweis mit optionalem Typ', en: 'Note or remark with optional type' },
            source_kinds: ['field', 'constant'],
            accepted_field_types: ['text'],
            cardinality: 'one',
            required: false,
            editor_kind: 'mods_note',
            settings_schema: {},
            is_core: false,
          }),
          key,
          label: { de: deLabel, en: enLabel },
          cardinality: 'one',
          is_core: false,
        }
      })

      const activeKeys = new Set([
        ...configuredModsElements,
        ...(rules.map(r => r.target_key)),
      ])

      const nonNoteTargets = profile.targets.filter(
        trg => trg.key !== 'mods:note' && (trg.is_core !== false || activeKeys.has(trg.key))
      )

      return [...nonNoteTargets, ...noteTargets]
    }
    return profile.targets
  }, [isLido, isMetsMods, profile.targets, lidoEvents, configuredModsElements, draftSet?.rules, t])

  const availableModsTargets = useMemo(() => {
    if (!isMetsMods) return []
    const activeKeys = new Set(effectiveTargets.map(t => t.key))
    return profile.targets.filter(
      trg => trg.is_core === false && (trg.key === 'mods:note' || !activeKeys.has(trg.key))
    )
  }, [isMetsMods, effectiveTargets, profile.targets])

  const load = useCallback(() => {
    return Promise.all([
      schema.list(recordType),
      exportMappingSets.list({ record_type: recordType, format_key: profile.format_key }),
      vocabularies.list().then(vocabs => {
        const relVocab = vocabs.find(v => v.kind === 'relation')
        if (!relVocab) return []
        return Promise.all([
          vocabularies.listTerms(relVocab.id, { from_type: recordType }),
          vocabularies.listTerms(relVocab.id, { to_type: recordType }),
        ]).then(([asSource, asTarget]) => {
          const byId = new Map(asSource.map(term => [term.id, term]))
          for (const term of asTarget) byId.set(term.id, term)
          return [...byId.values()]
        })
      }),
    ]).then(([fieldList, sets, terms]) => {
      setFields(fieldList)
      setRelationTypeOptions(terms.map(t => ({ term: t.term, label: t.label })))
      setPublishedSet(sets.find(s => s.status === 'published') ?? null)
      setDraftSet(sets.find(s => s.status === 'draft') ?? null)
    })
  }, [recordType, profile.format_key])

  useEffect(() => {
    setSelectedTargetKey(compact ? null : (profile.targets[0]?.key ?? null))
    setDiagnostics([])
    setValidated(false)
    load().catch(() => setError(t('loadFailed')))
  }, [load])


  useEffect(() => {
    if (!compact && !selectedTargetKey && effectiveTargets.length > 0) {
      setSelectedTargetKey(effectiveTargets[0].key)
    }
  }, [compact, selectedTargetKey, effectiveTargets])

  async function refreshDraft(id: string) {
    const full = await exportMappingSets.get(id)
    setDraftSet(full)
    setValidated(false)
    setDiagnostics([])
    return full
  }

  async function createDraft() {
    setBusy(true)
    setError(null)
    try {
      const created = await exportMappingSets.create({
        format_key: profile.format_key,
        profile_id: profile.profile_id,
        profile_version: profile.profile_version,
        record_type: recordType,
        name: `${profile.label[lang]} (${recordType})`,
        based_on_id: publishedSet?.id ?? null,
        institution_config: publishedSet?.institution_config ?? (isLido ? { lido_events: DEFAULT_LIDO_EVENTS } : {}),
      })
      await refreshDraft(created.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function discardDraft() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      await exportMappingSets.delete(draftSet.id)
      setDraftSet(null)
      setDiagnostics([])
      setValidated(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function runValidate() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const result = await exportMappingSets.validate(draftSet.id)
      setDiagnostics(result)
      setValidated(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function publish() {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const result = await exportMappingSets.validate(draftSet.id)
      setDiagnostics(result)
      setValidated(true)
      if (result.some(d => d.level === 'error')) return
      await exportMappingSets.publish(draftSet.id, draftSet.version)
      setDraftSet(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function handleExportYaml() {
    const target = draftSet ?? publishedSet
    if (!target) return
    setBusy(true)
    setError(null)
    try {
      await exportMappingSets.exportYaml(target.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function handleImportYaml(file: File) {
    setBusy(true)
    setError(null)
    setImportStatus(null)
    try {
      const res = await exportMappingSets.importYaml(file, {
        targetSetId: draftSet?.id,
      })
      await load()
      setImportStatus({
        message: t('importYamlSuccess', { count: res.rules_count }),
        type: 'success',
        warnings: res.warnings && res.warnings.length > 0 ? res.warnings : undefined,
      })
    } catch (e) {
      setImportStatus({
        message: t('importYamlFailed', { error: e instanceof Error ? e.message : String(e) }),
        type: 'error',
      })
    } finally {
      setBusy(false)
    }
  }

  async function updateInstitutionConfig(config: Record<string, unknown>): Promise<boolean> {
    if (!draftSet) return false
    setBusy(true)
    setError(null)
    try {
      await exportMappingSets.update(draftSet.id, { institution_config: config }, draftSet.version)
      await refreshDraft(draftSet.id)
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
      return false
    } finally {
      setBusy(false)
    }
  }

  async function handleAddLidoEvent(newEvent: LidoEventConfig) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const currentConfig = (draftSet.institution_config ?? {}) as Record<string, unknown>
      const currentEvents = Array.isArray(currentConfig.lido_events)
        ? (currentConfig.lido_events as LidoEventConfig[])
        : DEFAULT_LIDO_EVENTS
      if (currentEvents.some(e => e.id === newEvent.id)) return
      const updatedEvents = [...currentEvents, newEvent]
      await exportMappingSets.update(
        draftSet.id,
        { institution_config: { ...currentConfig, lido_events: updatedEvents } },
        draftSet.version,
      )
      await refreshDraft(draftSet.id)
      setSelectedTargetKey(`lido:events/${newEvent.id}/actor`)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteLidoEvent(eventId: string) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const rulesToDelete = (draftSet.rules ?? []).filter(r => r.target_key.startsWith(`lido:events/${eventId}/`))
      for (const rule of rulesToDelete) {
        await exportMappingSets.deleteRule(draftSet.id, rule.id)
      }
      const currentDraft = await exportMappingSets.get(draftSet.id)
      const currentConfig = (currentDraft.institution_config ?? {}) as Record<string, unknown>
      const currentEvents = Array.isArray(currentConfig.lido_events)
        ? (currentConfig.lido_events as LidoEventConfig[])
        : DEFAULT_LIDO_EVENTS
      const updatedEvents = currentEvents.filter(e => e.id !== eventId)
      await exportMappingSets.update(
        currentDraft.id,
        { institution_config: { ...currentConfig, lido_events: updatedEvents } },
        currentDraft.version,
      )
      await refreshDraft(currentDraft.id)
      if (selectedTargetKey?.startsWith(`lido:events/${eventId}/`)) {
        setSelectedTargetKey(effectiveTargets[0]?.key ?? null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function handleAddModsTarget(targetKey: string) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const currentConfig = (draftSet.institution_config ?? {}) as Record<string, unknown>
      const currentElements = Array.isArray(currentConfig.mods_elements)
        ? (currentConfig.mods_elements as string[])
        : []

      let actualTargetKey = targetKey
      if (targetKey === 'mods:note') {
        const existingNoteKeys = new Set([
          ...currentElements.filter(k => k === 'mods:note' || k.startsWith('mods:note/')),
          ...((draftSet.rules ?? []).map(r => r.target_key).filter(k => k === 'mods:note' || k.startsWith('mods:note/'))),
        ])
        if (existingNoteKeys.size === 0) {
          actualTargetKey = 'mods:note'
        } else {
          actualTargetKey = `mods:note/n_${Date.now().toString(36)}`
        }
      }

      if (!currentElements.includes(actualTargetKey)) {
        const updatedElements = [...currentElements, actualTargetKey]
        await exportMappingSets.update(
          draftSet.id,
          { institution_config: { ...currentConfig, mods_elements: updatedElements } },
          draftSet.version,
        )
      }

      const existingRules = (draftSet.rules ?? []).filter(r => r.target_key === actualTargetKey)
      if (existingRules.length === 0) {
        await exportMappingSets.createRule(draftSet.id, {
          source_kind: 'field',
          target_key: actualTargetKey,
          sort_order: (draftSet.rules ?? []).length,
        })
      }

      await refreshDraft(draftSet.id)
      setSelectedTargetKey(actualTargetKey)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteModsTarget(targetKey: string) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const rulesToDelete = (draftSet.rules ?? []).filter(r => r.target_key === targetKey)
      for (const rule of rulesToDelete) {
        await exportMappingSets.deleteRule(draftSet.id, rule.id)
      }
      const currentDraft = await exportMappingSets.get(draftSet.id)
      const currentConfig = (currentDraft.institution_config ?? {}) as Record<string, unknown>
      const currentElements = Array.isArray(currentConfig.mods_elements)
        ? (currentConfig.mods_elements as string[])
        : []
      const updatedElements = currentElements.filter(k => k !== targetKey)
      await exportMappingSets.update(
        currentDraft.id,
        { institution_config: { ...currentConfig, mods_elements: updatedElements } },
        currentDraft.version,
      )
      await refreshDraft(currentDraft.id)
      if (selectedTargetKey === targetKey) {
        const remaining = effectiveTargets.filter(t => t.key !== targetKey)
        setSelectedTargetKey(remaining[0]?.key ?? null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function addRule(targetKey: string, sourceKind: SourceKind) {
    if (!draftSet) return
    setBusy(true)
    setError(null)
    try {
      const rules = draftSet.rules ?? []
      await exportMappingSets.createRule(draftSet.id, {
        source_kind: sourceKind,
        target_key: targetKey,
        sort_order: rules.length,
      })
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function updateRule(ruleId: string, patch: SourceDraft) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.updateRule(draftSet.id, ruleId, patch)
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  async function toggleRule(ruleId: string, enabled: boolean) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.updateRule(draftSet.id, ruleId, { is_enabled: enabled })
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  async function deleteRule(ruleId: string) {
    if (!draftSet) return
    setBusyRuleId(ruleId)
    setError(null)
    try {
      await exportMappingSets.deleteRule(draftSet.id, ruleId)
      await refreshDraft(draftSet.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('actionFailed'))
    } finally {
      setBusyRuleId(null)
    }
  }

  const rulesByTarget: Record<string, ExportMappingRule[]> = {}
  for (const rule of draftSet?.rules ?? []) {
    (rulesByTarget[rule.target_key] ??= []).push(rule)
    const alias = LIDO_LEGACY_TARGET_ALIAS[rule.target_key]
    if (alias && alias !== rule.target_key) {
      (rulesByTarget[alias] ??= []).push(rule)
    }
  }
  const diagnosticsByTarget: Record<string, MappingDiagnostic[]> = {}
  for (const d of diagnostics) {
    if (d.target_key) {
      (diagnosticsByTarget[d.target_key] ??= []).push(d)
      const alias = LIDO_LEGACY_TARGET_ALIAS[d.target_key]
      if (alias && alias !== d.target_key) {
        (diagnosticsByTarget[alias] ??= []).push(d)
      }
    }
  }

  const selectedTarget = effectiveTargets.find(target => target.key === selectedTargetKey)
    ?? (selectedTargetKey && LIDO_LEGACY_TARGET_ALIAS[selectedTargetKey]
        ? effectiveTargets.find(target => target.key === LIDO_LEGACY_TARGET_ALIAS[selectedTargetKey])
        : null)
    ?? null

  return (
    <div>
      <button type="button" className="btn sm gh" onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16 }}>
        <ChevL size={13} /> {t('backToOverview')}
      </button>

      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 0 }}>{profile.label[lang]}</h2>


      {error && <div role="alert" style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {importStatus && (
        <div
          role="alert"
          style={{
            padding: '10px 14px',
            borderRadius: 6,
            marginBottom: 14,
            fontSize: 13,
            background: importStatus.type === 'error' ? 'var(--bg-danger-subtle, #fee2e2)' : 'var(--bg-success-subtle, #dcfce7)',
            color: importStatus.type === 'error' ? 'var(--fg-danger, #dc2626)' : 'var(--fg-success, #166534)',
            border: `1px solid ${importStatus.type === 'error' ? '#fca5a5' : '#86efac'}`,
          }}
        >
          <div style={{ fontWeight: 600 }}>{importStatus.message}</div>
          {importStatus.warnings && importStatus.warnings.length > 0 && (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontWeight: 500, fontSize: 12 }}>{t('importYamlWarnings')}</div>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                {importStatus.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <PublishMapping
        publishedSet={publishedSet}
        draftSet={draftSet}
        busy={busy}
        canPublish={!validated || diagnostics.every(d => d.level !== 'error')}
        onCreateDraft={createDraft}
        onPublish={publish}
        onDiscardDraft={discardDraft}
        onExportYaml={handleExportYaml}
        onImportYaml={handleImportYaml}
      />

      <ExportGuidance formatKey={profile.format_key} />

      {draftSet && (
        <>
          {!compact && (
            <InstitutionConfigEditor key={draftSet.id} config={draftSet.institution_config} busy={busy} isLido={isLido} isMetsMods={isMetsMods} onSave={updateInstitutionConfig} />
          )}

          {compact ? (
            <div className="settings-card" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginTop: 0 }}>{t('compactFieldsHeadline')}</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {effectiveTargets.map(target => {
                  const rules = rulesByTarget[target.key] ?? []
                  return (
                    <div key={target.key} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-s)' }}>
                      <div style={{ width: 200, fontSize: 13, flexShrink: 0 }}>{target.label[lang]}</div>
                      <div style={{ flex: 1 }}>
                        {rules.length === 0 ? (
                          <button type="button" className="btn sm gh" disabled={busy} onClick={() => addRule(target.key, 'field')}>
                            {t('ruleAddLabel')}
                          </button>
                        ) : (
                          <SourcePicker
                            allowedKinds={target.source_kinds}
                            fields={fields}
                            acceptedFieldTypes={target.accepted_field_types}
                            editorKind={target.editor_kind}
                            disabled={busyRuleId === rules[0].id}
                            relationTypeOptions={relationTypeOptions}
                            value={{ source_kind: rules[0].source_kind, source_config: rules[0].source_config, settings: rules[0].settings }}
                            onChange={draft => updateRule(rules[0].id, draft)}
                          />
                        )}
                      </div>
                      {rules.length > 0 && (
                        <button type="button" className="btn sm ico gh" aria-label={t('ruleDeleteLabel')} title={t('ruleDeleteLabel')} disabled={busyRuleId === rules[0].id} onClick={() => deleteRule(rules[0].id)}>
                          <Trash size={13} />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <TargetNavigator
                targets={effectiveTargets}
                rulesByTarget={rulesByTarget}
                diagnosticsByTarget={diagnosticsByTarget}
                selected={selectedTargetKey}
                onSelect={setSelectedTargetKey}
                isLido={isLido}
                lidoEvents={lidoEvents}
                onAddLidoEvent={handleAddLidoEvent}
                onDeleteLidoEvent={handleDeleteLidoEvent}
                isMetsMods={isMetsMods}
                availableModsTargets={availableModsTargets}
                onAddModsTarget={handleAddModsTarget}
                onDeleteModsTarget={handleDeleteModsTarget}
              />
              <div style={{ flex: 1, minWidth: 280 }}>
                {selectedTarget && (
                  <RuleEditor
                    target={selectedTarget}
                    rules={rulesByTarget[selectedTarget.key] ?? []}
                    fields={fields}
                    diagnostics={diagnosticsByTarget[selectedTarget.key] ?? []}
                    busyRuleId={busyRuleId}
                    relationTypeOptions={relationTypeOptions}
                    onAdd={() => addRule(selectedTarget.key, selectedTarget.source_kinds[0])}
                    onUpdate={updateRule}
                    onToggle={toggleRule}
                    onDelete={deleteRule}
                    onAddAnotherNote={
                      isMetsMods && (selectedTarget.key === 'mods:note' || selectedTarget.key.startsWith('mods:note/'))
                        ? () => handleAddModsTarget('mods:note')
                        : undefined
                    }
                  />
                )}
              </div>
            </div>
          )}

          <ValidationPanel
            diagnostics={diagnostics}
            validated={validated}
            validating={busy}
            onValidate={runValidate}
            onJump={key => setSelectedTargetKey(LIDO_LEGACY_TARGET_ALIAS[key] ?? key)}
          />

          <ExportPreview recordType={recordType} mappingSetId={draftSet.id} formatKey={profile.format_key} />
        </>
      )}
    </div>
  )
}
