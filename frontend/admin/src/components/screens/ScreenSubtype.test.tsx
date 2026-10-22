// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '../../i18n'
import { subtypes } from '../../api/client'
import { ScreenSubtype } from './ScreenSubtype'

vi.mock('../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))
vi.mock('../../api/client', async importOriginal => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  authority: { list: vi.fn().mockResolvedValue([]) },
  subtypes: { list: vi.fn().mockResolvedValue([]), create: vi.fn().mockResolvedValue({ id: 'new' }) },
}))
beforeEach(() => vi.clearAllMocks())

async function newSubtype() {
  const { container } = render(<ScreenSubtype />)
  fireEvent.click(await screen.findByRole('button', { name: 'Neuer Subtyp' }))
  return {
    germanLabel: screen.getAllByRole('textbox')[0],
    name: container.querySelector('input.mono') as HTMLInputElement,
  }
}
it('generates and persists an umlaut-safe slug, preserving a deliberate override', async () => {
  const { germanLabel, name } = await newSubtype()
  fireEvent.change(germanLabel, { target: { value: 'Öl-Gemälde' } })
  expect(name.value).toBe('oel_gemaelde')
  fireEvent.change(name, { target: { value: 'painting' } })
  fireEvent.change(germanLabel, { target: { value: 'Ölgemälde' } })
  expect(name.value).toBe('painting')
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  await waitFor(() => expect(subtypes.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'painting', label: { de: 'Ölgemälde' } })))
})
it('rejects whitespace-only internal names before sending a request', async () => {
  const { name } = await newSubtype()
  fireEvent.change(name, { target: { value: '   ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  expect(screen.getByText('Interner Name ist erforderlich.')).toBeTruthy()
  expect(subtypes.create).not.toHaveBeenCalled()
})
