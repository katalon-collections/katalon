// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { More } from './Icons'

export interface ActionMenuItem {
  key: string
  label: string
  icon?: React.ReactNode
  danger?: boolean
  disabled?: boolean
  onClick: () => void
}

export interface ActionMenuProps {
  items: ActionMenuItem[]
  ariaLabel?: string
  align?: 'left' | 'right'
  className?: string
  buttonClassName?: string
}

export function ActionMenu({
  items,
  ariaLabel = 'Aktionen',
  align = 'right',
  className,
  buttonClassName = 'btn sm ico gh',
}: ActionMenuProps) {
  const [open, setOpen] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const [activeIndex, setActiveIndex] = useState<number>(-1)

  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const updatePosition = useCallback(() => {
    if (!buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    const menuWidth = 160
    const estimatedHeight = items.length * 36 + 12

    let left = align === 'left' ? rect.left : rect.right - menuWidth
    left = Math.max(8, Math.min(left, window.innerWidth - menuWidth - 8))

    let top = rect.bottom + 4
    if (top + estimatedHeight > window.innerHeight && rect.top - estimatedHeight - 4 > 0) {
      top = rect.top - estimatedHeight - 4
    }

    setCoords({ top, left })
  }, [align, items.length])

  useEffect(() => {
    if (!open) {
      setActiveIndex(-1)
      return
    }

    updatePosition()

    function handleMouseDown(e: MouseEvent) {
      const target = e.target as Node | null
      if (
        buttonRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        setOpen(false)
        buttonRef.current?.focus()
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex(prev => {
          const next = prev + 1 >= items.length ? 0 : prev + 1
          return next
        })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex(prev => {
          const next = prev - 1 < 0 ? items.length - 1 : prev - 1
          return next
        })
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (activeIndex >= 0 && activeIndex < items.length) {
          const item = items[activeIndex]
          if (item && !item.disabled) {
            e.preventDefault()
            setOpen(false)
            item.onClick()
          }
        }
      } else if (e.key === 'Tab') {
        setOpen(false)
      }
    }

    function handleScrollOrResize() {
      setOpen(false)
    }

    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', handleScrollOrResize)
    window.addEventListener('scroll', handleScrollOrResize, true)

    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('resize', handleScrollOrResize)
      window.removeEventListener('scroll', handleScrollOrResize, true)
    }
  }, [open, updatePosition, items, activeIndex])

  if (items.length === 0) return null

  return (
    <div className={`action-menu-container${className ? ` ${className}` : ''}`} style={{ display: 'inline-flex', position: 'relative' }}>
      <button
        ref={buttonRef}
        type="button"
        className={buttonClassName}
        aria-label={ariaLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={e => {
          e.stopPropagation()
          setOpen(prev => {
            if (!prev) updatePosition()
            return !prev
          })
        }}
      >
        <More size={14} aria-hidden="true" />
      </button>

      {open && coords && typeof document !== 'undefined' && createPortal(
        <div
          ref={menuRef}
          role="menu"
          aria-label={ariaLabel}
          className="action-menu-dropdown"
          style={{
            top: coords.top,
            left: coords.left,
          }}
          onClick={e => e.stopPropagation()}
        >
          {items.map((item, idx) => (
            <button
              key={item.key}
              role="menuitem"
              type="button"
              className={`action-menu-item${item.danger ? ' danger' : ''}${idx === activeIndex ? ' active' : ''}`}
              disabled={item.disabled}
              onClick={() => {
                setOpen(false)
                item.onClick()
              }}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              {item.icon && <span className="action-menu-icon" aria-hidden="true">{item.icon}</span>}
              <span className="action-menu-label">{item.label}</span>
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}
