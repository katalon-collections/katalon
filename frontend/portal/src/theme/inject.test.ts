// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { applyTheme, themeScriptSrc } from './inject'

describe('theme script', () => {
  it('builds the URL inside the theme directory only', () => {
    expect(themeScriptSrc({ name: 'BPK', directory: 'bpk', script: 'custom.js' })).toBe('/themes/bpk/custom.js')
    expect(themeScriptSrc({ name: 'BPK', directory: 'bpk', script: '../x.js' })).toBeNull()
    expect(themeScriptSrc({ name: 'BPK', directory: 'bpk', script: 'https://cdn.example/x.js' })).toBeNull()
    expect(themeScriptSrc({ name: 'BPK', directory: '../etc', script: 'x.js' })).toBeNull()
    expect(themeScriptSrc({ name: 'BPK', script: 'x.js' })).toBeNull()
  })

  it('adds the script once, deferred', () => {
    const theme = { name: 'BPK', directory: 'bpk', script: 'custom.js' }
    applyTheme(theme)
    applyTheme(theme)
    const scripts = document.querySelectorAll('script[data-theme-script]')
    expect(scripts).toHaveLength(1)
    expect((scripts[0] as HTMLScriptElement).defer).toBe(true)
    expect(scripts[0].getAttribute('src')).toBe('/themes/bpk/custom.js')
  })
})
