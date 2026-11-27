// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { formatDateValue, renderFieldValue } from './renderFieldValue'

describe('formatDateValue', () => {
  it('formats negative ISO years using astronomical year-0 offset (de default)', () => {
    expect(formatDateValue('-0043')).toBe('44 v. Chr.')
    expect(formatDateValue('-0043-06-15')).toBe('44-06-15 v. Chr.')
    expect(formatDateValue('-0001')).toBe('2 v. Chr.')
    expect(formatDateValue('-0001-12-31')).toBe('2-12-31 v. Chr.')
  })

  it('formats astronomical year 0 (0000) as 1 v. Chr. / 1 BCE', () => {
    expect(formatDateValue('0000')).toBe('1 v. Chr.')
    expect(formatDateValue('0000-02-29')).toBe('1-02-29 v. Chr.')
    expect(formatDateValue('0000~')).toBe('ca. 1 v. Chr.')
    expect(formatDateValue('0000', 'en')).toBe('1 BCE')
    expect(formatDateValue('0000-06-15', 'en')).toBe('1-06-15 BCE')
  })

  it('leaves CE dates untouched and supports qualifiers and ranges in de and en', () => {
    expect(formatDateValue('0001')).toBe('0001')
    expect(formatDateValue('1900')).toBe('1900')
    expect(formatDateValue('-0043~', 'de')).toBe('ca. 44 v. Chr.')
    expect(formatDateValue('-0043?', 'de')).toBe('44 v. Chr. (unsicher)')
    expect(formatDateValue('-0043~?', 'de')).toBe('ca. 44 v. Chr. (unsicher)')
    expect(formatDateValue('-0100/-0043', 'de')).toBe('101 v. Chr.–44 v. Chr.')
    expect(formatDateValue('/-0043', 'de')).toBe('vor 44 v. Chr.')
    expect(formatDateValue('-0043/', 'de')).toBe('nach 44 v. Chr.')

    expect(formatDateValue('-0043', 'en')).toBe('44 BCE')
    expect(formatDateValue('-0043~', 'en')).toBe('ca. 44 BCE')
    expect(formatDateValue('-0043?', 'en')).toBe('44 BCE (uncertain)')
    expect(formatDateValue('-0043~?', 'en')).toBe('ca. 44 BCE (uncertain)')
    expect(formatDateValue('-0100/0000', 'en')).toBe('101 BCE–1 BCE')
    expect(formatDateValue('/-0043', 'en')).toBe('before 44 BCE')
    expect(formatDateValue('-0043/', 'en')).toBe('after 44 BCE')
  })
})

describe('renderFieldValue for date fields', () => {
  it('passes locale through for single and repeatable BCE date fields', () => {
    expect(renderFieldValue('-0043', 'de', 'date')).toBe('44 v. Chr.')
    expect(renderFieldValue('-0043', 'en', 'date')).toBe('44 BCE')
    expect(renderFieldValue(['-0043', '0000~'], 'en', 'date')).toBe('44 BCE, ca. 1 BCE')
  })
})
