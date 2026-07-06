import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('admin can create object from UI', async ({ page }) => {
  const idno = `E2E-${Date.now()}`

  await loginAsAdmin(page)
  await page.getByRole('button', { name: 'Neu anlegen' }).click()

  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(idno)
  await page.getByRole('button', { name: 'Speichern' }).click()

  // After save the app navigates to the edit view — wait for the idno to appear
  await expect(page.getByText(idno)).toBeVisible()
  await page.goto('/objects')

  await expect(page.getByText(idno)).toBeVisible()
})
