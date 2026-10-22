// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setLocale } from '../i18n'
import { encodeAdvancedQuery } from '../utils/advancedSearch'
import { SearchPage } from './SearchPage'

vi.mock('../hooks/useSubtypePlaceholders', () => ({ useSubtypePlaceholder: () => () => '' }))
vi.mock('../hooks/useRecordSubtypeLabels', () => ({ useRecordSubtypeLabels: () => (value: string) => value === 'postcard' ? 'Postkarte' : value }))
vi.mock('../hooks/useFieldLabels', () => ({ useFieldLabels: () => ({ object: { height: { label: 'Höhe', field_type: 'number' } } }) }))
vi.mock('./AdvancedSearchPage', () => ({ QuerySummary: () => null }))
vi.mock('../api/client', () => ({
  BASE: '', PORTAL_API: '/portal/v1',
  api: { portal: { config: async () => ({
    facet_fields: { _system: ['record_type', 'status', 'subtype'], object: ['subject', 'creator', 'date', 'flag', 'height'] },
    facet_kinds: { object: {
      subject: { kind: 'tree', label: { de: 'Thema', en: 'Subject' } },
      creator: { kind: 'relation', label: { de: 'Urheber' } },
      date: { kind: 'date', label: { de: 'Datum' }, granularity: 'decade' },
      flag: { kind: 'boolean', label: { de: 'Markiert' } },
    } },
  }) },
  // Never resolves: lets the tests look at the loading state of an advanced search.
  search: { advanced: () => new Promise(() => {}) } },
}))

function Location() {
  return <output data-testid="location">{useLocation().search}</output>
}

function openSearch(query: string) {
  render(<MemoryRouter initialEntries={[`/search?${query}`]}><SearchPage /><Location /></MemoryRouter>)
}

let totalResults = 134

