// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

interface LabelEditorProps {
  languages: string[]
  value: Record<string, string>
  onChange: (lang: string, val: string) => void
  labelPrefix?: string
}

/** Renders one input per configured language (wrap in a `.fg-*` grid container). */
export function LabelEditor({ languages, value, onChange, labelPrefix = 'Label' }: LabelEditorProps) {
  return (
    <>
      {languages.map(lang => (
        <div className="field" key={lang}>
          <div className="lbl">{labelPrefix} {lang.toUpperCase()}</div>
          <input
            className="fld"
            value={value[lang] ?? ''}
            onChange={e => onChange(lang, e.target.value)}
          />
        </div>
      ))}
    </>
  )
}
