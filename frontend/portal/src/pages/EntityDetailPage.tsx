// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, fetchRecord, mediaThumbnailUrl, type EntitySummary, type MediaFile, type ObjectSummary, type PortalUser, type Relation } from '../api/client'
import { useFieldDefinitions } from '../hooks/useFieldDefinitions'
import { useRelationTypeLabels } from '../hooks/useRelationTypeLabels'
import { RelationsList } from '../components/RelationsList'
import { RelatedObjects } from '../components/RelatedObjects'
import { useBackToSearch } from '../hooks/useBackToSearch'
import { usePortalConfig } from '../hooks/usePortalConfig'
import { recordTitle, renderFieldValue } from '../utils/renderFieldValue'
import { DetailPageLayout, MetaRow } from '../components/DetailPageLayout'
import { EditRecordLink } from '../components/EditRecordLink'
import { SearchResultNavigation } from '../components/SearchResultNavigation'
import { entityTypeLabel, useI18n } from '../i18n'

export function EntityDetailPage({ user }: { user: PortalUser | null }) {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [entity, setEntity] = useState<EntitySummary | null>(null)
  const [relations, setRelations] = useState<Relation[]>([])
  const [linkedObjects, setLinkedObjects] = useState<ObjectSummary[]>([])
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const [relationTitles, setRelationTitles] = useState<Record<string, string>>({})
  const [relationMeta, setRelationMeta] = useState<Record<string, Record<string, unknown>>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fieldDefs, fieldDefsLoading] = useFieldDefinitions('entity')
  const { t, locale } = useI18n()
  const resolveRelationType = useRelationTypeLabels(locale)
  const backSearch = useBackToSearch()
  const portalConfig = usePortalConfig()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.entities.get(id)
      .then(async e => {
        setEntity(e)
        const rels = await api.relations.forRecord('entity', id).catch(() => [] as Relation[])
        setRelations(rels)

        const objIds = rels
          .filter(r => r.from_type === 'object' || r.to_type === 'object')
          .map(r => r.from_type === 'object' ? r.from_id : r.to_id)
        const uniqueObjIds = [...new Set(objIds)]
        const objs = await Promise.all(uniqueObjIds.map(oid => api.objects.get(oid).catch(() => null)))
        const validObjs = objs.filter((o): o is ObjectSummary => o !== null)
        setLinkedObjects(validObjs)

        const thumbMap: Record<string, string> = {}
        await Promise.all(validObjs.map(obj =>
          api.objects.media(obj.id)
            .then((media: MediaFile[]) => {
              const ready = media.filter(mf => mf.status === 'ready')
              const primary = ready.find(mf => mf.is_primary) ?? ready[0]
              if (primary) thumbMap[obj.id] = mediaThumbnailUrl(obj.id, primary.id)
            })
            .catch(() => {})
        ))
        setThumbnails(thumbMap)

        const nonObjRels = rels.filter(r => r.from_type !== 'object' && r.to_type !== 'object')
        const pairs = nonObjRels.map(rel => {
          const isFrom = rel.from_id === e.id
          return { type: isFrom ? rel.to_type : rel.from_type, id: isFrom ? rel.to_id : rel.from_id }
        })
        const entries = await Promise.all(pairs.map(p => fetchRecord(p.type, p.id).then(r => ({ key: `${p.type}/${p.id}`, ...r }))))
        const titleMap: Record<string, string> = {}
        const metaMap: Record<string, Record<string, unknown>> = {}
        for (const entry of entries) {
          if (entry.title) titleMap[entry.key] = entry.title
          metaMap[entry.key] = entry.metadata
        }
        setRelationTitles(titleMap)
        setRelationMeta(metaMap)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading || fieldDefsLoading) return <div className="container page" style={{ color: 'var(--fg-3)' }}>{t('common.loading')}</div>
  if (error || !entity) return (
    <div className="container page">
      <div style={{ color: '#dc2626' }}>{error || t('error.entityNotFound')}</div>
    </div>
  )

  const m = entity.metadata_ as Record<string, unknown>
  const title = recordTitle(m, locale, entity.id)
  const typeLabel = entityTypeLabel(entity.entity_type)
  const description = renderFieldValue(m.description, locale) ?? ''

  const detailFieldDefs = fieldDefs.filter(f => f.name !== 'name' && f.name !== 'title')
  const nonObjectRelations = relations.filter(r => r.from_type !== 'object' && r.to_type !== 'object')

  return (
    <div className="container page">
      <Helmet>
        <title>{title}</title>
        {description && <meta name="description" content={description} />}
        <meta property="og:title" content={title} />
        {description && <meta property="og:description" content={description} />}
        <meta property="og:url" content={window.location.href} />
        <meta property="og:type" content="article" />
      </Helmet>
      <div className="bc">
        {backSearch ? (
          <a href="#" onClick={e => { e.preventDefault(); navigate(backSearch) }}>{t('common.backToSearch')}</a>
        ) : (
          <>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/') }}>{t('common.home')}</a>
            <span className="sep">/</span>
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=&type=entity') }}>{t('nav.entitiesLong')}</a>
          </>
        )}
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span className="tag" style={{ background: 'var(--accent-50)', color: 'var(--accent-ink)' }}>{typeLabel}</span>
        <span className="tag">{entity.status}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <h1 style={{ margin: '0 0 24px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em', display: 'flex', alignItems: 'center' }}>{title}<EditRecordLink user={user} recordType="entity" id={entity.id} /></h1>
        <SearchResultNavigation recordId={entity.id} />
      </div>

      <DetailPageLayout
        fieldDefs={detailFieldDefs}
        metadata={m}
        locale={locale}
        recordType="entity"
        sidebarPosition={portalConfig.detail_sidebar_position}
        mainExtra={linkedObjects.length > 0 && <RelatedObjects objects={linkedObjects} relations={relations} currentId={entity.id} thumbnails={thumbnails} resolveLabel={resolveRelationType} />}
        relations={nonObjectRelations.length > 0 && (
          <RelationsList
            relations={nonObjectRelations}
            currentId={entity.id}
            resolveLabel={resolveRelationType}
            titles={relationTitles}
            metadata={relationMeta}
            fieldDefs={fieldDefs}
          />
        )}
        sidebarExtra={<MetaRow label={t('common.type')} value={typeLabel} />}
      />
    </div>
  )
}
