// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '../../i18n'
import { ScreenForm } from './ScreenForm'
import { entities, schema, subtypes } from '../../api/client'
import type { RecordSubtype } from '../../types'

vi.mock('../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))
vi.mock('../../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual, getTokenUser: () => ({ role: 'admin', features: [] }),
    subtypes: { list: vi.fn() }, schema: { list: vi.fn().mockResolvedValue([]) },
    formVariants: { list: vi.fn().mockResolvedValue([]) }, formSections: { list: vi.fn().mockResolvedValue([]) },
    vocabularies: { list: vi.fn().mockResolvedValue([]) }, idno: { next: vi.fn().mockResolvedValue({ next: 'ENT-1' }) },
    entities: { ...actual.entities, get: vi.fn(), create: vi.fn().mockResolvedValue({ id: 'created', version: 1 }), snapshots: { list: vi.fn().mockResolvedValue([]) } },
    relations: { list: vi.fn().mockResolvedValue([]) }, locks: { get: vi.fn().mockResolvedValue(null) }, workingSets: { list: vi.fn().mockResolvedValue([]) },
  }
})
function subtype(name: string, is_default = false): RecordSubtype {
  return { id: name, primary_type: 'entity', name, label: { de: name }, description: '', sort_order: 0, is_default, placeholder_image_url: '' }
}
function openForm(props: Partial<React.ComponentProps<typeof ScreenForm>> = {}) {
  return render(<ScreenForm recordType="entity" quickCreate onBack={vi.fn()} {...props} />)
}
const saveButton = () => screen.getByRole('button', { name: 'Entwurf anlegen und verknüpfen' })
const subtypeInput = () => screen.getByLabelText(/Entitätstyp/) as HTMLSelectElement
beforeEach(() => { vi.clearAllMocks(); vi.mocked(subtypes.list).mockResolvedValue([]) })
describe('new record subtype selection', () => {
  it('preselects the only subtype and loads its schema without a configured default', async () => {
    vi.mocked(subtypes.list).mockResolvedValue([subtype('person')]); openForm()
    await waitFor(() => expect(subtypeInput().value).toBe('person'))
    expect(subtypeInput().required).toBe(true)
    expect(schema.list).toHaveBeenCalledWith('entity', 'person')
    fireEvent.click(saveButton())
    await waitFor(() => expect(entities.create).toHaveBeenCalledWith(expect.objectContaining({ entity_type: 'person' })))
  })
  it('requires a choice among multiple subtypes even for a draft', async () => {
    vi.mocked(subtypes.list).mockResolvedValue([subtype('person'), subtype('organization')]); openForm()
    await waitFor(() => expect(subtypeInput().value).toBe(''))
    fireEvent.click(saveButton())
    expect(await screen.findAllByText('Bitte einen Subtyp auswählen.')).toHaveLength(2)
    expect(entities.create).not.toHaveBeenCalled()
    fireEvent.change(subtypeInput(), { target: { value: 'organization' } }); fireEvent.click(saveButton())
    await waitFor(() => expect(entities.create).toHaveBeenCalledWith(expect.objectContaining({ entity_type: 'organization' })))
  })
  it('preserves the configured default among multiple subtypes', async () => {
    vi.mocked(subtypes.list).mockResolvedValue([subtype('person'), subtype('organization', true)]); openForm()
    await waitFor(() => expect(subtypeInput().value).toBe('organization'))
  })
  it('preserves an explicitly constrained relation subtype', async () => {
    vi.mocked(subtypes.list).mockResolvedValue([subtype('person', true), subtype('organization')]); openForm({ initialSubtype: 'organization', lockSubtype: true })
    await waitFor(() => expect(subtypeInput().value).toBe('organization'))
    expect(subtypeInput().disabled).toBe(true)
  })
  it('allows creation without a subtype when none are configured', async () => {
    openForm(); await screen.findByRole('button', { name: 'Entwurf anlegen und verknüpfen' })
    expect(screen.queryByLabelText(/Entitätstyp/)).toBeNull(); fireEvent.click(saveButton())
    await waitFor(() => expect(entities.create).toHaveBeenCalled())
  })
  it('does not let a failed subtype request bypass selection', async () => {
    vi.mocked(subtypes.list).mockRejectedValue(new Error('Subtype list unavailable')); openForm()
    await screen.findByText('Subtype list unavailable')
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
  })
  it('keeps an existing record without a subtype unchanged', async () => {
    vi.mocked(subtypes.list).mockResolvedValue([subtype('person', true)])
    vi.mocked(entities.get).mockResolvedValue({ id: 'existing', idno: 'ENT-1', metadata_: {}, version: 1, status: 'draft', entity_type: '', ai_provenance: {}, created_at: '', updated_at: '' })
    openForm({ recordId: 'existing' }); await waitFor(() => expect(subtypeInput().value).toBe(''))
    expect(subtypeInput().required).toBe(false); expect(schema.list).toHaveBeenCalledWith('entity', undefined)
  })
})
