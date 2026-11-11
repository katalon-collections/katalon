// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import type { MediaFile } from '../api/client'
import { BASE, PORTAL_API } from '../api/client'
import { useI18n } from '../i18n'
import { thumbnailUrl } from '../utils/thumbnails'

interface Props {
  objectId: string
  media: MediaFile
}

function fileUrl(objectId: string, media: MediaFile): string {
  return `${BASE}${PORTAL_API}/objects/${objectId}/media/${media.id}/file`
}

/**
 * model-viewer pulls in three.js (~1 MB). Register it lazily so the 3D
 * dependency only loads for objects that actually have a model file.
 */
function ModelViewer({ src, alt }: { src: string; alt: string }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    import('@google/model-viewer').then(() => {
      if (!cancelled) setReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (!ready) {
    return (
      <div
        style={{
          width: '100%', height: '60vh', borderRadius: 10, background: 'var(--viewer-bg, #0f172a)',
          display: 'grid', placeItems: 'center', color: '#94a3b8', fontSize: 14,
        }}
      >
        3D-Modell wird geladen…
      </div>
    )
  }

  return (
    <model-viewer
      src={src}
      alt={alt}
      camera-controls
      auto-rotate
      style={{ width: '100%', height: '60vh', borderRadius: 10, background: 'var(--viewer-bg, #0f172a)' }}
    />
  )
}

/**
 * The file endpoint answers inline (no Content-Disposition: attachment), so the
 * iframe renders the PDF directly. The link below it is the fallback for
 * browsers that cannot show PDFs inline.
 */
function PdfViewer({ src, title }: { src: string; title: string }) {
  const { t } = useI18n()
  return (
    <div>
      <iframe
        src={src}
        title={title}
        style={{ width: '100%', height: '78vh', border: 0, borderRadius: 10, background: 'var(--viewer-bg, #0f172a)' }}
      />
      <a href={src} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: 8, color: 'var(--accent)' }}>
        {t('media.openPdf', { name: title })}
      </a>
    </div>
  )
}

/**
 * Native viewer dispatch for non-image media (pdf/audio/video/model).
 * Images stay on the IIIF path in ObjectDetailPage.
 */
export function MediaViewer({ objectId, media }: Props) {
  const { t } = useI18n()
  const src = fileUrl(objectId, media)

  switch (media.category) {
    case 'pdf':
      return <PdfViewer src={src} title={media.filename} />
    case 'audio':
      return <audio src={src} controls style={{ width: '100%' }} />
    case 'video':
      return (
        <video
          src={src}
          controls
          style={{ width: '100%', maxHeight: '78vh', borderRadius: 10, background: 'var(--viewer-bg, #0f172a)' }}
        />
      )
    case 'model':
      return <ModelViewer src={src} alt={media.filename} />
    default:
      return (
        <div style={{ padding: 16, borderRadius: 10, background: 'var(--viewer-bg, #0f172a)' }}>
          <a href={src} target="_blank" rel="noreferrer" style={{ color: '#e2e8f0' }}>
            {t('media.openFile', { name: media.filename })}
          </a>
        </div>
      )
  }
}

/**
 * Collapsible license/attribution block for a single media file, shown as
 * "Rechteangaben ⌄ <license url> · <rights holder name>", plus the permission
 * note (credit line) on its own line.
 */
export function RightsStatement({ media, label }: { media: MediaFile; label: string }) {
  const { license_uri, rights_holder, credit_line } = media
  if (!license_uri && !rights_holder?.name && !credit_line) return null

  return (
    <details style={{ marginTop: 12, fontSize: 12, color: 'var(--fg-3)' }}>
      <summary style={{ cursor: 'pointer' }}>{label}</summary>
      <div style={{ marginTop: 6 }}>
        {license_uri && (
          <a href={license_uri} target="_blank" rel="noreferrer" style={{ color: 'var(--fg-3)' }}>
            {license_uri}
          </a>
        )}
        {license_uri && rights_holder?.name && ' · '}
        {rights_holder?.name && (
          rights_holder.uri ? (
            <a href={rights_holder.uri} target="_blank" rel="noreferrer" style={{ color: 'var(--fg-3)' }}>
              {rights_holder.name}
            </a>
          ) : rights_holder.name
        )}
        {credit_line && <div style={{ marginTop: 4 }}>{credit_line}</div>}
      </div>
    </details>
  )
}

/**
 * Download links for an object's public media files (original file as
 * attachment). Shown only when the portal enables media downloads.
 */
export function MediaDownloads({ media, label }: { media: MediaFile[]; label: string }) {
  if (media.length === 0) return null
  return (
    <div style={{ marginTop: 12, fontSize: 12, color: 'var(--fg-3)' }}>
      <div style={{ fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {media.map(m => {
          const ext = m.filename.includes('.') ? m.filename.split('.').pop()!.toUpperCase() : ''
          return (
            <li key={m.id} style={{ overflowWrap: 'anywhere' }}>
              <a href={`${BASE}${PORTAL_API}/media/${m.id}/download`} download={m.filename} style={{ color: 'var(--accent)' }}>
                ⬇ {m.filename}
              </a>
              {ext && <span> · {ext}</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

const MEDIA_BADGE: Record<string, string> = {
  audio: 'AUDIO',
  video: 'VIDEO',
  pdf: 'PDF',
  model: '3D',
}

/**
 * Square clickable thumbnail for the media strip. Images use the raw file as
 * thumbnail; videos use the browser's first-frame preview; audio/pdf/model
 * render a type badge + filename.
 */
export function MediaThumb({ objectId, media, active, onSelect }: {
  objectId: string
  media: MediaFile
  active: boolean
  onSelect: () => void
}) {
  const src = fileUrl(objectId, media)
  const thumbnailSrc = thumbnailUrl(objectId, media.id, media.iiif_identifier)
  const badge = MEDIA_BADGE[media.category]
  const isImage = media.category === 'image'
  const isVideo = media.category === 'video'

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={media.filename}
      title={media.filename}
      aria-current={active}
      style={{
        position: 'relative', aspectRatio: '1', width: '100%', padding: 0, cursor: 'pointer',
        border: active ? '2px solid var(--accent)' : '1px solid var(--border-s)',
        borderRadius: 8, overflow: 'hidden', background: 'var(--viewer-bg, #0f172a)',
      }}
    >
      {isImage ? (
        <img src={thumbnailSrc} alt={media.filename} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
      ) : isVideo ? (
        <video src={src} muted preload="metadata" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
      ) : (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, padding: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--fg-1)' }}>{badge ?? 'FILE'}</span>
          <span style={{ fontSize: 8, color: 'var(--fg-3)', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{media.filename}</span>
        </div>
      )}
      {badge && isVideo && (
        <span style={{ position: 'absolute', top: 4, left: 4, fontSize: 8, fontWeight: 700, padding: '1px 4px', borderRadius: 3, background: 'rgba(0,0,0,0.55)', color: '#fff' }}>
          {badge}
        </span>
      )}
    </button>
  )
}
