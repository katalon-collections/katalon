// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '../../i18n'
import { ScreenForm } from './ScreenForm'
import { objects, schema, subtypes } from '../../api/client'
import type { FieldDefinition } from '../../types'

vi.mock('../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))
vi.mock('../../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    getTokenUser: () => ({ role: 'admin', features: [] }),
    subtypes: { list: vi.fn().mockResolvedValue([]) },
    schema: { list: vi.fn() },
    formVariants: { list: vi.fn().mockResolvedValue([]) },
    formSections: { list: vi.fn().mockResolvedValue([]) },
    vocabularies: {
      list: vi.fn().mockResolvedValue([]),
      listTerms: vi.fn().mockResolvedValue([]),
      searchTerms: vi.fn().mockResolvedValue([]),
      ancestors: vi.fn().mockResolvedValue([]),
      tree: vi.fn().mockResolvedValue([]),
    },
    idno: { next: vi.fn().mockResolvedValue({ next: 'OBJ-1' }) },
    collections: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
    storageLocations: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
    objects: {
      ...actual.objects,
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      snapshots: { list: vi.fn().mockResolvedValue([]) },
    },
    relations: { list: vi.fn().mockResolvedValue([]) },
    locks: { get: vi.fn().mockResolvedValue(null) },
    workingSets: { list: vi.fn().mockResolvedValue([]) },
    media: { list: vi.fn().mockResolvedValue([]) },
    presence: { heartbeat: vi.fn().mockResolvedValue([]), release: vi.fn().mockResolvedValue(undefined) },
  }
})

function field(overrides: Partial<FieldDefinition> & Pick<FieldDefinition, 'id' | 'name' | 'field_type'>): FieldDefinition {
  return {
    target_type: 'object',
    target_subtype: null,
    label: { de: overrides.name },
    help_text: {},
    is_required: false,
    is_repeatable: false,
    is_translatable: false,
    is_public: true,
    is_searchable: true,
    is_facet: false,
    show_in_detail: true,
    show_in_list: false,
    sort_order: 0,
    settings: {},
    ...overrides,
  }
}

const SAMPLE_FIELDS: FieldDefinition[] = [
  field({ id: 'f-idno', name: 'idno', field_type: 'text', label: { de: 'Inventarnummer' }, is_required: true }),
  field({ id: 'f-label', name: 'label', field_type: 'text', label: { de: 'Bezeichnung' }, is_required: true }),
  field({ id: 'f-title', name: 'title', field_type: 'text', label: { de: 'Titel' }, is_required: true }),
  field({ id: 'f-tr', name: 'subtitle', field_type: 'text', label: { de: 'Untertitel' }, is_translatable: true }),
  field({ id: 'f-date', name: 'created_date', field_type: 'date', label: { de: 'Datierung' } }),
  field({ id: 'f-num', name: 'height', field_type: 'number', label: { de: 'Höhe' } }),
  field({ id: 'f-vocab', name: 'material', field_type: 'vocab', label: { de: 'Material' }, settings: { vocabulary_id: 'v-1' } }),
  field({ id: 'f-vfree', name: 'technique', field_type: 'vocab_free', label: { de: 'Technik' }, settings: { vocabulary_id: 'v-1' } }),
  field({ id: 'f-auth', name: 'subject_gnd', field_type: 'authority', label: { de: 'Schlagwort' }, settings: { source: 'gnd' } }),
  field({ id: 'f-rel', name: 'creator', field_type: 'relation', label: { de: 'Urheber' }, settings: { target_type: 'entity', fixed_relation_type: 'created_by' } }),
  field({ id: 'f-url', name: 'homepage', field_type: 'url', label: { de: 'Webseite' } }),
  field({ id: 'f-rep', name: 'keywords', field_type: 'text', label: { de: 'Stichwörter' }, is_repeatable: true }),
  field({
    id: 'f-group',
    name: 'dimensions',
    field_type: 'group',
    label: { de: 'Maße' },
    children: [
      field({ id: 'sf-val', name: 'measure_val', field_type: 'number', label: { de: 'Messwert' } }),
      field({ id: 'sf-unit', name: 'measure_unit', field_type: 'text', label: { de: 'Einheit' } }),
    ],
  }),
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(subtypes.list).mockResolvedValue([])
  vi.mocked(schema.list).mockResolvedValue(SAMPLE_FIELDS)
})

