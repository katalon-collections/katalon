import { useEffect, useState } from 'react'
import { authorizedFetch, type MediaFile } from '../api/client'

interface Props {
  objectId: string
  media: MediaFile
  onClose: () => void
}

/** Lazy-register model-viewer (pulls in three.js) only for 3D media. */
function ModelStage({ src, alt }: { src: string; alt: string }) {
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
    return <div style={{ height: 300, display: 'grid', placeItems: 'center', color: '#94a3b8', fontSize: 13 }}>3D-Modell wird geladen…</div>
  }

  return <model-viewer src={src} alt={alt} camera-controls auto-rotate style={{ width: '100%', height: '70vh' }} />
}

/**
 * Fullscreen overlay viewer for a media file. The file endpoint is
 * auth-protected, so the blob is fetched with the bearer token and played
 * back from an object URL (plain <img>/<video>/<audio>/<iframe> cannot send
 * the Authorization header).
 */
export function MediaLightbox({ objectId, media, onClose }: Props) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    authorizedFetch(`/v1/objects/${objectId}/media/${media.id}/file`)
      .then(res => {
        if (!res.ok) throw new Error(`Fehler ${res.status}`)
        return res.blob()
      })
      .then(blob => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(e => {
        if (!cancelled) setError((e as Error).message)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [objectId, media.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(2,6,23,0.85)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '24px 32px 40px',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ position: 'relative', width: '100%', maxWidth: 1100, maxHeight: '100%', display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
          <span style={{ fontSize: 13, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{media.filename}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            style={{ flexShrink: 0, width: 32, height: 32, borderRadius: 6, border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(255,255,255,0.08)', color: '#e2e8f0', cursor: 'pointer', fontSize: 16, lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        <div style={{ borderRadius: 10, overflow: 'hidden', background: '#0f172a', display: 'grid', placeItems: 'center', minHeight: 200 }}>
          {error ? (
            <div style={{ padding: 32, color: '#dc2626', fontSize: 13 }}>{error}</div>
          ) : !url ? (
            <div style={{ padding: 32, color: '#94a3b8', fontSize: 13 }}>Lädt…</div>
          ) : media.category === 'image' ? (
            <img src={url} alt={media.filename} style={{ maxWidth: '100%', maxHeight: '78vh', objectFit: 'contain', display: 'block' }} />
          ) : media.category === 'video' ? (
            <video src={url} controls autoPlay style={{ maxWidth: '100%', maxHeight: '78vh', display: 'block' }} />
          ) : media.category === 'audio' ? (
            <div style={{ padding: 48, width: '100%' }}>
              <audio src={url} controls autoPlay style={{ width: '100%' }} />
            </div>
          ) : media.category === 'pdf' ? (
            <iframe src={url} title={media.filename} style={{ width: '100%', height: '78vh', border: 0 }} />
          ) : media.category === 'model' ? (
            <ModelStage src={url} alt={media.filename} />
          ) : (
            <a href={url} download={media.filename} style={{ padding: 32, color: '#e2e8f0', fontSize: 13 }}>Datei herunterladen</a>
          )}
        </div>
      </div>
    </div>
  )
}
