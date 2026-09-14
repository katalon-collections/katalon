// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { expect, test, type Locator, type Page } from '@playwright/test'
import { loginAsAdmin } from './helpers'

async function expectDocumentFits(page: Page) {
  const size = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(size.scrollWidth, 'document must not scroll horizontally').toBeLessThanOrEqual(size.clientWidth)
}

async function expectTouchTarget(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.width).toBeGreaterThanOrEqual(44)
  expect(box!.height).toBeGreaterThanOrEqual(44)
}

async function expectWithinViewport(page: Page, locator: Locator) {
  const box = await locator.boundingBox()
  const viewport = page.viewportSize()
  expect(box).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height)
}

async function expectSingleColumnGrids(grids: Locator) {
  await expect(grids.first()).toBeVisible()
  const count = await grids.count()
  expect(count).toBeGreaterThanOrEqual(1)
  for (let index = 0; index < count; index += 1) {
    const metrics = await grids.nth(index).evaluate(grid => ({
      columns: getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).filter(Boolean).length,
      fits: grid.scrollWidth <= grid.clientWidth + 1,
    }))
    expect(metrics.columns).toBe(1)
    expect(metrics.fits).toBe(true)
  }
}

test.afterEach(async ({ page }, testInfo) => {
  await testInfo.attach('responsive-viewport', {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
})

test('object list fits a 319px viewport', async ({ page }) => {
  await page.setViewportSize({ width: 319, height: 359 })
  await loginAsAdmin(page)

  const createButton = page.getByRole('button', { name: 'Neu anlegen' })
  const tabs = page.locator('.tabs').first()
  const search = page.getByRole('textbox', { name: 'Objekte durchsuchen' })
  await expect(page.getByRole('heading', { name: 'Objekte' })).toBeVisible()
  await expect(createButton).toBeVisible()
  await expect(tabs).toBeVisible()
  await expect(search).toBeVisible()
  await expectTouchTarget(createButton)
  await expectTouchTarget(page.getByRole('button', { name: /^Alle\b/ }))
  await expectWithinViewport(page, createButton)
  await expectWithinViewport(page, search)

  const table = await page.locator('.tw').evaluate(wrapper => {
    const inner = wrapper.querySelector('table')!
    return {
      overflowX: getComputedStyle(wrapper).overflowX,
      wrapperClientWidth: wrapper.clientWidth,
      wrapperScrollWidth: wrapper.scrollWidth,
      tableScrollWidth: inner.scrollWidth,
    }
  })
  expect(table.overflowX).toMatch(/auto|scroll/)
  expect(table.tableScrollWidth).toBeGreaterThan(table.wrapperClientWidth)
  expect(table.wrapperScrollWidth).toBeGreaterThan(table.wrapperClientWidth)
  expect(table.wrapperScrollWidth).toBeGreaterThanOrEqual(table.tableScrollWidth)
  await expectDocumentFits(page)
})

test('configuration screens fit a 375px viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await loginAsAdmin(page)

  for (const route of ['audit', 'banners', 'settings', 'users']) {
    await page.goto(`/#${route}`)
    await expect(page.locator('h1').first()).toBeVisible()
    await expectDocumentFits(page)
  }
})

test('schema uses its mobile subtype control at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await loginAsAdmin(page)
  await page.goto('/#schema')

  const subtypeSelect = page.getByLabel('Subtyp', { exact: true })
  const createButton = page.getByRole('button', { name: 'Neues Feld' })
  await expect(page.getByRole('heading', { name: 'Schemata' })).toBeVisible()
  await expect(page.locator('.tabs').first()).toBeVisible()
  await expect(createButton).toBeVisible()
  await expect(subtypeSelect).toBeVisible()
  await expect(subtypeSelect).toBeEnabled()
  await expect(page.locator('.schema-subtype-panel')).toBeHidden()
  await expectTouchTarget(createButton)
  await expectTouchTarget(subtypeSelect)
  await expectWithinViewport(page, createButton)
  await expectWithinViewport(page, subtypeSelect)

  const firstField = page.locator('.field-row').first()
  const fieldAction = firstField.locator('.field-row-main')
  const deleteAction = firstField.locator('.actions button')
  await expect(firstField).toBeVisible()
  await expect(fieldAction).toBeVisible()
  await expect(deleteAction).toBeVisible()
  await expectTouchTarget(fieldAction)
  await expectTouchTarget(deleteAction)
  await expectWithinViewport(page, fieldAction)
  await expectWithinViewport(page, deleteAction)

  const subtypeOptions = subtypeSelect.locator('option')
  expect(await subtypeOptions.count()).toBeGreaterThanOrEqual(1)
  expect(await subtypeOptions.first().getAttribute('value')).toBe('')
  await expectDocumentFits(page)
})

test('new forms keep actions and multi-field grids usable at 768px', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await loginAsAdmin(page)
  await page.goto('/#procedures-form/new')

  const status = page.getByRole('group', { name: 'Status' })
  const saveButton = page.getByRole('button', { name: 'Speichern', exact: true })
  await expect(status).toBeVisible()
  await expect(saveButton).toBeVisible()
  await expectTouchTarget(saveButton)
  await expectTouchTarget(status.getByRole('button').first())
  await expectWithinViewport(page, saveButton)
  await expectWithinViewport(page, status)

  const nextStatus = status.getByRole('button').nth(1)
  await nextStatus.click()
  await expect(nextStatus).toHaveAttribute('aria-pressed', 'true')
  await expectSingleColumnGrids(page.locator('.fg-3'))

  await page.goto('/#places-form/new')
  await expect(page.getByRole('button', { name: 'Speichern', exact: true })).toBeVisible()
  await expectSingleColumnGrids(page.locator('.fg-2'))

  const form = await page.locator('.form-single').evaluate(element => ({
    fits: element.scrollWidth <= element.clientWidth + 1,
  }))
  expect(form.fits).toBe(true)
  await expectDocumentFits(page)
})
