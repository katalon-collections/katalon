// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { /* Bell, */ Search, Help, User } from '../ui/Icons'
import { UI_LANGUAGES, setUiLanguage } from '../../i18n'
import { search } from '../../api/client'
import type { AdminSearchResult, SearchResult } from '../../types'

const TYPE_LABELS: Record<string, string> = {
  object: 'Obj', entity: 'Ent', place: 'Ort', occurrence: 'Occ', procedure: 'Vor',
}

const ADMIN_LABELS: Record<string, [string, string]> = {
  user: ['Ben', 'User'], vocabulary: ['Vok', 'Vocab'], vocabulary_term: ['Term', 'Term'], page: ['Seite', 'Page'], oai_set: ['OAI', 'OAI'],
  schema_field: ['Feld', 'Field'], subtype: ['Subtyp', 'Subtype'], form_variant: ['Formular', 'Form'], banner: ['Banner', 'Banner'],
  authority_source: ['Normdaten', 'Authority'], settings: ['Einstellung', 'Settings'],
}

function typeLabel(kind: string, language: string): string {
  return TYPE_LABELS[kind] ?? ADMIN_LABELS[kind]?.[language.startsWith('de') ? 0 : 1] ?? kind
}

function recordResult(result: SearchResult): AdminSearchResult {
  const routes: Record<string, string> = {
    object: 'form', entity: 'entities-form', place: 'places-form', occurrence: 'occurrences-form', procedure: 'procedures-form',
  }
  return { id: result.id, kind: result.record_type, title: result.title, subtitle: result.status, route: routes[result.record_type], edit_id: result.id }
}

function settingsResults(language: string): AdminSearchResult[] {
  const german = language.startsWith('de')
  const sections = [
    ['profil', 'Profil', 'Profile'], ['ueber', 'Über Katalon', 'About Katalon'], ['portal', 'Portal', 'Portal'],
    ['startseite', 'Startseite', 'Homepage'],
    ['facetten', 'Facetten', 'Facets'], ['sprachen', 'Sprachen', 'Languages'], ['idno', 'ID-Schemas', 'ID schemas'],
    ['ki', 'KI', 'AI'], ['medien', 'Medienrechte', 'Media rights'], ['authorities', 'Normdatenquellen', 'Authority sources'],
    ['suche', 'Suche & Indexierung', 'Search & indexing'], ['changelog', 'Versionshinweise', 'Release notes'],
    ['gefahrenbereich', 'Gefahrenbereich', 'Danger zone'],
  ]
  return sections.map(([id, de, en]) => ({
    id: `settings-${id}`, kind: 'settings', title: german ? de : en, subtitle: german ? 'Einstellungen' : 'Settings', route: 'settings', edit_id: id,
  }))
}

const DOCS_ROOT = 'https://katalon-collections.github.io/katalon-docs'

