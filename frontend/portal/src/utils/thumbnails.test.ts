// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it, vi } from 'vitest'
import { iiifThumbnailUrl, thumbnailUrl } from './thumbnails'

describe('thumbnailUrl', () => {
  it('uses the IIIF derivative directly when the identifier is known', () => {
    expect(thumbnailUrl('o1', 'm1', 'ab%2Fscan.tif')).toBe('/iiif/3/ab%2Fscan.tif/full/,300/0/default.jpg')
  })

  it('falls back to the redirecting thumbnail route without identifier', () => {
    expect(thumbnailUrl('o1', 'm1', null)).toBe('/portal/v1/objects/o1/media/m1/thumbnail')
    expect(thumbnailUrl('o1', 'm1')).toBe('/portal/v1/objects/o1/media/m1/thumbnail')
  })

  it('builds the high-density size', () => {
    expect(iiifThumbnailUrl('x', 600)).toBe('/iiif/3/x/full/,600/0/default.jpg')
  })
})

describe('thumbnailSrcSet', () => {
  it('offers the 600 px derivative for high-density screens', async () => {
    const { thumbnailSrcSet } = await import('./thumbnails')
    expect(thumbnailSrcSet('x')).toBe('/iiif/3/x/full/,300/0/default.jpg 1x, /iiif/3/x/full/,600/0/default.jpg 2x')
    expect(thumbnailSrcSet(null)).toBeUndefined()
  })
})

describe('loadObjectTeasers', () => {
  it('loads objects and thumbnails with one batch request', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => new Response(JSON.stringify([
      { id: 'o2', primary_media: { id: 'm2', iiif_identifier: 'ab%2Fb.tif' } },
      { id: 'o1', primary_media: null },
    ])))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const { loadObjectTeasers } = await import('./thumbnails')
      const { objects, thumbnails } = await loadObjectTeasers(['o2', 'o1', 'o2'])
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(String(fetchMock.mock.calls[0][0])).toContain('/portal/v1/objects/summaries?ids=o2&ids=o1')
      expect(objects.map(o => o.id)).toEqual(['o2', 'o1'])
      expect(thumbnails).toEqual({ o2: '/iiif/3/ab%2Fb.tif/full/,300/0/default.jpg' })
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
