// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState, type CSSProperties } from 'react'

/** Starts loading this far ahead of the viewport: two screen heights. Chrome's native
 *  `loading="lazy"` starts only ~1250–2500 px ahead, too late for fast scrolling in
 *  dense grids. */
const ROOT_MARGIN = '200% 0px'

/** Thumbnail <img> for result grids: loads shortly before it scrolls into view, decodes
 *  off the main thread, and passes intrinsic width/height so the browser can reserve the
 *  space. `priority` is for the first visible results: loaded at once, fetched first. */
export function LazyImage({ src, srcSet, alt = '', width, height, priority = false, style }: {
  src: string
  srcSet?: string
  alt?: string
  width?: number | null
  height?: number | null
  priority?: boolean
  style?: CSSProperties
}) {
  const ref = useRef<HTMLImageElement>(null)
  const observable = typeof IntersectionObserver !== 'undefined'
  const [near, setNear] = useState(priority || !observable)

  useEffect(() => {
    if (near || !ref.current) return
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        setNear(true)
        observer.disconnect()
      }
    }, { rootMargin: ROOT_MARGIN })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [near])

  return (
    <img
      ref={ref}
      src={near ? src : undefined}
      srcSet={near ? srcSet : undefined}
      alt={alt}
      width={width ?? undefined}
      height={height ?? undefined}
      decoding="async"
      // The observer already decided when to load; native lazy only as fallback.
      loading={observable || priority ? 'eager' : 'lazy'}
      // Lowercase: React 18 does not know the camelCase prop yet.
      {...(priority ? { fetchpriority: 'high' } : {})}
      style={style}
    />
  )
}
