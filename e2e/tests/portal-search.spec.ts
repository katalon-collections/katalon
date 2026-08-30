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

test('hides a disabled system facet even when its URL filter is active', async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({
    json: { ...portalConfig, facet_fields: { _system: ['status'] } },
  }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/search?**', route => route.fulfill({
    json: {
      total: 1,
      page: 1,
      page_size: 20,
      items: [],
      facets: {
        by_type: [{ value: 'object', count: 1 }],
        by_status: [{ value: 'public', count: 1 }],
      },
    },
  }))

  await page.goto('http://127.0.0.1:5174/search?q=&type=object')

  await expect(page.getByRole('heading', { name: 'Type' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Status' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'All' })).toHaveCount(0)

  await page.getByRole('button', { name: /public/ }).click()
  await expect(page.getByRole('button', { name: 'All' })).toBeVisible()
})

test('adds metadata facet values and uses the translated field label fallback', async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({
    json: { ...portalConfig, facet_fields: { object: ['event_date'] } },
  }))
  await page.route('**/portal/v1/schema/object', route => route.fulfill({
    json: [{ id: 'field-1', name: 'event_date', label: { de: 'Datierung', en: '' }, field_type: 'text' }],
  }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/search?**', route => route.fulfill({
    json: {
      total: 21,
      page: 1,
      page_size: 20,
      items: [],
      facets: {
        by_type: [{ value: 'object', count: 21 }],
        by_status: [{ value: 'public', count: 21 }],
        meta_event_date: [
          { value: 'Neolithikum', count: 17 },
          { value: 'Paläolithikum', count: 4 },
        ],
      },
    },
  }))

  await page.goto('http://127.0.0.1:5174/search?lang=en&type=object')

  await expect(page.getByRole('heading', { name: 'Datierung' })).toBeVisible()
  await page.getByRole('button', { name: /Neolithikum/ }).click()
  await page.getByRole('button', { name: /Paläolithikum/ }).click()

  await expect.poll(() => new URL(page.url()).searchParams.getAll('meta_event_date'))
    .toEqual(['Neolithikum', 'Paläolithikum'])
  await expect(page.getByRole('button', { name: /Neolithikum/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: /Paläolithikum/ })).toHaveAttribute('aria-pressed', 'true')
})

test('filters a numeric facet through range controls', async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({
    json: { ...portalConfig, facet_fields: { object: ['year'] } },
  }))
  await page.route('**/portal/v1/schema/object', route => route.fulfill({
    json: [{ id: 'field-1', name: 'year', label: { de: 'Jahr' }, field_type: 'number' }],
  }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/search?**', route => route.fulfill({
    json: {
      total: 1, page: 1, page_size: 20, items: [], facets: {},
      numeric_facets: { year: { min: 1900, max: 2000 } },
    },
  }))

  await page.goto('http://127.0.0.1:5174/search?type=object&page=2')
  const from = page.getByRole('spinbutton', { name: 'Jahr: Von' })
  await from.fill('1950')

  await expect.poll(() => new URL(page.url()).searchParams.get('range_year_from')).toBe('1950')
  expect(new URL(page.url()).searchParams.get('page')).toBe('1')
  await expect(page.getByRole('slider', { name: 'Jahr: Bis slider' })).toBeVisible()
  await page.getByRole('button', { name: 'Alle' }).click()
  await expect.poll(() => new URL(page.url()).searchParams.has('range_year_from')).toBe(false)
})

test('refines within the active search filters', async ({ page }) => {
  await page.route('**/portal/v1/portal/config', route => route.fulfill({ json: portalConfig }))
  await page.route('**/portal/v1/banners/active/portal', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/pages', route => route.fulfill({ json: [] }))
  await page.route('**/portal/v1/search?**', route => route.fulfill({
    json: { total: 0, page: 1, page_size: 20, items: [], facets: {} },
  }))

  await page.goto('http://127.0.0.1:5174/search?q=stein&type=object&page=3&meta_classification=Archaeology&rel_place=Berlin')
  await page.getByRole('textbox', { name: 'Refine search…' }).fill('beil')
  await page.getByRole('textbox', { name: 'Refine search…' }).press('Enter')

  const params = new URL(page.url()).searchParams
  expect(params.get('q')).toBe('beil')
  expect(params.get('type')).toBe('object')
  expect(params.get('meta_classification')).toBe('Archaeology')
  expect(params.get('rel_place')).toBe('Berlin')
  expect(params.get('page')).toBe('1')
})
