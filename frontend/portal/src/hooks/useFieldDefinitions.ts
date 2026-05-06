import { useEffect, useState } from 'react'
import { BASE } from '../api/client'

export interface FieldDefinition {
  id: string
  name: string
  label: Record<string, string>
  field_type: string
  is_required: boolean
  is_repeatable: boolean
  sort_order: number
  settings: Record<string, unknown>
  show_in_detail: boolean
}

export function useFieldDefinitions(targetType: string): FieldDefinition[] {
  const [defs, setDefs] = useState<FieldDefinition[]>([])

  useEffect(() => {
    let cancelled = false
    fetch(`${BASE}/v1/schema/${targetType}`)
      .then(r => r.ok ? r.json() : [])
      .then((fields: FieldDefinition[]) => {
        if (!cancelled) setDefs(Array.isArray(fields) ? fields : [])
      })
      .catch(() => { if (!cancelled) setDefs([]) })
    return () => { cancelled = true }
  }, [targetType])

  return defs
}
