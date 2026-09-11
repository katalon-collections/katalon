// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { marked } from 'marked'
import DOMPurify from 'dompurify'

/** Strips markdown syntax down to plain text, for teaser/preview contexts (card excerpts,
 *  <meta name="description">) where richtext fields shouldn't leak raw `**`/`#`/link syntax. */
export function markdownToPlainText(value: string): string {
  return DOMPurify.sanitize(marked.parse(value) as string, { ALLOWED_TAGS: [] }).trim()
}

const AUTHORITY_BASE: Record<string, string> = {
  gnd:          'https://d-nb.info/gnd/',
  'gnd-person':  'https://d-nb.info/gnd/',
  'gnd-subject': 'https://d-nb.info/gnd/',
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

/** Returns resolver URL for PID field values ({value, label}): URN via nbn-resolving,
 *  ARK via n2t.net, plain http(s) URLs as-is. */
export function pidUrl(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  const pidValue = typeof obj.value === 'string' ? obj.value.trim() : ''
  if (!pidValue) return undefined
  const lower = pidValue.toLowerCase()
  if (lower.startsWith('urn:')) return `${PID_RESOLVER_BASE}${pidValue}`
  if (lower.startsWith('ark:')) return `https://n2t.net/${pidValue}`
  if (lower.startsWith('http://') || lower.startsWith('https://')) return pidValue
  return undefined
}

/** Returns the link target for URL field values ({value, label}), or undefined. */
export function urlHref(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  const url = typeof obj.value === 'string' ? obj.value.trim() : ''
  if (!url || !/^https?:\/\//i.test(url)) return undefined
  return url
}

/** Converts a single EDTF-lite qualified date ("1900~", "1900?", "1900~?") to display text. */
function formatQualifiedDate(value: string): string {
  const formatBce = (date: string) => {
    const match = /^-(\d{4})(.*)$/.exec(date)
    return match ? `${Number(match[1]) + 1}${match[2]} v. Chr.` : date
  }
  for (const [suffix, wrap] of [
    ['~?', (d: string) => `ca. ${d} (unsicher)`],
    ['~', (d: string) => `ca. ${d}`],
    ['?', (d: string) => `${d} (unsicher)`],
  ] as const) {
    if (value.endsWith(suffix)) return wrap(formatBce(value.slice(0, -suffix.length)))
  }
  return formatBce(value)
}

/** Converts a canonical EDTF-lite date value (single or "START/END" range) to display text. */
export function formatDateValue(value: string): string {
  if (value.includes('/')) {
    const [start, end] = value.split('/')
    if (!start) return `vor ${formatQualifiedDate(end)}`
    if (!end) return `nach ${formatQualifiedDate(start)}`
    return `${formatQualifiedDate(start)}–${formatQualifiedDate(end)}`
  }
  return formatQualifiedDate(value)
}

/**
 * Converts a metadata field value to a human-readable string for display.
 * Returns null if the value is empty / should be skipped.
 */
export function renderFieldValue(value: unknown, locale?: string, fieldType?: string): string | null {
  if (value == null) return null

  if (fieldType === 'date') {
    if (typeof value === 'string') return value ? formatDateValue(value) : null
    if (Array.isArray(value)) {
      const parts = value.filter((v): v is string => typeof v === 'string' && v !== '').map(formatDateValue)
      return parts.length > 0 ? parts.join(', ') : null
    }
  }

  // Authority entry {source, external_id, label} / translatable field {lang: text}
  if (typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>
    if (typeof obj.label === 'string' && obj.label) return obj.label
    if (typeof obj.value === 'string' && obj.value) return obj.value
    // Translatable field: prefer active locale → de → en → first non-empty value.
    const preferred = [locale, 'de', 'en'].filter((l, i, a): l is string => Boolean(l) && a.indexOf(l) === i)
    for (const lang of preferred) {
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

/** Extracts the raw keyword-facet string for a single metadata item, mirroring the
 *  backend's `_extract_display_value`/`_extract_facet_value` (search_service.py): dict
 *  values use `label` then `value`; booleans stringify Python-style ("True"/"False");
 *  everything else is the plain string form. Returns null for items with nothing to facet. */
function facetRawValue(item: unknown): string | null {
  if (item != null && typeof item === 'object' && !Array.isArray(item)) {
    const o = item as Record<string, unknown>
    if (typeof o.label === 'string' && o.label) return o.label
    if (typeof o.value === 'string' && o.value) return o.value
    return null
  }
  if (typeof item === 'boolean') return item ? 'True' : 'False'
  if (item != null) return String(item)
  return null
}

/** Pairs each metadata item with its facet-filter raw value (matching the `facet_all_<field>`
 *  term indexed in Elasticsearch) and its human-readable display text, so detail pages can
 *  render a click-to-filter link per value for fields marked `is_facet`. */
export function facetItems(value: unknown, locale?: string, fieldType?: string): { display: string; raw: string }[] {
  const entries = Array.isArray(value) ? value : [value]
  return entries
    .map(item => {
      const raw = facetRawValue(item)
      if (raw === null) return null
      const display = renderFieldValue(item, locale, fieldType) ?? raw
      return { display, raw }
    })
    .filter((entry): entry is { display: string; raw: string } => entry !== null)
}

/** Pick a human-readable display title from record metadata.
 *  Tries common label fields in order, resolves repeatable/translatable
 *  values via renderFieldValue, and falls back to id/idno when nothing matches.
 */
export function recordTitle(
  metadata: Record<string, unknown>,
  locale?: string,
  fallback?: string | null,
): string {
  const candidates = [
    metadata.title,
    metadata.name,
    metadata.label,
    metadata.display_name,
    metadata.place_name,
  ]
  for (const raw of candidates) {
    const rendered = renderFieldValue(raw, locale)
    if (rendered) return rendered
  }
  return fallback ?? ''
}
