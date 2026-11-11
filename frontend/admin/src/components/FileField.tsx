// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { attachments, HttpStatusError, type AttachmentRecordType, type AttachmentRef } from '../api/client'
import { AttachmentLightbox } from './AttachmentLightbox'
import { useAttachmentMaxUploadMb } from '../hooks/useAttachmentMaxUploadMb'
import { attachmentKind, formatFileSize, type AttachmentKind } from './attachmentUtils'
import { Alert, Eye, File as FileIcon, FileText, Image as ImageIcon, Music, Plus, Trash, Upload, Video, X } from './ui/Icons'

interface Props {
  recordType: AttachmentRecordType
  /** Id of the saved record; null while the record is still unsaved. */
  recordId: string | null
  repeatable: boolean
  /** Single reference, or the list for repeatable fields. */
  value: AttachmentRef | AttachmentRef[] | undefined
  /** Only changes the form value; the file is linked to the record when the form is saved. */
  onChange: (value: AttachmentRef | AttachmentRef[] | undefined) => void
  disabled?: boolean
}

interface UploadRow {
  key: number
  filename: string
  fraction: number
  controller: AbortController
}

interface ErrorRow {
  key: number
  filename: string
  message: string
}

const KIND_ICONS: Record<AttachmentKind, typeof FileIcon> = {
  pdf: FileText,
  image: ImageIcon,
  video: Video,
  audio: Music,
  other: FileIcon,
}

// Accept hint only; the backend validates the actual content.
const ACCEPT = 'application/pdf,image/*,audio/*,video/*'

let rowSeq = 0

function toList(value: AttachmentRef | AttachmentRef[] | undefined): AttachmentRef[] {
  if (Array.isArray(value)) return value
  return value ? [value] : []
}

/**
 * Form input for the "file" field type. Uploads go straight to the record's attachments
 * (requires a saved record); the reference is written into the form value and only
 * persisted with the rest of the form.
 */
