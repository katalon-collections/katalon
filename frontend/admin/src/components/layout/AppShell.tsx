import { useEffect, useRef, useState } from 'react'
import { hasToken, onUnauthorized, setToken, getTokenUser } from '../../api/client'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { ScreenList } from '../screens/ScreenList'
import { ScreenSchema } from '../screens/ScreenSchema'
import { ScreenVocab } from '../screens/ScreenVocab'
import { ScreenImporter } from '../screens/ScreenImporter'
import { ScreenAudit } from '../screens/ScreenAudit'
import { ScreenForm } from '../screens/ScreenForm'
import { ScreenLogin } from '../screens/ScreenLogin'
import { ScreenSettings } from '../screens/ScreenSettings'
import { ScreenUsers } from '../screens/ScreenUsers'
import { ScreenPages } from '../screens/ScreenPages'
import { ScreenOAISets } from '../screens/ScreenOAISets'
import { ScreenSubtype } from '../screens/ScreenSubtype'
import { ScreenBanners } from '../screens/ScreenBanners'
import { ScreenFormVariants } from '../screens/ScreenFormVariants'
import { BannerBar } from '../ui/BannerBar'
import { ImportStatusBanner } from '../ui/ImportStatusBanner'
import { Tour, type TourVariant } from '../tour/Tour'
import { BASE, req, users } from '../../api/client'
import type { PortalConfigRead } from '../../types'

type Crumb = { label: string; route?: string }

