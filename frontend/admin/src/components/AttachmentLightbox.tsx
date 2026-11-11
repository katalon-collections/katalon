// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { attachments, HttpStatusError, type AttachmentRef } from '../api/client'
import { attachmentKind } from './attachmentUtils'
import { ChevL, ChevR, Download, X } from './ui/Icons'

interface Props {
  /** All files of the same field (or group entry); arrow keys stay inside this list. */
  files: AttachmentRef[]
  index: number
  onIndexChange: (index: number) => void
  onClose: () => void
  /** Called when the server no longer has the file (404). */
  onMissing: (id: string) => void
  /** Element that opened the viewer; focus returns to it when the viewer closes. */
  returnFocusTo: HTMLElement | null
}

/**
 * Native <dialog> viewer for attachments. Images are fetched as blobs (the endpoint
 * needs the bearer token). Video, audio and PDF use the signed link: video and audio
 * can seek without downloading the whole file, and a PDF must not run from a blob:
 * document, which inherits the page CSP.
 */
export function AttachmentLightbox({ files, index, onIndexChange, onClose, onMissing, returnFocusTo }: Props) {
  const { t } = useTranslation('fileField')
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const file = files[index]
  const kind = attachmentKind(file.mime_type)
  const [src, setSrc] = useState<string | null>(null)
  const [failure, setFailure] = useState<'missing' | 'failed' | null>(null)

  // Keep the latest callback without re-running the loader on every parent render.
  const onMissingRef = useRef(onMissing)
  useEffect(() => {
    onMissingRef.current = onMissing
  })

  // Modal focus handling: open as modal, return focus to the opener on unmount.
  const returnFocusRef = useRef(returnFocusTo)
  useEffect(() => {
    dialogRef.current?.showModal()
    const target = returnFocusRef.current
    return () => target?.focus()
  }, [])

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setSrc(null)
    setFailure(null)

    const load = async (): Promise<string> => {
      // PDF also uses the signed same-origin link: a blob: document inherits the admin
      // page CSP (object-src 'none'), which blocks the browser PDF viewer.
      if (kind === 'video' || kind === 'audio' || kind === 'pdf') return attachments.link(file.id)
      const blob = await attachments.fileBlob(file.id)
      objectUrl = URL.createObjectURL(blob)
      return objectUrl
    }

    load().then(
      url => {
        if (cancelled) {
          if (objectUrl) URL.revokeObjectURL(objectUrl)
          return
        }
        setSrc(url)
      },
      (err: unknown) => {
        if (cancelled) return
        if (err instanceof HttpStatusError && err.status === 404) {
          setFailure('missing')
          onMissingRef.current(file.id)
        } else {
          setFailure('failed')
        }
      },
    )

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [file.id, kind])

  function handleKeyDown(e: KeyboardEvent<HTMLDialogElement>) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    // Native media controls use the arrow keys for seeking.
    if (e.target instanceof Element && e.target.closest('video, audio')) return
    if (e.key === 'ArrowLeft' && index > 0) onIndexChange(index - 1)
    if (e.key === 'ArrowRight' && index < files.length - 1) onIndexChange(index + 1)
  }

  function renderContent() {
    if (failure === 'missing') return <p role="alert" className="attachment-lightbox-message">{t('missing')}</p>
    if (failure === 'failed') return <p role="alert" className="attachment-lightbox-message">{t('lightbox.loadFailed')}</p>
    if (!src) return <p className="attachment-lightbox-message">{t('lightbox.loading')}</p>
    if (kind === 'image') return <img src={src} alt={file.filename} className="attachment-lightbox-media" />
    if (kind === 'pdf') return <iframe src={src} title={file.filename} className="attachment-lightbox-frame" />
    if (kind === 'video') return <video src={src} controls autoPlay className="attachment-lightbox-media" />
    if (kind === 'audio') return <audio src={src} controls autoPlay className="attachment-lightbox-audio" />
    return <p className="attachment-lightbox-message">{t('lightbox.noPreview')}</p>
  }

  return (
    <dialog
      ref={dialogRef}
      className="attachment-lightbox"
      aria-labelledby={titleId}
      onCancel={e => { e.preventDefault(); onClose() }}
      onKeyDown={handleKeyDown}
    >
      <header className="attachment-lightbox-head">
        <h2 id={titleId} className="attachment-lightbox-title" title={file.filename}>{file.filename}</h2>
        <span className="attachment-lightbox-counter">{t('lightbox.counter', { current: index + 1, total: files.length })}</span>
        {src && (
          <a className="btn sm ico gh attachment-lightbox-action" href={src} download={file.filename} aria-label={t('lightbox.download')} title={t('lightbox.download')}>
            <Download size={14} />
          </a>
        )}
        <button type="button" className="btn sm ico gh attachment-lightbox-action" onClick={onClose} aria-label={t('lightbox.close')} title={t('lightbox.close')}>
          <X size={14} />
        </button>
      </header>

      <div className="attachment-lightbox-stage">
        {index > 0 && (
          <button type="button" className="btn sm ico gh attachment-lightbox-nav prev" onClick={() => onIndexChange(index - 1)} aria-label={t('lightbox.previous')} title={t('lightbox.previous')}>
            <ChevL size={16} />
          </button>
        )}
        {renderContent()}
        {index < files.length - 1 && (
          <button type="button" className="btn sm ico gh attachment-lightbox-nav next" onClick={() => onIndexChange(index + 1)} aria-label={t('lightbox.next')} title={t('lightbox.next')}>
            <ChevR size={16} />
          </button>
        )}
      </div>

      {src && (
        <footer className="attachment-lightbox-foot">
          <a href={src} target="_blank" rel="noopener noreferrer">{t('lightbox.openInTab')}</a>
        </footer>
      )}
    </dialog>
  )
}
