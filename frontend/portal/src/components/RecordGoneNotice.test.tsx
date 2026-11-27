// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, render, screen } from '@testing-library/react'
import { HelmetProvider } from 'react-helmet-async'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { setLocale } from '../i18n'

const { RecordGoneNotice } = await import('./RecordGoneNotice')

function renderNotice() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <RecordGoneNotice />
      </MemoryRouter>
    </HelmetProvider>,
  )
}

describe('RecordGoneNotice', () => {
  beforeEach(() => { act(() => setLocale('de')) })
  afterEach(cleanup)

  it('renders the localized withdrawal notice with links back', () => {
    renderNotice()
    expect(screen.getByRole('heading', { level: 1, name: 'Datensatz zurückgezogen' })).toBeTruthy()
    expect(screen.getByText(/nicht mehr öffentlich verfügbar/i)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Zur Startseite' }).getAttribute('href')).toBe('/')
    expect(screen.getByRole('link', { name: 'Sammlung durchsuchen' }).getAttribute('href')).toBe('/search?q=')
  })

  it('switches the built-in text with the locale', () => {
    act(() => setLocale('en'))
    renderNotice()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBeTruthy()
  })
})
