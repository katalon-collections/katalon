// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { api } from '../api/client'

// Module-level cache: one API round-trip per primary_type per browser session
const _promises: Record<string, Promise<Record<string, string>>> = {}

function loadSubtypePlaceholders(primaryType: string): Promise<Record<string, string>> {
  if (!_promises[primaryType]) {
    _promises[primaryType] = api.recordSubtypes.list(primaryType)
      .then(subtypes => {
        const map: Record<string, string> = {}
        for (const s of subtypes) if (s.placeholder_image_url) map[s.name] = s.placeholder_image_url
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
 * Resolves a record's admin-configured subtype (e.g. `object_type`, stored as
 * `record_subtypes.name`) to the portal placeholder image configured for that subtype
 * (`record_subtypes.placeholder_image_url`), for use when the record itself has no media.
 * Returns '' when the subtype has no placeholder configured.
 */
export function useSubtypePlaceholder(primaryType: string) {
  const [placeholders, setPlaceholders] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    loadSubtypePlaceholders(primaryType).then(map => { if (!cancelled) setPlaceholders(map) })
    return () => { cancelled = true }
  }, [primaryType])

  return (name: string | null | undefined): string => (name && placeholders[name]) || ''
}
