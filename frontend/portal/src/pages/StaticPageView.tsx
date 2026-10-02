// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, type StaticPageSummary } from '../api/client'
import { useI18n } from '../i18n'
import { resolveLangText } from '../utils/renderFieldValue'

export function StaticPageView() {
  const { slug } = useParams<{ slug: string }>()
  const [page, setPage] = useState<StaticPageSummary | null>(null)
  const [error, setError] = useState(false)
  const { locale, t } = useI18n()

  useEffect(() => {
    if (!slug) return
    api.pages.get(slug)
      .then(setPage)
      .catch(() => setError(true))
  }, [slug])

  if (error) {
    return (
      <div className="container page">
        <h1>{t('page.notFound')}</h1>
        <p>{t('page.notFoundBody')}</p>
      </div>
    )
  }

  if (!page) {
    return <div className="container page" style={{ color: 'var(--fg-3)', fontSize: 14 }}>{t('common.loading')}</div>
  }

  const lang = locale
  const title = resolveLangText(page.title as Record<string, string>, lang, page.slug)
  const content = resolveLangText(page.content as Record<string, string>, lang, '')

  const html = DOMPurify.sanitize(marked.parse(content) as string, {
    ADD_TAGS: ['video', 'source'],
    ADD_ATTR: ['controls', 'preload', 'loop', 'muted', 'playsinline', 'type', 'poster'],
  })
  const plainText = content.replace(/[#*`_[\]()>]/g, '').slice(0, 160)

  return (
    <div className="container page">
      <Helmet>
        <title>{title}</title>
        {plainText && <meta name="description" content={plainText} />}
        <meta property="og:title" content={title} />
        <meta property="og:url" content={window.location.href} />
        <meta property="og:type" content="article" />
      </Helmet>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>{title}</h1>
      <div
        className="prose"
        style={{ lineHeight: 1.7, color: 'var(--fg)' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
