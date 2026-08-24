import { useEffect, useState } from 'react'
import { BASE, PORTAL_API } from '../api/client'

export interface FieldDefinition {
  id: string
  name: string
  label: Record<string, string>
  field_type: string
}

export function useFieldLabels(targetTypesKey: string, locale: string) {
  const [labels, setLabels] = useState<Record<string, Record<string, string>>>({})

  useEffect(() => {
    let cancelled = false
    const targetTypes = targetTypesKey.split(',').filter(Boolean)
    Promise.all(targetTypes.map(async targetType => {
      const response = await fetch(`${BASE}${PORTAL_API}/schema/${targetType}`)
      return [targetType, response.ok ? await response.json() as FieldDefinition[] : []] as const
    }))
      .then(results => {
        if (cancelled) return
        const map: Record<string, Record<string, string>> = {}
        for (const [targetType, fields] of results) {
          map[targetType] = {}
          for (const field of fields) {
            const label = [field.label?.[locale], field.label?.de, field.label?.en]
              .find(value => value?.trim())
            map[targetType][field.name] = label ?? field.name
          }
        }
        setLabels(map)
      })
      .catch(() => {
        if (!cancelled) setLabels({})
    })
    return () => { cancelled = true }
  }, [targetTypesKey, locale])

  return labels
}
