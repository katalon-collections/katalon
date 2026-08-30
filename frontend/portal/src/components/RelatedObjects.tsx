import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ObjectSummary, Relation } from '../api/client'
import { useI18n } from '../i18n'
import { recordTitle } from '../utils/renderFieldValue'

interface Props {
  objects: ObjectSummary[]
  relations: Relation[]
  currentId: string
  thumbnails: Record<string, string>
  resolveLabel: (code: string, isFrom: boolean) => string
}

export function RelatedObjects({ objects, relations, currentId, thumbnails, resolveLabel }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const { t, locale } = useI18n()

  useEffect(() => setSelectedType(null), [currentId])

  const relationsForObject = (objectId: string) => relations.filter(r =>
    (r.from_id === currentId && r.to_id === objectId) || (r.to_id === currentId && r.from_id === objectId)
  )
  const relationTypes = [...new Map(
    objects.flatMap(obj => relationsForObject(obj.id)).map(rel => [rel.relation_type, rel])
  ).values()]
  const visibleObjects = selectedType
    ? objects.filter(obj => relationsForObject(obj.id).some(rel => rel.relation_type === selectedType))
    : objects

  return (
    <section style={{ marginTop: 8 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>{t('common.relatedObjects')}</h2>
      {relationTypes.length > 1 && (
        <div className="relation-filter">
          <button type="button" className="tag relation-filter__chip" aria-pressed={selectedType === null} onClick={() => setSelectedType(null)}>
            {t('common.all')}
          </button>
          {relationTypes.map(rel => {
            const isFrom = rel.from_id === currentId
            return (
              <button key={rel.relation_type} type="button" className="tag relation-filter__chip" aria-pressed={selectedType === rel.relation_type} onClick={() => setSelectedType(rel.relation_type)}>
                {resolveLabel(rel.relation_type, isFrom)}
              </button>
            )
          })}
        </div>
      )}
      <div className="obj-grid">
        {visibleObjects.map(obj => {
          const rel = relationsForObject(obj.id)[0]
          const metadata = obj.metadata_ as Record<string, unknown>
          return (
            <Link key={obj.id} className="obj-card" to={`/objects/${obj.id}`}>
              <div className="thumb">
                {thumbnails[obj.id] && <img src={thumbnails[obj.id]} alt="" loading="lazy" />}
              </div>
              <div className="info">
                <div className="title">{recordTitle(metadata, locale, obj.idno ?? obj.id)}</div>
                {rel && (
                  <div className="meta" style={{ textTransform: 'uppercase', letterSpacing: '.04em', fontSize: 10 }}>
                    {resolveLabel(rel.relation_type, rel.from_id === currentId)}
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
