// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { Link, useNavigate } from 'react-router-dom'
import type { Relation } from '../api/client'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { useI18n } from '../i18n'
import { matchRelationFacet, relationFacetHref } from '../utils/facets'


const TYPE_PATHS: Record<string, string> = {
  object: 'objects',
  entity: 'entities',
  place: 'places',
  occurrence: 'occurrences',
  collection: 'collections',
}

function typePath(type: string, id: string): string {
  return `/${TYPE_PATHS[type] ?? `${type}s`}/${id}`
}

interface Props {
  relations: Relation[]
  currentId: string
  resolveLabel: (code: string, isFrom: boolean) => string
  /** Optional: pre-loaded titles keyed by "<type>/<id>" */
  titles?: Record<string, string>
  /** Optional: pre-loaded metadata keyed by "<type>/<id>" */
  metadata?: Record<string, Record<string, unknown>>
  /** Optional: current record's field definitions */
  fieldDefs?: FieldDefinition[]
  /** Current record type: enables "more with this …" links via relation facets. */
  recordType?: string
}

export function RelationsList({ relations, currentId, resolveLabel, titles = {}, recordType }: Props) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const portalConfig = usePortalConfig()
  const ownFacets = recordType ? portalConfig.relation_facets?.[recordType] : undefined

  if (relations.length === 0) return null

  return (
    <section className="detail-meta">
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: 'var(--fg-1)' }}>
        {t('common.relations')}
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {relations.map(r => {
          const isFrom = r.from_id === currentId
          const targetType = isFrom ? r.to_type : r.from_type
          const targetId = isFrom ? r.to_id : r.from_id
          const titleKey = `${targetType}/${targetId}`
          const resolvedLabel = isFrom ? r.to_label : r.from_label
          const targetLabel = resolvedLabel ?? titles[titleKey] ?? t('common.recordUnavailable')
          const path = typePath(targetType, targetId)
          const facet = matchRelationFacet(ownFacets, targetType, r.relation_type, isFrom ? 'outgoing' : 'incoming')

          return (
            <div key={r.id} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '9.5rem minmax(0, 1fr)', alignItems: 'baseline', columnGap: 12, fontSize: 13 }}>
                <span className="rel-key" style={{
                  color: 'var(--fg-2, #3a3f4a)',
                  fontSize: 11,
                  fontWeight: 600,
                  overflowWrap: 'anywhere',
                  letterSpacing: '.02em',
                }}>
                  {resolveLabel(r.relation_type, isFrom)}:
                </span>
                <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                  <a
                    href="#"
                    onClick={e => { e.preventDefault(); navigate(path) }}
                    style={{ color: 'var(--accent)', textDecoration: 'none' }}
                  >
                    {targetLabel}
                  </a>
                  {facet && recordType && (
                    <Link className="rel-facet-link" to={relationFacetHref(recordType, facet, targetId)}>
                      {t('relations.moreWithValue')}
                    </Link>
                  )}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
