// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import { formatDateValue, isLeapYear, isValidDateInput, normalizeDateInput, parseDateText } from './dateInput'

describe('isLeapYear (proleptic Gregorian incl. BCE)', () => {
  it('treats astronomical year 0 (1 BCE) and multiples of 4/400 as leap years', () => {
    expect(isLeapYear(2000)).toBe(true)
    expect(isLeapYear(2024)).toBe(true)
    expect(isLeapYear(0)).toBe(true)
    expect(isLeapYear(-4)).toBe(true)
    expect(isLeapYear(-400)).toBe(true)
  })

  it('rejects century non-leap years in both CE and BCE', () => {
    expect(isLeapYear(1900)).toBe(false)
    expect(isLeapYear(2023)).toBe(false)
    expect(isLeapYear(-43)).toBe(false)
    expect(isLeapYear(-100)).toBe(false)
    expect(isLeapYear(-1)).toBe(false)
  })
})

describe('normalizeDateInput', () => {
  it('pads BCE and early CE years to four digits', () => {
    expect(normalizeDateInput('-43')).toBe('-0043')
    expect(normalizeDateInput('-43-06')).toBe('-0043-06')
    expect(normalizeDateInput('-43-06-15')).toBe('-0043-06-15')
    expect(normalizeDateInput('-1-12-31')).toBe('-0001-12-31')
    expect(normalizeDateInput('100')).toBe('0100')
    expect(normalizeDateInput('50-03-04')).toBe('0050-03-04')
  })

  it('normalizes astronomical year 0 without negative zero', () => {
    expect(normalizeDateInput('0')).toBe('0000')
    expect(normalizeDateInput('0000')).toBe('0000')
    expect(normalizeDateInput('-0')).toBe('0000')
    expect(normalizeDateInput('-0000')).toBe('0000')
    expect(normalizeDateInput('-0000-02-29')).toBe('0000-02-29')
  })

  it('converts valid European dd.mm.yyyy dates to ISO and leaves invalid ones unchanged', () => {
    expect(normalizeDateInput('15.06.1980')).toBe('1980-06-15')
    expect(normalizeDateInput('5.3.1900')).toBe('1900-03-05')
    expect(normalizeDateInput('31.02.2020')).toBe('31.02.2020')
  })

  it('normalizes EDTF-lite qualifiers and German words for CE and BCE dates', () => {
    expect(normalizeDateInput('ca. -43')).toBe('-0043~')
    expect(normalizeDateInput('um 1900')).toBe('1900~')
    expect(normalizeDateInput('-43 (unsicher)')).toBe('-0043?')
    expect(normalizeDateInput('ca. -43 (unsicher)')).toBe('-0043~?')
    expect(normalizeDateInput('ca. 0')).toBe('0000~')
  })

  it('normalizes closed and open date ranges including BCE bounds', () => {
    expect(normalizeDateInput('-100/-43')).toBe('-0100/-0043')
    expect(normalizeDateInput('-100 bis -43')).toBe('-0100/-0043')
    expect(normalizeDateInput('ca. -100 bis 50?')).toBe('-0100~/0050?')
    expect(normalizeDateInput('vor -43')).toBe('/-0043')
    expect(normalizeDateInput('nach -43')).toBe('-0043/')
  })
})

describe('isValidDateInput', () => {
  it('accepts valid BCE, year-0, CE, qualified, and range dates', () => {
    const valid = [
      '-0043',
      '-43',
      '-0043-06',
      '-0043-06-15',
      '-0001-12-31',
      '0000',
      '0',
      '-0',
      '0000-02-29',
      '-0004-02-29',
      '-0400-02-29',
      '-4000-01-01',
      '1987-08-10',
      '15.06.1980',
      '-0043~',
      '-0043?',
      '-0043~?',
      'ca. -43 (unsicher)',
      '-0100/-0043',
      '-0043/',
      '/-0043',
      'vor -43',
      'nach 0',
    ]
    for (const value of valid) {
      expect(isValidDateInput(value), value).toBe(true)
    }
  })

  it('rejects invalid calendar dates, non-leap BCE Feb 29, and malformed ranges', () => {
    const invalid = [
      '--0043',
      '-0043-00',
      '-0043-13',
      '-0043-00-01',
      '-0043-13-01',
      '-0043-06-00',
      '-0043-06-31',
      '-0043-02-29',
      '-0100-02-29',
      '1900-02-29',
      '1987-08-46',
      '31.02.2020',
      '1900!',
      '/',
      '1900/1950/2000',
      '-0043-13~',
      'nicht-ein-datum',
    ]
    for (const value of invalid) {
      expect(isValidDateInput(value), value).toBe(false)
    }
  })
})

describe('display and typed dates', () => {
  it.each([
    ['-43', '-0042', '43 v. Chr.'],
    ['43 v. Chr.', '-0042', '43 v. Chr.'],
    ['1 v. Chr.', '0000', '1 v. Chr.'],
    ['ca. -43', '-0042~', 'ca. 43 v. Chr.'],
    ['vor 43 v. Chr.', '/-0042', 'vor 43 v. Chr.'],
    ['43 v. Chr.–14 n. Chr.', '-0042/0014', '43 v. Chr.–0014'],
    ['ca. 1900', '1900~', 'ca. 1900'],
    ['vor 1800', '/1800', 'vor 1800'],
    ['bis 1800', '/1800', 'vor 1800'],
    ['1900 (unsicher)', '1900?', '1900 (unsicher)'],
    ['12.05.1900', '1900-05-12', '1900-05-12'],
  ])('%s', (typed, stored, shown) => {
    expect(parseDateText(typed)).toBe(stored)
    expect(formatDateValue(stored, 'de')).toBe(shown)
    // What the field shows parses back to the same stored value.
    expect(parseDateText(shown)).toBe(stored)
    expect(parseDateText(formatDateValue(stored, 'en'))).toBe(stored)
    expect(isValidDateInput(stored)).toBe(true)
  })

  it.each(['-0', '0 v. Chr.', '31.02.2000', 'abc'])('rejects %s', typed => {
    expect(isValidDateInput(parseDateText(typed))).toBe(false)
  })
})
