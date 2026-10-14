// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { dateBucketLabel, facetKind, resolveLabel, splitRelationBucket } from './facets'

describe('facet helpers', () => {
  it('labels date buckets per granularity and locale', () => {
    expect(dateBucketLabel('1910', 'decade', 'de')).toBe('1910er')
    expect(dateBucketLabel('1910', 'decade', 'en')).toBe('1910s')
    expect(dateBucketLabel('1800', 'century', 'de')).toBe('19. Jh.')
    expect(dateBucketLabel('1800', 'century', 'en')).toBe('19th c.')
    expect(dateBucketLabel('1900', 'century', 'en')).toBe('20th c.')
    expect(dateBucketLabel('2000', 'century', 'en')).toBe('21st c.')
    expect(dateBucketLabel('1918', 'year', 'de')).toBe('1918')
  })

  it('splits relation buckets on the first pipe only', () => {
    expect(splitRelationBucket('abc|Müller | Sohn')).toEqual({ id: 'abc', title: 'Müller | Sohn' })
    expect(splitRelationBucket('plain')).toEqual({ id: 'plain', title: 'plain' })
  })

  it('resolves labels with fallbacks', () => {
    expect(resolveLabel({ de: 'Natur', en: 'Nature' }, 'en')).toBe('Nature')
    expect(resolveLabel({ de: 'Natur' }, 'en')).toBe('Natur')
    expect(resolveLabel(undefined, 'de', 'x')).toBe('x')
  })

  it('finds a facet kind for the selected or any type', () => {
    const kinds = { object: { a: { kind: 'date' as const } }, place: { b: { kind: 'tree' as const } } }
    expect(facetKind(kinds, 'object', 'a')?.kind).toBe('date')
    expect(facetKind(kinds, '', 'b')?.kind).toBe('tree')
    expect(facetKind(kinds, 'object', 'b')).toBeUndefined()
  })
})

describe('detail page facet helpers', () => {
  it('derives the date bucket of a stored value', async () => {
    const { dateBucketOf } = await import('./facets')
    expect(dateBucketOf('1918-03-21', 'decade')).toBe('1910')
    expect(dateBucketOf('1884/1919', 'decade')).toBe('1880')
    expect(dateBucketOf('/1905', 'century')).toBe('1900')
    expect(dateBucketOf('0196-11-26', 'decade')).toBeNull()
  })

  it('matches relation facets by target type, relation type and direction', async () => {
    const { matchRelationFacet } = await import('./facets')
    const facets = [
      { key: 'komponist', label: {}, target_type: 'entity', relation_types: ['komponist'] },
      { key: 'serie', label: {}, target_type: 'occurrence', relation_types: ['teil_von'], target_subtypes: ['serie'] },
      { key: 'beide', label: {}, target_type: 'place', relation_types: ['ort'], direction: 'both' as const },
    ]
    expect(matchRelationFacet(facets, 'entity', 'komponist', 'outgoing')?.key).toBe('komponist')
    expect(matchRelationFacet(facets, 'entity', 'komponist', 'incoming')).toBeUndefined()
    expect(matchRelationFacet(facets, 'entity', 'maler', 'outgoing')).toBeUndefined()
    // Subtype-restricted facets get no link (subtype unknown client-side).
    expect(matchRelationFacet(facets, 'occurrence', 'teil_von', 'outgoing')).toBeUndefined()
    expect(matchRelationFacet(facets, 'place', 'ort', 'incoming')?.key).toBe('beide')
  })
})
