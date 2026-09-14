// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useSyncExternalStore } from 'react'
import de from './locales/de'
import en from './locales/en'

const MESSAGES: Record<string, Record<string, string>> = { de, en }
const FALLBACK_LOCALE = 'de'
const STORAGE_KEY = 'katalon_lang'

let supportedLocales: string[] = ['de', 'en']

// Portal-configurable record-type terminology (#373), overriding the
// `type.*`/`nav.*` default labels below. Presentation only — does not
// touch the underlying `record_type` values used by the API.
type TerminologyEntry = { singular?: Record<string, string>; plural?: Record<string, string> }
let terminology: Record<string, TerminologyEntry> = {}

// Maps an i18n message key to the (record type, form) it represents, so
// every existing t('type.xxx') / t('nav.xxx') call site picks up overrides
// automatically without threading options through each call.
const TERMINOLOGY_KEYS: Record<string, [type: string, form: 'singular' | 'plural']> = {
  'type.object': ['object', 'singular'], 'nav.objects': ['object', 'plural'],
  'type.entity': ['entity', 'singular'], 'nav.entities': ['entity', 'plural'],
  'type.place': ['place', 'singular'], 'nav.places': ['place', 'plural'],
  'type.occurrence': ['occurrence', 'singular'], 'nav.works': ['occurrence', 'plural'],
  'type.collection': ['collection', 'singular'], 'nav.collections': ['collection', 'plural'],
}

const TERMINOLOGY_KEYS_BY_TYPE_PLURAL: Record<string, string> = {
  object: 'nav.objects', entity: 'nav.entities', place: 'nav.places',
  occurrence: 'nav.works', collection: 'nav.collections',
}

/** Set portal-configured terminology overrides (from `PortalConfig.terminology`). */
export function setTerminology(overrides: Record<string, TerminologyEntry> | undefined) {
  terminology = overrides ?? {}
  emit()
}

function terminologyOverride(key: string): string | undefined {
  const mapping = TERMINOLOGY_KEYS[key]
  if (!mapping) return undefined
  const [type, form] = mapping
  const entry = terminology[type]?.[form]
  if (!entry) return undefined
  return entry[currentLocale] || entry[FALLBACK_LOCALE] || undefined
}

function resolveInitial(): string {
  if (typeof window === 'undefined') return FALLBACK_LOCALE
  const url = new URLSearchParams(window.location.search).get('lang')
  if (url && supportedLocales.includes(url)) return url
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && supportedLocales.includes(stored)) return stored
  const nav = (navigator.language ?? '').slice(0, 2).toLowerCase()
  if (nav && supportedLocales.includes(nav)) return nav
  return supportedLocales[0] ?? FALLBACK_LOCALE
}

let currentLocale = resolveInitial()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach(l => l())
}

/** Set the available languages (ordered; first = primary). Re-resolves the active locale if unsupported. */
export function setSupportedLocales(langs: string[]) {
  supportedLocales = langs.length > 0 ? langs : ['de', 'en']
  if (!supportedLocales.includes(currentLocale)) {
    currentLocale = resolveInitial()
    emit()
  }
}

export function setLocale(lang: string) {
  if (!supportedLocales.includes(lang)) return
  currentLocale = lang
  localStorage.setItem(STORAGE_KEY, lang)
  emit()
}

export function getLocale(): string {
  return currentLocale
}

/** Translate a key with optional `{param}` interpolation. Falls back to German, then the key itself. */
export function t(key: string, params?: Record<string, string | number>): string {
  let str = terminologyOverride(key) ?? MESSAGES[currentLocale]?.[key] ?? MESSAGES[FALLBACK_LOCALE]?.[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replaceAll(`{${k}}`, String(v))
    }
  }
  return str
}

/** Translated record-type label, falling back to the raw code. */
export function typeLabel(type: string, opts?: { plural?: boolean }): string {
  const key = opts?.plural ? (TERMINOLOGY_KEYS_BY_TYPE_PLURAL[type] ?? `type.${type}`) : `type.${type}`
  const override = terminologyOverride(key)
  if (override) return override
  const v = MESSAGES[currentLocale]?.[key] ?? MESSAGES[FALLBACK_LOCALE]?.[key]
  return v ?? type
}

export function entityTypeLabel(type: string): string {
  const v = MESSAGES[currentLocale]?.[`entityType.${type}`] ?? MESSAGES[FALLBACK_LOCALE]?.[`entityType.${type}`]
  return v ?? type
}

export function occurrenceTypeLabel(type: string): string {
  const v = MESSAGES[currentLocale]?.[`occurrenceType.${type}`] ?? MESSAGES[FALLBACK_LOCALE]?.[`occurrenceType.${type}`]
  return v ?? type
}

const subscribe = (cb: () => void) => {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}
const getSnapshot = () => currentLocale

export function useI18n() {
  const locale = useSyncExternalStore(subscribe, getSnapshot)
  return { locale, t, setLocale }
}
