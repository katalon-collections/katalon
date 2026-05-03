import { useEffect, useState } from 'react'
import { BASE } from '../api/client'

export interface FieldDefinition {
  id: string
  name: string
  label: Record<string, string>
  field_type: string
}

export function useFieldLabels(targetType: string) {
  const [labels, setLabels] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    fetch(`${BASE}/v1/schema/${targetType}`)
      .then(r => r.ok ? r.json() : [])
      .then((fields: FieldDefinition[]) => {
        if (cancelled) return
        const map: Record<string, string> = {}
        for (const f of fields) {
          if (f && f.name) {
            map[f.name] = f.label?.de ?? f.label?.en ?? f.name
          }
        }
        setLabels(map)
      })
      .catch(() => {
        if (!cancelled) setLabels({})
      })
    return () => { cancelled = true }
  }, [targetType])

  return labels
}
