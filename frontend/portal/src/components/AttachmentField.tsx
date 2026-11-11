// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useRef, useState } from 'react'
import { useI18n } from '../i18n'
import { type AttachmentFile, attachmentKind, formatFileSize } from '../utils/attachments'
import { AttachmentIcon } from './AttachmentIcon'
import { AttachmentLightbox, attachmentFileUrl } from './AttachmentLightbox'

/** Rows of a `file` field value: name opens the lightbox, size and download link stay beside it. */
export function AttachmentList({ files }: { files: AttachmentFile[] }) {
  const { t, locale } = useI18n()
  const [index, setIndex] = useState<number | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  if (files.length === 0) return null

  return (
    <>
      <div className="attachment-list">
        {files.map((file, i) => {
          const kind = attachmentKind(file.mime_type)
          return (
            <div key={file.id} className="attachment-list__item">
              <button
                type="button"
                className="attachment-list__open"
                title={t('file.open')}
                onClick={event => {
                  triggerRef.current = event.currentTarget
                  setIndex(i)
                }}
              >
                <AttachmentIcon name={kind} label={t(`file.kind.${kind}`)} />
                <span className="attachment-list__name">{file.filename}</span>
              </button>
              {file.size !== undefined && (
                <span className="attachment-list__size">{formatFileSize(file.size, locale)}</span>
              )}
              <a
                href={attachmentFileUrl(file.id)}
                download={file.filename}
                className="attachment-list__download"
                aria-label={t('file.downloadNamed', { name: file.filename })}
                title={t('file.download')}
              >
                <AttachmentIcon name="download" />
              </a>
            </div>
          )
        })}
      </div>
      <AttachmentLightbox
        files={files}
        index={index}
        onIndexChange={setIndex}
        onClose={() => {
          setIndex(null)
          triggerRef.current?.focus()
        }}
      />
    </>
  )
}
