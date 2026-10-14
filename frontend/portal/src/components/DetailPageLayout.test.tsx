// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PortalFieldDefinition } from '../api/client'

vi.mock('../hooks/usePortalConfig', () => ({ usePortalConfig: () => ({ facet_kinds: {} }) }))
vi.mock('../hooks/useRelationTypeLabels', () => ({ useRelationTypeLabels: () => (code: string) => code }))

const { DetailPageLayout, GroupMetaRow } = await import('./DetailPageLayout')

function def(id: string, name: string, field_type: string, extra: Partial<PortalFieldDefinition> = {}): PortalFieldDefinition {
  return {
    id, name, field_type, label: { de: name }, is_repeatable: false, is_searchable: false, is_facet: false,
    parent_id: null, settings: {}, show_in_detail: true, detail_slot: 'sidebar', detail_role: 'none', ...extra,
  }
}

const fields = [
  def('g1', 'Datierung', 'group'),
  def('c1', 'Datum', 'date', { parent_id: 'g1' }),
  def('c2', 'Art', 'text', { parent_id: 'g1' }),
  def('c3', 'Intern', 'text', { parent_id: 'g1', show_in_detail: false }),
  def('g2', 'Links', 'group'),
  def('c4', 'URL', 'url', { parent_id: 'g2' }),
  def('g3', 'Normdaten', 'group', { detail_slot: 'main' }),
  def('c5', 'Kennung', 'authority', { parent_id: 'g3' }),
  def('c6', 'Schlagwort', 'text', { parent_id: 'g3', is_facet: true }),
]

describe('group fields on detail pages', () => {
  afterEach(cleanup)

  it('renders each entry with sub-field labels, links and facet links', () => {
    const { container } = render(
      <MemoryRouter>
        <DetailPageLayout
          fieldDefs={fields}
          metadata={{
            Datierung: [{ Datum: '1905', Art: 'Poststempel', Intern: 'geheim' }, { Datum: '1906~' }],
            Links: [{ URL: { value: 'https://viaf.org/viaf/1', label: 'VIAF' } }],
            Normdaten: [{ Kennung: { source: 'gnd', external_id: '118540238', label: 'GND' }, Schlagwort: 'Musik' }],
            // A sub-field name never renders as a top-level field.
            Datum: 'falsch',
          }}
          locale="de"
          recordType="entity"
          sidebarPosition="right"
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('Datierung')).toBeTruthy()
    const lines = [...container.querySelectorAll('.group-entry')].map(el => el.textContent)
    expect(lines).toContain('Datum: 1905 · Art: Poststempel')
    expect(lines).toContain('Datum: ca. 1906')
    expect(screen.queryByText('geheim')).toBeNull()
    expect(screen.queryByText('falsch')).toBeNull()
    // Single-sub-field group: value without sub-field label, as external link.
    expect(screen.getByRole('link', { name: 'VIAF' }).getAttribute('href')).toBe('https://viaf.org/viaf/1')
    expect(lines).toContain('VIAF')
    expect(screen.getByRole('link', { name: 'GND' }).getAttribute('href')).toBe('https://d-nb.info/gnd/118540238')
    expect(screen.getByRole('link', { name: 'Musik' }).getAttribute('href')).toBe('/search?type=entity&meta_Normdaten__Schlagwort=Musik')
  })

  it('GroupMetaRow renders nothing without values', () => {
    const { container } = render(
      <MemoryRouter>
        <GroupMetaRow field={fields[0]} fieldDefs={fields} value={[{ Intern: 'x' }, {}]} locale="de" recordType="collection" />
      </MemoryRouter>,
    )
    expect(container.innerHTML).toBe('')
  })
})
