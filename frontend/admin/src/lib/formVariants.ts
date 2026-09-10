// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { FormVariant } from '../types'

/**
 * Priority chain: context override > role default > global default > null
 * (fallback = full schema, current behavior). No choice is remembered across
 * records or page loads — the configured default always applies.
 */
export function resolveActiveVariant(
  variants: FormVariant[],
  currentRole: string,
  contextHint?: string | null,
): FormVariant | null {
  if (contextHint) {
    const hinted = variants.find(v => v.id === contextHint)
    if (hinted) return hinted
  }
  const roleDefault = variants.find(v => v.default_for_roles.includes(currentRole))
  if (roleDefault) return roleDefault
  const globalDefault = variants.find(v => v.is_default_global)
  if (globalDefault) return globalDefault
  return null
}
