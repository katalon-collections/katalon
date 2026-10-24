// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fetchRecord, type PortalFieldDefinition } from '../api/client'
import { useI18n } from '../i18n'
import { renderFieldValue } from '../utils/renderFieldValue'

const GeoMap = lazy(() => import('./GeoMap'))

const TYPE_PATHS: Record<string, string> = {
  object: 'objects',
  entity: 'entities',
  place: 'places',
  occurrence: 'occurrences',
  collection: 'collections',
}

export interface RelationEntry {
  id: string
  label: string
  relation_type?: string
}

function parseEntries(value: unknown): RelationEntry[] {
  if (value == null) return []

  const normalize = (v: unknown): RelationEntry | null => {
    if (typeof v !== 'object' || v === null || Array.isArray(v)) return null
    const o = v as Record<string, unknown>
    const id = typeof o.id === 'string' ? o.id : ''
    const label = typeof o.label === 'string' ? o.label : ''
    if (!id || !label) return null
    return { id, label, relation_type: typeof o.relation_type === 'string' ? o.relation_type : undefined }
  }

  if (Array.isArray(value)) {
    return value.map(normalize).filter((e): e is RelationEntry => e !== null)
  }
  const single = normalize(value)
  return single ? [single] : []
}

interface Props {
  label: string
  value: unknown
  targetType: string | undefined
  inheritedFields?: string[]
  showPlaceMap?: boolean
  locale?: string
  resolveRelationType: (code: string) => string
  /** Search pre-filtered by this target (field or relation facet); undefined: no facet covers it. */
  filterHref?: (entry: RelationEntry) => string | undefined
}

interface TargetRecordDetails {
  coords?: { lat: number; lon: number }
  metadata: Record<string, unknown>
}

export function RelationFieldRow({
  label,
  value,
  targetType,
  inheritedFields = [],
  showPlaceMap = false,
  locale = 'de',
  resolveRelationType,
  filterHref,
}: Props) {
  const { t } = useI18n()
  const entries = useMemo(() => parseEntries(value), [value])
  const [targetDetails, setTargetDetails] = useState<Record<string, TargetRecordDetails>>({})
  const [targetSchema, setTargetSchema] = useState<Record<string, PortalFieldDefinition>>({})
  const hasInherited = inheritedFields.length > 0
  const needsPlaceCoords = showPlaceMap && targetType === 'place'

  useEffect(() => {
    let cancelled = false
    if (!targetType || !hasInherited) {
      setTargetSchema({})
      return () => { cancelled = true }
    }
    api.portal.schema(targetType)
      .then(defs => {
        if (cancelled) return
        const byName: Record<string, PortalFieldDefinition> = {}
        for (const d of defs) byName[d.name] = d
        setTargetSchema(byName)
      })
      .catch(() => {
        if (!cancelled) setTargetSchema({})
      })
    return () => { cancelled = true }
  }, [targetType, hasInherited])

  useEffect(() => {
    let cancelled = false
    if (!targetType || (!needsPlaceCoords && !hasInherited) || entries.length === 0) {
      setTargetDetails({})
      return () => { cancelled = true }
    }
    const ids = [...new Set(entries.map(e => e.id))]
    Promise.all(
      ids.map(async id => {
        try {
          if (targetType === 'place') {
            const p = await api.places.get(id)
            const coords = typeof p.lat === 'number' && typeof p.lon === 'number'
              && Number.isFinite(p.lat) && Number.isFinite(p.lon)
              && Math.abs(p.lat) <= 90 && Math.abs(p.lon) <= 180
              ? { lat: p.lat, lon: p.lon }
              : undefined
            return [id, { coords, metadata: p.metadata_ ?? {} }] as const
          }
          const rec = await fetchRecord(targetType, id)
          return [id, { metadata: rec.metadata }] as const
        } catch {
          return null
        }
      })
    ).then(results => {
      if (cancelled) return
      const next: Record<string, TargetRecordDetails> = {}
      for (const item of results) {
        if (item) next[item[0]] = item[1]
      }
      setTargetDetails(next)
    })
    return () => { cancelled = true }
  }, [entries, needsPlaceCoords, hasInherited, targetType])

  if (entries.length === 0) return null

  const path = targetType ? TYPE_PATHS[targetType] : undefined

  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {entries.map(entry => {
          const details = targetDetails[entry.id]
          const coords = needsPlaceCoords ? details?.coords : undefined
          const inheritedRows = hasInherited && details?.metadata
            ? inheritedFields.flatMap(fname => {
                const fdef = targetSchema[fname]
                const text = renderFieldValue(details.metadata[fname], locale, fdef?.field_type)
                if (!text) return []
                const flabel = fdef?.label?.[locale] ?? fdef?.label?.de ?? fdef?.label?.en ?? fname
                return [{ key: fname, label: String(flabel), text }]
              })
            : []
          // Like vocabulary values: the name filters the search, a small link opens the record.
          const href = filterHref?.(entry)
          const recordPath = path ? `/${path}/${entry.id}` : undefined
          return (
            <span key={entry.id} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span>
                {href ? (
                  <>
                    <Link className="tag tag-link" to={href}>{entry.label}</Link>
                    {recordPath && <Link className="rel-facet-link" to={recordPath}>{t('relations.openRecord')}</Link>}
                  </>
                ) : recordPath ? (
                  <Link to={recordPath}>{entry.label}</Link>
                ) : (
                  entry.label
                )}
                {entry.relation_type && (
                  <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 6 }}>
                    {resolveRelationType(entry.relation_type)}
                  </span>
                )}
              </span>
              {inheritedRows.map(row => (
                <span key={row.key} style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {row.label}: {row.text}
                </span>
              ))}
              {coords && (
                <Suspense fallback={null}>
                  <GeoMap lat={coords.lat} lon={coords.lon} label={entry.label} />
                </Suspense>
              )}
            </span>
          )
        })}
      </span>
    </div>
  )
}