describe('SearchPage filters and pagination', () => {
  beforeEach(() => {
    totalResults = 134
    localStorage.clear()
    act(() => setLocale('de'))
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
      total: totalResults, page: 3, page_size: 20, items: [],
      facets: { meta_creator: [{ value: 'person-id|Anna Beispiel', count: 134 }] },
      tree_facets: { subject: { nodes: {}, paths: { leaf: [
        { id: 'root', label: { de: 'Natur', en: 'Nature' } },
        { id: 'leaf', label: { de: 'Tiere', en: 'Animals' } },
      ] } } },
    }) })))
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('removes one selected value, resets the page, and preserves the other search state', async () => {
    openSearch('q=Karte&type=object&subtype=postcard&rel_collection=Assel&rel_collection=Silcher&page=3&sort=title_asc')
    const pills = await screen.findByRole('group', { name: 'Filter' })
    expect(within(pills).getByText('Subtyp: Postkarte')).toBeTruthy()
    fireEvent.click(within(pills).getByRole('button', { name: 'Filter entfernen: Sammlungen: Assel' }))
    await waitFor(() => {
      const params = new URLSearchParams(screen.getByTestId('location').textContent ?? '')
      expect(params.getAll('rel_collection')).toEqual(['Silcher'])
      expect(params.get('page')).toBeNull()
      expect(params.get('q')).toBe('Karte')
      expect(params.get('sort')).toBe('title_asc')
      expect(params.get('type')).toBe('object')
      expect(params.get('subtype')).toBe('postcard')
    })
  })

  it('resolves metadata labels and removes a whole range without clearing other filters', async () => {
    openSearch('type=object&meta_subject=leaf&meta_creator=person-id&meta_date=1910&meta_flag=True&range_height_from=10&range_height_to=20&page=3')
    await screen.findByText('Thema: Natur › Tiere')
    expect(screen.getByText('Urheber: Anna Beispiel')).toBeTruthy()
    expect(screen.getByText('Datum: 1910er')).toBeTruthy()
    expect(screen.getByText('Markiert: Ja')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Filter entfernen: Höhe: 10–20' }))
    const params = new URLSearchParams(screen.getByTestId('location').textContent ?? '')
    expect(params.has('range_height_from')).toBe(false)
    expect(params.has('range_height_to')).toBe(false)
    expect(params.get('meta_subject')).toBe('leaf')
    expect(params.get('page')).toBeNull()
  })

  it('uses English labels and preserves another selected metadata value', async () => {
    act(() => setLocale('en'))
    openSearch('type=object&meta_subject=leaf&meta_subject=other&page=3')
    await screen.findByText('Subject: Nature › Animals')
    fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Subject: Nature › Animals' }))
    expect(new URLSearchParams(screen.getByTestId('location').textContent ?? '').getAll('meta_subject')).toEqual(['other'])
  })

  it('shows no pills for a search with only query, sort, and page', async () => {
    openSearch('q=Karte&page=3&sort=title_asc')
    await screen.findByText(/134 Treffer/)
    expect(screen.queryByRole('group', { name: 'Filter' })).toBeNull()
  })

  it('jumps to a page while preserving query, filters, and sort', async () => {
    openSearch('q=Karte&rel_collection=Assel&page=3&sort=title_asc')
    const input = await screen.findByRole('spinbutton', { name: 'Seite' })
    fireEvent.change(input, { target: { value: '5' } })
    fireEvent.submit(input.closest('form')!)
    const params = new URLSearchParams(screen.getByTestId('location').textContent ?? '')
    expect(params.get('page')).toBe('5')
    expect(params.get('q')).toBe('Karte')
    expect(params.get('rel_collection')).toBe('Assel')
    expect(params.get('sort')).toBe('title_asc')
  })

  it.each([
    ['', 500, true], ['', 501, false], ['', 691, false], ['', 692, true], ['', 1191, true],
    ['q=Karte', 500, true], ['q=Karte', 692, false],
    ['q=Karte&sort=title_asc', 692, true],
  ])('checks reachability for %s, page %s', async (query, target, reachable) => {
    totalResults = 23804
    openSearch(`${query}&page=3`)
    const input = await screen.findByRole('spinbutton', { name: 'Seite' })
    fireEvent.change(input, { target: { value: String(target) } })
    fireEvent.click(screen.getByRole('button', { name: 'Los' }))
    if (reachable) {
      expect(new URLSearchParams(screen.getByTestId('location').textContent ?? '').get('page')).toBe(String(target))
    } else {
      expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Diese Seite ist nicht abrufbar. Bitte die Suche eingrenzen.')
      expect(new URLSearchParams(screen.getByTestId('location').textContent ?? '').get('page')).toBe('3')
      expect(screen.getByText(/23804 Treffer/)).toBeTruthy()
      expect(input.getAttribute('aria-invalid')).toBe('true')
    }
  })

  it.each(['0', '8', '1.5', ''])('rejects invalid input %s without changing the page', async value => {
    openSearch('page=3')
    const input = await screen.findByRole('spinbutton', { name: 'Seite' })
    fireEvent.change(input, { target: { value } })
    fireEvent.submit(input.closest('form')!)
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Bitte eine ganze Seitenzahl zwischen 1 und 7 eingeben.')
    expect(new URLSearchParams(screen.getByTestId('location').textContent ?? '').get('page')).toBe('3')
  })

  it('guards numbered buttons as well and uses an English hint', async () => {
    totalResults = 23804
    act(() => setLocale('en'))
    openSearch('q=Karte&page=3')
    const pagination = await screen.findByRole('navigation', { name: 'Result pages' })
    fireEvent.click(within(pagination).getByRole('button', { name: '1191' }))
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'This page is unavailable. Please narrow your search.')
    expect(new URLSearchParams(screen.getByTestId('location').textContent ?? '').get('page')).toBe('3')
  })

  it('omits pagination for one page', async () => {
    totalResults = 20
    openSearch('')
    await screen.findByText('20 Treffer')
    expect(screen.queryByRole('spinbutton', { name: 'Seite' })).toBeNull()
  })
})

describe('SearchPage advanced search over relations', () => {
  afterEach(() => { cleanup(); vi.useRealTimers() })

  it('says that a relation search is running and why it may take longer', async () => {
    act(() => setLocale('de'))
    vi.useFakeTimers()
    const aq = encodeAdvancedQuery({
      version: 1, record_type: 'object', group: { mode: 'all', clauses: [{
        kind: 'relation_type', relation_type: 'wurde_abgesendet', direction: 'outgoing', target_type: 'place',
        group: { mode: 'all', clauses: [{ kind: 'field', field: 'label', operator: 'contains', value: 'Georgsmarienhütte' }] },
      }] },
    })
    render(<MemoryRouter initialEntries={[`/search?aq=${aq}`]}><SearchPage /></MemoryRouter>)
    await act(async () => { await Promise.resolve() })

    expect(screen.getByRole('status').textContent).toContain('Suche über Verknüpfungen läuft…')
    expect(screen.queryByText(/kann das einen Moment dauern/)).toBeNull()
    await act(async () => { vi.advanceTimersByTime(1600) })
    expect(screen.getByText(/kann das einen Moment dauern/)).toBeTruthy()
  })
})

