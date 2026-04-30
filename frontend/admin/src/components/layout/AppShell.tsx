import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { ScreenList } from '../screens/ScreenList'
import { ScreenSchema } from '../screens/ScreenSchema'
import { ScreenVocab } from '../screens/ScreenVocab'
import { ScreenImporter } from '../screens/ScreenImporter'
import { ScreenAudit } from '../screens/ScreenAudit'

const CRUMBS: Record<string, string[]> = {
  list:     ['Katalon', 'Objekte'],
  form:     ['Katalon', 'Objekte', 'Bearbeiten'],
  schema:   ['Katalon', 'Konfiguration', 'Schemata'],
  vocab:    ['Katalon', 'Konfiguration', 'Vokabular'],
  import:   ['Katalon', 'Importer'],
  audit:    ['Katalon', 'Audit-Log'],
  users:    ['Katalon', 'Verwaltung', 'Benutzer'],
  settings: ['Katalon', 'Einstellungen'],
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
  const [route, setRoute] = useState('list')
  const [editId, setEditId] = useState<string | null>(null)

  const crumbs = CRUMBS[route] ?? ['Katalon']

  function renderScreen() {
    switch (route) {
      case 'list':     return <ScreenList onOpen={(id) => { setEditId(id); setRoute('form') }} />
      case 'schema':   return <ScreenSchema />
      case 'vocab':    return <ScreenVocab />
      case 'import':   return <ScreenImporter />
      case 'audit':    return <ScreenAudit />
      default:         return <Placeholder label={crumbs[crumbs.length - 1]} />
    }
  }

  return (
    <div className="app">
      <Sidebar route={route} setRoute={setRoute} />
      <div className="main">
        <Topbar crumbs={crumbs} />
        {renderScreen()}
      </div>
    </div>
  )
}
