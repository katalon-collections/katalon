// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, fetchRecord, mediaThumbnailUrl, type MediaFile, type ObjectSummary, type PlaceSummary, type PortalUser, type Relation } from '../api/client'
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
import { useI18n } from '../i18n'

function StaticMap({ lat, lon, name }: { lat: number; lon: number; name: string }) {
  const bbox = `${lon - 0.05},${lat - 0.03},${lon + 0.05},${lat + 0.03}`
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`
  return (
    <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 16 }}>
      <iframe
        src={src}
        title={`Karte: ${name}`}
        width="100%"
        height="300"
        style={{ border: 0, display: 'block' }}
        loading="lazy"
      />
      <div style={{ padding: '6px 10px', fontSize: 12, color: 'var(--fg-3)', background: 'var(--panel)' }}>
        {lat.toFixed(5)}, {lon.toFixed(5)} ·{' '}
        <a
          href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=13/${lat}/${lon}`}
          target="_blank" rel="noreferrer"
          style={{ color: 'var(--fg-3)' }}
        >
          OpenStreetMap ↗
        </a>
      </div>
    </div>
  )
}

export function PlaceDetailPage({ user }: { user: PortalUser | null }) {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [place, setPlace] = useState<PlaceSummary | null>(null)
  const [relations, setRelations] = useState<Relation[]>([])
  const [linkedObjects, setLinkedObjects] = useState<ObjectSummary[]>([])
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({})
  const [relationTitles, setRelationTitles] = useState<Record<string, string>>({})
  const [relationMeta, setRelationMeta] = useState<Record<string, Record<string, unknown>>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fieldDefs, fieldDefsLoading] = useFieldDefinitions('place')
  const { t, locale } = useI18n()
  const resolveRelationType = useRelationTypeLabels(locale)
  const backSearch = useBackToSearch()
  const portalConfig = usePortalConfig()

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.places.get(id)
      .then(async p => {
        setPlace(p)
        const rels = await api.relations.forRecord('place', id).catch(() => [] as Relation[])
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
          const isFrom = rel.from_id === p.id
          return { type: isFrom ? rel.to_type : rel.from_type, id: isFrom ? rel.to_id : rel.from_id }
        })
        const entries = await Promise.all(pairs.map(q => fetchRecord(q.type, q.id).then(r => ({ key: `${q.type}/${q.id}`, ...r }))))
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
  if (error || !place) return (
    <div className="container page">
      <div style={{ color: '#dc2626' }}>{error || t('error.placeNotFound')}</div>
    </div>
  )

  const m = place.metadata_ as Record<string, unknown>
  const title = recordTitle(m, locale, place.id)
  const hasCoords = place.lat != null && place.lon != null
  const description = renderFieldValue(m.description, locale) ?? ''

  const detailFieldDefs = fieldDefs.filter(f => f.name !== 'title' && f.name !== 'name')
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
            <a href="#" onClick={e => { e.preventDefault(); navigate('/search?q=&type=place') }}>{t('nav.places')}</a>
          </>
        )}
        <span className="sep">/</span>
        <span>{title}</span>
      </div>

      <div style={{ marginBottom: 6 }}>
        <span className="tag">{place.status}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <h1 style={{ margin: '0 0 24px', fontSize: 26, fontWeight: 700, letterSpacing: '-.015em', display: 'flex', alignItems: 'center' }}>{title}<EditRecordLink user={user} recordType="place" id={place.id} /></h1>
        <SearchResultNavigation recordId={place.id} />
      </div>

      <DetailPageLayout
        fieldDefs={detailFieldDefs}
        metadata={m}
        locale={locale}
        recordType="place"
        aiProvenance={place.ai_provenance}
        sidebarPosition={portalConfig.detail_sidebar_position}
        media={hasCoords ? <StaticMap lat={place.lat!} lon={place.lon!} name={title} /> : undefined}
        mainExtra={linkedObjects.length > 0 && <RelatedObjects objects={linkedObjects} relations={relations} currentId={place.id} thumbnails={thumbnails} resolveLabel={resolveRelationType} />}
        relations={nonObjectRelations.length > 0 && (
          <RelationsList
            relations={nonObjectRelations}
            currentId={place.id}
            resolveLabel={resolveRelationType}
            titles={relationTitles}
            metadata={relationMeta}
            fieldDefs={fieldDefs}
          />
        )}
        sidebarExtra={hasCoords && (
          <MetaRow label={t('common.coordinates')} value={`${place.lat!.toFixed(5)}, ${place.lon!.toFixed(5)}`} />
        )}
      />
    </div>
  )
}
