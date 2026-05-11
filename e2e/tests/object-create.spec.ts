import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('admin can create object from UI', async ({ page }) => {
  const idno = `E2E-${Date.now()}`

  await loginAsAdmin(page)
  await page.getByRole('button', { name: 'Neu anlegen' }).click()

  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(idno)
  await page.getByRole('button', { name: 'Speichern' }).click()

  await expect(page.getByText('Objekt gespeichert.')).toBeVisible()
  await page.getByRole('button', { name: 'Zur Liste' }).click()

  await expect(page.getByText(idno)).toBeVisible()
})
