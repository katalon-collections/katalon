// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

/** Proleptic Gregorian leap rule; also correct for BCE years (year 0 = 1 v. Chr.). */
export function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
}

export function daysInMonth(year: number, month: number): number {
  return [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
}

/** Normalizes a single (unqualified) date: European dd.mm.yyyy → ISO, BCE/CE year padding. */
export function normalizeBareDate(value: string): string {
  const trimmed = value.trim()
  const european = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(trimmed)
  if (european) {
    const [, day, month, year] = european
    const iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
    const parsed = new Date(`${iso}T00:00:00Z`)
    if (parsed.getUTCFullYear() === Number(year) &&
      parsed.getUTCMonth() + 1 === Number(month) &&
      parsed.getUTCDate() === Number(day)) {
      return iso
    }
    return trimmed
  }
  // BCE years: pad the year to 4 digits, e.g. "-43" → "-0043" (44 v. Chr.);
  // astronomical year 0 has no sign ("-0" / "-0000" → "0000").
  const bce = /^-(\d{1,4})(-\d{2}(-\d{2})?)?$/.exec(trimmed)
  if (bce) {
    const padded = bce[1].padStart(4, '0')
    return padded === '0000' ? `0000${bce[2] ?? ''}` : `-${padded}${bce[2] ?? ''}`
  }
  // CE years under 1000: pad the year to 4 digits, e.g. "100" → "0100"
  const ce = /^(\d{1,4})(-\d{2}(-\d{2})?)?$/.exec(trimmed)
  if (ce) return `${ce[1].padStart(4, '0')}${ce[2] ?? ''}`
  return trimmed
}

/**
 * Normalizes a single date with optional uncertainty qualifier into canonical
 * EDTF-lite form ("1900~" = circa, "1900?" = unsicher, "1900~?" = beides).
 * Accepts German words ("ca.", "um", "(unsicher)") as well as the symbols directly.
 */
export function normalizeQualifiedDate(value: string): string {
  let s = value.trim()
  let circa = false
  let uncertain = false
  const unsicher = /^(.*?)\s*\(\s*unsicher\s*\)$/i.exec(s)
  if (unsicher) {
    uncertain = true
    s = unsicher[1].trim()
  }
  if (s.endsWith('?')) {
    uncertain = true
    s = s.slice(0, -1).trim()
  }
  if (s.endsWith('~')) {
    circa = true
    s = s.slice(0, -1).trim()
  }
  const ca = /^(ca\.?|um)\s+(.+)$/i.exec(s)
  if (ca) {
    circa = true
    s = ca[2].trim()
  }
  const bare = normalizeBareDate(s)
  const suffix = circa && uncertain ? '~?' : circa ? '~' : uncertain ? '?' : ''
  return `${bare}${suffix}`
}

/**
 * Normalizes date input into canonical storage form. Supports ranges via "START/END",
 * "START bis END", "vor END" (offener Anfang) and "nach START" (offenes Ende).
 */
export function normalizeDateInput(value: string): string {
  const trimmed = value.trim()
  const bis = /^(.*?)\s+bis\s+(.*)$/i.exec(trimmed)
  if (bis) {
    const [, left, right] = bis
    return `${left.trim() ? normalizeQualifiedDate(left) : ''}/${right.trim() ? normalizeQualifiedDate(right) : ''}`
  }
  if (trimmed.split('/').length === 2) {
    const [left, right] = trimmed.split('/')
    return `${left.trim() ? normalizeQualifiedDate(left) : ''}/${right.trim() ? normalizeQualifiedDate(right) : ''}`
  }
  const vor = /^vor\s+(.+)$/i.exec(trimmed)
  if (vor) return `/${normalizeQualifiedDate(vor[1])}`
  const nach = /^nach\s+(.+)$/i.exec(trimmed)
  if (nach) return `${normalizeQualifiedDate(nach[1])}/`
  return normalizeQualifiedDate(trimmed)
}

function isValidDatePart(value: string): boolean {
  if (/^-?\d{4}$/.test(value)) return true
  if (/^-?\d{4}-(0[1-9]|1[0-2])$/.test(value)) return true
  const full = /^(-?\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!full) return false
  const year = Number(full[1])
  const month = Number(full[2])
  const day = Number(full[3])
  if (month < 1 || month > 12) return false
  return day >= 1 && day <= daysInMonth(year, month)
}

function isValidQualifiedDate(value: string): boolean {
  for (const suffix of ['~?', '~', '?']) {
    if (value.endsWith(suffix)) return isValidDatePart(value.slice(0, -suffix.length))
  }
  return isValidDatePart(value)
}

export function isValidDateInput(value: string): boolean {
  const normalized = normalizeDateInput(value)
  if (normalized.includes('/')) {
    const parts = normalized.split('/')
    if (parts.length !== 2) return false
    const [start, end] = parts
    if (!start && !end) return false
    return (start === '' || isValidQualifiedDate(start)) && (end === '' || isValidQualifiedDate(end))
  }
  return isValidQualifiedDate(normalized)
}

const pad4 = (value: number | string) => String(value).padStart(4, '0')

function formatQualifiedDate(value: string, isEn: boolean): string {
  const bceLabel = isEn ? 'BCE' : 'v. Chr.'
  const formatBce = (date: string) => {
    const negative = /^-(\d{4})(.*)$/.exec(date)
    if (negative) return `${Number(negative[1]) + 1}${negative[2]} ${bceLabel}`
    const yearZero = /^0000(.*)$/.exec(date)
    if (yearZero) return `1${yearZero[1]} ${bceLabel}`
    return date
  }
  const uncertain = isEn ? 'uncertain' : 'unsicher'
  if (value.endsWith('~?')) return `ca. ${formatBce(value.slice(0, -2))} (${uncertain})`
  if (value.endsWith('~')) return `ca. ${formatBce(value.slice(0, -1))}`
  if (value.endsWith('?')) return `${formatBce(value.slice(0, -1))} (${uncertain})`
  return formatBce(value)
}

/** Stored value → display text. Must render like the portal's `formatDateValue`. */
export function formatDateValue(value: string, locale?: string): string {
  if (!value) return ''
  const isEn = locale?.startsWith('en') ?? false
  const parts = value.split('/')
  if (parts.length !== 2) return formatQualifiedDate(value, isEn)
  const [start, end] = parts
  if (!start) return `${isEn ? 'before' : 'vor'} ${formatQualifiedDate(end, isEn)}`
  if (!end) return `${isEn ? 'after' : 'nach'} ${formatQualifiedDate(start, isEn)}`
  return `${formatQualifiedDate(start, isEn)}–${formatQualifiedDate(end, isEn)}`
}

/** "43 v. Chr." / "-43" (as people count) → stored ISO year "-0042"; year 1 BCE is "0000". */
function parseEraDate(text: string): string {
  const bce = /^(?:-\s*(.+)|(.+?)\s*(?:v\.\s*chr\.?|bce|bc))$/i.exec(text)
  if (bce) {
    const match = /^(\d{1,4})(-\d{2}(?:-\d{2})?)?$/.exec((bce[1] ?? bce[2]).trim())
    // Returned in a form that validation rejects, e.g. for the non-existent year 0 BCE.
    if (!match || Number(match[1]) < 1) return `${(bce[1] ?? bce[2]).trim()} v. Chr.`
    const year = Number(match[1]) - 1
    return `${year ? '-' : ''}${pad4(year)}${match[2] ?? ''}`
  }
  const ce = /^(.+?)\s*(?:n\.\s*chr\.?|ce|ad)$/i.exec(text)
  return normalizeBareDate(ce ? ce[1] : text)
}

function parseQualifiedText(text: string): string {
  let s = text.trim()
  if (!s) return ''
  let circa = false
  let uncertain = false
  const word = /^(.*?)\s*\(\s*(?:unsicher|uncertain)\s*\)$/i.exec(s)
  if (word) { uncertain = true; s = word[1].trim() }
  if (s.endsWith('?')) { uncertain = true; s = s.slice(0, -1).trim() }
  if (s.endsWith('~')) { circa = true; s = s.slice(0, -1).trim() }
  const ca = /^(?:ca\.?|circa|um)\s+(.+)$/i.exec(s)
  if (ca) { circa = true; s = ca[1].trim() }
  return `${parseEraDate(s)}${circa && uncertain ? '~?' : circa ? '~' : uncertain ? '?' : ''}`
}

/**
 * Typed text → stored value. Apply to user input only: a leading minus counts BCE years
 * the way people do ("-43" = 43 BCE), while stored values use ISO years ("-0042").
 */
export function parseDateText(text: string): string {
  const s = text.trim()
  const range = /^(.*?)\s*(?:–|\/|(?:^|\s)(?:bis|to)\s)\s*(.*)$/i.exec(s)
  if (range) return `${parseQualifiedText(range[1])}/${parseQualifiedText(range[2])}`
  const open = /^(vor|before|nach|after)\s+(.+)$/i.exec(s)
  if (open) {
    const date = parseQualifiedText(open[2])
    return /^(vor|before)$/i.test(open[1]) ? `/${date}` : `${date}/`
  }
  return parseQualifiedText(s)
}
