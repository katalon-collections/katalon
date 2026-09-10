// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { adminEditUrl, canEdit, type PortalUser } from '../api/client'
import { t } from '../i18n'

/** Pencil icon linking to the admin edit screen for this record, shown only to signed-in staff with edit rights. */
export function EditRecordLink({ user, recordType, id }: { user: PortalUser | null; recordType: string; id: string }) {
  if (!canEdit(user)) return null
  return (
    <a
      href={adminEditUrl(recordType, id)}
      title={t('common.editInAdmin')}
      aria-label={t('common.editInAdmin')}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 28,
        height: 28,
        borderRadius: 6,
        border: '1px solid var(--border)',
        color: 'var(--fg-3)',
        marginLeft: 8,
        flexShrink: 0,
      }}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
        <path d="M11 2l3 3-8 8H3v-3l8-8z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </a>
  )
}
