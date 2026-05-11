import { expect, test } from '@playwright/test'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByPlaceholder('admin@katalon.dev').fill('admin@katalon.dev')
  await page.getByPlaceholder('••••••••').fill('admin')
  await page.getByRole('button', { name: 'Anmelden' }).click()
}

test('admin can upload an image to an object', async ({ page }) => {
  const idno = `E2E-UP-${Date.now()}`

  await login(page)
  await page.getByRole('button', { name: 'Neu anlegen' }).click()
  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(idno)
  await page.getByRole('button', { name: 'Speichern' }).click()

  const pngBytes = Uint8Array.from([
    137, 80, 78, 71, 13, 10, 26, 10,
    0, 0, 0, 13, 73, 72, 68, 82,
    0, 0, 0, 1, 0, 0, 0, 1,
    8, 6, 0, 0, 0, 31, 21, 196,
    137, 0, 0, 0, 13, 73, 68, 65,
    84, 120, 156, 99, 248, 255, 255, 63,
    0, 5, 254, 2, 254, 167, 53, 129,
    132, 0, 0, 0, 0, 73, 69, 78,
    68, 174, 66, 96, 130,
  ])

  await page.locator('input[type="file"]').setInputFiles({
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: Buffer.from(pngBytes),
  })

  await expect(page.getByText('tiny.png')).toBeVisible()
})
