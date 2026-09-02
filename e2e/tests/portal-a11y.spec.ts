// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const portalConfig = {
  site_title: 'Katalon',
  site_subtitle: '',
  hero_text: '',
  featured_object_ids: [],
  facet_fields: { object: ['classification'] },
  subtitle_fields: {},
  browse_enabled_types: ['object', 'entity', 'place', 'occurrence'],
  accent_color: '#1e3a8a',
  logo_url: '',
  placeholder_image_url: '',
  color_tokens: {},
  supported_languages: ['de', 'en'],
  detail_sidebar_position: 'right',
}

test.beforeEach(async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({ json: portalConfig }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
})

test('homepage has no automatically detectable a11y violations', async ({ page }) => {
  await page.route('**/portal/v1/search?**', route =>
    route.fulfill({
      json: {
        total: 0,
        page: 1,
        page_size: 20,
        items: [],
        facets: { by_type: [], by_status: [] },
      },
    }),
  )
  await page.goto('http://127.0.0.1:5174/')
  await expect(page.locator('body')).toBeVisible()

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
})

test('search results page has no automatically detectable a11y violations', async ({ page }) => {
  await page.route('**/portal/v1/search?**', route =>
    route.fulfill({
      json: {
        total: 1,
        page: 1,
        page_size: 20,
        items: [
          {
            id: 'obj-1',
            type: 'object',
            title: 'Stein aus Marrakesch',
            subtitle: '',
            thumbnail_url: null,
            status: 'public',
          },
        ],
        facets: {
          by_type: [{ value: 'object', count: 1 }],
          by_status: [{ value: 'public', count: 1 }],
        },
      },
    }),
  )
  await page.goto('http://127.0.0.1:5174/search?q=&type=object')
  await expect(page.getByText('Stein aus Marrakesch')).toBeVisible()

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
})
