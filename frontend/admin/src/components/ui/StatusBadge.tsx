type Status = 'draft' | 'internal' | 'public'

const LABELS: Record<Status, string> = {
  draft: 'Entwurf',
  internal: 'Intern',
  public: 'Öffentlich',
}

export function StatusBadge({ status }: { status: string }) {
  const s = (status as Status) in LABELS ? (status as Status) : 'draft'
  return (
    <span className={`st ${s}`}>
      <span className="dot" />
      {LABELS[s]}
    </span>
  )
}
