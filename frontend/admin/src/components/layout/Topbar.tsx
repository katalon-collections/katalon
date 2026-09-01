// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { /* Bell, */ Search, Help, User } from '../ui/Icons'
import { UI_LANGUAGES, setUiLanguage } from '../../i18n'
import { search } from '../../api/client'
import type { SearchResult } from '../../types'

const TYPE_LABELS: Record<string, string> = {
  object: 'Obj', entity: 'Ent', place: 'Ort', occurrence: 'Occ', procedure: 'Vor',
}

const DOCS_BASE = 'https://github.com/karkraeg/katalon-docs/blob/main'
const DOCS_ROOT = 'https://github.com/karkraeg/katalon-docs'
// TODO: form-variants/subtypes docs sind noch nicht ins katalon-docs-Repo migriert,
// deshalb übergangsweise Blob-Link ins Hauptrepo statt DOCS_BASE. Nach Migration auf DOCS_BASE umstellen.
const MAIN_REPO_DOCS = 'https://github.com/karkraeg/Katalon/blob/main/docs'

const ROUTE_DOCS: Record<string, string> = {
  schema: `${DOCS_BASE}/02_schema_verwaltung.md`,
  import: `${DOCS_BASE}/03_csv_import.md`,
  'form-variants': `${MAIN_REPO_DOCS}/11_formularvarianten.md`,
  subtypes: `${MAIN_REPO_DOCS}/12_subtypen.md`,
  list: `${MAIN_REPO_DOCS}/05_batch_bearbeitung.md`,
  'entities-list': `${MAIN_REPO_DOCS}/05_batch_bearbeitung.md`,
  'places-list': `${MAIN_REPO_DOCS}/05_batch_bearbeitung.md`,
  'occurrences-list': `${MAIN_REPO_DOCS}/05_batch_bearbeitung.md`,
  'procedures-list': `${MAIN_REPO_DOCS}/05_batch_bearbeitung.md`,
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
  const [results, setResults] = useState<SearchResult[]>([])
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
      search.query(q.trim())
        .then(r => { setResults(r.items); setOpen(true) })
        .catch(() => { setResults([]) })
        .finally(() => setLoading(false))
    }, 250)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q])

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  function handleSelect(r: SearchResult) {
    setQ('')
    setOpen(false)
    if (r.record_type === 'object') {
      onNavigate?.('form', r.id)
    } else if (r.record_type === 'entity') {
      onNavigate?.('entities-form', r.id)
    } else if (r.record_type === 'place') {
      onNavigate?.('places-form', r.id)
    } else if (r.record_type === 'occurrence') {
      onNavigate?.('occurrences-form', r.id)
    } else if (r.record_type === 'procedure') {
      onNavigate?.('procedures-form', r.id)
    }
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
                onMouseLeave={e => (e.currentTarget.style.background = '')}
              >
                <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--accent-50)', color: 'var(--accent-ink)', padding: '1px 5px', borderRadius: 4, flexShrink: 0 }}>
                  {TYPE_LABELS[r.record_type] ?? r.record_type}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</span>
                {r.status && <span style={{ fontSize: 11, color: 'var(--fg-3)', flexShrink: 0 }}>{r.status}</span>}
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
