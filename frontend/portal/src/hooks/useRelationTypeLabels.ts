// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { VocabTerm } from '../api/client'
import { resolveLabel } from '../utils/facets'

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

  return (code: string, isFrom = true): string => relationTypeLabel(termMap[code], code, isFrom, lang)
}

/** Label of a relation type in `lang`, falling back to the other languages (a vocabulary
 *  maintained in German only must not show raw codes in the English portal), then `code`. */
export function relationTypeLabel(term: VocabTerm | undefined, code: string, isFrom: boolean, lang: string): string {
  if (!term) return code
  const inverse = isFrom ? '' : resolveLabel(term.inverse_label, lang)
  return inverse || resolveLabel(term.label, lang, code)
}
