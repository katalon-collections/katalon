// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { api } from '../api/client'

// Module-level cache: one API round-trip per primary_type per browser session
const _promises: Record<string, Promise<Record<string, Record<string, string>>>> = {}

function loadSubtypeLabels(primaryType: string): Promise<Record<string, Record<string, string>>> {
  if (!_promises[primaryType]) {
    _promises[primaryType] = api.recordSubtypes.list(primaryType)
      .then(subtypes => {
        const map: Record<string, Record<string, string>> = {}
        for (const s of subtypes) map[s.name] = s.label
        return map
      })
      .catch(() => {
        delete _promises[primaryType]  // allow retry on next mount if fetch failed
        return {}
      })
  }
  return _promises[primaryType]
}

/**
 * Resolves a record's admin-configured subtype (`collection_type`, `object_type`, …,
 * stored as `record_subtypes.name`) to its human-readable `label`. Falls back to the
 * raw slug when no matching subtype or translation exists.
 */
export function useSubtypeLabel(primaryType: string, lang = 'de') {
  const [labels, setLabels] = useState<Record<string, Record<string, string>>>({})

  useEffect(() => {
    let cancelled = false
    loadSubtypeLabels(primaryType).then(map => { if (!cancelled) setLabels(map) })
    return () => { cancelled = true }
  }, [primaryType])

  return (name: string | null | undefined): string | null => {
    if (!name) return null
    const label = labels[name]
    return label?.[lang] ?? label?.en ?? name
  }
}
