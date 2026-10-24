// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { Relation } from '../api/client'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'
import { withoutFieldRelations } from './relations'

const rel = (id: string, from: string, source_field: string | null): Relation => ({
  id, from_type: 'object', from_id: from, to_type: 'entity', to_id: 'e1', relation_type: 'schenker',
  from_label: null, to_label: null, source_field,
})
const field = (name: string, show_in_detail = true): FieldDefinition => ({
  id: name, name, label: {}, field_type: 'relation', is_repeatable: true, is_searchable: true, is_facet: false,
  parent_id: null, settings: {}, show_in_detail, detail_slot: 'sidebar', detail_role: 'none',
})

describe('withoutFieldRelations', () => {
  it('drops outgoing relations shown by a visible relation field or group', () => {
    const rels = [rel('a', 'o1', 'schenker'), rel('b', 'o1', 'personen.person'), rel('c', 'o1', null)]
    expect(withoutFieldRelations(rels, 'o1', [field('schenker'), field('personen')]).map(r => r.id)).toEqual(['c'])
  })

  it('keeps incoming relations and those of hidden or unknown fields', () => {
    const rels = [rel('a', 'other', 'schenker'), rel('b', 'o1', 'schenker'), rel('c', 'o1', 'internal')]
    expect(withoutFieldRelations(rels, 'o1', [field('schenker', false)]).map(r => r.id)).toEqual(['a', 'b', 'c'])
  })
})
