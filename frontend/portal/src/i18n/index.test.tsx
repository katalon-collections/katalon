// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { setLocale, setTerminology, useI18n } from '.'

function NavLabel() {
  const { t } = useI18n()
  return <span data-testid="nav">{t('nav.objects')}</span>
}

describe('terminology overrides', () => {
  beforeEach(() => setLocale('de'))
  afterEach(() => {
    act(() => setTerminology(undefined))
    cleanup()
  })

  it('re-renders already mounted components when terminology arrives', () => {
    render(<NavLabel />)
    expect(screen.getByTestId('nav').textContent).toBe('Objekte')

    // Portal config resolves after the header has mounted (no locale change).
    act(() => setTerminology({ object: { plural: { de: 'Postkarten', en: 'Postcards' } } }))

    expect(screen.getByTestId('nav').textContent).toBe('Postkarten')
  })

  it('falls back to the default label when the override is cleared', () => {
    act(() => setTerminology({ object: { plural: { de: 'Postkarten' } } }))
    render(<NavLabel />)
    expect(screen.getByTestId('nav').textContent).toBe('Postkarten')

    act(() => setTerminology(undefined))

    expect(screen.getByTestId('nav').textContent).toBe('Objekte')
  })
})
