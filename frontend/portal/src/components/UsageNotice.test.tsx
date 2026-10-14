// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PortalConfig } from '../api/client'
import { setLocale } from '../i18n'

let config: Partial<PortalConfig> = {}
vi.mock('../hooks/usePortalConfig', () => ({ usePortalConfig: () => config }))
const { UsageNotice, noticeStorageKey } = await import('./UsageNotice')

const notice = { enabled: true, version: 3, title: { de: 'Hinweis' }, text: { de: 'Historische Inhalte' }, accept_label: { de: 'Verstanden' } }

describe('UsageNotice', () => {
  beforeEach(() => { localStorage.clear(); act(() => setLocale('de')) })
  afterEach(cleanup)

  it('shows an accessible dialog once and remembers the version', () => {
    config = { notice }
    const { unmount } = render(<UsageNotice />)
    const dialog = screen.getByRole('dialog', { name: 'Hinweis' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    const button = screen.getByRole('button', { name: 'Verstanden' })
    expect(document.activeElement).toBe(button)

    fireEvent.click(button)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(localStorage.getItem(noticeStorageKey(3))).toBe('1')
    unmount()

    render(<UsageNotice />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows again for a new version and not when disabled', () => {
    localStorage.setItem(noticeStorageKey(2), '1')
    config = { notice }
    const { unmount } = render(<UsageNotice />)
    expect(screen.getByRole('dialog')).toBeTruthy()
    unmount()

    config = { notice: { ...notice, enabled: false } }
    render(<UsageNotice />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
