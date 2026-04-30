import { useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useNavigate } from 'react-router-dom'
import './styles.css'
import { loadAndApplyTheme } from './theme/loader'
import { HomePage } from './pages/HomePage'
import { SearchPage } from './pages/SearchPage'
import { ObjectDetailPage } from './pages/ObjectDetailPage'

function Header() {
  const navigate = useNavigate()
  return (
    <header className="site-header">
      <Link to="/" className="logo">Katalon</Link>
      <nav>
        <Link to="/search?q=">Objekte</Link>
        <Link to="/search?q=">Personen</Link>
        <Link to="/search?q=">Orte</Link>
      </nav>
      <div className="sp" />
      <form className="search-bar" onSubmit={e => { e.preventDefault(); const q = (e.currentTarget.elements.namedItem('q') as HTMLInputElement).value; if (q) navigate(`/search?q=${encodeURIComponent(q)}`) }}>
        <input name="q" placeholder="Suchen…" />
      </form>
    </header>
  )
}

function Footer() {
  return (
    <footer className="site-footer">
      Katalon · Metadata Management System · <a href="/api/docs" style={{ color: 'inherit' }}>API</a>
    </footer>
  )
}

function AppInner() {
  useEffect(() => { loadAndApplyTheme() }, [])
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/objects/:id" element={<ObjectDetailPage />} />
      </Routes>
      <Footer />
    </>
  )
}

export function App() {
  return <BrowserRouter><AppInner /></BrowserRouter>
}
