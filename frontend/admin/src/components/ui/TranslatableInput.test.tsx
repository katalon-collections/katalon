// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import i18n from '../../i18n'
import { TranslatableInput } from './TranslatableInput'

function Input() {
  const [value, setValue] = useState<Record<string, string>>({ de: 'Bild' })
  return <TranslatableInput languages={['de', 'en']} value={value}
    labels={{ de: 'Titel', en: 'Title' }}
    onChange={(lang, text) => setValue(previous => ({ ...previous, [lang]: text }))}
    onRemove={lang => setValue(previous => ({ ...previous, [lang]: '' }))} />
}

beforeEach(async () => { await i18n.changeLanguage('de') })

describe('TranslatableInput', () => {
  it('adds, edits and removes a translation without changing the primary text', async () => {
    const user = userEvent.setup()
    render(<Input />)
    expect(screen.queryByPlaceholderText('Title')).toBeNull()
    await user.click(screen.getByRole('button', { name: '+ EN' }))
    await user.type(screen.getByPlaceholderText('Title'), 'Picture')
    expect((screen.getByPlaceholderText('Title') as HTMLInputElement).value).toBe('Picture')
    await user.click(screen.getByRole('button', { name: 'EN entfernen' }))
    expect(screen.queryByPlaceholderText('Title')).toBeNull()
    expect((screen.getByPlaceholderText('Titel') as HTMLInputElement).value).toBe('Bild')
  })

  it('uses English labels for language controls', async () => {
    await i18n.changeLanguage('en')
    const user = userEvent.setup()
    render(<Input />)
    await user.click(screen.getByRole('button', { name: '+ EN' }))
    expect(screen.getByRole('button', { name: 'Remove EN' })).toBeTruthy()
  })
})
