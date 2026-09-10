// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { BASE, PORTAL_API, type PortalFieldDefinition } from '../api/client'

export type FieldDefinition = PortalFieldDefinition

/**
 * Returns [fields, loading]. The detail pages fold `loading` into their own loading gate:
 * detail_slot/detail_role now decide what's in the main column vs. the sidebar (including
 * whether the record is "metadata only"), so rendering before fields have arrived would
 * briefly show the wrong layout and then jump once they load.
 */
export function useFieldDefinitions(targetType: string): [FieldDefinition[], boolean] {
  const [defs, setDefs] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${BASE}${PORTAL_API}/schema/${targetType}`)
      .then(r => r.ok ? r.json() : [])
      .then((fields: FieldDefinition[]) => {
        if (!cancelled) { setDefs(Array.isArray(fields) ? fields : []); setLoading(false) }
      })
      .catch(() => { if (!cancelled) { setDefs([]); setLoading(false) } })
    return () => { cancelled = true }
  }, [targetType])

  return [defs, loading]
}
