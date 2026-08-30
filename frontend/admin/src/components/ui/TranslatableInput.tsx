import { useState, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { X } from './Icons'
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
}: TranslatableInputProps) {
  const { t } = useTranslation('translatableInput')
  const primary = languages[0]
  const [expanded, setExpanded] = useState<string[]>([])

  const shown = (lang: string) =>
    lang === primary || expanded.includes(lang) || (value[lang] ?? '').trim() !== ''
  const hidden = languages.slice(1).filter(lang => !shown(lang))
  const visibleExtra = languages.slice(1).filter(shown)

  const field = (lang: string) => {
    const ph = labels?.[lang] ?? placeholder
    return richtext ? (
      <RichTextEditor value={value[lang] ?? ''} onChange={v => onChange(lang, v)} placeholder={ph} disabled={disabled} style={{ flex: 1, ...style }} />
    ) : (
      <input className="fld" value={value[lang] ?? ''} onChange={e => onChange(lang, e.target.value)} placeholder={ph} disabled={disabled} style={{ flex: 1, ...style }} />
    )
  }

  const remove = (lang: string) => {
    setExpanded(prev => prev.filter(l => l !== lang))
    onRemove?.(lang)
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span style={LANG_TAG}>{primary}</span>
        {field(primary)}
        {hidden.map(lang => (
          <button key={lang} type="button" className="btn sm gh" disabled={disabled} onClick={() => setExpanded(prev => [...prev, lang])}>
            + {lang.toUpperCase()}
          </button>
        ))}
      </div>
      {visibleExtra.map(lang => (
        <div key={lang} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 6 }}>
          <span style={LANG_TAG}>{lang}</span>
          {field(lang)}
          {onRemove && (
            <button type="button" className="btn sm ico gh" onClick={() => remove(lang)} disabled={disabled} aria-label={t('removeLang', { lang: lang.toUpperCase() })} title={t('removeLang', { lang: lang.toUpperCase() })}>
              <X size={12} />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
