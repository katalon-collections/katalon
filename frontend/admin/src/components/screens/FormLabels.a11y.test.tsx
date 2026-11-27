// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import '../../i18n'
import { TransformModal } from '../importer/TransformModal'
import { StepDryRun } from './importer/StepDryRun'

describe('Importer form label accessibility', () => {
  it('links transform configuration labels to their inputs with unique ids', () => {
    const { container } = render(
      <TransformModal
        csvColumn="title"
        sourceColumns={['title', 'subtitle']}
        sampleValues={['A, B']}
        sampleRows={[{ title: 'A, B', subtitle: 'C' }]}
        mappingEntry={{
          target: 'title',
          transforms: [
            { type: 'split', delimiter: ',' },
            { type: 'replace', search: 'A', replace: 'X' },
            { type: 'regex_extract', pattern: '\\d+', group: 1 },
            { type: 'expression', expression: '${value:trim}' },
            { type: 'combine', sources: ['title', 'subtitle'], template: '{0} - {1}' },
          ],
        }}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Trennzeichen')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Suchen')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Ersetzen durch')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Regex-Pattern')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText(/Capture Group/)).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Expression')).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByLabelText('Format')).toBeInstanceOf(HTMLInputElement)

    const ids = Array.from(container.querySelectorAll('[id]')).map(el => el.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('links the upsert strategy label to its select in StepDryRun', () => {
    render(
      <StepDryRun
        dryResult={{ total: 2, valid: 2, errors: [], warnings: [], preview: [] }}
        upsertStrategy="skip"
        onUpsertStrategyChange={vi.fn()}
        autoPublish={false}
        onAutoPublishChange={vi.fn()}
        idnoStrategy="column"
        onImport={vi.fn()}
        onApplyCluster={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Bestehende Datensätze|Existing records/i)).toBeInstanceOf(HTMLSelectElement)
  })
})
