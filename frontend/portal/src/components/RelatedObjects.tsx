// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ObjectSummary, Relation } from '../api/client'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { useSubtypePlaceholder } from '../hooks/useSubtypePlaceholders'
import { typeLabel, useI18n } from '../i18n'
import { matchRelationFacet, relationFacetHref, resolveLabel as resolveText, type RelationFacetConfig } from '../utils/facets'
import { recordTitle } from '../utils/renderFieldValue'
import { LazyImage } from './LazyImage'

interface Props {
  objects: ObjectSummary[]
  relations: Relation[]
  currentId: string
  thumbnails: Record<string, string>
  resolveLabel: (code: string, isFrom: boolean) => string
  /** Type of the current record: enables links to the object search filtered by
   *  a relation facet ("postcards with this person as composer"). */
  recordType?: string
}

export function RelatedObjects({ objects, relations, currentId, thumbnails, resolveLabel, recordType }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const { t, locale } = useI18n()
  const portalConfig = usePortalConfig()
  const facetLinks = recordType
    ? [...new Map(
      relations
        .filter(r => r.from_type === 'object' && r.to_id === currentId)
        .map(r => matchRelationFacet(portalConfig.relation_facets?.object, recordType, r.relation_type, 'outgoing'))
        .filter((facet): facet is RelationFacetConfig => !!facet)
        .map(facet => [facet.key, facet]),
    ).values()]
    : []
  const subtypePlaceholder = useSubtypePlaceholder('object')

  useEffect(() => setSelectedType(null), [currentId])

  const relationsForObject = (objectId: string) => relations.filter(r =>
    (r.from_id === currentId && r.to_id === objectId) || (r.to_id === currentId && r.from_id === objectId)
  )
  const uniqueObjects = [...new Map(objects.map(obj => [obj.id, obj])).values()]
  const relationTypes = [...new Map(
    uniqueObjects.flatMap(obj => relationsForObject(obj.id)).map(rel => [rel.relation_type, rel])
  ).values()]
  const visibleObjects = selectedType
    ? uniqueObjects.filter(obj => relationsForObject(obj.id).some(rel => rel.relation_type === selectedType))
    : uniqueObjects

  return (
    <section style={{ marginTop: 8 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>{t('common.relatedObjects')}</h2>
      {facetLinks.length > 0 && (
        <div className="rel-facet-links">
          {facetLinks.map(facet => (
            <Link key={facet.key} className="tag tag-link" to={relationFacetHref('object', facet, currentId)}>
              {t('relations.searchByRole', { type: typeLabel('object', { plural: true }), role: resolveText(facet.label, locale, facet.key) })}
            </Link>
          ))}
        </div>
      )}
      {relationTypes.length > 1 && (
        <div className="relation-filter">
          <button type="button" className="tag relation-filter__chip" aria-pressed={selectedType === null} onClick={() => setSelectedType(null)}>
            {t('common.all')}
          </button>
          {relationTypes.map(rel => {
            const isFrom = rel.from_id === currentId
            const count = uniqueObjects.filter(obj => relationsForObject(obj.id).some(item => item.relation_type === rel.relation_type)).length
            return (
              <button key={rel.relation_type} type="button" className="tag relation-filter__chip" aria-pressed={selectedType === rel.relation_type} onClick={() => setSelectedType(rel.relation_type)}>
                {resolveLabel(rel.relation_type, isFrom)} ({count})
              </button>
            )
          })}
        </div>
      )}
      <div className="obj-grid">
        {visibleObjects.map(obj => {
          const relationLabels = [...new Set(relationsForObject(obj.id).map(rel =>
            resolveLabel(rel.relation_type, rel.from_id === currentId)
          ))]
          const metadata = obj.metadata_ as Record<string, unknown>
          return (
            <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
              <div className="thumb">
                {(() => {
                  const src = thumbnails[obj.id] || subtypePlaceholder(obj.object_type)
                  return src ? <LazyImage src={src} /> : null
                })()}
              </div>
              <div className="info">
                <div className="title">{recordTitle(metadata, locale, obj.idno ?? obj.id)}</div>
                {relationLabels.length > 0 && (
                  <div className="meta" style={{ textTransform: 'uppercase', letterSpacing: '.04em', fontSize: 10 }}>
                    {relationLabels.join(' · ')}
                  </div>
                )}
                {obj.idno && <div className="meta">{obj.idno}</div>}
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
