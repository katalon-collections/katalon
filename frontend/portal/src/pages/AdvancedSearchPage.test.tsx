// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setLocale } from '../i18n'
import { AdvancedSearchPage, QuerySummary } from './AdvancedSearchPage'

const schemas: Record<string, unknown[]> = {
  object: [
    { name: 'material', field_type: 'vocab', label: { de: 'Material' }, is_searchable: true, parent_id: null, settings: {} },
    { name: 'intern', field_type: 'text', label: { de: 'Interne Notiz' }, is_searchable: true, is_public: false, parent_id: null, settings: {} },
  ],
  place: [{ name: 'label', field_type: 'text', label: { de: 'Name' }, is_searchable: true, parent_id: null, settings: {} }],
}

vi.mock('../hooks/useRelationTypeLabels', () => ({
  useRelationTypeLabels: () => (code: string, isFrom = true) =>
    code === 'wurde_abgesendet' ? (isFrom ? 'Absendeort' : 'sendet ab') : code,
}))
vi.mock('../api/client', () => ({
  api: {
    portal: {
      schema: async (type: string) => schemas[type] ?? [],
      searchFieldTerms: async () => [
        { id: 'karton', term: 'karton', label: { de: 'Karton' } },
        { id: 'leder', term: 'leder', label: { de: 'Leder' } },
      ],
    },
    search: {
      advancedRelationTypes: async (type: string) => type === 'object'
        ? [{ relation_type: 'wurde_abgesendet', direction: 'outgoing', target_type: 'place', count: 11399 }]
        : [],
    },
  },
}))

describe('AdvancedSearchPage', () => {
  beforeEach(() => { act(() => setLocale('de')) })
  afterEach(cleanup)

  it('offers free relation types and nests conditions on their target', async () => {
    render(<MemoryRouter><AdvancedSearchPage /></MemoryRouter>)
    const fieldSelect = screen.getAllByLabelText('Feld')[0]
    await waitFor(() => expect(within(fieldSelect).getByRole('option', { name: 'Absendeort → Ort' })).toBeTruthy())
    expect(within(fieldSelect).getByRole('group', { name: 'Verknüpfungen' })).toBeTruthy()
    // Staff receive internal fields as well; the public index cannot search them.
    expect(within(fieldSelect).queryByRole('option', { name: 'Interne Notiz' })).toBeNull()

    fireEvent.change(fieldSelect, { target: { value: 'rel:0' } })

    // The nested group searches places: its field picker offers the place's name.
    await waitFor(() => expect(screen.getAllByLabelText('Feld')).toHaveLength(2))
    const nested = screen.getAllByLabelText('Feld')[1]
    await waitFor(() => expect(within(nested).getByRole('option', { name: 'Name' })).toBeTruthy())
  })

  it('collects several values for "is one of" as removable chips', async () => {
    render(<MemoryRouter><AdvancedSearchPage /></MemoryRouter>)
    const fieldSelect = screen.getAllByLabelText('Feld')[0]
    await waitFor(() => expect(within(fieldSelect).getByRole('option', { name: 'Material' })).toBeTruthy())
    fireEvent.change(fieldSelect, { target: { value: 'material' } })
    fireEvent.change(screen.getByLabelText('Operator'), { target: { value: 'in' } })

    const add = await screen.findByLabelText('Wert hinzufügen…')
    await waitFor(() => expect(within(add).getByRole('option', { name: 'Karton' })).toBeTruthy())
    fireEvent.change(add, { target: { value: 'karton' } })
    fireEvent.change(screen.getByLabelText('Wert hinzufügen…'), { target: { value: 'leder' } })

    expect(screen.getByRole('button', { name: 'Wert entfernen: Karton' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Wert entfernen: Leder' }))
    expect(screen.queryByRole('button', { name: 'Wert entfernen: Leder' })).toBeNull()
  })

  it('summarises relation types and value lists', async () => {
    render(<QuerySummary query={{
      version: 1, record_type: 'object', group: { mode: 'all', clauses: [
        { kind: 'relation_type', relation_type: 'wurde_abgesendet', direction: 'outgoing', target_type: 'place',
          group: { mode: 'all', clauses: [{ kind: 'field', field: 'label', operator: 'contains', value: 'Georgsmarienhütte' }] } },
        { kind: 'field', field: 'material', operator: 'in', value: ['karton', 'leder'] },
      ] },
    }} />)

    await waitFor(() => {
      const text = document.querySelector('.advanced-query-summary')?.textContent ?? ''
      expect(text).toContain('Absendeort → Ort (Name enthält "Georgsmarienhütte")')
      expect(text).toContain('Material ist eines von "Karton" oder "Leder"')
    })
  })
})
