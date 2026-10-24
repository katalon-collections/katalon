// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { X } from './ui/Icons'

export type GeoEntry = { lat: number; lon: number; accuracy_m?: number }

interface NominatimHit {
  place_id: number
  display_name: string
  lat: string
  lon: string
}

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
const DEFAULT_VIEW: [number, number] = [51, 10]

function parseCoord(text: string, limit: number): number | null {
  const n = Number(text.replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(n) && Math.abs(n) <= limit ? n : null
}

interface Props {
  value: GeoEntry | undefined
  onChange: (v: GeoEntry | undefined) => void
  disabled?: boolean
  showAccuracy?: boolean
}

/** WGS84 point as two decimal-degree inputs plus an optional accuracy; a map click or place search sets the point. */
export function GeoInput({ value, onChange, disabled, showAccuracy = true }: Props) {
  const { t } = useTranslation('screenForm')
  const [lat, setLat] = useState(value ? String(value.lat) : '')
  const [lon, setLon] = useState(value ? String(value.lon) : '')
  const [accuracy, setAccuracy] = useState(value?.accuracy_m != null ? String(value.accuracy_m) : '')
  const [showMap, setShowMap] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<NominatimHit[]>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchBusy, setSearchBusy] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const listId = useId()
  const searchWrapRef = useRef<HTMLDivElement>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const mapEl = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const marker = useRef<L.CircleMarker | null>(null)
  const circle = useRef<L.Circle | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const latNum = parseCoord(lat, 90)
  const lonNum = parseCoord(lon, 180)
  const accNum = !showAccuracy || accuracy.trim() === '' ? undefined : Number(accuracy.replace(',', '.'))
  const accInvalid = accNum !== undefined && !(Number.isFinite(accNum) && accNum >= 0)
  const invalid = (lat !== '' && latNum === null) || (lon !== '' && lonNum === null) || accInvalid

  useEffect(() => {
    if (!value) {
      if (latNum !== null && lonNum !== null) {
        setLat('')
        setLon('')
        setAccuracy('')
      }
      return
    }
    if (value.lat !== latNum) setLat(String(value.lat))
    if (value.lon !== lonNum) setLon(String(value.lon))
    const nextAcc = value.accuracy_m != null ? String(value.accuracy_m) : ''
    if ((value.accuracy_m ?? undefined) !== accNum) setAccuracy(nextAcc)
  }, [value?.lat, value?.lon, value?.accuracy_m])

  function emit(nextLat: string, nextLon: string, nextAcc: string) {
    const la = parseCoord(nextLat, 90)
    const lo = parseCoord(nextLon, 180)
    const ac = !showAccuracy || nextAcc.trim() === '' ? undefined : Number(nextAcc.replace(',', '.'))
    if (la === null || lo === null || (ac !== undefined && !(Number.isFinite(ac) && ac >= 0))) {
      onChangeRef.current(undefined)
      return
    }
    onChangeRef.current(ac === undefined ? { lat: la, lon: lo } : { lat: la, lon: lo, accuracy_m: ac })
  }

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [])

  useEffect(() => {
    clearTimeout(searchTimerRef.current)
    const q = searchQuery.trim()
    if (q.length < 2) {
      setSearchResults([])
      setSearchOpen(false)
      setSearchBusy(false)
      return
    }
    searchTimerRef.current = setTimeout(() => {
      setSearchBusy(true)
      const params = new URLSearchParams({ format: 'jsonv2', limit: '6', q })
      fetch(`${NOMINATIM_URL}?${params.toString()}`, { headers: { Accept: 'application/json' } })
        .then(r => (r.ok ? (r.json() as Promise<NominatimHit[]>) : Promise.resolve([])))
        .then(hits => {
          const valid = Array.isArray(hits) ? hits.filter(h => parseCoord(String(h.lat), 90) !== null && parseCoord(String(h.lon), 180) !== null) : []
          setSearchResults(valid)
          setSearchOpen(true)
          setActiveIndex(valid.length > 0 ? 0 : -1)
        })
        .catch(() => {
          setSearchResults([])
          setActiveIndex(-1)
        })
        .finally(() => setSearchBusy(false))
    }, 300)
    return () => clearTimeout(searchTimerRef.current)
  }, [searchQuery])

  function pickSearchResult(hit: NominatimHit) {
    const laNum = parseCoord(String(hit.lat), 90)
    const loNum = parseCoord(String(hit.lon), 180)
    if (laNum === null || loNum === null) return
    const la = laNum.toFixed(6)
    const lo = loNum.toFixed(6)
    setLat(la)
    setLon(lo)
    emit(la, lo, accuracy)
    setSearchOpen(false)
    setSearchQuery(hit.display_name)
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
    if (showAccuracy && accNum && !accInvalid) circle.current = L.circle([latNum, lonNum], { radius: accNum }).addTo(m)
    m.setView([latNum, lonNum], Math.max(m.getZoom(), 12))
  }, [showMap, showAccuracy, latNum, lonNum, accNum, accInvalid])

  return (
    <div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input className="fld mono" inputMode="decimal" value={lat} disabled={disabled} style={{ flex: 1 }}
          aria-label={t('geo.lat')} placeholder={t('geo.lat')}
          onChange={e => { setLat(e.target.value); emit(e.target.value, lon, accuracy) }} />
        <input className="fld mono" inputMode="decimal" value={lon} disabled={disabled} style={{ flex: 1 }}
          aria-label={t('geo.lon')} placeholder={t('geo.lon')}
          onChange={e => { setLon(e.target.value); emit(lat, e.target.value, accuracy) }} />
        {showAccuracy && (
          <input className="fld mono" inputMode="decimal" value={accuracy} disabled={disabled} style={{ flex: 1 }}
            aria-label={t('geo.accuracy')} placeholder={t('geo.accuracy')}
            onChange={e => { setAccuracy(e.target.value); emit(lat, lon, e.target.value) }} />
        )}
        <button type="button" className="btn sm gh" onClick={() => setShowMap(s => !s)} disabled={disabled}>
          {showMap ? t('geo.hideMap') : t('geo.showMap')}
        </button>
      </div>
      {invalid && (
        <div role="alert" style={{ color: 'var(--danger, #b00020)', fontSize: 12, marginTop: 4 }}>
          {showAccuracy ? t('geo.invalid') : t('geo.invalidCoords')}
        </div>
      )}
      {showMap && (
        <div style={{ marginTop: 6 }}>
          <div ref={searchWrapRef} style={{ position: 'relative', marginBottom: 6 }}>
            <input
              className="fld"
              value={searchQuery}
              disabled={disabled}
              placeholder={t('geo.searchPlaceholder')}
              aria-label={t('geo.searchPlaceholder')}
              aria-expanded={searchOpen}
              aria-controls={searchOpen ? listId : undefined}
              onFocus={() => { if (searchResults.length > 0) setSearchOpen(true) }}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Escape') {
                  setSearchOpen(false)
                  return
                }
                if (!searchResults.length || !['ArrowDown', 'ArrowUp', 'Enter'].includes(e.key)) return
                e.preventDefault()
                if (e.key === 'Enter') {
                  if (searchOpen && activeIndex >= 0 && searchResults[activeIndex]) {
                    pickSearchResult(searchResults[activeIndex])
                  }
                  return
                }
                setSearchOpen(true)
                setActiveIndex(i => e.key === 'ArrowDown'
                  ? Math.min(i + 1, searchResults.length - 1)
                  : Math.max(i <= 0 ? searchResults.length - 1 : i - 1, 0))
              }}
              style={{ paddingRight: searchQuery ? 28 : undefined }}
            />
            {searchQuery && !disabled && (
              <button
                type="button"
                className="btn sm ico gh"
                onClick={() => { setSearchQuery(''); setSearchResults([]); setSearchOpen(false) }}
                style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)' }}
              >
                <X size={12} />
              </button>
            )}
            {searchOpen && (searchResults.length > 0 || (!searchBusy && searchQuery.trim().length >= 2)) && (
              <div
                id={listId}
                role="listbox"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  left: 0,
                  right: 0,
                  zIndex: 1000,
                  background: 'var(--panel, #fff)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  boxShadow: '0 4px 16px rgba(0,0,0,.08)',
                  maxHeight: 240,
                  overflowY: 'auto',
                  padding: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                {searchResults.length === 0 ? (
                  <div style={{ padding: '6px 10px', fontSize: 12, color: 'var(--fg-3)' }}>{t('geo.noResults')}</div>
                ) : (
                  searchResults.map((hit, idx) => (
                    <button
                      key={hit.place_id}
                      type="button"
                      role="option"
                      aria-selected={idx === activeIndex}
                      className="btn sm gh"
                      style={{
                        textAlign: 'left',
                        justifyContent: 'flex-start',
                        background: idx === activeIndex ? 'var(--bg-hover, rgba(0,0,0,.04))' : undefined,
                      }}
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => pickSearchResult(hit)}
                    >
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hit.display_name}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <div ref={mapEl} style={{ height: 280, borderRadius: 8, border: '1px solid var(--border)' }} />
        </div>
      )}
    </div>
  )
}
