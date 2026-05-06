import { useEffect, useState } from 'react'
import { api, BASE } from '../api/client'

// Module-level cache: one API round-trip per browser session
let _promise: Promise<Record<string, Record<string, string>>> | null = null

function loadRelationTypeLabels(): Promise<Record<string, Record<string, string>>> {
  if (_promise) return _promise
  _promise = api.vocabularies.list()
    .then(async vocabs => {
      const rt = vocabs.find(v => v.name === 'relation_types')
      if (!rt) return {}
      const terms = await api.vocabularies.terms(rt.id)
      const map: Record<string, Record<string, string>> = {}
      for (const t of terms) {
        map[t.term] = t.label
      }
      return map
    })
    .catch(() => {
      _promise = null  // allow retry on next mount if fetch failed
      return {}
    })
  return _promise
}

/** Returns a resolver function that maps a relation_type code to a human-readable label. */
export function useRelationTypeLabels(lang = 'de') {
  const [labelMap, setLabelMap] = useState<Record<string, Record<string, string>>>({})

  useEffect(() => {
    loadRelationTypeLabels().then(setLabelMap)
  }, [])

  return (code: string): string => {
    const entry = labelMap[code]
    if (!entry) return code
    return entry[lang] ?? entry['en'] ?? code
  }
}
