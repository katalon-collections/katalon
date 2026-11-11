// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { type KeyboardEvent, useEffect, useId, useRef } from 'react'
import { BASE, PORTAL_API } from '../api/client'
import { useI18n } from '../i18n'
import { type AttachmentFile, attachmentKind } from '../utils/attachments'
import { AttachmentIcon } from './AttachmentIcon'

/** Portal route answering inline (Content-Disposition: inline, Range support). */
export function attachmentFileUrl(id: string): string {
  return `${BASE}${PORTAL_API}/attachments/${encodeURIComponent(id)}/file`
}

interface Props {
  /** Files of one field (or one group entry); arrow keys move only within this list. */
  files: AttachmentFile[]
  /** Index of the shown file, or null when closed. */
  index: number | null
  onIndexChange: (index: number) => void
  /** Called once the dialog has closed (close button, Esc, or the dialog's own close). */
  onClose: () => void
}

/** Native modal dialog previewing one attachment. Inline routes make the file URL directly usable. */
export function AttachmentLightbox({ files, index, onIndexChange, onClose }: Props) {
  const { t } = useI18n()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const open = index !== null
  const file = index !== null ? files[index] : undefined

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    const handleClose = () => onClose()
    dialog.addEventListener('close', handleClose)
    return () => dialog.removeEventListener('close', handleClose)
  }, [onClose])

  function onKeyDown(event: KeyboardEvent<HTMLDialogElement>) {
    if (index === null) return
    // Arrow keys belong to the native audio/video controls while they have focus.
    if (event.target instanceof HTMLMediaElement) return
    if (event.key === 'ArrowLeft' && index > 0) {
      event.preventDefault()
      onIndexChange(index - 1)
    } else if (event.key === 'ArrowRight' && index < files.length - 1) {
      event.preventDefault()
      onIndexChange(index + 1)
    }
  }

  const url = file ? attachmentFileUrl(file.id) : ''

  return (
    <dialog
      ref={dialogRef}
      className="attachment-lightbox"
      aria-labelledby={titleId}
      onKeyDown={onKeyDown}
    >
      {file && index !== null && (
        <>
          <div className="attachment-lightbox__header">
            <span id={titleId} className="attachment-lightbox__title">{file.filename}</span>
            <span className="attachment-lightbox__count">
              {t('file.position', { current: index + 1, total: files.length })}
            </span>
            <a
              href={url}
              download={file.filename}
              className="attachment-lightbox__icon-btn"
              aria-label={t('file.downloadNamed', { name: file.filename })}
              title={t('file.download')}
            >
              <AttachmentIcon name="download" />
            </a>
            <button
              type="button"
              className="attachment-lightbox__icon-btn"
              aria-label={t('file.close')}
              title={t('file.close')}
              onClick={() => dialogRef.current?.close()}
            >
              <AttachmentIcon name="close" />
            </button>
          </div>
          <div className="attachment-lightbox__body">
            <button
              type="button"
              className="attachment-lightbox__nav"
              aria-label={t('file.previous')}
              title={t('file.previous')}
              disabled={index === 0}
              onClick={() => onIndexChange(index - 1)}
            >
              <AttachmentIcon name="previous" />
            </button>
            <div className="attachment-lightbox__content">
              <AttachmentPreview key={file.id} file={file} url={url} />
            </div>
            <button
              type="button"
              className="attachment-lightbox__nav"
              aria-label={t('file.next')}
              title={t('file.next')}
              disabled={index >= files.length - 1}
              onClick={() => onIndexChange(index + 1)}
            >
              <AttachmentIcon name="next" />
            </button>
          </div>
          <div className="attachment-lightbox__footer">
            <a href={url} target="_blank" rel="noopener noreferrer">{t('file.openInNewTab')}</a>
          </div>
        </>
      )}
    </dialog>
  )
}

function AttachmentPreview({ file, url }: { file: AttachmentFile; url: string }) {
  const { t } = useI18n()
  switch (attachmentKind(file.mime_type)) {
    case 'pdf':
      return <iframe src={url} title={file.filename} className="attachment-lightbox__frame" />
    case 'image':
      return <img src={url} alt={file.filename} className="attachment-lightbox__image" />
    case 'video':
      return <video src={url} controls className="attachment-lightbox__media" />
    case 'audio':
      return <audio src={url} controls className="attachment-lightbox__audio" />
    default:
      return <p className="attachment-lightbox__fallback">{t('file.noPreview')}</p>
  }
}
