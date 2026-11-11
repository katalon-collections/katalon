// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { headerLabel } from './headerLabel'

describe('headerLabel', () => {
  it('keeps plain CSV headers', () => {
    expect(headerLabel('Titel')).toBe('Titel')
  })

  it('shortens Clark-notation paths to the last two steps', () => {
    const ns = '{http://www.lido-schema.org}'
    expect(headerLabel(`${ns}titleSet/${ns}appellationValue`)).toBe('titleSet/appellationValue')
    expect(headerLabel(`${ns}a/${ns}b/${ns}titleSet/${ns}appellationValue`)).toBe('…/titleSet/appellationValue')
    expect(headerLabel(`${ns}placeID@${ns}type`)).toBe('placeID@type')
  })
})
