import { useEffect, useState } from 'react'
import { bannersApi } from '../../api/client'
import type { Banner } from '../../types'
import { X } from './Icons'

const COLOR_STYLES: Record<Banner['color'], React.CSSProperties> = {
  blue:   { background: '#dbeafe', color: '#1e40af', borderBottom: '1px solid #bfdbfe' },
  yellow: { background: '#fef9c3', color: '#854d0e', borderBottom: '1px solid #fde047' },
  red:    { background: '#fee2e2', color: '#991b1b', borderBottom: '1px solid #fca5a5' },
  green:  { background: '#dcfce7', color: '#166534', borderBottom: '1px solid #86efac' },
}

const POLL_INTERVAL = 5 * 60 * 1000 // 5 minutes

export function BannerBar({ surface }: { surface: 'admin' | 'portal' }) {
  const [banners, setBanners] = useState<Banner[]>([])
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  useEffect(() => {
    const load = () => {
      const fetcher = surface === 'admin' ? bannersApi.activeAdmin : bannersApi.activePortal
      fetcher().then(setBanners).catch(() => {})
    }
    load()
    const id = setInterval(load, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [surface])

  const visible = banners.filter(b => !dismissed.has(b.id))
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
            fontSize: 13,
            gap: 8,
            lineHeight: 1.5,
          }}
        >
          <span style={{ flex: 1 }}>{b.message}</span>
          <button
            onClick={() => setDismissed(d => new Set([...d, b.id]))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: 'inherit', opacity: 0.6, display: 'flex', alignItems: 'center' }}
            title="Schließen"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
