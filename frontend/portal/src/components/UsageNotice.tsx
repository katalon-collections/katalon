// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { useI18n } from '../i18n'
import { renderMarkdown } from '../utils/markdown'
import { resolveLangText } from '../utils/renderFieldValue'

export function noticeStorageKey(version: number): string {
  return `katalon_notice_v${version}`
}

function alreadyAccepted(version: number): boolean {
  try {
    return localStorage.getItem(noticeStorageKey(version)) === '1'
  } catch {
    return false
  }
}

/** One-time usage notice (portal settings): a modal dialog shown once per
 *  browser and notice version. Focus moves into the dialog, Tab stays inside
 *  it, and returns to where it was after accepting. */
export function UsageNotice() {
  const { locale, t } = useI18n()
  const notice = usePortalConfig().notice
  const [accepted, setAccepted] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const open = !!notice?.enabled && !accepted && !alreadyAccepted(notice.version)

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    buttonRef.current?.focus()
    return () => previous?.focus?.()
  }, [open])

  if (!open || !notice) return null

  function accept() {
    try {
      localStorage.setItem(noticeStorageKey(notice!.version), '1')
    } catch {
      // Private mode: the notice shows again next visit — acceptable.
    }
    setAccepted(true)
  }

  function trapFocus(event: React.KeyboardEvent) {
    if (event.key !== 'Tab' || !dialogRef.current) return
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>('a[href], button, [tabindex]:not([tabindex="-1"])')
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }

  const title = resolveLangText(notice.title, locale, t('notice.defaultTitle'))
  return (
    <div className="usage-notice-backdrop">
      <div
        ref={dialogRef}
        className="usage-notice"
        role="dialog"
        aria-modal="true"
        aria-labelledby="usage-notice-title"
        aria-describedby="usage-notice-text"
        onKeyDown={trapFocus}
      >
        <h2 id="usage-notice-title">{title}</h2>
        <div
          id="usage-notice-text"
          className="prose"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(resolveLangText(notice.text, locale, ''), { breaks: true }) }}
        />
        <div className="usage-notice__actions">
          <button ref={buttonRef} type="button" className="usage-notice__accept" onClick={accept}>
            {resolveLangText(notice.accept_label, locale, t('notice.accept'))}
          </button>
        </div>
      </div>
    </div>
  )
}
