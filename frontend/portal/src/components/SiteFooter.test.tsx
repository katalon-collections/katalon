// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PortalConfig } from '../api/client'

let config: Partial<PortalConfig> = {}
vi.mock('../hooks/usePortalConfig', () => ({ usePortalConfig: () => config }))
vi.mock('../api/client', async importOriginal => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  api: { pages: { list: () => Promise.resolve([]) } },
}))

const { SiteFooter, hasFooterContent } = await import('./SiteFooter')

describe('SiteFooter', () => {
  afterEach(cleanup)

  it('keeps the one-line default without configuration', () => {
    config = { site_title: { de: 'Bildpostkarten' }, footer: { columns: [], bottom: { text: {}, links: [] } } }
    render(<MemoryRouter><SiteFooter /></MemoryRouter>)
    expect(screen.getByText(/Bildpostkarten · Metadata Management System/)).toBeTruthy()
  })

  it('renders text, link and logo columns plus the bottom line', () => {
    config = {
      site_title: { de: 'X' },
      footer: {
        columns: [
          { type: 'text', title: { de: 'Hinweis' }, content: { de: 'Nach **§ 86**' }, links: [], include_footer_pages: false, logos: [] },
          { type: 'links', title: { de: 'Links' }, content: {}, links: [{ label: { de: 'Uni' }, url: 'https://uni.example' }, { label: { de: 'Hilfe' }, url: '/page/hilfe' }], include_footer_pages: false, logos: [] },
          { type: 'logos', title: {}, content: {}, links: [], include_footer_pages: false, logos: [{ src: '/themes/bpk/dfg.png', alt: { de: 'DFG' }, href: 'https://dfg.example' }] },
        ],
        bottom: { text: { de: '© 2026' }, links: [] },
      },
    }
    render(<MemoryRouter><SiteFooter /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Hinweis' })).toBeTruthy()
    expect(screen.getByText('§ 86').tagName).toBe('STRONG')
    const external = screen.getByRole('link', { name: 'Uni' })
    expect(external.getAttribute('target')).toBe('_blank')
    expect(external.getAttribute('rel')).toContain('noopener')
    expect(screen.getByRole('link', { name: 'Hilfe' }).getAttribute('href')).toBe('/page/hilfe')
    expect(screen.getByRole('img', { name: 'DFG' }).getAttribute('src')).toBe('/themes/bpk/dfg.png')
    expect(screen.getByText('© 2026')).toBeTruthy()
  })

  it('detects configured content', () => {
    expect(hasFooterContent(undefined)).toBe(false)
    expect(hasFooterContent({ columns: [], bottom: { text: { de: 'x' }, links: [] } })).toBe(true)
  })
})
