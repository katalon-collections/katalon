// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { FacetKind } from '../api/client'

export function resolveLabel(label: Record<string, string> | undefined | null, locale: string, fallback = ''): string {
  if (!label) return fallback
  return [label[locale], label.de, label.en, ...Object.values(label)].find(v => v?.trim()) ?? fallback
}

/** Relation facet buckets are "<id>|<title>": filter by id, show the title. */
export function splitRelationBucket(value: string): { id: string; title: string } {
  const index = value.indexOf('|')
  return index < 0 ? { id: value, title: value } : { id: value.slice(0, index), title: value.slice(index + 1) }
}

/** Display label for a date bucket ("1910" → "1910er" / "1910s", "1800" → "19. Jh." / "19th c."). */
export function dateBucketLabel(bucket: string, granularity: string | undefined, locale: string): string {
  const year = Number(bucket)
  if (!Number.isFinite(year)) return bucket
  if (granularity === 'decade') return locale === 'en' ? `${year}s` : `${year}er`
  if (granularity === 'century') {
    const century = Math.floor(year / 100) + 1
    if (locale === 'en') {
      const suffix = century % 100 >= 11 && century % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[century % 10] ?? 'th'
      return `${century}${suffix} c.`
    }
    return `${century}. Jh.`
  }
  return String(year)
}

/** Kind info for a facet: the selected type's entry, else the first type that has it. */
export function facetKind(
  kinds: Record<string, Record<string, FacetKind>> | undefined,
  recordType: string,
  name: string,
): FacetKind | undefined {
  if (!kinds) return undefined
  if (recordType) return kinds[recordType]?.[name]
  for (const perType of Object.values(kinds)) {
    if (perType?.[name]) return perType[name]
  }
  return undefined
}

export interface RelationFacetConfig {
  key: string
  label: Record<string, string>
  target_type: string
  relation_types: string[]
  target_subtypes?: string[]
  direction?: 'outgoing' | 'incoming' | 'both'
}

/** The relation facet of `facets` that covers a relation of this type to a
 *  record of `targetType`, seen from the facet's own record. Facets restricted
 *  to target subtypes are skipped: the subtype is not known client-side, and a
 *  link must never lead to an empty result. */
export function matchRelationFacet(
  facets: RelationFacetConfig[] | undefined,
  targetType: string,
  relationType: string,
  direction: 'outgoing' | 'incoming',
): RelationFacetConfig | undefined {
  return (facets ?? []).find(facet =>
    facet.target_type === targetType
    && facet.relation_types.includes(relationType)
    && [direction, 'both'].includes(facet.direction ?? 'outgoing')
    && !(facet.target_subtypes?.length),
  )
}

export function relationFacetHref(recordType: string, facet: RelationFacetConfig, targetId: string): string {
  return `/search?type=${encodeURIComponent(recordType)}&meta_relfacet_${facet.key}=${encodeURIComponent(targetId)}`
}

/** Facet bucket of one stored date value (start year for intervals), or null. */
export function dateBucketOf(value: string, granularity: string | undefined): string | null {
  const match = value.trim().match(/^\/?(-?\d{1,4})/)
  if (!match) return null
  const year = Number(match[1])
  if (!Number.isFinite(year) || year < 1000) return null
  if (granularity === 'century') return String(Math.floor(year / 100) * 100)
  if (granularity === 'decade') return String(Math.floor(year / 10) * 10)
  return String(year)
}
