// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { VocabTerm } from '../api/client'
import { relationTypeLabel } from './useRelationTypeLabels'

const germanOnly = {
  term: 'part_of', label: { de: 'ist Teil von' }, inverse_label: { de: 'enthält' },
} as unknown as VocabTerm

describe('relationTypeLabel', () => {
  it('falls back to German when the portal language has no label', () => {
    expect(relationTypeLabel(germanOnly, 'part_of', true, 'en')).toBe('ist Teil von')
    expect(relationTypeLabel(germanOnly, 'part_of', false, 'en')).toBe('enthält')
  })

  it('prefers the portal language', () => {
    const term = { ...germanOnly, label: { de: 'ist Teil von', en: 'is part of' } } as VocabTerm
    expect(relationTypeLabel(term, 'part_of', true, 'en')).toBe('is part of')
  })

  it('uses the forward label without inverse label and the code without term', () => {
    const term = { ...germanOnly, inverse_label: {} } as VocabTerm
    expect(relationTypeLabel(term, 'part_of', false, 'de')).toBe('ist Teil von')
    expect(relationTypeLabel(undefined, 'part_of', true, 'de')).toBe('part_of')
  })
})
