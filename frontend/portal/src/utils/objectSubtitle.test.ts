// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { PortalFieldDefinition } from '../api/client'
import { recordSubtitle } from './objectSubtitle'

function def(name: string, field_type: string): PortalFieldDefinition {
  return {
    id: name, name, field_type, label: {}, is_repeatable: false, is_searchable: true, is_facet: true,
    parent_id: null, settings: {}, show_in_detail: true, detail_slot: 'main', detail_role: 'none',
  }
}

const postcard = {
  status: 'published',
  idno: 'BPK-1',
  metadata_: {
    // Repeatable group, as in the BPK schema — must never render "[object Object]".
    date: [{ dates_value: '1918-03-21', dc_dates_types: { label: 'Poststempel' } }],
    verlag: [{ value: 'Stengel & Co.' }],
    entstehung: '1890/',
  },
}
const defs = [def('date', 'group'), def('verlag', 'text'), def('entstehung', 'date')]

describe('recordSubtitle', () => {
  it('is empty without configuration', () => {
    expect(recordSubtitle(postcard, 'object', undefined, defs, 'de')).toBe('')
    expect(recordSubtitle(postcard, 'object', [], defs, 'de')).toBe('')
  })

  it('renders configured fields and skips group fields', () => {
    const text = recordSubtitle(postcard, 'object', ['date', 'verlag', 'idno', 'entstehung'], defs, 'de')
    expect(text).not.toContain('[object Object]')
    expect(text).toBe('Stengel & Co. · BPK-1 · nach 1890')
  })

  it('skips unknown and inherited fields', () => {
    expect(recordSubtitle(postcard, 'object', ['inherited_entity_x', 'missing'], defs, 'de')).toBe('')
  })
})
