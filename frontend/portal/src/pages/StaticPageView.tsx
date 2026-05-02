import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type StaticPageSummary } from '../api/client'

export function StaticPageView() {
  const { slug } = useParams<{ slug: string }>()
  const [page, setPage] = useState<StaticPageSummary | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!slug) return
    api.pages.get(slug)
      .then(setPage)
      .catch(() => setError(true))
  }, [slug])

  if (error) {
    return (
      <div className="container page">
        <h1>Seite nicht gefunden</h1>
        <p>Die angeforderte Seite existiert nicht oder ist nicht veröffentlicht.</p>
      </div>
    )
  }

  if (!page) {
    return <div className="container page" style={{ color: 'var(--fg-3)', fontSize: 14 }}>Lade…</div>
  }

  const lang = 'de'
  const title = (page.title as Record<string, string>)[lang] ?? Object.values(page.title)[0] ?? page.slug
  const content = (page.content as Record<string, string>)[lang] ?? Object.values(page.content)[0] ?? ''

  return (
    <div className="container page">
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>{title}</h1>
      <div style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap', color: 'var(--fg)' }}>
        {content}
      </div>
    </div>
  )
}
