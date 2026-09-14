// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useNavigate } from 'react-router-dom'
import { useSearchResultNavigation } from '../hooks/useBackToSearch'
import { useI18n } from '../i18n'

export function SearchResultNavigation({ recordId }: { recordId: string }) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const { canPrevious, canNext, loading, move } = useSearchResultNavigation(recordId)

  if (!canPrevious && !canNext) return null

  async function navigateTo(direction: -1 | 1) {
    const path = await move(direction)
    if (path) navigate(path)
  }

  return (
    <div style={{ display: 'flex', gap: 2, marginLeft: 'auto' }} aria-label={t('search.resultNavigation')}>
      <button type="button" className="search-result-nav" onClick={() => navigateTo(-1)} disabled={!canPrevious || loading} aria-label={t('search.previousResult')} title={t('search.previousResult')}>←</button>
      <button type="button" className="search-result-nav" onClick={() => navigateTo(1)} disabled={!canNext || loading} aria-label={t('search.nextResult')} title={t('search.nextResult')}>→</button>
    </div>
  )
}
