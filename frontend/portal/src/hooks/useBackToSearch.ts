// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

const KEY = 'katalon_last_search'

export function saveLastSearch(url: string): void {
  sessionStorage.setItem(KEY, url)
}

export function useBackToSearch(): string | null {
  return sessionStorage.getItem(KEY)
}
