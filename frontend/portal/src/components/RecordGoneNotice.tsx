// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useI18n } from '../i18n'

/** Tombstone page shown on HTTP 410 Gone for withdrawn public records. */
export function RecordGoneNotice() {
  const { t } = useI18n()
  const title = t('gone.defaultTitle')

  return (
    <div className="container page">
      <Helmet>
        <title>{title}</title>
        <meta name="robots" content="noindex" />
      </Helmet>
      <section className="record-gone" role="status" aria-labelledby="record-gone-title">
        <div className="record-gone__badge">{t('gone.badge')}</div>
        <h1 id="record-gone-title" className="record-gone__title">{title}</h1>
        <p className="record-gone__body">{t('gone.defaultText')}</p>
        <div className="record-gone__actions">
          <Link to="/" className="record-gone__primary">{t('gone.backHome')}</Link>
          <Link to="/search?q=" className="record-gone__secondary">{t('gone.browseCollection')}</Link>
        </div>
      </section>
    </div>
  )
}
