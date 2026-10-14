// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, render } from '@testing-library/react'
import { MemoryRouter, useNavigate, type NavigateFunction } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScrollToTop } from './ScrollToTop'

let navigate: NavigateFunction = () => {}
function Capture() {
  navigate = useNavigate()
  return null
}

describe('ScrollToTop', () => {
  const scrollTo = vi.fn()
  beforeEach(() => {
    vi.stubGlobal('scrollTo', scrollTo)
    render(<MemoryRouter initialEntries={['/search?q=a']}><ScrollToTop /><Capture /></MemoryRouter>)
    scrollTo.mockClear()
  })
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('scrolls to the top when another page opens', () => {
    act(() => navigate('/objects/1'))
    expect(scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('keeps the position when only the query changes', () => {
    act(() => navigate('/search?q=a&type=object'))
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('leaves back/forward to the browser', () => {
    act(() => navigate('/objects/1'))
    scrollTo.mockClear()
    act(() => navigate(-1))
    expect(scrollTo).not.toHaveBeenCalled()
  })
})
