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

export type AdvancedClause = AdvancedFieldClause | AdvancedRelationClause

export type AdvancedGroup = {
  mode: 'all' | 'any'
  clauses: AdvancedClause[]
}

export type AdvancedQuery = {
  version: 1
  record_type: 'object' | 'entity' | 'place' | 'occurrence'
  group: AdvancedGroup
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
