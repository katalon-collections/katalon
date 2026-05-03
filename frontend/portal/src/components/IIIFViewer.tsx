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
        // Extract IIIF Image API URL from manifest
        let tileSource: string | undefined

        if (manifest.items && manifest.items[0]) {
          const canvas = manifest.items[0]
          if (canvas.items && canvas.items[0] && canvas.items[0].items) {
            const annotation = canvas.items[0].items[0]
            if (annotation.body) {
              const body = annotation.body
              if (body.service && body.service[0]) {
                tileSource = body.service[0].id + '/info.json'
              } else if (typeof body.id === 'string') {
                tileSource = body.id.replace(/\/full\/.*$/, '') + '/info.json'
              }
            }
          }
        }

        if (!tileSource) {
          throw new Error('Kein IIIF Tile Source im Manifest gefunden')
        }

        // Check if info.json is reachable
        return fetch(tileSource, { method: 'HEAD' })
          .then(r => {
            if (!r.ok) throw new Error('IIIF Image API nicht erreichbar')
            return tileSource!
          })
      })
      .then(tileSource => {
        if (!containerRef.current) return
        viewerRef.current = OpenSeadragon({
          element: containerRef.current,
          tileSources: tileSource,
          prefixUrl: 'https://cdn.jsdelivr.net/npm/openseadragon@6.0/build/openseadragon/images/',
          showNavigationControl: true,
          showZoomControl: true,
          showHomeControl: true,
          showFullPageControl: false,
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
