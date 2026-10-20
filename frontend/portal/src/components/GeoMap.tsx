// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

/** Read-only map for a WGS84 point; a blue circle shows the accuracy (metres) when set. */
export default function GeoMap({ lat, lon, accuracy, label }: { lat: number; lon: number; accuracy?: number; label: string }) {
  const el = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!el.current) return
    const map = L.map(el.current, { scrollWheelZoom: false })
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map)
    map.setView([lat, lon], 14)
    L.circleMarker([lat, lon], { radius: 6 }).addTo(map)
    if (accuracy && accuracy > 0) {
      const circle = L.circle([lat, lon], { radius: accuracy }).addTo(map)
      map.fitBounds(circle.getBounds(), { maxZoom: 17 })
    }
    return () => { map.remove() }
  }, [lat, lon, accuracy])

  return <div ref={el} role="img" aria-label={label} style={{ height: 200, borderRadius: 8, border: '1px solid var(--border)', marginTop: 8 }} />
}
