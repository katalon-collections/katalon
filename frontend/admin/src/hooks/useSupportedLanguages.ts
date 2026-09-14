// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { req } from '../api/client'

const DEFAULT_LANGUAGES = ['de', 'en']

let _cached: string[] | null = null
let _promise: Promise<string[]> | null = null

function loadLanguages(): Promise<string[]> {
  if (_cached) return Promise.resolve(_cached)
  if (!_promise) {
    _promise = req<{ supported_languages?: string[] }>('/v1/portal/config')
      .then(cfg => {
        const langs = cfg.supported_languages
        _cached = langs && langs.length > 0 ? langs : DEFAULT_LANGUAGES
        return _cached
      })
      .catch(() => DEFAULT_LANGUAGES)
  }
  return _promise
}

/** Configured content languages (ordered, first = primary/fallback). */
export function useSupportedLanguages(): string[] {
  const [languages, setLanguages] = useState<string[]>(_cached ?? DEFAULT_LANGUAGES)
  useEffect(() => {
    loadLanguages().then(setLanguages)
  }, [])
  return languages
}
