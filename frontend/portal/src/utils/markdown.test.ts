// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('renders markdown', () => {
    const html = renderMarkdown('## Titel\n\nEin [Link](https://example.org) und **fett**.')
    expect(html).toContain('<h2')
    expect(html).toContain('<a href="https://example.org">Link</a>')
    expect(html).toContain('<strong>fett</strong>')
  })

  it('strips scripts and event handlers', () => {
    const html = renderMarkdown('<script>alert(1)</script><img src="x" onerror="alert(1)">')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('onerror')
  })

  it('keeps paragraphs and, with breaks, single line breaks of plain text', () => {
    const html = renderMarkdown('Zeile eins\nZeile zwei\n\nAbsatz zwei', { breaks: true })
    expect(html).toContain('Zeile eins<br>')
    expect(html.match(/<p>/g)).toHaveLength(2)
  })
})
