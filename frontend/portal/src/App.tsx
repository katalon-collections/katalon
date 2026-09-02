// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Helmet, HelmetProvider } from 'react-helmet-async'
import './styles.css'
import { loadAndApplyTheme } from './theme/loader'
import { api, BASE, PORTAL_API, currentUser, logout as endSession, restoreSession, type PortalUser, type StaticPageSummary } from './api/client'
import { HomePage } from './pages/HomePage'
import { SearchPage } from './pages/SearchPage'
import { AdvancedSearchPage } from './pages/AdvancedSearchPage'
import { ObjectDetailPage } from './pages/ObjectDetailPage'
import { EntityDetailPage } from './pages/EntityDetailPage'
import { PlaceDetailPage } from './pages/PlaceDetailPage'
import { OccurrenceDetailPage } from './pages/OccurrenceDetailPage'
import { StaticPageView } from './pages/StaticPageView'
import { LoginPage } from './pages/LoginPage'
import { ErrorBoundary } from './components/ErrorBoundary'
import { BannerBar } from './components/BannerBar'
import { useI18n, typeLabel, setSupportedLocales } from './i18n'
import { usePortalConfig } from './hooks/usePortalConfig'

const BROWSE_NAV_ITEMS = [
  { type: 'object', to: '/search?q=&type=object', label: 'nav.objects' },
  { type: 'entity', to: '/search?q=&type=entity', label: 'nav.entities' },
  { type: 'place', to: '/search?q=&type=place', label: 'nav.places' },
  { type: 'occurrence', to: '/search?q=&type=occurrence', label: 'nav.works' },
]

function pageLabel(p: StaticPageSummary, locale: string): string {
  const t = (p.title ?? {}) as Record<string, string>
  return t[locale] ?? Object.values(t)[0] ?? p.slug
}

function LanguageSwitcher() {
  const { locale, setLocale } = useI18n()
  const config = usePortalConfig()
  const langs = config.supported_languages ?? ['de', 'en']
  if (langs.length <= 1) return null
  return (
    <select
      className="lang-switcher"
      value={locale}
      onChange={e => setLocale(e.target.value)}
      aria-label="Language"
    >
      {langs.map(l => <option key={l} value={l}>{l.toUpperCase()}</option>)}
    </select>
  )
}

function Header({ user, onLogout }: { user: PortalUser | null; onLogout: () => void }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { t, locale } = useI18n()
  const config = usePortalConfig()
  const [q, setQ] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ id: string; record_type: string; title: string }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [headerPages, setHeaderPages] = useState<StaticPageSummary[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.pages.list().then(ps => setHeaderPages(ps.filter(p => p.placement === 'header'))).catch(() => {})
  }, [])

  // Debounced autocomplete
  useEffect(() => {
    if (q.trim().length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    setLoadingSuggestions(true)
    const timer = setTimeout(() => {
      const qs = new URLSearchParams({ q: q.trim(), page_size: '5' })
      fetch(`${BASE}${PORTAL_API}/search?${qs.toString()}`)
        .then(r => r.json())
        .then((result: { items: Array<{ id: string; record_type: string; title: string }> }) => {
          setSuggestions(result.items ?? [])
          setShowSuggestions(true)
        })
        .catch(() => setSuggestions([]))
        .finally(() => setLoadingSuggestions(false))
    }, 200)
    return () => clearTimeout(timer)
  }, [q])

  // Close dropdown on outside click
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  function submit(e?: React.FormEvent) {
    e?.preventDefault()
    const term = q.trim()
    if (!term) return
    const qs = new URLSearchParams({ q: term })
    navigate(`/search?${qs.toString()}`)
    setShowSuggestions(false)
    inputRef.current?.blur()
  }

  function resultPath(item: { record_type: string; id: string }) {
    return item.record_type === 'entity' ? `/entities/${item.id}`
      : item.record_type === 'place' ? `/places/${item.id}`
      : item.record_type === 'occurrence' ? `/occurrences/${item.id}`
      : `/objects/${item.id}`
  }

  return (
    <header className="site-header">
      <Link to="/" className="logo">{config.site_title}</Link>
      <nav>
        {BROWSE_NAV_ITEMS
          .filter(({ type }) => config.browse_enabled_types.includes(type))
          .map(({ type, to, label }) => <Link key={type} to={to}>{t(label)}</Link>)}
        {headerPages.map(p => <Link key={p.slug} to={`/page/${p.slug}`}>{pageLabel(p, locale)}</Link>)}
      </nav>
      <div className="sp" />
      <div ref={wrapRef} className={`search-wrap${location.pathname === '/' ? ' is-home' : ''}`} style={{ position: 'relative' }}>
        <form className="search-bar" onSubmit={submit}>
          <input
            ref={inputRef}
            role="combobox"
            aria-autocomplete="list"
            aria-label={t('search.ariaLabel')}
            aria-expanded={showSuggestions}
            aria-controls="search-suggestions"
            value={q}
            onChange={e => setQ(e.target.value)}
            onFocus={() => { if (suggestions.length) setShowSuggestions(true) }}
            placeholder={t('search.placeholder')}
          />
        </form>
        {showSuggestions && (
          <div className="search-suggestions" id="search-suggestions">
            {suggestions.length === 0 && loadingSuggestions && (
              <div className="suggest-item" style={{ color: 'var(--fg-3)' }}>{t('search.searching')}</div>
            )}
            {suggestions.length === 0 && !loadingSuggestions && (
              <div className="suggest-item" style={{ color: 'var(--fg-3)' }}>{t('search.noResults')}</div>
            )}
            {suggestions.map(item => (
              <Link key={`${item.record_type}-${item.id}`} className="suggest-item" to={resultPath(item)} onClick={() => setShowSuggestions(false)}>
                <span className="suggest-title">{item.title || item.id}</span>
                <span className="suggest-badge">{typeLabel(item.record_type)}</span>
              </Link>
            ))}
            <button type="button" className="suggest-footer" onClick={() => submit()}>
              {t('search.showAll')}
            </button>
          </div>
        )}
      </div>
      <Link className="advanced-search-link" to="/advanced-search">{t('advanced.link')}</Link>
      <LanguageSwitcher />
      {user ? <button className="portal-account" type="button" onClick={onLogout}>{t('account.logout')}</button>
        : <Link className="portal-account" to="/login">{t('account.login')}</Link>}
    </header>
  )
}

