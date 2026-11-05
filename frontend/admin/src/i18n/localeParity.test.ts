// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'

const de = import.meta.glob('./locales/de/*.json', { eager: true, import: 'default' })
const en = import.meta.glob('./locales/en/*.json', { eager: true, import: 'default' })

function keyPaths(value: unknown, prefix = ''): string[] {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return [prefix]
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    keyPaths(child, prefix ? `${prefix}.${key}` : key),
  )
}

const namespaces = Object.keys(de).map(path => path.replace('./locales/de/', ''))

describe('admin locale parity', () => {
  it('has an English file for every German namespace', () => {
    expect(Object.keys(en).map(path => path.replace('./locales/en/', '')).sort()).toEqual([...namespaces].sort())
  })

  it.each(namespaces)('%s has the same keys in German and English', file => {
    const deKeys = keyPaths(de[`./locales/de/${file}`]).sort()
    const enKeys = keyPaths(en[`./locales/en/${file}`]).sort()
    expect(enKeys).toEqual(deKeys)
  })
})