const CRUMBS: Record<string, Crumb[]> = {
  list:               [{ label: 'Katalon' }, { label: 'Objekte' }],
  form:               [{ label: 'Katalon' }, { label: 'Objekte', route: 'list' }, { label: 'Bearbeiten' }],
  'entities-list':    [{ label: 'Katalon' }, { label: 'Entitäten' }],
  'entities-form':    [{ label: 'Katalon' }, { label: 'Entitäten', route: 'entities-list' }, { label: 'Bearbeiten' }],
  'places-list':      [{ label: 'Katalon' }, { label: 'Orte' }],
  'places-form':      [{ label: 'Katalon' }, { label: 'Orte', route: 'places-list' }, { label: 'Bearbeiten' }],
  'occurrences-list': [{ label: 'Katalon' }, { label: 'Occurrences' }],
  'occurrences-form': [{ label: 'Katalon' }, { label: 'Occurrences', route: 'occurrences-list' }, { label: 'Bearbeiten' }],
  'procedures-list':  [{ label: 'Katalon' }, { label: 'Vorgänge' }],
  'procedures-form':  [{ label: 'Katalon' }, { label: 'Vorgänge', route: 'procedures-list' }, { label: 'Bearbeiten' }],
  banners:            [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Banner' }],
  subtypes:           [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Subtypen' }],
  schema:             [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Schemata' }],
  'form-variants':    [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Formularvarianten' }],
  vocab:              [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Vokabular' }],
  pages:              [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Statische Seiten' }],
  'oai-sets':         [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'OAI-PMH Sets' }],
  import:             [{ label: 'Katalon' }, { label: 'Importer' }],
  audit:              [{ label: 'Katalon' }, { label: 'Audit-Log' }],
  users:              [{ label: 'Katalon' }, { label: 'Verwaltung' }, { label: 'Benutzer' }],
  settings:           [{ label: 'Katalon' }, { label: 'Einstellungen' }],
}

function withBrand(crumbs: Crumb[], appTitle: string): Crumb[] {
  return crumbs.map((crumb, index) => (index === 0 ? { ...crumb, label: appTitle } : crumb))
}

function adminDocumentTitle(appTitle: string, route: string, crumbs: Crumb[]): string {
  if (route === 'settings') return `${appTitle} Admin`
  const current = crumbs[crumbs.length - 1]?.label
  return current && current !== appTitle ? `${current} - ${appTitle} Admin` : `${appTitle} Admin`
}

function hashToState(hash: string): { route: string; editId: string | null } {
  const h = hash.replace(/^#/, '') || 'list'
  const slash = h.indexOf('/')
  if (slash === -1) return { route: h, editId: null }
  return { route: h.slice(0, slash), editId: h.slice(slash + 1) }
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="scroll">
      <div className="empty" style={{ paddingTop: 80 }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>🚧</div>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
        <div style={{ color: 'var(--fg-4)', fontSize: 12 }}>Dieser Screen ist noch nicht implementiert.</div>
      </div>
    </div>
  )
}

export function AppShell() {
  const [loggedIn, setLoggedIn] = useState(hasToken)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const isDirtyRef = useRef(false)
  const [appTitle, setAppTitle] = useState('Katalon')

  const init = hashToState(window.location.hash)
  const [route, setRoute] = useState(init.route)
  const [editId, setEditId] = useState<string | null>(init.editId)
  const [activeTour, setActiveTour] = useState<TourVariant | null>(null)

  useEffect(() => {
    onUnauthorized(() => setLoggedIn(false))
  }, [])

  useEffect(() => {
    req<PortalConfigRead>(`${BASE}/v1/portal/config`)
      .then(config => {
        if (config.site_title?.trim()) setAppTitle(config.site_title.trim())
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!loggedIn) return
    const user = getTokenUser()
    if (user?.role !== 'superuser' && user?.role !== 'admin') return
    users.me()
      .then(me => { if (!me.onboarding_completed_at) setActiveTour('basic') })
      .catch(() => {})
  }, [loggedIn])

  useEffect(() => {
    function onPop() {
      const { route: r, editId: id } = hashToState(window.location.hash)
      setRoute(r)
      setEditId(id)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  function navigate(r: string, id?: string | null) {
    const newId = id ?? null
    setRoute(r)
    setEditId(newId)
    const hash = newId ? `#${r}/${newId}` : `#${r}`
    window.history.pushState({ route: r, editId: newId }, '', hash)
  }

  // Used by sidebar/topbar — confirms before leaving a dirty form
  function safeNavigate(r: string, id?: string | null) {
    if (isDirtyRef.current && !window.confirm('Du hast ungespeicherte Änderungen. Trotzdem verlassen?')) return
    isDirtyRef.current = false
    setSidebarOpen(false)
    navigate(r, id)
  }

  function handleLogout() {
    setToken(null)
    setLoggedIn(false)
  }

  useEffect(() => {
    const titleCrumbs = withBrand(CRUMBS[route] ?? [{ label: appTitle }], appTitle)
    document.title = adminDocumentTitle(appTitle, route, titleCrumbs)
  }, [appTitle, route])

  const crumbs = withBrand(CRUMBS[route] ?? [{ label: appTitle }], appTitle)

  if (!loggedIn) {
    return <ScreenLogin onLogin={() => setLoggedIn(true)} />
  }

  const currentUser = getTokenUser()
  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'superuser'

  function renderScreen() {
    switch (route) {
      case 'list':              return <ScreenList recordType="object"     onOpen={(id) => navigate('form', id)} initialTab={editId} onTabChange={(t) => navigate('list', t)} />
      case 'form':              return <ScreenForm recordType="object"     recordId={editId ?? undefined} onBack={() => navigate('list')} onSaved={(id) => navigate('form', id)} onDirtyChange={(d) => { isDirtyRef.current = d }} />
      case 'entities-list':     return <ScreenList recordType="entity"     onOpen={(id) => navigate('entities-form', id)} initialTab={editId} onTabChange={(t) => navigate('entities-list', t)} />
      case 'entities-form':     return <ScreenForm recordType="entity"     recordId={editId ?? undefined} onBack={() => navigate('entities-list')} onSaved={(id) => navigate('entities-form', id)} onDirtyChange={(d) => { isDirtyRef.current = d }} />
      case 'places-list':       return <ScreenList recordType="place"      onOpen={(id) => navigate('places-form', id)} initialTab={editId} onTabChange={(t) => navigate('places-list', t)} />
      case 'places-form':       return <ScreenForm recordType="place"      recordId={editId ?? undefined} onBack={() => navigate('places-list')} onSaved={(id) => navigate('places-form', id)} onDirtyChange={(d) => { isDirtyRef.current = d }} />
      case 'occurrences-list':  return <ScreenList recordType="occurrence" onOpen={(id) => navigate('occurrences-form', id)} initialTab={editId} onTabChange={(t) => navigate('occurrences-list', t)} />
      case 'occurrences-form':  return <ScreenForm recordType="occurrence" recordId={editId ?? undefined} onBack={() => navigate('occurrences-list')} onSaved={(id) => navigate('occurrences-form', id)} onDirtyChange={(d) => { isDirtyRef.current = d }} />
      case 'procedures-list':   return <ScreenList recordType="procedure" onOpen={(id) => navigate('procedures-form', id)} initialTab={editId} onTabChange={(t) => navigate('procedures-list', t)} />
      case 'procedures-form':   return <ScreenForm recordType="procedure" recordId={editId ?? undefined} onBack={() => navigate('procedures-list')} onSaved={(id) => navigate('procedures-form', id)} onDirtyChange={(d) => { isDirtyRef.current = d }} />
      case 'banners':           return isAdmin ? <ScreenBanners /> : <Placeholder label="Kein Zugriff" />
      case 'subtypes':          return isAdmin ? <ScreenSubtype initialType={editId} onTypeChange={(t) => navigate('subtypes', t)} /> : <Placeholder label="Kein Zugriff" />
      case 'schema':            return <ScreenSchema initialPath={editId} onPathChange={(p) => navigate('schema', p)} />
      case 'form-variants':     return isAdmin ? <ScreenFormVariants initialPath={editId} onPathChange={(p) => navigate('form-variants', p)} /> : <Placeholder label="Kein Zugriff" />
      case 'vocab':             return <ScreenVocab initialVocab={editId} onVocabSelect={(name) => navigate('vocab', name)} />
      case 'pages':             return <ScreenPages initialSlug={editId} onSlugChange={(s) => navigate('pages', s)} />
      case 'oai-sets':          return isAdmin ? <ScreenOAISets /> : <Placeholder label="Kein Zugriff" />
      case 'import':            return <ScreenImporter initialTab={editId} onTabChange={(t) => navigate('import', t)} />
      case 'audit':             return <ScreenAudit initialFilter={editId} onFilterChange={(f) => navigate('audit', f)} />
      case 'users':             return <ScreenUsers />
      case 'settings':          return <ScreenSettings isAdmin={isAdmin} onNavigate={(r) => safeNavigate(r)} onStartTour={setActiveTour} />
      default:                  return <Placeholder label={crumbs[crumbs.length - 1].label} />
    }
  }

  return (
    <div className="app">
      <Sidebar
        route={route}
        setRoute={(r) => safeNavigate(r)}
        onLogout={handleLogout}
        appTitle={appTitle}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && <button className="sb-backdrop" aria-label="Navigation schließen" onClick={() => setSidebarOpen(false)} />}
      <div className="main">
        <Topbar
          crumbs={crumbs}
          onNavigate={(r, id) => safeNavigate(r, id)}
          currentUser={currentUser}
          onLogout={handleLogout}
          onOpenNavigation={() => setSidebarOpen(true)}
        />
        <BannerBar surface="admin" />
        <ImportStatusBanner currentRoute={route} />
        <main className="screen" id="main-content">
          {renderScreen()}
        </main>
      </div>
      <Tour variant={activeTour} route={route} navigate={navigate} onDone={() => setActiveTour(null)} />
    </div>
  )
}
