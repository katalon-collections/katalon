import { expect, test } from '@playwright/test'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByPlaceholder('admin@katalon.dev').fill('admin@katalon.dev')
  await page.getByPlaceholder('••••••••').fill('admin')
  await page.getByRole('button', { name: 'Anmelden' }).click()
}

test('admin can create object from UI', async ({ page }) => {
  const idno = `E2E-${Date.now()}`

  await login(page)
  await page.getByRole('button', { name: 'Neu anlegen' }).click()

  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(idno)
  await page.getByRole('button', { name: 'Speichern' }).click()

  await expect(page.getByText('Objekt gespeichert.')).toBeVisible()
  await page.getByRole('button', { name: 'Zur Liste' }).click()

  await expect(page.getByText(idno)).toBeVisible()
})
