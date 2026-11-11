// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { attachments } from '../api/client'

let _cached: number | null = null
let _promise: Promise<number | null> | null = null

function loadAttachmentMaxUploadMb(): Promise<number | null> {
  if (_cached != null) return Promise.resolve(_cached)
  if (!_promise) {
    _promise = attachments.limits()
      .then(limits => {
        _cached = limits.max_upload_mb
        return _cached
      })
      .catch(() => {
        // Unknown limit: callers skip the pre-check, the backend still enforces it. Retry on next mount.
        _promise = null
        return null
      })
  }
  return _promise
}

/** Configured maximum upload size in MB, or null while unknown (loading or request failed). */
export function useAttachmentMaxUploadMb(): number | null {
  const [maxMb, setMaxMb] = useState<number | null>(_cached)
  useEffect(() => {
    let active = true
    loadAttachmentMaxUploadMb().then(value => {
      if (active) setMaxMb(value)
    })
    return () => {
      active = false
    }
  }, [])
  return maxMb
}
