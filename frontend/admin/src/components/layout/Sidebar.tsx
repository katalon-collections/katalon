import { History, Gear, Image, Layers, Lightning, MapPin, Tag, Upload, User, Users } from '../ui/Icons'
import { Search } from '../ui/Icons'

type Route = string

interface NavItem {
  g?: string
  id?: string
  label?: string
  Icon?: React.FC<{ size?: number; className?: string }>
  ct?: string
  routes?: string[]
}

const NAV: NavItem[] = [
  { g: 'Inhalte' },
  { id: 'list',             label: 'Objekte',       Icon: Image,     routes: ['list', 'form'] },
  { id: 'entities-list',   label: 'Entitäten',      Icon: User,      routes: ['entities-list', 'entities-form'] },
  { id: 'places-list',     label: 'Orte',           Icon: MapPin,    routes: ['places-list', 'places-form'] },
  { id: 'occurrences-list', label: 'Occurrences',   Icon: Lightning, routes: ['occurrences-list', 'occurrences-form'] },
  { id: 'import',          label: 'Importer',       Icon: Upload,    ct: '2 aktiv' },
  { id: 'audit',           label: 'Audit-Log',      Icon: History },
  { g: 'Konfiguration' },
  { id: 'schema', label: 'Schemata',       Icon: Layers,  ct: '5' },
  { id: 'vocab',  label: 'Vokabular',      Icon: Tag,     ct: '4' },
  { g: 'Verwaltung' },
  { id: 'users',  label: 'Benutzer',       Icon: Users,   ct: '12' },
  { id: 'settings', label: 'Einstellungen', Icon: Gear },
]

interface Props {
  route: Route
  setRoute: (r: Route) => void
}

export function Sidebar({ route, setRoute }: Props) {
  return (
    <aside className="sb">
      <div className="sb-brand">
        <div className="logo">K</div>
        <div className="sb-name">Katalon</div>
        <div className="sb-env">Stage</div>
      </div>

      <div className="sb-search">
        <Search className="ic" size={14} />
        <input placeholder="Suchen…" />
        <span className="kbd">⌘K</span>
      </div>

      <nav className="sb-nav">
        {NAV.map((it, i) =>
          it.g ? (
            <div key={`g${i}`} className="sb-grp">{it.g}</div>
          ) : (
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
        )}
      </nav>

      <div className="sb-foot">
        <div className="sb-av">MB</div>
        <div>
          <b>Mira Bauer</b>
          <small>Kuratorin</small>
        </div>
      </div>
    </aside>
  )
}
