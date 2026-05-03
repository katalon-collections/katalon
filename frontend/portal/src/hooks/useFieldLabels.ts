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
    fetch(`${BASE}/v1/schema/fields?target_type=${targetType}`)
      .then(r => r.ok ? r.json() : [])
      .then((fields: FieldDefinition[]) => {
        const map: Record<string, string> = {}
        for (const f of fields) {
          map[f.name] = f.label?.de ?? f.label?.en ?? f.name
        }
        setLabels(map)
      })
      .catch(() => setLabels({}))
  }, [targetType])

  return labels
}
