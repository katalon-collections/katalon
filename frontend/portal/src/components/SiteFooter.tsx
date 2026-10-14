// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type FooterConfig, type FooterLink, type StaticPageSummary } from '../api/client'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { useI18n } from '../i18n'
import { renderMarkdown } from '../utils/markdown'
import { resolveLangText } from '../utils/renderFieldValue'

export function hasFooterContent(footer: FooterConfig | undefined): boolean {
  if (!footer) return false
  return footer.columns.length > 0
    || Object.values(footer.bottom?.text ?? {}).some(Boolean)
    || (footer.bottom?.links ?? []).length > 0
}

function pageLabel(page: StaticPageSummary, locale: string): string {
  return resolveLangText(page.title, locale, page.slug)
}

function FooterAnchor({ link, locale }: { link: FooterLink; locale: string }) {
  const label = resolveLangText(link.label, locale, link.url)
  return link.url.startsWith('/')
    ? <Link to={link.url}>{label}</Link>
    : <a href={link.url} target="_blank" rel="noopener noreferrer">{label}</a>
}

/** Portal footer: configured columns (Markdown text, links, logos) and a
 *  bottom line from the portal settings, or the built-in one-line footer. */
export function SiteFooter() {
  const { locale } = useI18n()
  const config = usePortalConfig()
  const [pages, setPages] = useState<StaticPageSummary[]>([])
  useEffect(() => { api.pages.list().then(ps => setPages(ps.filter(p => p.placement === 'footer'))).catch(() => {}) }, [])
  const footer = config.footer

  if (!hasFooterContent(footer)) {
    return (
      <footer className="site-footer">
        {resolveLangText(config.site_title, locale, 'Katalon')} · Metadata Management System
        {pages.map(p => (
          <span key={p.slug}>
            {' · '}
            <Link to={`/page/${p.slug}`} style={{ color: 'inherit' }}>{pageLabel(p, locale)}</Link>
          </span>
        ))}
        {' · '}
        <a href="/api/docs" style={{ color: 'inherit' }}>API</a>
      </footer>
    )
  }

  const bottomText = resolveLangText(footer!.bottom?.text, locale, '')
  return (
    <footer className="site-footer site-footer--configured">
      {footer!.columns.length > 0 && (
        <div className="site-footer__columns">
          {footer!.columns.map((column, index) => {
            const title = resolveLangText(column.title, locale, '')
            return (
              <section key={index} className={`site-footer__column site-footer__column--${column.type}`} aria-label={title || undefined}>
                {title && <h2 className="site-footer__title">{title}</h2>}
                {column.type === 'text' && (
                  <div
                    className="prose site-footer__text"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(resolveLangText(column.content, locale, ''), { breaks: true }) }}
                  />
                )}
                {column.type === 'links' && (
                  <ul className="site-footer__links">
                    {column.links.map((link, i) => <li key={i}><FooterAnchor link={link} locale={locale} /></li>)}
                    {column.include_footer_pages && pages.map(p => (
                      <li key={p.slug}><Link to={`/page/${p.slug}`}>{pageLabel(p, locale)}</Link></li>
                    ))}
                  </ul>
                )}
                {column.type === 'logos' && (
                  <ul className="site-footer__logos">
                    {column.logos.map((logo, i) => {
                      const img = <img src={logo.src} alt={resolveLangText(logo.alt, locale, '')} loading="lazy" />
                      return (
                        <li key={i}>
                          {logo.href
                            ? <a href={logo.href} target={logo.href.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{img}</a>
                            : img}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
      )}
      {(bottomText || (footer!.bottom?.links ?? []).length > 0) && (
        <div className="site-footer__bottom">
          {bottomText && (
            <div className="site-footer__bottom-text" dangerouslySetInnerHTML={{ __html: renderMarkdown(bottomText) }} />
          )}
          {(footer!.bottom?.links ?? []).length > 0 && (
            <ul className="site-footer__bottom-links">
              {footer!.bottom.links.map((link, i) => <li key={i}><FooterAnchor link={link} locale={locale} /></li>)}
            </ul>
          )}
        </div>
      )}
    </footer>
  )
}
