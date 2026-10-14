// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LazyImage } from './LazyImage'

type Callback = (entries: { isIntersecting: boolean }[]) => void

describe('LazyImage', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('defers src until the observer reports it near the viewport', () => {
    let trigger: Callback = () => {}
    const options: IntersectionObserverInit[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: Callback, init: IntersectionObserverInit) { trigger = cb; options.push(init) }
      observe() {}
      disconnect() {}
    })
    const { container } = render(<LazyImage src="/a.jpg" srcSet="/a.jpg 1x, /b.jpg 2x" width={600} height={400} />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('src')).toBeNull()
    expect(img.getAttribute('width')).toBe('600')
    expect(img.getAttribute('decoding')).toBe('async')
    expect(options[0].rootMargin).toBe('200% 0px')
    act(() => trigger([{ isIntersecting: true }]))
    expect(img.getAttribute('src')).toBe('/a.jpg')
    expect(img.getAttribute('srcset')).toBe('/a.jpg 1x, /b.jpg 2x')
  })

  it('loads priority images at once with high fetch priority', () => {
    vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} })
    const { container } = render(<LazyImage src="/a.jpg" priority />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('src')).toBe('/a.jpg')
    expect(img.getAttribute('fetchpriority')).toBe('high')
    expect(img.getAttribute('loading')).toBe('eager')
  })

  it('falls back to native lazy loading without IntersectionObserver', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    const { container } = render(<LazyImage src="/a.jpg" />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('src')).toBe('/a.jpg')
    expect(img.getAttribute('loading')).toBe('lazy')
  })
})
