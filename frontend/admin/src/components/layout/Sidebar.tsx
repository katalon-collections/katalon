// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import pkg from '../../../package.json'
import { useTranslation } from 'react-i18next'
import { getTokenUser } from '../../api/client'
import { FeedbackButton } from '../feedback/FeedbackButton'
import { Bell, Bookmark, Box, Code, Download, File, Folder, Globe, History, Gear, Image, Layers, Lightning, ListTree, MapPin, Tag, Upload, User, Users } from '../ui/Icons'

type Route = string

interface NavItem {
  gKey?: string
  id?: string
  labelKey?: string
  Icon?: React.FC<{ size?: number; className?: string }>
  ct?: string
  routes?: string[]
  roles?: string[]
  feature?: string
}

const NAV: NavItem[] = [
  { gKey: 'sidebar.groups.content' },
  { id: 'list',             labelKey: 'sidebar.nav.list',             Icon: Image,     routes: ['list', 'form'] },
  { id: 'collections-list', labelKey: 'sidebar.nav.collectionsList',  Icon: Folder,    routes: ['collections-list', 'collections-form'] },
  { id: 'entities-list',    labelKey: 'sidebar.nav.entitiesList',     Icon: User,      routes: ['entities-list', 'entities-form'] },
  { id: 'places-list',      labelKey: 'sidebar.nav.placesList',       Icon: MapPin,    routes: ['places-list', 'places-form'] },
  { id: 'occurrences-list', labelKey: 'sidebar.nav.occurrencesList',  Icon: Lightning, routes: ['occurrences-list', 'occurrences-form'] },
  { id: 'procedures-list',  labelKey: 'sidebar.nav.proceduresList',   Icon: ListTree,  routes: ['procedures-list', 'procedures-form'], roles: ['admin', 'superuser', 'editor', 'cataloger'] },
  { id: 'import',           labelKey: 'sidebar.nav.import',           Icon: Upload, feature: 'import' },
  { id: 'audit',            labelKey: 'sidebar.nav.audit',            Icon: History, feature: 'audit_log' },
  { id: 'working-sets',     labelKey: 'sidebar.nav.workingSets',      Icon: Bookmark,  routes: ['working-sets'], feature: 'working_sets' },
  { gKey: 'sidebar.groups.config', roles: ['admin', 'superuser'] },
  { id: 'subtypes', labelKey: 'sidebar.nav.subtypes',       Icon: ListTree, roles: ['admin', 'superuser'] },
  { id: 'storage-locations', labelKey: 'sidebar.nav.storageLocations', Icon: Box, feature: 'storage_locations' },
  { id: 'schema', labelKey: 'sidebar.nav.schema',           Icon: Layers,  ct: '6', roles: ['admin', 'superuser'] },
  { id: 'form-variants', labelKey: 'sidebar.nav.formVariants', Icon: Layers, roles: ['admin', 'superuser'] },
  { id: 'vocab',  labelKey: 'sidebar.nav.vocab',            Icon: Tag,     ct: '4', feature: 'vocab_terms' },
  { id: 'pages',     labelKey: 'sidebar.nav.pages',         Icon: File,  feature: 'pages' },
  { id: 'oai-sets',  labelKey: 'sidebar.nav.oaiSets',       Icon: Globe, feature: 'oai_sets' },
  { id: 'banners',   labelKey: 'sidebar.nav.banners',       Icon: Bell,  feature: 'banners' },
  { id: 'export',    labelKey: 'sidebar.nav.export',        Icon: Download, feature: 'export' },
  { id: 'sparql',    labelKey: 'sidebar.nav.sparql',        Icon: Code, feature: 'sparql' },
  { gKey: 'sidebar.groups.admin', roles: ['admin', 'superuser'] },
  { id: 'users',  labelKey: 'sidebar.nav.users',         Icon: Users,   roles: ['admin', 'superuser'] },
  { id: 'settings', labelKey: 'sidebar.nav.settings',    Icon: Gear, roles: ['admin', 'superuser'] },
]

interface Props {
  route: Route
  setRoute: (r: Route) => void
  appTitle?: string
  open?: boolean
  onClose?: () => void
  sparqlEnabled?: boolean
}

export function Sidebar({ route, setRoute, appTitle = 'Katalon', open = false, onClose, sparqlEnabled }: Props) {
  const { t } = useTranslation()
  const user = getTokenUser()

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
          const roleOk = !it.roles || it.roles.includes(user?.role ?? '')
          const featureOk = !it.feature || user?.features?.includes(it.feature)
          if (!roleOk || !featureOk) return null
          if (it.id === 'sparql' && !sparqlEnabled) return null
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

      <div className="sb-ver">Katalon Collections v{pkg.version}</div>
    </aside>
  )
}
