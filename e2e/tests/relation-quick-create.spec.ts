import { expect, test, type Locator, type Page } from '@playwright/test'
import { loginAsAdmin } from './helpers'

async function expectTouchTarget(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.width).toBeGreaterThanOrEqual(44)
  expect(box!.height).toBeGreaterThanOrEqual(44)
}

async function setRelationType(page: Page, value: string) {
  const control = page.getByLabel('Relationstyp')
  if (await control.evaluate(element => element.tagName === 'SELECT')) {
    const option = await control.locator('option:not([value=""])').first().getAttribute('value')
    expect(option, 'relation type vocabulary needs at least one term').toBeTruthy()
    await control.selectOption(option!)
    return option!
  }
  await control.fill(value)
  return value
}

async function selectSubtypeWhenRequired(dialog: Locator) {
  const subtype = dialog.locator('.field').filter({ hasText: /Objekt-Typ/ }).locator('select')
  if (await subtype.count()) {
    await expect(subtype).toBeEnabled()
    if (!(await subtype.inputValue())) {
      const option = await subtype.locator('option:not([value=""])').first().getAttribute('value')
      if (option) await subtype.selectOption(option)
    }
  }
}

test('generic relations picker quick-creates and links an object draft accessibly', async ({ page }) => {
  const sourceIdno = `E2E-REL-SOURCE-${Date.now()}`
  const targetIdno = `E2E-REL-TARGET-${Date.now()}`

  await loginAsAdmin(page)
  await page.getByRole('button', { name: 'Neu anlegen' }).click()
  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(sourceIdno)
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByText(sourceIdno)).toBeVisible()

  await page.getByRole('button', { name: 'Beziehung hinzufügen' }).click()
  const targetType = page.getByLabel('Zieltyp')
  await expect(targetType.locator('option')).toHaveText([
    'Objekt',
    'Entität',
    'Ort',
    'Occurrence',
    'Vorgang',
  ])
  await targetType.selectOption('object')
  const relationType = await setRelationType(page, `e2e-related-${Date.now()}`)

  const createButton = page.getByRole('button', { name: 'Neues Objekt anlegen' })
  await expect(createButton).toBeEnabled()
  await createButton.click()

  let dialog = page.getByRole('dialog', { name: 'Neues Objekt anlegen' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('Wird als Entwurf gespeichert')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Entwurf anlegen und verknüpfen' })).toBeVisible()
  await expect(dialog.getByPlaceholder('z.B. FOT.1958.0412')).toBeEnabled()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(createButton).toBeFocused()

  await page.setViewportSize({ width: 375, height: 667 })
  await createButton.click()
  dialog = page.getByRole('dialog', { name: 'Neues Objekt anlegen' })
  await expect(dialog).toBeVisible()
  await expectTouchTarget(dialog.getByRole('button', { name: 'Schnellanlage schließen' }))
  await expectTouchTarget(dialog.getByRole('button', { name: 'Entwurf anlegen und verknüpfen' }))
  await expectTouchTarget(dialog.getByPlaceholder('z.B. FOT.1958.0412'))
  const width = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(width.scroll, 'document must not scroll horizontally').toBeLessThanOrEqual(width.client)

  await dialog.getByPlaceholder('z.B. FOT.1958.0412').fill(targetIdno)
  await selectSubtypeWhenRequired(dialog)
  const [createRequest, relationRequest] = await Promise.all([
    page.waitForRequest(request => request.method() === 'POST' && new URL(request.url()).pathname === '/v1/objects'),
    page.waitForRequest(request => request.method() === 'POST' && new URL(request.url()).pathname === '/v1/relations'),
    dialog.getByRole('button', { name: 'Entwurf anlegen und verknüpfen' }).click(),
  ])

  expect(createRequest.postDataJSON()).toMatchObject({ idno: targetIdno, status: 'draft' })
  expect(relationRequest.postDataJSON()).toMatchObject({
    from_type: 'object',
    to_type: 'object',
    relation_type: relationType,
  })
  await expect(dialog).toBeHidden()
  await expect(page.getByText(targetIdno)).toBeVisible()
})
