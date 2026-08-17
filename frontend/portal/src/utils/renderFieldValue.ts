const AUTHORITY_BASE: Record<string, string> = {
  gnd:       'https://d-nb.info/gnd/',
  wikidata:  'https://www.wikidata.org/wiki/',
  viaf:      'https://viaf.org/viaf/',
  geonames:  'https://www.geonames.org/',
  tgn:       'https://vocab.getty.edu/page/tgn/',
  iconclass: 'https://iconclass.org/',
}

const PID_RESOLVER_BASE = 'https://nbn-resolving.org/'

/** Returns the external URL for an authority field value, or undefined. */
export function authorityUrl(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  const source = typeof obj.source === 'string' ? obj.source : ''
  const externalId = typeof obj.external_id === 'string' ? obj.external_id : ''
  if (!source || !externalId) return undefined
  const base = AUTHORITY_BASE[source]
  return base ? base + externalId : undefined
}

/** Returns resolver URL for PID field values ({value, label}) if it looks like an URN. */
export function pidUrl(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  const pidValue = typeof obj.value === 'string' ? obj.value.trim() : ''
  if (!pidValue.toLowerCase().startsWith('urn:')) return undefined
  return `${PID_RESOLVER_BASE}${pidValue}`
}

/**
 * Converts a metadata field value to a human-readable string for display.
 * Returns null if the value is empty / should be skipped.
 */
export function renderFieldValue(value: unknown): string | null {
  if (value == null) return null

  // Authority entry {source, external_id, label} / translatable field {lang: text}
  if (typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>
    if (typeof obj.label === 'string' && obj.label) return obj.label
    if (typeof obj.value === 'string' && obj.value) return obj.value
    // Translatable field: prefer de → en → first non-empty language value.
    for (const lang of ['de', 'en']) {
      const v = obj[lang]
      if (typeof v === 'string' && v.trim()) return v
    }
    for (const key of Object.keys(obj)) {
      const v = obj[key]
      if (typeof v === 'string' && v.trim()) return v
    }
    return null
  }

  // Repeatable field stored as array
  if (Array.isArray(value)) {
    const parts = value
      .map(item => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item !== null) {
          const o = item as Record<string, unknown>
          if (typeof o.label === 'string' && o.label) return o.label
          if (typeof o.value === 'string' && o.value) return o.value
          if (typeof o.name === 'string' && o.name) return o.name
        }
        return null
      })
      .filter((s): s is string => s !== null && s !== '')
    return parts.length > 0 ? parts.join(', ') : null
  }

  // Primitive
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nein'
  const s = String(value)
  return s || null
}
