import { useSyncExternalStore } from 'react'
import de from './locales/de'
import en from './locales/en'

const MESSAGES: Record<string, Record<string, string>> = { de, en }
const FALLBACK_LOCALE = 'de'
const STORAGE_KEY = 'katalon_lang'

let supportedLocales: string[] = ['de', 'en']

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
  let str = MESSAGES[currentLocale]?.[key] ?? MESSAGES[FALLBACK_LOCALE]?.[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replaceAll(`{${k}}`, String(v))
    }
  }
  return str
}

/** Translated record-type label, falling back to the raw code. */
export function typeLabel(type: string): string {
  const v = MESSAGES[currentLocale]?.[`type.${type}`] ?? MESSAGES[FALLBACK_LOCALE]?.[`type.${type}`]
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
