const KEY = 'katalon_last_search'

export function saveLastSearch(url: string): void {
  sessionStorage.setItem(KEY, url)
}

export function useBackToSearch(): string | null {
  return sessionStorage.getItem(KEY)
}
