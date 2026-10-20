// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export interface ThemeManifest {
  name: string
  version?: string
  tokens?: Record<string, string>
  fonts?: { body?: string | null; mono?: string | null }
  logo?: string | null
  favicon?: string | null
  /** Optional script file inside the theme directory (theme.json "script"). */
  script?: string | null
  /** Theme directory name under /themes/ (added by the API). */
  directory?: string | null
}
