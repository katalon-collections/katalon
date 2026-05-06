import { useEffect, useState } from 'react'
import { BrowserRouter, Link, Route, Routes, useNavigate } from 'react-router-dom'
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

function Header() {
  const navigate = useNavigate()
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
      <form className="search-bar" onSubmit={e => { e.preventDefault(); const q = (e.currentTarget.elements.namedItem('q') as HTMLInputElement).value; if (q) navigate(`/search?q=${encodeURIComponent(q)}`) }}>
        <input name="q" placeholder="Suchen…" />
      </form>
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
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/objects/:id" element={<ErrorBoundary><ObjectDetailPage /></ErrorBoundary>} />
        <Route path="/entities/:id" element={<EntityDetailPage />} />
        <Route path="/places/:id" element={<PlaceDetailPage />} />
        <Route path="/occurrences/:id" element={<OccurrenceDetailPage />} />
        <Route path="/page/:slug" element={<StaticPageView />} />
      </Routes>
      <Footer />
    </>
  )
}

export function App() {
  return <HelmetProvider><BrowserRouter><AppInner /></BrowserRouter></HelmetProvider>
}
