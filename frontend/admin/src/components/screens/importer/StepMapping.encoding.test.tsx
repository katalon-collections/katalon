// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import '../../../i18n'
import { StepMapping } from './StepMapping'

vi.mock('../../../hooks/useSupportedLanguages', () => ({ useSupportedLanguages: () => ['de', 'en'] }))

function renderMapping(uploaded: Record<string, unknown>, onEncodingChange?: (e: string) => void) {
  const props = {
    uploaded: { upload_id: 'u', headers: ['ID'], row_count: 1, preview: [{ ID: 'x_1' }], suggestions: {}, ...uploaded },
    fields: [], mapping: {}, onMappingChange: vi.fn(), recordType: 'occurrence', mediaSelector: null,
    onMediaSelectorChange: vi.fn(), idnoStrategy: 'auto', idnoColumn: null, onIdnoStrategyChange: vi.fn(),
    pendingFields: [], onPendingFieldsChange: vi.fn(), vocabModes: {}, onVocabModeChange: vi.fn(),
    onEncodingChange, relationOptions: {}, onRelationOptionChange: vi.fn(),
    missingRequired: [], idnoMissing: false, mappedCount: 0, ignoredCount: 1,
    dryRunning: false, onDryRun: vi.fn(), onBack: vi.fn(),
  }
  render(<StepMapping {...(props as unknown as Parameters<typeof StepMapping>[0])} />)
}

it('shows the detected CSV encoding and reports a manual change', () => {
  const onChange = vi.fn()
  renderMapping({ encoding: 'windows-1252', encoding_detected: 'windows-1252' }, onChange)
  const select = screen.getByLabelText('Zeichenkodierung') as HTMLSelectElement
  expect(select.value).toBe('windows-1252')
  expect(screen.getByText(/automatisch erkannt/)).toBeTruthy()
  fireEvent.change(select, { target: { value: 'utf-8' } })
  expect(onChange).toHaveBeenCalledWith('utf-8')
})

it('says so when the encoding was changed by hand', () => {
  renderMapping({ encoding: 'utf-8', encoding_detected: 'windows-1252' }, vi.fn())
  expect(screen.getByText(/von Hand geändert \(erkannt: windows-1252\)/)).toBeTruthy()
})

it('shows no encoding control for Excel/XML uploads and disables it without the file', () => {
  renderMapping({ source_type: 'excel' }, vi.fn())
  expect(screen.queryByLabelText('Zeichenkodierung')).toBeNull()
})

it('disables the select when the file is no longer available', () => {
  renderMapping({ encoding: 'utf-8', encoding_detected: 'utf-8' })
  expect((screen.getByLabelText('Zeichenkodierung') as HTMLSelectElement).disabled).toBe(true)
})
