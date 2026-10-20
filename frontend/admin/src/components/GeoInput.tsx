// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export type GeoEntry = { lat: number; lon: number; accuracy_m?: number }

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const DEFAULT_VIEW: [number, number] = [51, 10]

function parseCoord(text: string, limit: number): number | null {
  const n = Number(text.replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(n) && Math.abs(n) <= limit ? n : null
}

interface Props {
  value: GeoEntry | undefined
  onChange: (v: GeoEntry | undefined) => void
  disabled?: boolean
}

/** WGS84 point as two decimal-degree inputs plus an optional accuracy; a map click sets the point. */
export function GeoInput({ value, onChange, disabled }: Props) {
  const { t } = useTranslation('screenForm')
  const [lat, setLat] = useState(value ? String(value.lat) : '')
  const [lon, setLon] = useState(value ? String(value.lon) : '')
  const [accuracy, setAccuracy] = useState(value?.accuracy_m != null ? String(value.accuracy_m) : '')
  const [showMap, setShowMap] = useState(false)
  const mapEl = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const marker = useRef<L.CircleMarker | null>(null)
  const circle = useRef<L.Circle | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const latNum = parseCoord(lat, 90)
  const lonNum = parseCoord(lon, 180)
  const accNum = accuracy.trim() === '' ? undefined : Number(accuracy.replace(',', '.'))
  const accInvalid = accNum !== undefined && !(Number.isFinite(accNum) && accNum >= 0)
  const invalid = (lat !== '' && latNum === null) || (lon !== '' && lonNum === null) || accInvalid

  function emit(nextLat: string, nextLon: string, nextAcc: string) {
    const la = parseCoord(nextLat, 90)
    const lo = parseCoord(nextLon, 180)
    const ac = nextAcc.trim() === '' ? undefined : Number(nextAcc.replace(',', '.'))
    if (la === null || lo === null || (ac !== undefined && !(Number.isFinite(ac) && ac >= 0))) {
      onChange(undefined)
      return
    }
    onChange(ac === undefined ? { lat: la, lon: lo } : { lat: la, lon: lo, accuracy_m: ac })
  }

  useEffect(() => {
    if (!showMap || !mapEl.current) return
    const m = L.map(mapEl.current).setView(DEFAULT_VIEW, 5)
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(m)
    m.on('click', e => {
      const la = e.latlng.lat.toFixed(6)
      const lo = ((((e.latlng.lng + 180) % 360) + 360) % 360 - 180).toFixed(6)
      setLat(la)
      setLon(lo)
      emit(la, lo, accuracy)
    })
    map.current = m
    return () => {
      m.remove()
      map.current = null
      marker.current = null
      circle.current = null
    }
  }, [showMap])

  useEffect(() => {
    const m = map.current
    if (!m) return
    marker.current?.remove()
    circle.current?.remove()
    marker.current = circle.current = null
    if (latNum === null || lonNum === null) return
    marker.current = L.circleMarker([latNum, lonNum], { radius: 6 }).addTo(m)
    if (accNum && !accInvalid) circle.current = L.circle([latNum, lonNum], { radius: accNum }).addTo(m)
    m.setView([latNum, lonNum], Math.max(m.getZoom(), 12))
  }, [showMap, latNum, lonNum, accNum, accInvalid])

  return (
    <div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input className="fld mono" inputMode="decimal" value={lat} disabled={disabled} style={{ flex: 1 }}
          aria-label={t('geo.lat')} placeholder={t('geo.lat')}
          onChange={e => { setLat(e.target.value); emit(e.target.value, lon, accuracy) }} />
        <input className="fld mono" inputMode="decimal" value={lon} disabled={disabled} style={{ flex: 1 }}
          aria-label={t('geo.lon')} placeholder={t('geo.lon')}
          onChange={e => { setLon(e.target.value); emit(lat, e.target.value, accuracy) }} />
        <input className="fld mono" inputMode="decimal" value={accuracy} disabled={disabled} style={{ flex: 1 }}
          aria-label={t('geo.accuracy')} placeholder={t('geo.accuracy')}
          onChange={e => { setAccuracy(e.target.value); emit(lat, lon, e.target.value) }} />
        <button type="button" className="btn sm gh" onClick={() => setShowMap(s => !s)} disabled={disabled}>
          {showMap ? t('geo.hideMap') : t('geo.showMap')}
        </button>
      </div>
      {invalid && <div role="alert" style={{ color: 'var(--danger, #b00020)', fontSize: 12, marginTop: 4 }}>{t('geo.invalid')}</div>}
      {showMap && <div ref={mapEl} style={{ height: 280, marginTop: 6, borderRadius: 8, border: '1px solid var(--border)' }} />}
    </div>
  )
}
