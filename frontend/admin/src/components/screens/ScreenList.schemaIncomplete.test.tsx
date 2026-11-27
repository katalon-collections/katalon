// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '../../i18n'
import { ScreenList } from './ScreenList'
import { ScreenForm } from './ScreenForm'
import { objects, schema } from '../../api/client'
import type { FieldDefinition, KatalonObject } from '../../types'

vi.mock('../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))
vi.mock('../../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    getTokenUser: () => ({ email: 'admin@example.org', role: 'admin', features: [] }),
    objects: {
      ...actual.objects,
      list: vi.fn(),
      get: vi.fn(),
      update: vi.fn(),
      snapshots: { list: vi.fn().mockResolvedValue([]) },
    },
    collections: { ...actual.collections, list: vi.fn().mockResolvedValue({ total: 0, page: 1, page_size: 100, items: [] }) },
    subtypes: { list: vi.fn().mockResolvedValue([]) },
    schema: { list: vi.fn().mockResolvedValue([]) },
    formVariants: { list: vi.fn().mockResolvedValue([]) },
    formSections: { list: vi.fn().mockResolvedValue([]) },
    vocabularies: { list: vi.fn().mockResolvedValue([]) },
    idno: { next: vi.fn().mockResolvedValue({ next: 'OBJ-1' }) },
    relations: { list: vi.fn().mockResolvedValue([]) },
    media: { list: vi.fn().mockResolvedValue([]) },
    locks: { get: vi.fn().mockResolvedValue(null), batch: vi.fn().mockResolvedValue({}) },
    presence: {
      batch: vi.fn().mockResolvedValue({}),
      heartbeat: vi.fn().mockResolvedValue({ others: [] }),
      release: vi.fn().mockResolvedValue(undefined),
    },
    users: { ...actual.users, recordPermissions: vi.fn().mockResolvedValue([]) },
    workingSets: {
      list: vi.fn().mockResolvedValue([]),
      forRecord: vi.fn().mockResolvedValue([]),
    },
    exportApi: { formats: vi.fn().mockResolvedValue([]) },
  }
})

function makeObject(overrides: Partial<KatalonObject> = {}): KatalonObject {
  return {
    id: 'obj-1',
    idno: 'OBJ-1',
    object_type: null,
    collection_status: 'active',
    status: 'internal',
    schema_incomplete: false,
    metadata_: { label: 'Beispielobjekt' },
    ai_provenance: {},
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    version: 1,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(schema.list).mockResolvedValue([])
})

describe('schema_incomplete admin UI', () => {
  it('shows the marker in ScreenList and filters via schema_incomplete=true', async () => {
    vi.mocked(objects.list).mockResolvedValue({
      total: 2,
      page: 1,
      page_size: 50,
      items: [
        makeObject({ id: 'obj-inc', idno: 'OBJ-INC', schema_incomplete: true, metadata_: { label: 'Unvollständig' } }),
        makeObject({ id: 'obj-ok', idno: 'OBJ-OK', schema_incomplete: false, metadata_: { label: 'Vollständig' } }),
      ],
    })

    render(<ScreenList recordType="object" />)

    await waitFor(() => expect(screen.getByText('Unvollständig')).toBeTruthy())
    expect(screen.getAllByText('Schema unvollständig')).toHaveLength(2) // filter button + one row badge

    const filterBtn = screen.getByRole('button', { name: 'Schema unvollständig' })
    expect(filterBtn.getAttribute('aria-pressed')).toBe('false')

    fireEvent.click(filterBtn)
    await waitFor(() =>
      expect(objects.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ schema_incomplete: true }),
      ),
    )
    expect(filterBtn.getAttribute('aria-pressed')).toBe('true')
  })

  it('shows the notice in ScreenForm and clears it after saving missing required fields', async () => {
    const requiredField: FieldDefinition = {
      id: 'f-rights',
      target_type: 'object',
      target_subtype: null,
      name: 'rights',
      label: { de: 'Rechte', en: 'Rights' },
      field_type: 'text',
      is_required: true,
      is_repeatable: false,
      is_translatable: false,
      sort_order: 1,
      settings: {},
      show_in_detail: true,
      show_in_list: false,
      is_facet: false,
      is_searchable: true,
    }
    vi.mocked(schema.list).mockResolvedValue([requiredField])
    vi.mocked(objects.get).mockResolvedValue(
      makeObject({ id: 'obj-inc', idno: 'OBJ-INC', schema_incomplete: true, metadata_: {} }),
    )
    vi.mocked(objects.update).mockResolvedValue(
      makeObject({
        id: 'obj-inc',
        idno: 'OBJ-INC',
        schema_incomplete: false,
        metadata_: { rights: 'CC0' },
        version: 2,
      }),
    )

    render(<ScreenForm recordType="object" recordId="obj-inc" />)

    expect(await screen.findByText(/Schema unvollständig:/)).toBeTruthy()

    const rightsLabel = await screen.findByText(/^Rechte/)
    const rightsInput = rightsLabel.closest('.field')?.querySelector('input')
    expect(rightsInput).toBeTruthy()
    fireEvent.change(rightsInput!, { target: { value: 'CC0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => expect(objects.update).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText(/Schema unvollständig:/)).toBeNull())
  })
})