describe('ScreenForm label accessibility', () => {
  it('programmatically associates labels with inputs across all field types', async () => {
    const { container } = render(<ScreenForm recordType="object" recordId="new" onBack={vi.fn()} />)

    expect(await screen.findByLabelText(/Inventarnummer/)).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText(/Bezeichnung/)).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Bestandsstatus')).toBeInstanceOf(HTMLSelectElement)
    expect(screen.getByLabelText(/Titel/)).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText(/Untertitel/)).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Datierung')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Höhe')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Material')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Technik')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByRole('combobox', { name: /Schlagwort/ })).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Urheber')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Webseite')).toBeInstanceOf(HTMLInputElement)

    const allIds = Array.from(container.querySelectorAll('[id]')).map(el => el.id)
    expect(new Set(allIds).size).toBe(allIds.length)
  })

  it('assigns unique ids and programmatic labels for repeatable fields and repeatable groups', async () => {
    vi.mocked(objects.get).mockResolvedValue({
      id: 'obj-1',
      idno: 'OBJ-1',
      status: 'draft',
      version: 1,
      collection_status: 'active',
      object_type: null,
      ai_provenance: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      metadata_: {
        keywords: ['eins', 'zwei'],
        dimensions: [
          { measure_val: 10, measure_unit: 'cm' },
          { measure_val: 20, measure_unit: 'mm' },
        ],
      },
    })

    const { container } = render(<ScreenForm recordType="object" recordId="obj-1" onBack={vi.fn()} />)

    await waitFor(() => expect(screen.getAllByLabelText('Messwert')).toHaveLength(2))
    const measureInputs = screen.getAllByLabelText('Messwert') as HTMLInputElement[]
    expect(measureInputs[0].value).toBe('10')
    expect(measureInputs[1].value).toBe('20')
    expect(measureInputs[0].id).not.toBe(measureInputs[1].id)

    const unitInputs = screen.getAllByLabelText('Einheit') as HTMLInputElement[]
    expect(unitInputs).toHaveLength(2)
    expect(unitInputs[0].id).not.toBe(unitInputs[1].id)

    const keywordInputs = screen.getAllByLabelText('Stichwörter') as HTMLInputElement[]
    expect(keywordInputs).toHaveLength(2)
    expect(keywordInputs[0].id).not.toBe(keywordInputs[1].id)

    const allIds = Array.from(container.querySelectorAll('[id]')).map(el => el.id)
    expect(new Set(allIds).size).toBe(allIds.length)
  })

  it('keeps ids unique when two ScreenForm instances render simultaneously', async () => {
    const { container } = render(
      <>
        <ScreenForm recordType="object" recordId="new" onBack={vi.fn()} />
        <ScreenForm recordType="object" recordId="new" quickCreate onBack={vi.fn()} />
      </>,
    )

    await waitFor(() => expect(screen.getAllByLabelText(/Titel/)).toHaveLength(2))
    const titleInputs = screen.getAllByLabelText(/Titel/) as HTMLInputElement[]
    expect(titleInputs[0].id).not.toBe(titleInputs[1].id)

    fireEvent.click(screen.getAllByRole('button', { name: '+ EN' })[0])
    const controlAndLabelIds = Array.from(container.querySelectorAll('input[id], select[id], textarea[id], label[id]')).map(el => el.id)
    expect(controlAndLabelIds.length).toBeGreaterThan(0)
    expect(new Set(controlAndLabelIds).size).toBe(controlAndLabelIds.length)
  })
})
