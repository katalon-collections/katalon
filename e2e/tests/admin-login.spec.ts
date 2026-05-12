import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('admin can log in', async ({ page }) => {
  await loginAsAdmin(page)
  await expect(page.getByRole('heading', { name: 'Objekte' })).toBeVisible()
  await expect(page.locator('.sb-foot')).toContainText('admin@katalon.dev')
})
