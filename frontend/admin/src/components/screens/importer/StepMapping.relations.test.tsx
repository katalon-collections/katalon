// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '../../../i18n'
import type { FieldDefinition } from '../../../types'
import { StepMapping } from './StepMapping'

vi.mock('../../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))

const developer = {
  id: 'f1', name: 'entwickler', label: { de: 'Entwickler' }, field_type: 'relation',
  is_required: false, is_repeatable: false, parent_id: null,
  settings: { target_type: 'entity', fixed_relation_type: 'rel-0001' },
} as unknown as FieldDefinition

function renderMapping(overrides: Record<string, unknown> = {}) {
  const props = {
    uploaded: { upload_id: 'u', headers: ['ID', 'Publisher'], row_count: 1, preview: [{ ID: 'x_1', Publisher: 'Sproing' }], suggestions: {} },
    fields: [developer],
    mapping: { ID: { target: '__idno__' }, Publisher: { target: 'entwickler' } },
    onMappingChange: vi.fn(), recordType: 'occurrence', mediaSelector: null, onMediaSelectorChange: vi.fn(),
    idnoStrategy: 'column', idnoColumn: 'ID', onIdnoStrategyChange: vi.fn(),
    pendingFields: [], onPendingFieldsChange: vi.fn(), vocabModes: {}, onVocabModeChange: vi.fn(),
    relationOptions: {}, onRelationOptionChange: vi.fn(),
    missingRequired: [], idnoMissing: false, mappedCount: 1, ignoredCount: 0,
    dryRunning: false, onDryRun: vi.fn(), onBack: vi.fn(), ...overrides,
  }
  render(<StepMapping {...(props as unknown as Parameters<typeof StepMapping>[0])} />)
  return props
}

it('offers lookup and missing-target choice for mapped relation fields and reports changes', () => {
  const props = renderMapping()
  const [lookup, missing] = screen.getAllByRole('combobox').filter(el => el.getAttribute('aria-label')?.includes('Entwickler'))
  expect((lookup as HTMLSelectElement).value).toBe('idno')
  expect((missing as HTMLSelectElement).value).toBe('error')
  fireEvent.change(lookup, { target: { value: 'label' } })
  expect(props.onRelationOptionChange).toHaveBeenCalledWith('entwickler', { lookup: 'label', on_missing: 'error' })
  fireEvent.change(missing, { target: { value: 'create' } })
  expect(props.onRelationOptionChange).toHaveBeenCalledWith('entwickler', { lookup: 'idno', on_missing: 'create' })
})

it('labels the ID column as assigned via the ID number card instead of ignored', () => {
  renderMapping()
  expect(screen.getByText('→ ID-Nummer (siehe oben)')).toBeTruthy()
})

it('shows no relation card without a mapped relation field', () => {
  renderMapping({ mapping: { ID: { target: '__idno__' } } })
  expect(screen.queryByText('Beziehungsfelder')).toBeNull()
})

it('loads a mapping profile file in the mapping step (XML never returns to upload)', async () => {
  const onProfileLoaded = vi.fn()
  renderMapping({ onProfileLoaded })
  const input = screen.getByLabelText('Mapping-Profil laden (Datei)') as HTMLInputElement
  const profile = { version: 1, record_type: 'occurrence', mapping: { ID: { target: '__idno__' } } }
  fireEvent.change(input, { target: { files: [new File([JSON.stringify(profile)], 'p.json')] } })
  await waitFor(() => expect(onProfileLoaded).toHaveBeenCalledWith(profile))

  fireEvent.change(input, { target: { files: [new File(['{"version":2}'], 'bad.json')] } })
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Ungültiges Profilformat.')
  expect(onProfileLoaded).toHaveBeenCalledTimes(1)
})
