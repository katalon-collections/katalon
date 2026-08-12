import type { Page } from '@playwright/test'

export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByPlaceholder('admin@katalon.dev').fill('admin@katalon.dev')
  await page.getByPlaceholder('••••••••').fill('admin')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await page.waitForFunction(() => Boolean(localStorage.getItem('katalon_token')))
  const token = await page.evaluate(() => localStorage.getItem('katalon_token'))
  const onboarding = await page.request.put('/v1/users/me/onboarding', {
    headers: { Authorization: `Bearer ${token}` },
    data: { completed: true },
  })
  if (!onboarding.ok()) throw new Error(`Onboarding setup failed: ${onboarding.status()}`)
  await page.reload()
}
