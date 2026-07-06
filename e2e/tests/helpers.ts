import type { Page } from '@playwright/test'

export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByPlaceholder('admin@katalon.dev').fill('admin@katalon.dev')
  await page.getByPlaceholder('••••••••').fill('admin')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await page.waitForFunction(() => Boolean(localStorage.getItem('katalon_token')))
}
