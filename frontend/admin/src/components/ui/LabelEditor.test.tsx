// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LabelEditor } from './LabelEditor'

describe('LabelEditor accessibility', () => {
  it('links each language label programmatically to its input with unique ids', () => {
    const { container } = render(
      <>
        <LabelEditor languages={['de', 'en']} value={{ de: 'Titel', en: 'Title' }} onChange={vi.fn()} labelPrefix="Label" />
        <LabelEditor languages={['de', 'en']} value={{ de: 'Hilfe', en: 'Help' }} onChange={vi.fn()} labelPrefix="Hilfetext" />
      </>,
    )

    const labelDe = screen.getByLabelText('Label DE') as HTMLInputElement
    const labelEn = screen.getByLabelText('Label EN') as HTMLInputElement
    const helpDe = screen.getByLabelText('Hilfetext DE') as HTMLInputElement
    const helpEn = screen.getByLabelText('Hilfetext EN') as HTMLInputElement

    expect(labelDe.value).toBe('Titel')
    expect(labelEn.value).toBe('Title')
    expect(helpDe.value).toBe('Hilfe')
    expect(helpEn.value).toBe('Help')

    const ids = Array.from(container.querySelectorAll('[id]')).map(el => el.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
