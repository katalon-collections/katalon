// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { FormVariant } from '../types'
import { resolveActiveVariant } from './formVariants'

function variant(id: string, overrides: Partial<FormVariant> = {}): FormVariant {
  return { id, name: id, target_type: 'object', target_subtype: null, label: {}, field_names: [], is_default_global: false, sort_order: 0, is_deleted: false, default_for_roles: [], ...overrides }
}

describe('resolveActiveVariant', () => {
  const global = variant('global', { is_default_global: true })
  const role = variant('role', { default_for_roles: ['editor'] })
  const context = variant('context')
  const variants = [global, role, context]

  it('prefers an explicit context over role and global defaults', () => {
    expect(resolveActiveVariant(variants, 'editor', 'context')).toBe(context)
  })

  it('falls back from a missing context to the role default', () => {
    expect(resolveActiveVariant(variants, 'editor', 'deleted')).toBe(role)
  })

  it('uses the global default when the role has no default', () => {
    expect(resolveActiveVariant(variants, 'viewer')).toBe(global)
  })

  it('returns the full-schema fallback when no default exists', () => {
    expect(resolveActiveVariant([context], 'editor')).toBeNull()
    expect(resolveActiveVariant([], 'editor')).toBeNull()
  })
})
