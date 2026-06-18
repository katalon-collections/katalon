import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { VocabTerm } from '../api/client'

// Module-level cache: one API round-trip per browser session
let _promise: Promise<Record<string, VocabTerm>> | null = null

function loadRelationTypeLabels(): Promise<Record<string, VocabTerm>> {
  if (_promise) return _promise
  _promise = api.vocabularies.list()
    .then(async vocabs => {
      const rt = vocabs.find(v => v.name === 'relation_types')
      if (!rt) return {}
      const terms = await api.vocabularies.terms(rt.id)
      const map: Record<string, VocabTerm> = {}
      for (const t of terms) {
        map[t.term] = t
      }
      return map
    })
    .catch(() => {
      _promise = null  // allow retry on next mount if fetch failed
      return {}
    })
  return _promise
}

/**
 * Returns a resolver: (code, isFrom) => human-readable label.
 * When isFrom=false (current record is the relation target), inverse_label is used.
 */
export function useRelationTypeLabels(lang = 'de') {
  const [termMap, setTermMap] = useState<Record<string, VocabTerm>>({})

  useEffect(() => {
    loadRelationTypeLabels().then(setTermMap)
  }, [])

  return (code: string, isFrom = true): string => {
    const term = termMap[code]
    if (!term) return code
    const labelObj = isFrom ? term.label : (term.inverse_label ?? term.label)
    return labelObj[lang] ?? labelObj['en'] ?? code
  }
}
