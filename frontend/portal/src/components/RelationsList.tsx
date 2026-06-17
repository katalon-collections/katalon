import { useNavigate } from 'react-router-dom'
import type { Relation } from '../api/client'


const TYPE_PATHS: Record<string, string> = {
  object: 'objects',
  entity: 'entities',
  place: 'places',
  occurrence: 'occurrences',
}

function typePath(type: string, id: string): string {
  return `/${TYPE_PATHS[type] ?? `${type}s`}/${id}`
}

interface Props {
  relations: Relation[]
  currentId: string
  resolveLabel: (code: string) => string
  /** Optional: pre-loaded titles keyed by "<type>/<id>" */
  titles?: Record<string, string>
}

export function RelationsList({ relations, currentId, resolveLabel, titles = {} }: Props) {
  const navigate = useNavigate()

  if (relations.length === 0) return null

  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: 'var(--fg-1)' }}>
        Verknüpfungen
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {relations.map(r => {
          const isFrom = r.from_id === currentId
          const targetType = isFrom ? r.to_type : r.from_type
          const targetId = isFrom ? r.to_id : r.from_id
          const titleKey = `${targetType}/${targetId}`
          const targetLabel = titles[titleKey] ?? `[${targetId.slice(0, 8)}…]`
          const path = typePath(targetType, targetId)

          return (
            <div key={r.id} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 13 }}>
              <span style={{
                color: 'var(--fg-3)',
                fontSize: 11,
                minWidth: 110,
                flexShrink: 0,
                textTransform: 'uppercase',
                letterSpacing: '.04em',
              }}>
                {resolveLabel(r.relation_type)}
              </span>
              <a
                href="#"
                onClick={e => { e.preventDefault(); navigate(path) }}
                style={{ color: 'var(--accent)', textDecoration: 'none' }}
              >
                {targetLabel}
              </a>
            </div>
          )
        })}
      </div>
    </section>
  )
}
