import pkg from '../../../package.json'
import { useTranslation } from 'react-i18next'
import { getTokenUser } from '../../api/client'
import { FeedbackButton } from '../feedback/FeedbackButton'
import { Bell, Download, File, Globe, History, Gear, Image, Layers, Lightning, ListTree, MapPin, Tag, Upload, User, Users } from '../ui/Icons'

type Route = string

interface NavItem {
  gKey?: string
  id?: string
  labelKey?: string
  Icon?: React.FC<{ size?: number; className?: string }>
  ct?: string
  routes?: string[]
  roles?: string[]
}

const NAV: NavItem[] = [
  { gKey: 'sidebar.groups.content' },
  { id: 'list',             labelKey: 'sidebar.nav.list',             Icon: Image,     routes: ['list', 'form'] },
  { id: 'entities-list',    labelKey: 'sidebar.nav.entitiesList',     Icon: User,      routes: ['entities-list', 'entities-form'] },
  { id: 'places-list',      labelKey: 'sidebar.nav.placesList',       Icon: MapPin,    routes: ['places-list', 'places-form'] },
  { id: 'occurrences-list', labelKey: 'sidebar.nav.occurrencesList',  Icon: Lightning, routes: ['occurrences-list', 'occurrences-form'] },
  { id: 'procedures-list',  labelKey: 'sidebar.nav.proceduresList',   Icon: ListTree,  routes: ['procedures-list', 'procedures-form'] },
  { id: 'import',           labelKey: 'sidebar.nav.import',           Icon: Upload },
  { id: 'audit',            labelKey: 'sidebar.nav.audit',            Icon: History },
  { gKey: 'sidebar.groups.config', roles: ['admin', 'superuser'] },
  { id: 'subtypes', labelKey: 'sidebar.nav.subtypes',       Icon: ListTree, roles: ['admin', 'superuser'] },
  { id: 'schema', labelKey: 'sidebar.nav.schema',           Icon: Layers,  ct: '5', roles: ['admin', 'superuser'] },
  { id: 'form-variants', labelKey: 'sidebar.nav.formVariants', Icon: Layers, roles: ['admin', 'superuser'] },
  { id: 'vocab',  labelKey: 'sidebar.nav.vocab',            Icon: Tag,     ct: '4', roles: ['admin', 'superuser'] },
  { id: 'pages',     labelKey: 'sidebar.nav.pages',         Icon: File,  roles: ['admin', 'superuser'] },
  { id: 'oai-sets',  labelKey: 'sidebar.nav.oaiSets',       Icon: Globe, roles: ['admin', 'superuser'] },
  { id: 'banners',   labelKey: 'sidebar.nav.banners',       Icon: Bell,  roles: ['admin', 'superuser'] },
  { id: 'export',    labelKey: 'sidebar.nav.export',        Icon: Download, roles: ['admin', 'superuser'] },
  { gKey: 'sidebar.groups.admin', roles: ['admin', 'superuser'] },
  { id: 'users',  labelKey: 'sidebar.nav.users',         Icon: Users,   roles: ['admin', 'superuser'] },
  { id: 'settings', labelKey: 'sidebar.nav.settings',    Icon: Gear, roles: ['admin', 'superuser'] },
]

interface Props {
  route: Route
  setRoute: (r: Route) => void
  onLogout: () => void
  appTitle?: string
  open?: boolean
  onClose?: () => void
}

export function Sidebar({ route, setRoute, onLogout, appTitle = 'Katalon', open = false, onClose }: Props) {
  const { t } = useTranslation()
  const user = getTokenUser()
  const initials = user?.email ? user.email[0].toUpperCase() : 'A'
  const roleLabel: Record<string, string> = {
    admin: t('sidebar.roles.admin'),
    editor: t('sidebar.roles.editor'),
    cataloger: t('sidebar.roles.cataloger'),
    viewer: t('sidebar.roles.viewer'),
  }

  return (
    <aside className={`sb${open ? ' open' : ''}`} aria-label={t('sidebar.mainNav')}>
      <div className="sb-brand">
        <div className="logo">K</div>
        <div className="sb-name">{appTitle}</div>
        <button className="sb-close" aria-label={t('sidebar.closeNav')} onClick={onClose}>×</button>
      </div>

      <nav className="sb-nav">
        {NAV.map((it, i) => {
          if (it.gKey) {
            const visible = !it.roles || it.roles.includes(user?.role ?? '')
            return visible ? <div key={`g${i}`} className="sb-grp">{t(it.gKey)}</div> : null
          }
          const visible = !it.roles || it.roles.includes(user?.role ?? '')
          if (!visible) return null
          return (
            <button
              key={it.id}
              className={`sb-it${route === it.id || (it.routes ?? []).includes(route) ? ' active' : ''}`}
              onClick={() => setRoute(it.id!)}
              data-tour={`nav-${it.id}`}
            >
              {it.Icon && <it.Icon className="ic" size={15} />}
              <span>{t(it.labelKey!)}</span>
              {it.ct && <span className="ct">{it.ct}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sb-feedback">
        <FeedbackButton />
      </div>

      <div className="sb-ver">v{pkg.version}</div>

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
          title={t('sidebar.logout')}
          style={{ background: 'none', border: 0, color: 'var(--sb-mute)', cursor: 'pointer', padding: '4px', borderRadius: 4, flexShrink: 0 }}
        >
          ⏻
        </button>
      </div>
    </aside>
  )
}
