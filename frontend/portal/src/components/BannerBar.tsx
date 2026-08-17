import { useEffect, useState } from 'react'
import { banners, type BannerItem } from '../api/client'
import { useI18n } from '../i18n'

const COLOR_STYLES: Record<BannerItem['color'], React.CSSProperties> = {
  blue:   { background: '#dbeafe', color: '#1e40af', borderBottom: '1px solid #bfdbfe' },
  yellow: { background: '#fef9c3', color: '#854d0e', borderBottom: '1px solid #fde047' },
  red:    { background: '#fee2e2', color: '#991b1b', borderBottom: '1px solid #fca5a5' },
  green:  { background: '#dcfce7', color: '#166534', borderBottom: '1px solid #86efac' },
}

const POLL_INTERVAL = 5 * 60 * 1000

export function BannerBar() {
  const [items, setItems] = useState<BannerItem[]>([])
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const { t } = useI18n()

  useEffect(() => {
    const load = () => banners.activePortal().then(setItems).catch(() => {})
    load()
    const id = setInterval(load, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [])

  const visible = items.filter(b => !dismissed.has(b.id))
  if (visible.length === 0) return null

  return (
    <div>
      {visible.map(b => (
        <div
          key={b.id}
          style={{
            ...COLOR_STYLES[b.color],
            display: 'flex',
            alignItems: 'center',
            padding: '8px 16px',
            fontSize: 14,
            gap: 8,
            lineHeight: 1.5,
          }}
        >
          <span style={{ flex: 1 }}>{b.message}</span>
          <button
            onClick={() => setDismissed(d => new Set([...d, b.id]))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px', color: 'inherit', opacity: 0.6, fontSize: 18, lineHeight: 1 }}
            title={t('banner.close')}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