function Footer() {
  const { locale } = useI18n()
  const config = usePortalConfig()
  const [pages, setPages] = useState<StaticPageSummary[]>([])
  useEffect(() => { api.pages.list().then(ps => setPages(ps.filter(p => p.placement === 'footer'))).catch(() => {}) }, [])
  return (
    <footer className="site-footer">
      {config.site_title} · Metadata Management System
      {pages.map(p => {
        const label = pageLabel(p, locale)
        return (
          <span key={p.slug}>
            {' · '}
            <Link to={`/page/${p.slug}`} style={{ color: 'inherit' }}>{label}</Link>
          </span>
        )
      })}
      {' · '}
      <a href="/api/docs" style={{ color: 'inherit' }}>API</a>
    </footer>
  )
}

function AppInner() {
  const [user, setUser] = useState<PortalUser | null>(() => currentUser())
  const config = usePortalConfig()
  useEffect(() => { restoreSession().then(setUser).catch(() => setUser(null)) }, [])
  function logout() {
    void endSession()
    setUser(null)
  }
  useEffect(() => {
    loadAndApplyTheme()
    // Apply portal config color_tokens on top of the base theme
    api.portal.config().then(c => {
      setSupportedLocales(c.supported_languages ?? ['de', 'en'])
      const tokens = c.color_tokens ?? {}
      const root = document.documentElement
      for (const [k, v] of Object.entries(tokens)) {
        if (v) root.style.setProperty(k, v as string)
      }
      if (c.accent_color) root.style.setProperty('--accent', c.accent_color)
    }).catch(() => {})
  }, [])
  return (
    <>
      <Helmet defaultTitle={config.site_title} titleTemplate={`%s – ${config.site_title}`}>
        <meta name="description" content="Metadata Management System für Sammlungen" />
      </Helmet>
      <BannerBar />
      <Header user={user} onLogout={logout} />
      <main id="main-content" style={{ flex: 1, width: '100%' }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/advanced-search" element={<AdvancedSearchPage />} />
          <Route path="/login" element={<LoginPage onLogin={() => setUser(currentUser())} />} />
          <Route path="/objects/:id" element={<ErrorBoundary><ObjectDetailPage /></ErrorBoundary>} />
          <Route path="/entities/:id" element={<EntityDetailPage />} />
          <Route path="/places/:id" element={<PlaceDetailPage />} />
          <Route path="/occurrences/:id" element={<OccurrenceDetailPage />} />
          <Route path="/page/:slug" element={<StaticPageView />} />
        </Routes>
      </main>
      <Footer />
    </>
  )
}

export function App() {
  return <HelmetProvider><BrowserRouter><AppInner /></BrowserRouter></HelmetProvider>
}
