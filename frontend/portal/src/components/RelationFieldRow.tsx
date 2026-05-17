import { Link } from 'react-router-dom'

const TYPE_PATHS: Record<string, string> = {
  object: 'objects',
  entity: 'entities',
  place: 'places',
  occurrence: 'occurrences',
}

interface RelationEntry {
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
}

export function RelationFieldRow({ label, value, targetType }: Props) {
  const entries = parseEntries(value)
  if (entries.length === 0) return null

  const path = targetType ? TYPE_PATHS[targetType] : undefined

  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {entries.map(entry => (
          <span key={entry.id}>
            {path ? (
              <Link to={`/${path}/${entry.id}`}>{entry.label}</Link>
            ) : (
              entry.label
            )}
            {entry.relation_type && (
              <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 6 }}>
                {entry.relation_type}
              </span>
            )}
          </span>
        ))}
      </span>
    </div>
  )
}
