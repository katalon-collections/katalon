// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type PortalFieldDefinition } from '../api/client'

vi.mock('../hooks/usePortalConfig', () => ({ usePortalConfig: () => ({ facet_kinds: {} }) }))
vi.mock('../hooks/useRelationTypeLabels', () => ({ useRelationTypeLabels: () => (code: string) => code }))
vi.mock('./GeoMap', () => ({
  default: ({ lat, lon, label }: { lat: number; lon: number; label: string }) => (
    <div data-testid="geo-map" aria-label={label}>{`${lat},${lon}`}</div>
  ),
}))

const { DetailPageLayout, GroupMetaRow, fieldsForSubtype, withoutTitleFields } = await import('./DetailPageLayout')

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

  it.each(['sidebar', 'main'] as const)('links every entry of a repeatable authority field (%s)', slot => {
    render(
      <MemoryRouter>
        <DetailPageLayout
          fieldDefs={[def('a', 'Normdaten', 'authority', { is_repeatable: true, detail_slot: slot })]}
          metadata={{ Normdaten: [
            { source: 'wikidata', external_id: 'Q173626', label: 'Wikidata-Eintrag' },
            { source: 'aat', external_id: '300025103', label: 'AAT-Eintrag' },
          ] }}
          locale="de"
          recordType="occurrence"
          sidebarPosition="right"
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Wikidata-Eintrag' }).getAttribute('href')).toBe('https://www.wikidata.org/wiki/Q173626')
    expect(screen.getByRole('link', { name: 'AAT-Eintrag' }).getAttribute('href')).toBe('https://vocab.getty.edu/aat/300025103')
  })

  it('withoutTitleFields drops top-level title/name but keeps group sub-fields of that name', () => {
    const defs = [
      def('t', 'title', 'text'),
      def('n', 'name', 'text'),
      def('k', 'keywords', 'text'),
      def('g', 'beteiligte_personen', 'group'),
      def('gn', 'name', 'text', { parent_id: 'g' }),
      def('gt', 'title', 'text', { parent_id: 'g' }),
    ]
    expect(withoutTitleFields(defs).map(f => f.id)).toEqual(['k', 'g', 'gn', 'gt'])
    expect(withoutTitleFields(defs, ['keywords']).map(f => f.id)).toEqual(['g', 'gn', 'gt'])
    const { container } = render(
      <MemoryRouter>
        <DetailPageLayout fieldDefs={withoutTitleFields(defs)} metadata={{ beteiligte_personen: [{ name: 'David Braben' }] }} locale="de" recordType="occurrence" sidebarPosition="right" />
      </MemoryRouter>,
    )
    expect(container.textContent).toContain('David Braben')
  })

  it('fieldsForSubtype keeps generic fields and the record subtype, drops other subtypes', () => {
    const defs = [
      def('a', 'alle', 'text'),
      def('w', 'expression', 'relation', { target_subtype: 'work' }),
      def('m', 'expression', 'group', { target_subtype: 'manifestation' }),
    ]
    expect(fieldsForSubtype(defs, 'work').map(f => f.id)).toEqual(['a', 'w'])
    expect(fieldsForSubtype(defs, 'manifestation').map(f => f.id)).toEqual(['a', 'm'])
    expect(fieldsForSubtype(defs, null).map(f => f.id)).toEqual(['a'])
  })

  it('emphasizes the first sub-field of a group when the group setting is on', () => {
    const defs = [
      def('g', 'Fan', 'group', { settings: { emphasize_first_child: true } }),
      def('t', 'Titel', 'text', { parent_id: 'g' }),
      def('d', 'Beschreibung', 'text', { parent_id: 'g' }),
    ]
    const { container } = render(
      <MemoryRouter>
        <DetailPageLayout fieldDefs={defs} metadata={{ Fan: [{ Titel: 'Scummbar', Beschreibung: 'Fanseite' }, { Beschreibung: 'ohne Titel' }] }} locale="de" recordType="occurrence" sidebarPosition="right" />
      </MemoryRouter>,
    )
    const bold = [...container.querySelectorAll('.group-entry strong')].map(el => el.textContent)
    expect(bold).toEqual(['Scummbar'])
  })

  it('does not emphasize anything without the group setting', () => {
    const defs = [def('g', 'Fan', 'group'), def('t', 'Titel', 'text', { parent_id: 'g' }), def('d', 'Beschreibung', 'text', { parent_id: 'g' })]
    const { container } = render(
      <MemoryRouter>
        <DetailPageLayout fieldDefs={defs} metadata={{ Fan: [{ Titel: 'Scummbar', Beschreibung: 'Fanseite' }] }} locale="de" recordType="occurrence" sidebarPosition="right" />
      </MemoryRouter>,
    )
    expect(container.querySelector('.group-entry strong')).toBeNull()
  })

  it('GroupMetaRow renders nothing without values', () => {
    const { container } = render(
      <MemoryRouter>
        <GroupMetaRow field={fields[0]} fieldDefs={fields} value={[{ Intern: 'x' }, {}]} locale="de" recordType="collection" />
      </MemoryRouter>,
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders a map under place relation fields with show_place_map only when the place has coordinates', async () => {
    const getPlaceSpy = vi.spyOn(api.places, 'get').mockImplementation(async (id: string) => ({
      id,
      status: 'public',
      lat: id === 'p-berlin' ? 52.52 : null,
      lon: id === 'p-berlin' ? 13.405 : null,
      metadata_: {},
      ai_provenance: {},
      created_at: '',
      updated_at: '',
      ancestors: [],
      children: [],
    }))
    const placeRelField = def('r1', 'Fundort', 'relation', {
      is_repeatable: true,
      settings: { target_type: 'place', show_place_map: true },
    })
    render(
      <MemoryRouter>
        <DetailPageLayout
          fieldDefs={[placeRelField]}
          metadata={{
            Fundort: [
              { id: 'p-berlin', label: 'Berlin', relation_type: 'found_at' },
              { id: 'p-atlantis', label: 'Atlantis', relation_type: 'found_at' },
            ],
          }}
          locale="de"
          recordType="object"
          sidebarPosition="right"
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Berlin' }).getAttribute('href')).toBe('/places/p-berlin')
    expect(screen.getByRole('link', { name: 'Atlantis' }).getAttribute('href')).toBe('/places/p-atlantis')
    await waitFor(() => {
      const maps = screen.getAllByTestId('geo-map')
      expect(maps).toHaveLength(1)
      expect(maps[0].getAttribute('aria-label')).toBe('Berlin')
      expect(maps[0].textContent).toBe('52.52,13.405')
    })
    getPlaceSpy.mockRestore()
  })
})
