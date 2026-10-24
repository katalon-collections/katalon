// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { relationFilterHref } from './DetailPageLayout'

const field = (is_facet = false) => ({
  name: 'kuenstler', field_type: 'relation', is_facet, settings: { target_type: 'entity' },
})
const facets = {
  object: [{ key: 'komponist', label: { de: 'Komponist' }, target_type: 'entity', relation_types: ['komponist'] }],
}

describe('relationFilterHref', () => {
  it('uses the relation facet covering the entry type', () => {
    expect(relationFilterHref('object', field(), { id: 'e1', label: 'X', relation_type: 'komponist' }, undefined, facets))
      .toBe('/search?type=object&meta_relfacet_komponist=e1')
  })

  it('prefers the field itself when it is a relation facet', () => {
    expect(relationFilterHref('object', field(true), { id: 'e1', label: 'X', relation_type: 'komponist' }, { kind: 'relation' }, facets))
      .toBe('/search?type=object&meta_kuenstler=e1')
  })

  it('returns undefined when no facet covers the entry', () => {
    expect(relationFilterHref('object', field(), { id: 'e1', label: 'X', relation_type: 'fotograf' }, undefined, facets))
      .toBeUndefined()
  })
})
