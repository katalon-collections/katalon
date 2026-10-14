// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const received: { options?: { background?: string } } = {}
vi.mock('@samvera/clover-iiif/viewer', () => ({
  default: (props: { options: { background?: string } }) => {
    received.options = props.options
    return null
  },
}))

const { IIIFViewer } = await import('./IIIFViewer')

describe('IIIFViewer', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('takes its background from the theme token --viewer-bg', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 'm' }) }))
    render(<IIIFViewer manifestUrl="/m.json" />)
    await waitFor(() => expect(received.options).toBeDefined())
    expect(received.options?.background).toBe('var(--viewer-bg, #0f172a)')
  })
})
