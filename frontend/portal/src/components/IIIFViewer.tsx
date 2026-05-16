import { useEffect, useRef } from 'react'
import OpenSeadragon from 'openseadragon'

interface Props {
  manifestUrl: string
  onError?: () => void
}

export function IIIFViewer({ manifestUrl, onError }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<OpenSeadragon.Viewer | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Destroy previous viewer
    if (viewerRef.current) {
      viewerRef.current.destroy()
      viewerRef.current = null
    }

    fetch(manifestUrl)
      .then(r => r.ok ? r.json() : Promise.reject(new Error('Manifest nicht verfügbar')))
      .then(manifest => {
        const canvases: unknown[] = Array.isArray(manifest.items) ? manifest.items : []
        if (canvases.length === 0) throw new Error('Kein Canvas im Manifest gefunden')

        const tileSources: string[] = []
        for (const canvas of canvases) {
          const c = canvas as Record<string, unknown>
          const pageList = c.items as Record<string, unknown>[] | undefined
          const annotation = pageList?.[0]?.items as Record<string, unknown>[] | undefined
          const body = (annotation?.[0] as Record<string, unknown> | undefined)?.body as Record<string, unknown> | undefined
          if (!body) continue
          const services = body.service as Record<string, unknown>[] | undefined
          if (services?.[0]?.id) {
            tileSources.push(String(services[0].id) + '/info.json')
          } else if (typeof body.id === 'string') {
            tileSources.push(body.id.replace(/\/full\/.*$/, '') + '/info.json')
          }
        }

        if (tileSources.length === 0) throw new Error('Kein IIIF Tile Source im Manifest gefunden')

        return fetch(tileSources[0], { method: 'HEAD' }).then(r => {
          if (!r.ok) throw new Error('IIIF Image API nicht erreichbar')
          return tileSources
        })
      })
      .then(tileSources => {
        if (!containerRef.current) return
        const multiImage = tileSources.length > 1
        viewerRef.current = OpenSeadragon({
          element: containerRef.current,
          tileSources,
          prefixUrl: 'https://cdn.jsdelivr.net/npm/openseadragon@6.0/build/openseadragon/images/',
          showNavigationControl: true,
          showZoomControl: true,
          showHomeControl: true,
          showFullPageControl: false,
          showSequenceControl: multiImage,
          sequenceMode: multiImage,
          minZoomLevel: 0.1,
          maxZoomLevel: 10,
          defaultZoomLevel: 0,
          visibilityRatio: 1,
          constrainDuringPan: true,
        })
      })
      .catch(() => {
        onError?.()
      })

    return () => {
      if (viewerRef.current) {
        viewerRef.current.destroy()
        viewerRef.current = null
      }
    }
  }, [manifestUrl, onError])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '500px',
        background: '#0f172a',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    />
  )
}
