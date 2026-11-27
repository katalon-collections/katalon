// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import '../../../i18n'
import type { FieldDefinition } from '../../../types'
import { StepMapping } from './StepMapping'

vi.mock('../../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))

const rightsUrlField = {
  id: 'f-url',
  name: 'rechte_uri',
  label: { de: 'Rechte-URI', en: 'Rights URI' },
  field_type: 'url',
  is_required: false,
  is_repeatable: false,
  parent_id: null,
  settings: {},
} as unknown as FieldDefinition

const titleField = {
  id: 'f-title',
  name: 'title',
  label: { de: 'Titel', en: 'Title' },
  field_type: 'text',
  is_required: true,
  is_repeatable: false,
  parent_id: null,
  settings: {},
} as unknown as FieldDefinition

function renderStep(overrides: Record<string, unknown> = {}) {
  const props = {
    uploaded: {
      upload_id: 'u1',
      headers: ['rights_uri', 'rights_text', 'title'],
      row_count: 1,
      preview: [{ rights_uri: 'https://example.org/r', rights_text: 'Eingeschränkt', title: 'Objekt' }],
      suggestions: {},
    },
    fields: [titleField, rightsUrlField],
    mapping: { rights_uri: { target: 'rechte_uri' }, title: { target: 'title' } },
    onMappingChange: vi.fn(),
    recordType: 'object',
    mediaSelector: null,
    onMediaSelectorChange: vi.fn(),
    idnoStrategy: 'auto',
    idnoColumn: null,
    onIdnoStrategyChange: vi.fn(),
    pendingFields: [],
    onPendingFieldsChange: vi.fn(),
    vocabModes: {},
    onVocabModeChange: vi.fn(),
    relationOptions: {},
    onRelationOptionChange: vi.fn(),
    missingRequired: [],
    idnoMissing: false,
    mappedCount: 2,
    ignoredCount: 1,
    dryRunning: false,
    onDryRun: vi.fn(),
    onBack: vi.fn(),
    ...overrides,
  }
  render(<StepMapping {...(props as unknown as Parameters<typeof StepMapping>[0])} />)
  return props
}

describe('StepMapping URL label selector', () => {
  it('shows label column picker only for URL-mapped rows and stores label_selector', () => {
    const props = renderStep()
    const selects = screen.getAllByLabelText(/Beschriftung aus Spalte|Label from column/i)
    expect(selects).toHaveLength(1)

    fireEvent.change(selects[0], { target: { value: 'rights_text' } })
    expect(props.onMappingChange).toHaveBeenCalledWith({
      rights_uri: { target: 'rechte_uri', label_selector: 'rights_text' },
      title: { target: 'title' },
    })
  })

  it('clears label_selector when choosing the empty option', () => {
    const props = renderStep({
      mapping: { rights_uri: { target: 'rechte_uri', label_selector: 'rights_text' } },
    })
    const select = screen.getByLabelText(/Beschriftung aus Spalte|Label from column/i) as HTMLSelectElement
    expect(select.value).toBe('rights_text')

    fireEvent.change(select, { target: { value: '' } })
    expect(props.onMappingChange).toHaveBeenCalledWith({
      rights_uri: { target: 'rechte_uri' },
    })
  })
})
