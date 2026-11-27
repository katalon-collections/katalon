// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useId } from 'react'

interface LabelEditorProps {
  languages: string[]
  value: Record<string, string>
  onChange: (lang: string, val: string) => void
  labelPrefix?: string
}

/** Renders one input per configured language (wrap in a `.fg-*` grid container). */
export function LabelEditor({ languages, value, onChange, labelPrefix = 'Label' }: LabelEditorProps) {
  const idPrefix = useId()
  return (
    <>
      {languages.map(lang => {
        const inputId = `${idPrefix}-${lang}`
        return (
          <div className="field" key={lang}>
            <label className="lbl" htmlFor={inputId}>{labelPrefix} {lang.toUpperCase()}</label>
            <input
              id={inputId}
              className="fld"
              value={value[lang] ?? ''}
              onChange={e => onChange(lang, e.target.value)}
            />
          </div>
        )
      })}
    </>
  )
}
