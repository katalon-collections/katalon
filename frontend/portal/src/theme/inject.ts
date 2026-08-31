import type { ThemeManifest } from './defaults'
import { DEFAULT_TOKENS } from './defaults'

export function applyTheme(theme: ThemeManifest | null): void {
  const root = document.documentElement
  const tokens = { ...DEFAULT_TOKENS, ...(theme?.tokens ?? {}) }

  for (const [k, v] of Object.entries(tokens)) {
    root.style.setProperty(k, v)
  }

  if (theme?.fonts?.body) {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = theme.fonts.body
    document.head.appendChild(link)
  }

  if (theme?.favicon) {
    const el = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
      ?? Object.assign(document.createElement('link'), { rel: 'icon' })
    el.href = `/themes/${theme.favicon}`
    document.head.appendChild(el)
  }

}
