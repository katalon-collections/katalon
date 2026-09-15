// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { Lightning, X } from './Icons'
import { RichTextEditor } from './RichTextEditor'

interface TranslatableInputProps {
  languages: string[]
  value: Record<string, string>
  onChange: (lang: string, val: string) => void
  onRemove?: (lang: string) => void
  richtext?: boolean
  /** Per-language placeholder (e.g. the field label in that language). */
  labels?: Record<string, string>
  placeholder?: string
  disabled?: boolean
  style?: CSSProperties
  translationEnabled?: boolean
  translationDisabled?: boolean
  translationBusyLanguage?: string | null
  onTranslate?: (sourceLanguage: string, targetLanguage: string) => void
  aiProvenance?: Record<string, { model: string; at: string }>
  provenancePrefix?: string
}

const LANG_TAG: CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  color: 'var(--fg-3)',
  minWidth: 24,
  lineHeight: '32px',
}

/** Primary language input always visible, "+ XY" buttons inline; added languages get a remove button. */
export function TranslatableInput({
  languages,
  value,
  onChange,
  onRemove,
  richtext,
  labels,
  placeholder,
  disabled,
  style,
  translationEnabled,
  translationDisabled,
  translationBusyLanguage,
  onTranslate,
  aiProvenance,
  provenancePrefix,
}: TranslatableInputProps) {
  const { t } = useTranslation('translatableInput')
  // A field's value can still be a legacy plain string here (e.g. a soft-deleted
  // record was excluded from the backend's is_translatable migration and later
  // restored, see #399) — never index a string by language key, show it under the
  // primary language instead of silently rendering an empty row.
  const primary = languages[0]
  const safeValue: Record<string, string> =
    value && typeof value === 'object' && !Array.isArray(value)
      ? value
      : typeof value === 'string' && value
        ? { [primary]: value }
        : {}
  const [expanded, setExpanded] = useState<string[]>([])
  const [translationSources, setTranslationSources] = useState<Record<string, string>>({})

  const shown = (lang: string) =>
    lang === primary || expanded.includes(lang) || (safeValue[lang] ?? '').trim() !== ''
  const hidden = languages.slice(1).filter(lang => !shown(lang))
  const visibleExtra = languages.slice(1).filter(shown)

  const field = (lang: string) => {
    const ph = labels?.[lang] ?? placeholder
    return richtext ? (
      <RichTextEditor value={safeValue[lang] ?? ''} onChange={v => onChange(lang, v)} placeholder={ph} disabled={disabled} style={{ flex: 1, ...style }} toolbarEnd={translationAction(lang)} />
    ) : (
      <input className="fld" value={safeValue[lang] ?? ''} onChange={e => onChange(lang, e.target.value)} placeholder={ph} disabled={disabled} style={{ flex: 1, ...style }} />
    )
  }

  const remove = (lang: string) => {
    setExpanded(prev => prev.filter(l => l !== lang))
    onRemove?.(lang)
  }

  const translationAction = (targetLanguage: string) => {
    const sources = languages.filter(lang => lang !== targetLanguage && (safeValue[lang] ?? '').trim() !== '')
    const translate = onTranslate
    if (!translationEnabled || !translate) return null
    const sourceLanguage = sources.includes(translationSources[targetLanguage])
      ? translationSources[targetLanguage]
      : (sources[0] ?? '')
    const busy = translationBusyLanguage === targetLanguage
    const hasTargetValue = (safeValue[targetLanguage] ?? '').trim() !== ''
    const noSource = sources.length === 0
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {sources.length > 1 && (
          <select
            className="fld"
            value={sourceLanguage}
            onChange={event => setTranslationSources(prev => ({ ...prev, [targetLanguage]: event.target.value }))}
            disabled={Boolean(translationDisabled)}
            aria-label={t('translationSource', { target: targetLanguage.toUpperCase() })}
            style={{ height: 24, padding: '0 4px', fontSize: 11 }}
          >
            {sources.map(lang => <option key={lang} value={lang}>{t('translationFromOption', { lang: lang.toUpperCase() })}</option>)}
          </select>
        )}
        <button
          type="button"
          className="btn sm gh"
          style={{ height: 24, padding: '2px 8px' }}
          onClick={() => translate(sourceLanguage, targetLanguage)}
          disabled={Boolean(translationDisabled) || noSource}
          title={noSource ? t('translationNoSource') : undefined}
        >
          <Lightning size={12} />
          {busy
            ? t('translationRunning')
            : noSource
              ? t('createTranslation')
              : hasTargetValue
                ? t('updateTranslation')
                : sources.length === 1
                  ? t('translateFrom', { lang: sourceLanguage.toUpperCase() })
                  : t('createTranslation')}
        </button>
      </span>
    )
  }

  const provenance = (lang: string) => {
    const entry = aiProvenance?.[provenancePrefix ? `${provenancePrefix}.${lang}` : lang]
    return entry ? (
      <span className="h" title={t('aiGeneratedTitle', { model: entry.model, at: new Date(entry.at).toLocaleString() })} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: 'var(--accent-ink)' }}>
        <Lightning size={11} /> KI
      </span>
    ) : null
  }

  const row = (lang: string, removable: boolean) => (
    <div key={lang} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: lang === primary ? 0 : 6 }}>
      <span style={LANG_TAG}>{lang}</span>
      {provenance(lang)}
      {field(lang)}
      {!richtext && translationAction(lang)}
      {removable && onRemove && (
        <button type="button" className="btn sm ico gh" onClick={() => remove(lang)} disabled={disabled} aria-label={t('removeLang', { lang: lang.toUpperCase() })} title={t('removeLang', { lang: lang.toUpperCase() })}>
          <X size={12} />
        </button>
      )}
    </div>
  )

  return (
    <div>
      {row(primary, false)}
      {hidden.map(lang => (
        <button key={lang} type="button" className="btn sm gh" disabled={disabled} onClick={() => setExpanded(prev => [...prev, lang])} style={{ marginTop: 6, marginLeft: 32 }}>
          + {lang.toUpperCase()}
        </button>
      ))}
      {visibleExtra.map(lang => row(lang, true))}
    </div>
  )
}
