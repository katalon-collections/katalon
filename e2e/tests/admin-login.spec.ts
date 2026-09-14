// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('admin can log in', async ({ page }) => {
  await loginAsAdmin(page)
  await expect(page.getByRole('heading', { name: 'Objekte' })).toBeVisible()
  await expect(page.locator('.sb-foot')).toContainText('admin@katalon.dev')
})

test('admin navigation works on a narrow mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 319, height: 359 })
  await loginAsAdmin(page)

  const sidebar = page.getByRole('complementary', { name: 'Hauptnavigation' })
  await page.getByRole('button', { name: 'Navigation öffnen' }).click()
  await expect(sidebar).toHaveClass(/open/)
  await expect(sidebar).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 0)')

  await page.getByRole('button', { name: 'Navigation schließen' }).first().click()
  await expect(sidebar).not.toHaveClass(/open/)
})
