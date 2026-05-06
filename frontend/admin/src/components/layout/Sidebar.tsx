import { getTokenUser } from '../../api/client'
import { File, History, Gear, Image, Layers, Lightning, MapPin, Tag, Upload, User, Users } from '../ui/Icons'
import { Search } from '../ui/Icons'

type Route = string

interface NavItem {
  g?: string
  id?: string
  label?: string
  Icon?: React.FC<{ size?: number; className?: string }>
  ct?: string
  routes?: string[]
  roles?: string[]
}

const NAV: NavItem[] = [
  { g: 'Inhalte' },
  { id: 'list',             label: 'Objekte',       Icon: Image,     routes: ['list', 'form'] },
  { id: 'entities-list',   label: 'Entitäten',      Icon: User,      routes: ['entities-list', 'entities-form'] },
  { id: 'places-list',     label: 'Orte',           Icon: MapPin,    routes: ['places-list', 'places-form'] },
  { id: 'occurrences-list', label: 'Occurrences',   Icon: Lightning, routes: ['occurrences-list', 'occurrences-form'] },
  { id: 'import',          label: 'Importer',       Icon: Upload,    ct: '2 aktiv' },
  { id: 'audit',           label: 'Audit-Log',      Icon: History },
  { g: 'Konfiguration', roles: ['admin'] },
  { id: 'schema', label: 'Schemata',        Icon: Layers,  ct: '5', roles: ['admin'] },
  { id: 'vocab',  label: 'Vokabular',       Icon: Tag,     ct: '4', roles: ['admin'] },
  { id: 'pages',  label: 'Statische Seiten', Icon: File,              roles: ['admin'] },
  { g: 'Verwaltung', roles: ['admin'] },
  { id: 'users',  label: 'Benutzer',       Icon: Users,   roles: ['admin'] },
  { id: 'settings', label: 'Einstellungen', Icon: Gear, roles: ['admin'] },
]

interface Props {
  route: Route
  setRoute: (r: Route) => void
  onLogout: () => void
}

export function Sidebar({ route, setRoute, onLogout }: Props) {
  const user = getTokenUser()
  const initials = user?.email ? user.email[0].toUpperCase() : 'A'
  const roleLabel: Record<string, string> = { admin: 'Administrator', editor: 'Redakteur', cataloger: 'Katalogisierer', viewer: 'Betrachter' }

  return (
    <aside className="sb">
      <div className="sb-brand">
        <div className="logo">K</div>
        <div className="sb-name">Katalon</div>
        <div className="sb-env">Stage</div>
      </div>

      <nav className="sb-nav">
        {NAV.map((it, i) => {
          if (it.g) {
            const visible = !it.roles || it.roles.includes(user?.role ?? '')
            return visible ? <div key={`g${i}`} className="sb-grp">{it.g}</div> : null
          }
          const visible = !it.roles || it.roles.includes(user?.role ?? '')
          if (!visible) return null
          return (
            <button
              key={it.id}
              className={`sb-it${route === it.id || (it.routes ?? []).includes(route) ? ' active' : ''}`}
              onClick={() => setRoute(it.id!)}
            >
              {it.Icon && <it.Icon className="ic" size={15} />}
              <span>{it.label}</span>
              {it.ct && <span className="ct">{it.ct}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sb-foot">
        <div className="sb-av">{initials}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <b style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.email ?? '—'}
          </b>
          <small>{roleLabel[user?.role ?? ''] ?? user?.role ?? ''}</small>
        </div>
        <button
          onClick={onLogout}
          title="Abmelden"
          style={{ background: 'none', border: 0, color: 'var(--sb-mute)', cursor: 'pointer', padding: '4px', borderRadius: 4, flexShrink: 0 }}
        >
          ⏻
        </button>
      </div>
    </aside>
  )
}
