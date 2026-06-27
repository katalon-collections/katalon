import { useNavigate } from 'react-router-dom'
import type { Relation } from '../api/client'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'


const TYPE_PATHS: Record<string, string> = {
  object: 'objects',
  entity: 'entities',
  place: 'places',
  occurrence: 'occurrences',
}

function typePath(type: string, id: string): string {
  return `/${TYPE_PATHS[type] ?? `${type}s`}/${id}`
}

function extractText(val: unknown): string | null {
  if (val == null) return null
  if (typeof val === 'string') return val || null
  if (typeof val === 'number' || typeof val === 'boolean') return String(val)
  if (Array.isArray(val)) {
    const first = val[0]
    if (first == null) return null
    if (typeof first === 'string') return first || null
    if (typeof first === 'object') {
      const v = (first as Record<string, unknown>).value
      return typeof v === 'string' ? v || null : null
    }
  }
  return null
}

interface Props {
  relations: Relation[]
  currentId: string
  resolveLabel: (code: string, isFrom: boolean) => string
  /** Optional: pre-loaded titles keyed by "<type>/<id>" */
  titles?: Record<string, string>
  /** Optional: pre-loaded metadata keyed by "<type>/<id>" */
  metadata?: Record<string, Record<string, unknown>>
  /** Optional: current record's field definitions (used to find inherited_fields config) */
  fieldDefs?: FieldDefinition[]
}

export function RelationsList({ relations, currentId, resolveLabel, titles = {}, metadata = {}, fieldDefs = [] }: Props) {
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

          const inheritedFieldNames = fieldDefs
            .filter(f => f.field_type === 'relation' && (f.settings?.target_type as string) === targetType)
            .flatMap(f => (f.settings?.inherited_fields as string[]) ?? [])
          const meta = metadata[titleKey]

          return (
            <div key={r.id} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 13 }}>
                <span style={{
                  color: 'var(--fg-3)',
                  fontSize: 11,
                  minWidth: 110,
                  flexShrink: 0,
                  textTransform: 'uppercase',
                  letterSpacing: '.04em',
                }}>
                  {resolveLabel(r.relation_type, isFrom)}
                </span>
                <a
                  href="#"
                  onClick={e => { e.preventDefault(); navigate(path) }}
                  style={{ color: 'var(--accent)', textDecoration: 'none' }}
                >
                  {targetLabel}
                </a>
              </div>
              {meta && inheritedFieldNames.length > 0 && (
                <div style={{ paddingLeft: 118, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {inheritedFieldNames.map(fname => {
                    const text = extractText(meta[fname])
                    if (!text) return null
                    return (
                      <span key={fname} style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                        {fname}: {text}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
