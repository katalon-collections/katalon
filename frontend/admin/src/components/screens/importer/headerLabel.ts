// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

/** Readable column title: XML selectors are Clark-notation paths ("{ns}a/{ns}b/{ns}c"); show the last two steps. */
export function headerLabel(header: string): string {
  if (!header.startsWith('{')) return header
  const steps = header.replace(/\{[^}]*\}/g, '').split('/').filter(Boolean)
  return steps.length > 2 ? `…/${steps.slice(-2).join('/')}` : steps.join('/')
}
