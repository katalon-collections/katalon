// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export type AdvancedFieldClause = {
  kind: 'field'
  field: string
  operator: string
  value?: unknown
}

export type AdvancedRelationClause = {
  kind: 'relation'
  field: string
  group: AdvancedGroup
}

/** A free relation (not a relation field) of one type, with conditions on its target. */
export type AdvancedRelationTypeClause = {
  kind: 'relation_type'
  relation_type: string
  direction: 'outgoing' | 'incoming'
  target_type: AdvancedRecordType
  group: AdvancedGroup
}

export type AdvancedClause = AdvancedFieldClause | AdvancedRelationClause | AdvancedRelationTypeClause

export type AdvancedGroup = {
  mode: 'all' | 'any'
  clauses: AdvancedClause[]
}

export type AdvancedRecordType = 'object' | 'entity' | 'place' | 'occurrence'

export type AdvancedQuery = {
  version: 1
  record_type: AdvancedRecordType
  group: AdvancedGroup
}

/** True when a condition follows relations; such searches resolve targets first and take longer. */
export function usesRelations(group: AdvancedGroup): boolean {
  return group.clauses.some(clause => clause.kind !== 'field')
}

export function encodeAdvancedQuery(query: AdvancedQuery): string {
  const bytes = new TextEncoder().encode(JSON.stringify(query))
  let binary = ''
  bytes.forEach(byte => { binary += String.fromCharCode(byte) })
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
}

export function decodeAdvancedQuery(value: string | null): AdvancedQuery | null {
  if (!value) return null
  try {
    const padded = value.replaceAll('-', '+').replaceAll('_', '/')
      .padEnd(Math.ceil(value.length / 4) * 4, '=')
    const binary = atob(padded)
    const bytes = Uint8Array.from(binary, char => char.charCodeAt(0))
    const parsed = JSON.parse(new TextDecoder().decode(bytes)) as Partial<AdvancedQuery>
    if (parsed.version !== 1 || !parsed.record_type || !parsed.group) return null
    return parsed as AdvancedQuery
  } catch {
    return null
  }
}
