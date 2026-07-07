import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Helmet, HelmetProvider } from 'react-helmet-async'
import './styles.css'
import { loadAndApplyTheme } from './theme/loader'
import { api, type StaticPageSummary } from './api/client'
import { HomePage } from './pages/HomePage'
import { SearchPage } from './pages/SearchPage'
import { ObjectDetailPage } from './pages/ObjectDetailPage'
import { EntityDetailPage } from './pages/EntityDetailPage'
import { PlaceDetailPage } from './pages/PlaceDetailPage'
import { OccurrenceDetailPage } from './pages/OccurrenceDetailPage'
import { StaticPageView } from './pages/StaticPageView'
import { ErrorBoundary } from './components/ErrorBoundary'
import { BannerBar } from './components/BannerBar'
import { FeedbackButton } from './components/FeedbackButton'

const TYPE_LABELS: Record<string, string> = {
  object: 'Objekt', entity: 'Person/Org', place: 'Ort', occurrence: 'Werk/Ereignis',
}

function Header() {
  const navigate = useNavigate()
  const location = useLocation()
  const [q, setQ] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ id: string; record_type: string; title: string }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Preserve type scope from current search page
  const currentType = new URLSearchParams(location.search).get('type') ?? ''

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
      if (currentType) qs.set('type', currentType)
      fetch(`${import.meta.env.VITE_API_URL ?? ''}/v1/search?${qs.toString()}`)
        .then(r => r.json())
        .then((result: { items: Array<{ id: string; record_type: string; title: string }> }) => {
          setSuggestions(result.items ?? [])
          setShowSuggestions(true)
        })
        .catch(() => setSuggestions([]))
        .finally(() => setLoadingSuggestions(false))
    }, 200)
    return () => clearTimeout(timer)
  }, [q, currentType])

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
    if (currentType) qs.set('type', currentType)
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
      <Link to="/" className="logo">Katalon</Link>
      <nav>
        <Link to="/search?q=&type=object">Objekte</Link>
        <Link to="/search?q=&type=entity">Personen</Link>
        <Link to="/search?q=&type=place">Orte</Link>
        <Link to="/search?q=&type=occurrence">Werke</Link>
      </nav>
      <div className="sp" />
      <div ref={wrapRef} style={{ position: 'relative' }}>
        <form className="search-bar" onSubmit={submit}>
          <input
            ref={inputRef}
            aria-label="Sammlung durchsuchen"
            aria-expanded={showSuggestions}
            aria-controls="search-suggestions"
            value={q}
            onChange={e => setQ(e.target.value)}
            onFocus={() => { if (suggestions.length) setShowSuggestions(true) }}
            placeholder={currentType ? `Suchen in ${TYPE_LABELS[currentType] ?? currentType}…` : 'Suchen…'}
          />
        </form>
        {showSuggestions && (
          <div className="search-suggestions" id="search-suggestions">
            {suggestions.length === 0 && loadingSuggestions && (
              <div className="suggest-item" style={{ color: 'var(--fg-3)' }}>Suche…</div>
            )}
            {suggestions.length === 0 && !loadingSuggestions && (
              <div className="suggest-item" style={{ color: 'var(--fg-3)' }}>Keine Ergebnisse</div>
            )}
            {suggestions.map(item => (
              <Link key={`${item.record_type}-${item.id}`} className="suggest-item" to={resultPath(item)} onClick={() => setShowSuggestions(false)}>
                <span className="suggest-title">{item.title || item.id}</span>
                <span className="suggest-badge">{TYPE_LABELS[item.record_type] ?? item.record_type}</span>
              </Link>
            ))}
            <button type="button" className="suggest-footer" onClick={() => submit()}>
              Alle Ergebnisse anzeigen →
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

function Footer() {
  const [pages, setPages] = useState<StaticPageSummary[]>([])
  useEffect(() => { api.pages.list().then(setPages).catch(() => {}) }, [])
  return (
    <footer className="site-footer">
      Katalon · Metadata Management System
      {pages.map(p => {
        const lang = 'de'
        const label = (p.title as Record<string, string>)[lang] ?? Object.values(p.title)[0] ?? p.slug
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
  useEffect(() => {
    loadAndApplyTheme()
    // Apply portal config color_tokens on top of the base theme
    api.portal.config().then(c => {
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
      <Helmet defaultTitle="Katalon" titleTemplate="%s – Katalon">
        <meta name="description" content="Metadata Management System für Sammlungen" />
      </Helmet>
      <BannerBar />
      <Header />
      <main id="main-content" style={{ flex: 1, width: '100%' }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/objects/:id" element={<ErrorBoundary><ObjectDetailPage /></ErrorBoundary>} />
          <Route path="/entities/:id" element={<EntityDetailPage />} />
          <Route path="/places/:id" element={<PlaceDetailPage />} />
          <Route path="/occurrences/:id" element={<OccurrenceDetailPage />} />
          <Route path="/page/:slug" element={<StaticPageView />} />
        </Routes>
      </main>
      <Footer />
      <FeedbackButton />
    </>
  )
}

export function App() {
  return <HelmetProvider><BrowserRouter><AppInner /></BrowserRouter></HelmetProvider>
}
