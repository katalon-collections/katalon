// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useState } from 'react'
import { api, type PortalConfig } from '../api/client'

const DEFAULT: PortalConfig = {
  site_title: 'Katalon',
  site_subtitle: '',
  hero_text: '',
  featured_object_ids: [],
  facet_fields: {},
  subtitle_fields: {},
  browse_enabled_types: ['object', 'entity', 'place', 'occurrence'],
  accent_color: '#1e3a8a',
  logo_url: '',
  placeholder_image_url: '',
  color_tokens: {},
  supported_languages: ['de', 'en'],
  detail_sidebar_position: 'right',
  facet_sort: 'count',
  facet_initial_count: 10,
  homepage_blocks: [],
  terminology: {},
  show_iiif_manifest_link: true,
}

// Module-level cache so multiple components share one fetch per page load
let _cached: PortalConfig | null = null
let _promise: Promise<PortalConfig> | null = null

function getConfig(): Promise<PortalConfig> {
  if (_cached) return Promise.resolve(_cached)
  if (!_promise) {
    _promise = api.portal.config().then(c => { _cached = c; return c }).catch(() => DEFAULT)
  }
  return _promise
}

export function usePortalConfig(): PortalConfig {
  const [config, setConfig] = useState<PortalConfig>(_cached ?? DEFAULT)
  useEffect(() => {
    getConfig().then(setConfig)
    // An already-open portal tab keeps the config from page load. Refresh when
    // the tab becomes visible again so admin-side facet or portal changes show
    // up without a manual reload.
    const refresh = () => {
      if (document.visibilityState === 'visible') {
        api.portal.config().then(setConfig).catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', refresh)
    return () => document.removeEventListener('visibilitychange', refresh)
  }, [])
  return config
}
