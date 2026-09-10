// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Help, X } from './Icons'

export interface HelpPopoverProps {
  title?: string
  content: ReactNode
  ariaLabel?: string
  size?: number
}

const POPOVER_WIDTH = 320

export function HelpPopover({ title, content, ariaLabel = 'Hilfe anzeigen', size = 12 }: HelpPopoverProps) {
  const [open, setOpen] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  const updatePosition = useCallback(() => {
    if (!buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()

    // Calculate horizontal position (keep within viewport with 12px margin)
    let left = rect.left
    if (left + POPOVER_WIDTH > window.innerWidth - 12) {
      left = Math.max(12, window.innerWidth - POPOVER_WIDTH - 12)
    }
    if (left < 12) {
      left = 12
    }

    // Calculate vertical position (prefer below, flip above if not enough space)
    const spaceBelow = window.innerHeight - rect.bottom - 8
    const spaceAbove = rect.top - 8
    const estimatedHeight = 180
    const showBelow = spaceBelow >= estimatedHeight || spaceBelow >= spaceAbove
    const top = showBelow
      ? rect.bottom + 6
      : Math.max(8, rect.top - estimatedHeight - 6)

    setCoords({ top, left })
  }, [])

  useEffect(() => {
    if (!open) return

    updatePosition()

    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (
        buttonRef.current?.contains(target) ||
        popoverRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }

    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, updatePosition])

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          setOpen(v => {
            if (!v) updatePosition()
            return !v
          })
        }}
        className="btn ico gh"
        aria-label={ariaLabel}
        aria-expanded={open}
        style={{
          padding: 0,
          width: 18,
          height: 18,
          minHeight: 18,
          borderRadius: '50%',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: open ? 'var(--accent, #2563eb)' : 'var(--fg-3, #6b7280)',
          background: open ? 'var(--accent-50, #eff6ff)' : 'transparent',
          border: 'none',
          cursor: 'pointer',
          verticalAlign: 'middle',
          marginLeft: 4,
          flexShrink: 0,
        }}
      >
        <Help size={size} aria-hidden="true" />
      </button>

      {open && coords && typeof document !== 'undefined' && createPortal(
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={title || ariaLabel}
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
            zIndex: 99999,
            width: POPOVER_WIDTH,
            maxWidth: 'calc(100vw - 24px)',
            background: 'var(--panel, #ffffff)',
            border: '1px solid var(--border, #e5e7eb)',
            borderRadius: 8,
            boxShadow: '0 12px 28px -4px rgba(0, 0, 0, 0.18), 0 4px 12px -2px rgba(0, 0, 0, 0.08)',
            padding: '12px 14px',
            fontSize: 12,
            lineHeight: 1.45,
            color: 'var(--fg-2, #374151)',
            fontWeight: 'normal',
            textAlign: 'left',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: title ? 6 : 4,
              borderBottom: title ? '1px solid var(--border-s, #f3f4f6)' : 'none',
              paddingBottom: title ? 6 : 0,
            }}
          >
            {title && (
              <strong style={{ color: 'var(--fg, #111827)', fontSize: 12, fontWeight: 600 }}>
                {title}
              </strong>
            )}
            <button
              type="button"
              className="btn ico gh"
              style={{
                padding: 0,
                width: 16,
                height: 16,
                minHeight: 16,
                marginLeft: 'auto',
                color: 'var(--fg-3, #9ca3af)',
                flexShrink: 0,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
              }}
              onClick={() => setOpen(false)}
              aria-label="Schließen"
            >
              <X size={12} />
            </button>
          </div>
          <div>{content}</div>
        </div>,
        document.body,
      )}
    </>
  )
}
