// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MediaFile } from '../api/client'

const recordView = vi.fn()
vi.mock('../api/client', async importOriginal => ({
  ...await importOriginal<typeof import('../api/client')>(),
  recordView: (...args: unknown[]) => recordView(...args),
}))

const { UsageStats } = await import('./DetailPageLayout')
const { MediaDownloads } = await import('./MediaViewer')

describe('UsageStats', () => {
  afterEach(() => { cleanup(); recordView.mockReset() })

  it('counts the view and shows views and downloads', async () => {
    recordView.mockResolvedValue({ views: 12, downloads: 3 })
    render(<UsageStats recordType="object" recordId="o1" />)
    expect(await screen.findByText('12')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    expect(recordView).toHaveBeenCalledWith('object', 'o1')
  })

  it('omits the download row when downloads are off', async () => {
    recordView.mockResolvedValue({ views: 5, downloads: null })
    const { container } = render(<UsageStats recordType="entity" recordId="e1" />)
    expect(await screen.findByText('5')).toBeTruthy()
    expect(container.querySelectorAll('.meta-row').length).toBe(1)
  })

  it('renders nothing when the portal hides statistics', async () => {
    recordView.mockResolvedValue(null)
    const { container } = render(<UsageStats recordType="place" recordId="p1" />)
    await Promise.resolve()
    expect(container.textContent).toBe('')
  })
})

describe('MediaDownloads', () => {
  afterEach(cleanup)

  it('links each file to the attachment download', () => {
    const media: MediaFile = {
      id: 'm1', filename: 'katalog.pdf', mime_type: 'application/pdf', category: 'pdf',
      status: 'ready', is_primary: false, created_at: '2026-10-01T00:00:00',
    }
    render(<MediaDownloads media={[media]} label="Downloads" />)
    const link = screen.getByRole('link', { name: /katalog\.pdf/ })
    expect(link.getAttribute('href')).toBe('/portal/v1/media/m1/download')
    expect(link.hasAttribute('download')).toBe(true)
  })
})
