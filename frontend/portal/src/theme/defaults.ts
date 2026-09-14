// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export const DEFAULT_TOKENS: Record<string, string> = {
  '--accent':       '#1e3a8a',
  '--accent-50':    '#eef2fb',
  '--accent-100':   '#dde3f5',
  '--accent-ink':   '#15296b',
  '--bg':           '#f4f5f7',
  '--panel':        '#ffffff',
  '--panel-2':      '#fafbfc',
  '--border':       '#e4e6eb',
  '--fg':           '#181a1f',
  '--fg-2':         '#3a4150',
  '--fg-3':         '#5a6173',
  '--fg-4':         '#8a92a3',
  '--header-bg':    '#0b1a33',
  '--header-fg':    '#ffffff',
}

export interface ThemeManifest {
  name: string
  version?: string
  tokens?: Record<string, string>
  fonts?: { body?: string | null; mono?: string | null }
  logo?: string | null
  favicon?: string | null
}