export function FileField({ recordType, recordId, repeatable, value, onChange, disabled = false }: Props) {
  const { t, i18n } = useTranslation('fileField')
  // null while the limit is unknown: the pre-check is skipped and the backend enforces it.
  const maxUploadMb = useAttachmentMaxUploadMb()
  const files = toList(value)
  const inputRef = useRef<HTMLInputElement>(null)
  // Latest list, so parallel uploads in a repeatable field do not overwrite each other.
  const latestFilesRef = useRef(files)
  useEffect(() => {
    latestFilesRef.current = files
  })

  const [uploads, setUploads] = useState<UploadRow[]>([])
  const [errors, setErrors] = useState<ErrorRow[]>([])
  const [missingIds, setMissingIds] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  // Lightbox state; `opener` is the button that opened it, focus returns there on close.
  const [preview, setPreview] = useState<{ index: number; opener: HTMLElement } | null>(null)

  if (recordId == null) {
    return <div className="file-field-hint">{t('saveFirst')}</div>
  }

  const savedId = recordId
  const canUpload = !disabled

  function addError(filename: string, message: string) {
    const key = ++rowSeq
    setErrors(prev => [...prev, { key, filename, message }])
  }

  function tooLargeMessage(size: number) {
    const sizeLabel = formatFileSize(size, i18n.language)
    return maxUploadMb == null
      ? t('errorTooLargeNoMax', { size: sizeLabel })
      : t('errorTooLarge', { size: sizeLabel, max: maxUploadMb })
  }

  function uploadErrorMessage(err: unknown, size: number): string {
    if (err instanceof HttpStatusError) {
      if (err.status === 415) return t('errorType')
      if (err.status === 413) return tooLargeMessage(size)
      return err.message || t('errorGeneric')
    }
    return err instanceof Error && err.message ? err.message : t('errorGeneric')
  }

  function startUpload(file: File) {
    if (maxUploadMb != null && file.size > maxUploadMb * 1024 * 1024) {
      addError(file.name, tooLargeMessage(file.size))
      return
    }
    const key = ++rowSeq
    const controller = new AbortController()
    setUploads(prev => [...prev, { key, filename: file.name, fraction: 0, controller }])
    attachments.upload(
      recordType,
      savedId,
      file,
      fraction => setUploads(prev => prev.map(u => (u.key === key ? { ...u, fraction } : u))),
      controller.signal,
    )
      .then(ref => {
        if (repeatable) {
          const next = [...latestFilesRef.current, ref]
          latestFilesRef.current = next
          onChange(next)
        } else {
          onChange(ref)
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        addError(file.name, uploadErrorMessage(err, file.size))
      })
      .finally(() => {
        setUploads(prev => prev.filter(u => u.key !== key))
      })
  }

  function handleFiles(list: FileList | File[]) {
    // A non-repeatable field takes one file; extra files in a multi-selection are ignored.
    const selected = Array.from(list)
    const chosen = repeatable ? selected : selected.slice(0, 1)
    chosen.forEach(startUpload)
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files) handleFiles(e.target.files)
    e.target.value = ''
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    if (canUpload) handleFiles(e.dataTransfer.files)
  }

  function removeAt(index: number) {
    if (repeatable) {
      const next = files.filter((_, i) => i !== index)
      latestFilesRef.current = next
      onChange(next)
    } else {
      onChange(undefined)
    }
  }

  function markMissing(id: string) {
    setMissingIds(prev => (prev.includes(id) ? prev : [...prev, id]))
  }

  const openPicker = () => inputRef.current?.click()
  const showDropZone = !repeatable || files.length === 0

  return (
    <div className="file-field">
      {files.length > 0 && (
        <ul className="file-field-list">
          {files.map((file, index) => {
            const Icon = KIND_ICONS[attachmentKind(file.mime_type)]
            const missing = missingIds.includes(file.id)
            return (
              <li key={`${file.id}-${index}`} className="file-field-row">
                <Icon size={16} className="file-field-icon" />
                <span className="file-field-name" title={file.filename}>{file.filename}</span>
                {missing ? (
                  <span className="file-field-missing"><Alert size={13} /> {t('missing')}</span>
                ) : (
                  <span className="file-field-size">{formatFileSize(file.size, i18n.language)}</span>
                )}
                {!missing && (
                  <button type="button" className="btn sm ico gh" onClick={e => setPreview({ index, opener: e.currentTarget })} aria-label={t('view')} title={t('view')}>
                    <Eye size={14} />
                  </button>
                )}
                <button type="button" className="btn sm ico gh dn" onClick={() => removeAt(index)} disabled={disabled} aria-label={t('remove')} title={t('remove')}>
                  <Trash size={14} />
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {uploads.map(upload => (
        <div key={upload.key} className="file-field-row file-field-uploading">
          <FileIcon size={16} className="file-field-icon" />
          <span className="file-field-name" title={upload.filename}>{upload.filename}</span>
          <progress className="file-field-progress" value={upload.fraction} max={1} aria-label={upload.filename} />
          <span className="file-field-size">{t('uploadPercent', { percent: Math.round(upload.fraction * 100) })}</span>
          <button type="button" className="btn sm ico gh" onClick={() => upload.controller.abort()} aria-label={t('cancelUpload')} title={t('cancelUpload')}>
            <X size={14} />
          </button>
        </div>
      ))}

      {errors.map(error => (
        <div key={error.key} className="file-field-row file-field-error" role="alert">
          <Alert size={14} className="file-field-icon" />
          <span className="file-field-name">{t('errorRow', { filename: error.filename, message: error.message })}</span>
          <button
            type="button"
            className="btn sm ico gh"
            onClick={() => setErrors(prev => prev.filter(e => e.key !== error.key))}
            aria-label={t('dismiss')}
            title={t('dismiss')}
          >
            <X size={14} />
          </button>
        </div>
      ))}

      <input ref={inputRef} type="file" hidden multiple={repeatable} accept={ACCEPT} disabled={!canUpload} onChange={onInputChange} />

      {showDropZone ? (
        <div
          className={`dz file-field-dropzone${dragOver ? ' over' : ''}`}
          onDragOver={e => { if (!canUpload) return; e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <button type="button" className="btn sm" onClick={openPicker} disabled={!canUpload}>
            <Upload size={13} /> {t('select')}
          </button>
          <span className="file-field-drop-text">{t('dropHint')}</span>
          <span className="file-field-limit">{maxUploadMb == null ? t('hintNoMax') : t('hint', { max: maxUploadMb })}</span>
        </div>
      ) : (
        <div>
          <button type="button" className="btn sm gh" onClick={openPicker} disabled={!canUpload}>
            <Plus size={12} /> {t('addMore')}
          </button>
        </div>
      )}

      {preview && files[preview.index] && (
        <AttachmentLightbox
          files={files}
          index={preview.index}
          onIndexChange={index => setPreview({ ...preview, index })}
          onClose={() => setPreview(null)}
          onMissing={markMissing}
          returnFocusTo={preview.opener}
        />
      )}
    </div>
  )
}
