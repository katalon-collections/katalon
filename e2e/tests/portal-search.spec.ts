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

test('keeps configured facets when an older search response arrives last', async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({ json: portalConfig }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/search?**', async route => {
    const configured = new URL(route.request().url()).searchParams.has('facets')
    await new Promise(resolve => setTimeout(resolve, configured ? 20 : 300))
    await route.fulfill({
      json: {
        total: 1,
        page: 1,
        page_size: 20,
        items: [],
        facets: {
          by_type: [{ value: 'object', count: 1 }],
          by_status: [{ value: 'public', count: 1 }],
          ...(configured ? { meta_classification: [{ value: 'Archaeology', count: 1 }] } : {}),
        },
      },
    })
  })

  await page.goto('http://127.0.0.1:5174/search?q=&type=object')
  await page.waitForTimeout(500)

  await expect(page.getByRole('heading', { name: 'classification' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Archaeology/ })).toBeVisible()
})
