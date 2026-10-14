// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { BASE, mediaThumbnailUrl } from '../api/client'

// Mirrors backend/src/katalon/core/thumbnails.py (the warm-up task pre-renders exactly
// these heights; a backend test keeps both in sync).
export const THUMBNAIL_HEIGHT = 300
export const THUMBNAIL_HEIGHT_HIDPI = 600

export function iiifThumbnailUrl(iiifIdentifier: string, height: number = THUMBNAIL_HEIGHT): string {
  return `${BASE}/iiif/3/${iiifIdentifier}/full/,${height}/0/default.jpg`
}

/** Thumbnail URL for an image: the IIIF derivative directly when the API delivered its
 *  identifier (one request), otherwise the redirecting thumbnail route (records indexed
 *  before the identifier existed). Access is checked on /iiif/ either way. */
export function thumbnailUrl(objectId: string, mediaId: string, iiifIdentifier?: string | null): string {
  return iiifIdentifier ? iiifThumbnailUrl(iiifIdentifier) : mediaThumbnailUrl(objectId, mediaId)
}

/** `srcset` with the high-density derivative, or undefined without IIIF identifier. */
export function thumbnailSrcSet(iiifIdentifier?: string | null): string | undefined {
  if (!iiifIdentifier) return undefined
  return `${iiifThumbnailUrl(iiifIdentifier)} 1x, ${iiifThumbnailUrl(iiifIdentifier, THUMBNAIL_HEIGHT_HIDPI)} 2x`
}
