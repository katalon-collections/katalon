import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('admin can upload an image to an object', async ({ page }) => {
  const idno = `E2E-UP-${Date.now()}`

  await loginAsAdmin(page)
  const token = await page.evaluate(() => localStorage.getItem('katalon_token'))
  const response = await page.request.post('/v1/objects', {
    headers: { Authorization: `Bearer ${token}` },
    data: { idno, status: 'draft', object_type: 'objekt', metadata_: {} },
  })
  expect(response.status()).toBe(201)
  const object = await response.json()
  await page.goto(`/#form/${object.id}`)

  const pngBytes = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
    'base64',
  )

  await page.locator('input[type="file"]').setInputFiles({
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: pngBytes,
  })

  await expect(page.getByText('tiny.png')).toBeVisible()
})
