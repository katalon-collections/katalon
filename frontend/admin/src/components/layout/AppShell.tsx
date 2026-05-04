import { useEffect, useState } from 'react'
import { hasToken, onUnauthorized, setToken } from '../../api/client'
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
  schema:             [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Schemata' }],
  vocab:              [{ label: 'Katalon' }, { label: 'Konfiguration' }, { label: 'Vokabular' }],
  import:             [{ label: 'Katalon' }, { label: 'Importer' }],
  audit:              [{ label: 'Katalon' }, { label: 'Audit-Log' }],
  users:              [{ label: 'Katalon' }, { label: 'Verwaltung' }, { label: 'Benutzer' }],
  settings:           [{ label: 'Katalon' }, { label: 'Einstellungen' }],
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

  const init = hashToState(window.location.hash)
  const [route, setRoute] = useState(init.route)
  const [editId, setEditId] = useState<string | null>(init.editId)

  useEffect(() => {
    onUnauthorized(() => setLoggedIn(false))
  }, [])

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

  function handleLogout() {
    setToken(null)
    setLoggedIn(false)
  }

  if (!loggedIn) {
    return <ScreenLogin onLogin={() => setLoggedIn(true)} />
  }

  const crumbs = CRUMBS[route] ?? [{ label: 'Katalon' }]

  function renderScreen() {
    switch (route) {
      case 'list':              return <ScreenList recordType="object"     onOpen={(id) => navigate('form', id)} />
      case 'form':              return <ScreenForm recordType="object"     recordId={editId ?? undefined} onBack={() => navigate('list')} onSaved={(id) => navigate('form', id)} />
      case 'entities-list':     return <ScreenList recordType="entity"     onOpen={(id) => navigate('entities-form', id)} />
      case 'entities-form':     return <ScreenForm recordType="entity"     recordId={editId ?? undefined} onBack={() => navigate('entities-list')} onSaved={(id) => navigate('entities-form', id)} />
      case 'places-list':       return <ScreenList recordType="place"      onOpen={(id) => navigate('places-form', id)} />
      case 'places-form':       return <ScreenForm recordType="place"      recordId={editId ?? undefined} onBack={() => navigate('places-list')} onSaved={(id) => navigate('places-form', id)} />
      case 'occurrences-list':  return <ScreenList recordType="occurrence" onOpen={(id) => navigate('occurrences-form', id)} />
      case 'occurrences-form':  return <ScreenForm recordType="occurrence" recordId={editId ?? undefined} onBack={() => navigate('occurrences-list')} onSaved={(id) => navigate('occurrences-form', id)} />
      case 'schema':            return <ScreenSchema />
      case 'vocab':             return <ScreenVocab />
      case 'import':            return <ScreenImporter />
      case 'audit':             return <ScreenAudit />
      case 'users':             return <ScreenUsers />
      case 'settings':          return <ScreenSettings onNavigate={(r) => navigate(r)} />
      default:                  return <Placeholder label={crumbs[crumbs.length - 1].label} />
    }
  }

  return (
    <div className="app">
      <Sidebar route={route} setRoute={(r) => navigate(r)} onLogout={handleLogout} />
      <div className="main">
        <Topbar crumbs={crumbs} onNavigate={(r, id) => navigate(r, id)} />
        {renderScreen()}
      </div>
    </div>
  )
}