const ROUTE_DOCS: Record<string, string> = {
  schema: `${DOCS_ROOT}/administration/schema/`,
  import: `${DOCS_ROOT}/administration/import/`,
  'form-variants': `${DOCS_ROOT}/administration/formularvarianten/`,
  subtypes: `${DOCS_ROOT}/administration/subtypen/`,
  'storage-locations': `${DOCS_ROOT}/administration/lagerorte/`,
  list: `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'entities-list': `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'places-list': `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'occurrences-list': `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'procedures-list': `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'collections-list': `${DOCS_ROOT}/administration/batch-bearbeitung/`,
  'collections-form': `${DOCS_ROOT}/administration/sammlungen/`,
  'procedures-form': `${DOCS_ROOT}/reference/procedures/`,
  users: `${DOCS_ROOT}/administration/benutzer-und-rollen/`,
  'user-roles': `${DOCS_ROOT}/administration/benutzer-und-rollen/`,
  vocab: `${DOCS_ROOT}/administration/vokabulare/`,
  pages: `${DOCS_ROOT}/administration/statische-seiten/`,
  banners: `${DOCS_ROOT}/administration/banner/`,
  audit: `${DOCS_ROOT}/administration/audit-log/`,
  'working-sets': `${DOCS_ROOT}/administration/arbeitslisten/`,
  settings: `${DOCS_ROOT}/administration/einstellungen/`,
  'oai-sets': `${DOCS_ROOT}/integration/oai-pmh/`,
  export: `${DOCS_ROOT}/integration/export-mappings/`,
  sparql: `${DOCS_ROOT}/integration/sparql/`,
 }

interface Props {
  crumbs: Array<{ label: string; route?: string }>
  route?: string
  onNavigate?: (route: string, id?: string) => void
  currentUser?: { email: string; role: string } | null
  onLogout?: () => void
  onOpenNavigation?: () => void
}

export function Topbar({ crumbs, route, onNavigate, currentUser, onLogout, onOpenNavigation }: Props) {
  const { t, i18n } = useTranslation()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<AdminSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!q.trim()) { setResults([]); setOpen(false); return }
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      const query = q.trim()
      const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'superuser'
      const request = isAdmin
        ? search.admin(query)
        : search.query(query).then(r => ({ items: r.items.map(recordResult) }))
      request
        .then(r => {
          const settings = settingsResults(i18n.language).filter(item =>
            `${item.title} ${item.subtitle}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())
          )
          setResults([...r.items, ...settings])
          setOpen(true)
        })
        .catch(() => { setResults([]) })
        .finally(() => setLoading(false))
    }, 250)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q, currentUser?.role, i18n.language])

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  function handleSelect(r: AdminSearchResult) {
    setQ('')
    setOpen(false)
    onNavigate?.(r.route, r.edit_id ?? undefined)
  }

  return (
    <div className="tb">
      <button className="mobile-menu" aria-label={t('topbar.openNav')} onClick={onOpenNavigation}>
        <span />
        <span />
        <span />
      </button>
      <div className="cr">
        {crumbs.map((c, i) =>
          i === crumbs.length - 1 ? (
            <b key={i}>{c.label}</b>
          ) : c.route ? (
            <span key={i}>
              <button onClick={() => onNavigate?.(c.route!)}>{c.label}</button>
              <span className="sep"> / </span>
            </span>
          ) : (
            <span key={i}>{c.label}<span className="sep"> / </span></span>
          )
        )}
      </div>
      <div className="sp" />
      <div className="gs" ref={wrapRef} style={{ position: 'relative' }}>
        <Search size={14} />
        <input
          aria-label={t('topbar.globalSearch')}
          aria-expanded={open}
          aria-controls="global-search-results"
          placeholder={t('topbar.globalSearchPlaceholder')}
          value={q}
          onChange={e => setQ(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true) }}
        />
        {loading && <span style={{ fontSize: 11, color: 'var(--fg-4)', marginRight: 4 }}>…</span>}
        {/* <span className="kbd">⌘K</span> */}

        {open && results.length > 0 && (
          <div id="global-search-results" style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
            background: '#fff', border: '1px solid var(--border)', borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)', zIndex: 200, overflow: 'hidden',
          }}>
            {results.map(r => (
              <button key={r.id}
                type="button"
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', cursor: 'pointer', fontSize: 13, width: '100%', border: 0, background: 'transparent', textAlign: 'left' }}
                onClick={() => handleSelect(r)}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--accent-50)', color: 'var(--accent-ink)', padding: '1px 5px', borderRadius: 4, flexShrink: 0 }}>
                  {typeLabel(r.kind, i18n.language)}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</span>
                {r.subtitle && <span style={{ fontSize: 11, color: 'var(--fg-3)', flexShrink: 0 }}>{r.subtitle}</span>}
              </button>
            ))}
          </div>
        )}

        {open && results.length === 0 && q.trim() && !loading && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
            background: '#fff', border: '1px solid var(--border)', borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)', zIndex: 200,
            padding: '12px', fontSize: 13, color: 'var(--fg-3)', textAlign: 'center',
          }}>
            {t('topbar.noResults', { query: q })}
          </div>
        )}
      </div>
      {/* Benachrichtigungen ausgeblendet bis Implementierung (Issue #46) */}
      {/* <button className="ib" title="Benachrichtigungen"><Bell size={15} /></button> */}
      <a
        className="ib"
        title={t('topbar.help')}
        aria-label={t('topbar.help')}
        href={(route && ROUTE_DOCS[route]) || DOCS_ROOT}
        target="_blank"
        rel="noopener noreferrer"
      >
        <Help size={15} />
      </a>
      <div ref={userMenuRef} style={{ position: 'relative' }}>
        <button className="btn gh sm user-menu-trigger" onClick={() => setUserMenuOpen(v => !v)}>
          <User size={15} className="mobile-only" aria-hidden="true" />
          <span className="desktop-only">{currentUser?.email || t('topbar.user')} ▾</span>
        </button>
        {userMenuOpen && (
          <div style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            width: 220,
            background: '#fff',
            border: '1px solid var(--border)',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)',
            zIndex: 220,
            padding: 6,
          }}>
            <button
              className="btn gh"
              style={{ width: '100%', justifyContent: 'flex-start', borderRadius: 6 }}
              onClick={() => {
                setUserMenuOpen(false)
                onNavigate?.('settings')
              }}
            >
              {t('topbar.account')}
            </button>
            <div style={{ display: 'flex', gap: 4, padding: '4px 8px' }}>
              {UI_LANGUAGES.map(lng => (
                <button
                  key={lng}
                  className="btn gh sm"
                  style={{ flex: 1, fontWeight: i18n.language === lng ? 700 : 400 }}
                  onClick={() => setUiLanguage(lng)}
                >
                  {lng.toUpperCase()}
                </button>
              ))}
            </div>
            <button
              className="btn gh"
              style={{ width: '100%', justifyContent: 'flex-start', borderRadius: 6, color: '#b91c1c' }}
              onClick={() => {
                setUserMenuOpen(false)
                onLogout?.()
              }}
            >
              {t('topbar.logout')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
