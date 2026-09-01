// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import Viewer from '@samvera/clover-iiif/viewer'

interface Props {
  manifestUrl: string
  onError?: () => void
}

const options = {
  background: '#0f172a',
  showTitle: false,
  showIIIFBadge: false,
  showDownload: false,
  informationPanel: {
    open: false,
    renderToggle: false,
    renderAbout: false,
    renderSupplementing: false,
    renderAnnotation: false,
    renderContentSearch: false,
  },
  openSeadragon: {
    gestureSettingsMouse: {
      scrollToZoom: true,
    },
  },
}

export function IIIFViewer({ manifestUrl, onError }: Props) {
  const [manifest, setManifest] = useState<object | null>(null)

  useEffect(() => {
    setManifest(null)
    fetch(manifestUrl)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json() })
      .then(setManifest)
      .catch(() => onError?.())
  }, [manifestUrl])

  if (!manifest) return null

  return (
    <div style={{ borderRadius: 10, overflow: 'hidden', width: '100%', maxWidth: '100%' }}>
      <Viewer
        iiifContent={manifest}
        options={options}
      />
    </div>
  )
}
