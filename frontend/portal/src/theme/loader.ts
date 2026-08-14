import type { ThemeManifest } from './defaults'
import { BASE, PORTAL_API } from '../api/client'
import { applyTheme } from './inject'

export async function loadAndApplyTheme(): Promise<ThemeManifest | null> {
  try {
    const res = await fetch(`${BASE}${PORTAL_API}/theme`)
    if (!res.ok) return null
    const theme: ThemeManifest = await res.json()
    applyTheme(theme)
    return theme
  } catch {
    applyTheme(null)
    return null
  }
}
