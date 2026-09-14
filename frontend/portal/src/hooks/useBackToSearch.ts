// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { BASE, PORTAL_API, type SearchResponse } from '../api/client'

const KEY = 'katalon_last_search'
const CONTEXT_KEY = 'katalon_search_context'

export interface SearchContextItem {
  id: string
  record_type: string
}

export interface SearchContext {
  url: string
  items: SearchContextItem[]
  page: number
  pageSize: number
  total: number
  index: number
}

export function saveLastSearch(url: string): void {
  sessionStorage.setItem(KEY, url)
}

export function saveSearchContext(context: SearchContext): void {
  sessionStorage.setItem(CONTEXT_KEY, JSON.stringify(context))
}

export function useBackToSearch(): string | null {
  return sessionStorage.getItem(KEY)
}

function readSearchContext(recordId: string): SearchContext | null {
  try {
    const context = JSON.parse(sessionStorage.getItem(CONTEXT_KEY) ?? '') as SearchContext
    const index = context.items.findIndex(item => item.id === recordId)
    return index >= 0 ? { ...context, index } : null
  } catch {
    return null
  }
}

function recordPath(item: SearchContextItem): string {
  const segment = item.record_type === 'entity' ? 'entities'
    : item.record_type === 'place' ? 'places'
    : item.record_type === 'occurrence' ? 'occurrences'
    : item.record_type === 'collection' ? 'collections'
    : 'objects'
  return `/${segment}/${item.id}`
}

async function loadPage(context: SearchContext, page: number): Promise<SearchContextItem[] | null> {
  const search = new URL(context.url, window.location.origin)
  if (search.searchParams.has('aq')) return null
  search.searchParams.set('page', String(page))
  search.searchParams.set('page_size', String(context.pageSize))
  const response = await fetch(`${BASE}${PORTAL_API}/search?${search.searchParams}`)
  if (!response.ok) return null
  const data = await response.json() as SearchResponse
  return data.items.map(({ id, record_type }) => ({ id, record_type }))
}

export function useSearchResultNavigation(recordId: string) {
  const [context, setContext] = useState<SearchContext | null>(() => readSearchContext(recordId))
  const [loading, setLoading] = useState(false)

  useEffect(() => setContext(readSearchContext(recordId)), [recordId])

  const canLoadPage = !!context && !new URL(context.url, window.location.origin).searchParams.has('aq')
  const canPrevious = !!context && (context.index > 0 || (canLoadPage && context.page > 1))
  const canNext = !!context && (context.index < context.items.length - 1 || (canLoadPage && context.page * context.pageSize < context.total))

  async function move(direction: -1 | 1): Promise<string | null> {
    if (!context || loading) return null
    const nextIndex = context.index + direction
    if (nextIndex >= 0 && nextIndex < context.items.length) {
      const next = { ...context, index: nextIndex }
      saveSearchContext(next)
      setContext(next)
      return recordPath(next.items[nextIndex])
    }

    const page = direction < 0 ? context.page - 1 : context.page + Math.ceil(context.items.length / context.pageSize)
    if (page < 1) return null
    setLoading(true)
    try {
      const items = await loadPage(context, page)
      if (!items?.length) return null
      const next = { ...context, items, page, index: direction < 0 ? items.length - 1 : 0 }
      saveSearchContext(next)
      setContext(next)
      return recordPath(next.items[next.index])
    } finally {
      setLoading(false)
    }
  }

  return { canPrevious, canNext, loading, move }
}
