import { useEffect, useState } from 'react'
import type { MediaFile } from '../api/client'
import { BASE, PORTAL_API } from '../api/client'

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
          width: '100%', height: '60vh', borderRadius: 10, background: '#0f172a',
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
      style={{ width: '100%', height: '60vh', borderRadius: 10, background: '#0f172a' }}
    />
  )
}

/**
 * The media file endpoint serves with `Content-Disposition: attachment`,
 * which makes a direct <iframe src> trigger a download instead of inline
 * rendering. Fetch the blob and play it back from an object URL (mirrors the
 * admin MediaLightbox approach) so the browser's PDF viewer renders inline.
 */
function PdfViewer({ src, title }: { src: string; title: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setUrl(null)
    setFailed(false)
    fetch(src)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.blob()
      })
      .then(blob => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  if (failed) {
    return (
      <div style={{ padding: 16, borderRadius: 10, background: '#0f172a' }}>
        <a href={src} target="_blank" rel="noreferrer" style={{ color: '#e2e8f0' }}>
          PDF öffnen ({title})
        </a>
      </div>
    )
  }
  if (!url) {
    return (
      <div style={{ width: '100%', height: '78vh', borderRadius: 10, background: '#0f172a', display: 'grid', placeItems: 'center', color: '#94a3b8', fontSize: 14 }}>
        PDF wird geladen…
      </div>
    )
  }
  return (
    <iframe
      src={url}
      title={title}
      style={{ width: '100%', height: '78vh', border: 0, borderRadius: 10, background: '#0f172a' }}
    />
  )
}

/**
 * Native viewer dispatch for non-image media (pdf/audio/video/model).
 * Images stay on the IIIF path in ObjectDetailPage.
 */
export function MediaViewer({ objectId, media }: Props) {
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
          style={{ width: '100%', maxHeight: '78vh', borderRadius: 10, background: '#0f172a' }}
        />
      )
    case 'model':
      return <ModelViewer src={src} alt={media.filename} />
    default:
      return (
        <div style={{ padding: 16, borderRadius: 10, background: '#0f172a' }}>
          <a href={src} target="_blank" rel="noreferrer" style={{ color: '#e2e8f0' }}>
            Datei öffnen ({media.filename})
          </a>
        </div>
      )
  }
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
        borderRadius: 8, overflow: 'hidden', background: '#0f172a',
      }}
    >
      {isImage ? (
        <img src={src} alt={media.filename} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
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
