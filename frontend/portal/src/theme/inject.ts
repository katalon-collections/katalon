// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { ThemeManifest } from './defaults'

/** Tokens and the theme stylesheet come render-blocking from
 *  /portal/v1/theme.css (linked in index.html); this adds the rest. */
export function applyTheme(theme: ThemeManifest | null): void {
  const script = themeScriptSrc(theme)
  if (script && !document.querySelector(`script[data-theme-script]`)) {
    // Same-origin file from the theme directory only (CSP script-src 'self').
    const el = document.createElement('script')
    el.src = script
    el.defer = true
    el.dataset.themeScript = 'true'
    document.head.appendChild(el)
  }

  if (theme?.favicon) {
    const el = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
      ?? Object.assign(document.createElement('link'), { rel: 'icon' })
    el.href = `/themes/${theme.favicon}`
    document.head.appendChild(el)
  }

}

const SCRIPT_PATH = /^(?!.*\.\.)[A-Za-z0-9_][A-Za-z0-9_./-]*\.js$/
const DIRECTORY = /^[A-Za-z0-9_-]+$/

/** URL of the theme's optional script, or null unless it is a plain .js path
 *  inside the theme directory (the API validates this too). */
export function themeScriptSrc(theme: ThemeManifest | null): string | null {
  if (!theme?.script || !theme.directory) return null
  if (!SCRIPT_PATH.test(theme.script) || !DIRECTORY.test(theme.directory)) return null
  return `/themes/${theme.directory}/${theme.script}`
}
