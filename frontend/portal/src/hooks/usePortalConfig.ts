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
  }, [])
  return config
}
