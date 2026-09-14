// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { BASE, PORTAL_API, type RecordSubtype } from '../api/client'

// Module-level cache: one API round-trip per browser session, independent of locale
// (the raw multilingual labels are cached; resolution to a display string happens per-locale below).
let _promise: Promise<RecordSubtype[]> | null = null

function loadRecordSubtypes(): Promise<RecordSubtype[]> {
  if (!_promise) {
    _promise = fetch(`${BASE}${PORTAL_API}/record-subtypes`)
      .then(r => r.ok ? r.json() as Promise<RecordSubtype[]> : [])
      .catch(() => {
        _promise = null  // allow retry on next mount if fetch failed
        return []
      })
  }
  return _promise
}

/**
 * Resolves a record subtype's technical name (e.g. `kunsthandwerk`, stored as
 * `object_type`/`entity_type`/... and indexed as the ES `subtype` facet value)
 * to its admin-configured, human-readable label. Falls back through the active
 * locale, then `de`, then `en`, then the raw technical name if no label is set.
 */
export function useRecordSubtypeLabels(locale: string) {
  const [subtypes, setSubtypes] = useState<RecordSubtype[]>([])

  useEffect(() => {
    let cancelled = false
    loadRecordSubtypes().then(list => { if (!cancelled) setSubtypes(list) })
    return () => { cancelled = true }
  }, [])

  return (name: string): string => {
    const subtype = subtypes.find(s => s.name === name)
    if (!subtype) return name
    return [subtype.label?.[locale], subtype.label?.de, subtype.label?.en]
      .find(value => value?.trim()) ?? name
  }
}
