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

const CRUMBS: Record<string, string[]> = {
  list:              ['Katalon', 'Objekte'],
  form:              ['Katalon', 'Objekte', 'Bearbeiten'],
  'entities-list':   ['Katalon', 'Entitäten'],
  'entities-form':   ['Katalon', 'Entitäten', 'Bearbeiten'],
  'places-list':     ['Katalon', 'Orte'],
  'places-form':     ['Katalon', 'Orte', 'Bearbeiten'],
  'occurrences-list': ['Katalon', 'Occurrences'],
  'occurrences-form': ['Katalon', 'Occurrences', 'Bearbeiten'],
  schema:            ['Katalon', 'Konfiguration', 'Schemata'],
  vocab:             ['Katalon', 'Konfiguration', 'Vokabular'],
  import:            ['Katalon', 'Importer'],
  audit:             ['Katalon', 'Audit-Log'],
  users:             ['Katalon', 'Verwaltung', 'Benutzer'],
  settings:          ['Katalon', 'Einstellungen'],
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
  const [route, setRoute] = useState('list')
  const [editId, setEditId] = useState<string | null>(null)

  useEffect(() => {
    onUnauthorized(() => setLoggedIn(false))
  }, [])

  function handleLogout() {
    setToken(null)
    setLoggedIn(false)
  }

  if (!loggedIn) {
    return <ScreenLogin onLogin={() => setLoggedIn(true)} />
  }

  const crumbs = CRUMBS[route] ?? ['Katalon']

  function renderScreen() {
    switch (route) {
      case 'list':              return <ScreenList recordType="object"     onOpen={(id) => { setEditId(id); setRoute('form') }} />
      case 'form':              return <ScreenForm recordType="object"     recordId={editId ?? undefined} onBack={() => setRoute('list')} onSaved={(id) => setEditId(id)} />
      case 'entities-list':     return <ScreenList recordType="entity"     onOpen={(id) => { setEditId(id); setRoute('entities-form') }} />
      case 'entities-form':     return <ScreenForm recordType="entity"     recordId={editId ?? undefined} onBack={() => setRoute('entities-list')} onSaved={(id) => setEditId(id)} />
      case 'places-list':       return <ScreenList recordType="place"      onOpen={(id) => { setEditId(id); setRoute('places-form') }} />
      case 'places-form':       return <ScreenForm recordType="place"      recordId={editId ?? undefined} onBack={() => setRoute('places-list')} onSaved={(id) => setEditId(id)} />
      case 'occurrences-list':  return <ScreenList recordType="occurrence" onOpen={(id) => { setEditId(id); setRoute('occurrences-form') }} />
      case 'occurrences-form':  return <ScreenForm recordType="occurrence" recordId={editId ?? undefined} onBack={() => setRoute('occurrences-list')} onSaved={(id) => setEditId(id)} />
      case 'schema':            return <ScreenSchema />
      case 'vocab':             return <ScreenVocab />
      case 'import':            return <ScreenImporter />
      case 'audit':             return <ScreenAudit />
      default:                  return <Placeholder label={crumbs[crumbs.length - 1]} />
    }
  }

  return (
    <div className="app">
      <Sidebar route={route} setRoute={setRoute} onLogout={handleLogout} />
      <div className="main">
        <Topbar crumbs={crumbs} onNavigate={(r, id) => { if (id) setEditId(id); setRoute(r) }} />
        {renderScreen()}
      </div>
    </div>
  )
}
