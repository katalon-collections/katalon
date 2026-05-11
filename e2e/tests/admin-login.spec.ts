import { expect, test } from '@playwright/test'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByPlaceholder('admin@katalon.dev').fill('admin@katalon.dev')
  await page.getByPlaceholder('••••••••').fill('admin')
  await page.getByRole('button', { name: 'Anmelden' }).click()
}

test('admin can log in', async ({ page }) => {
  await login(page)
  await expect(page.getByText('Objekte')).toBeVisible()
  await expect(page.locator('.sb-foot')).toContainText('admin@katalon.dev')
})
