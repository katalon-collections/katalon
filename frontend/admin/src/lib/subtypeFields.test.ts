// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { FieldDefinition } from '../types'
import { fieldsForSubtype } from './subtypeFields'

const field = (name: string, target_subtype: string | null) =>
  ({ name, target_subtype, is_required: true }) as FieldDefinition
const all = [field('label', null), field('only_a', 'a')]
const shown = (...args: Parameters<typeof fieldsForSubtype>) =>
  fieldsForSubtype(...args).map(f => [f.name, f.is_required])

describe('fieldsForSubtype', () => {
  it('hides other subtypes without a chosen subtype', () => {
    expect(shown(all, '')).toEqual([['label', true]])
  })
  it('requires subtype fields for that subtype', () => {
    expect(shown(all, 'a')).toEqual([['label', true], ['only_a', true]])
  })
  it('keeps stored values of other subtypes visible and optional', () => {
    expect(shown(all, 'b', { only_a: 'x' })).toEqual([['label', true], ['only_a', false]])
  })
})
