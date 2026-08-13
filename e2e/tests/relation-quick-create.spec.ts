import { expect, test, type Locator, type Page } from '@playwright/test'
import { loginAsAdmin } from './helpers'

async function expectTouchTarget(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.width).toBeGreaterThanOrEqual(44)
  expect(box!.height).toBeGreaterThanOrEqual(44)
}

async function setRelationType(scope: Page | Locator, value: string) {
  const control = scope.getByLabel('Relationstyp')
  if (await control.evaluate(element => element.tagName === 'SELECT')) {
    const option = await control.locator('option:not([value=""])').first().getAttribute('value')
    expect(option, 'relation type vocabulary needs at least one term').toBeTruthy()
    await control.selectOption(option!)
    return option!
  }
  await control.fill(value)
  return value
}

async function createRelationType(page: Page, term = `e2e-related-${Date.now()}`): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem('katalon_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const vocabularies = await page.request.get('/v1/vocabularies', { headers })
  expect(vocabularies.ok()).toBeTruthy()
  const vocabulary = (await vocabularies.json()).find((item: { name: string }) => item.name === 'relation_types')
  expect(vocabulary).toBeTruthy()
  const created = await page.request.post(`/v1/vocabularies/${vocabulary.id}/terms`, {
    headers,
    data: {
      vocabulary_id: vocabulary.id,
      term,
      label: { de: 'E2E-Beziehung' },
    },
  })
  expect(created.ok()).toBeTruthy()
  return vocabulary.id
}

type E2ERelationField = { id: string; name: string }

async function createRelationFields(page: Page, relationType: string, relationTypeVocab: string): Promise<Record<string, E2ERelationField>> {
  const token = await page.evaluate(() => localStorage.getItem('katalon_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const entries = await Promise.all(['object', 'entity', 'place', 'occurrence', 'procedure'].map(async targetType => {
    const name = `e2e_inline_${targetType}_${Date.now()}`
    const response = await page.request.post('/v1/schema', {
      headers,
      data: {
        target_type: 'object',
        name,
        label: { de: `E2E ${targetType}` },
        field_type: 'relation',
        settings: { target_type: targetType, relation_type_vocab: relationTypeVocab, fixed_relation_type: relationType },
      },
    })
    expect(response.ok()).toBeTruthy()
    const field = await response.json() as { id: string }
    return [targetType, { id: field.id, name }] as const
  }))
  return Object.fromEntries(entries)
}

async function deleteRelationFields(page: Page, fields: Record<string, E2ERelationField>) {
  const token = await page.evaluate(() => localStorage.getItem('katalon_token'))
  const headers = { Authorization: `Bearer ${token}` }
  await Promise.all(Object.values(fields).map(async field => {
    const response = await page.request.delete(`/v1/schema/${field.id}`, { headers })
    expect(response.status()).toBe(204)
  }))
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
  await page.setViewportSize({ width: 375, height: 667 })
  await createRelationType(page)
  await page.reload()
  await page.getByRole('button', { name: 'Neu anlegen' }).click()
  await page.getByPlaceholder('z.B. FOT.1958.0412').fill(sourceIdno)
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByText(sourceIdno)).toBeVisible()

  await page.getByRole('button', { name: 'Freie Beziehung zu anderen Haupttypen hinzufügen' }).click()
  const picker = page.locator('.generic-relation-picker')
  const targetType = picker.getByLabel('Zieltyp')
  await expect(targetType.locator('option')).toHaveText([
    'Objekt',
    'Entität',
    'Ort',
    'Occurrence',
    'Vorgang',
  ])
  await targetType.selectOption('object')
  const relationType = await setRelationType(picker, `e2e-related-${Date.now()}`)

  const search = picker.getByPlaceholder('object suchen (mind. 2 Zeichen)…')
  await search.fill(targetIdno)
  const createButton = picker.getByRole('button', { name: `Neues Objekt „${targetIdno}“ anlegen` })
  await expect(createButton).toBeVisible()
  await createButton.click()

  let dialog = page.getByRole('dialog', { name: 'Neues Objekt anlegen' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('Wird als Entwurf gespeichert')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Entwurf anlegen und verknüpfen' })).toBeVisible()
  await expect(dialog.getByPlaceholder('z.B. FOT.1958.0412')).toBeEnabled()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(createButton).toBeFocused()

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

test('quick-create relation fields offer every primary type', async ({ page }) => {
  await loginAsAdmin(page)
  const relationType = `e2e-inline-${Date.now()}`
  const relationTypeVocab = await createRelationType(page, relationType)
  const fields = await createRelationFields(page, relationType, relationTypeVocab)
  try {
    await page.reload()

    await page.getByRole('button', { name: 'Neu anlegen' }).click()
    await page.getByPlaceholder('z.B. FOT.1958.0412').fill(`E2E-INLINE-SOURCE-${Date.now()}`)
    await page.getByRole('button', { name: 'Speichern', exact: true }).click()
    await page.getByRole('button', { name: 'Freie Beziehung zu anderen Haupttypen hinzufügen' }).click()
    const picker = page.locator('.generic-relation-picker')
    await picker.getByLabel('Zieltyp').selectOption('object')
    await setRelationType(picker, relationType)
    const query = `E2E-INLINE-TARGET-${Date.now()}`
    await picker.getByPlaceholder('object suchen (mind. 2 Zeichen)…').fill(query)
    await picker.getByRole('button', { name: `Neues Objekt „${query}“ anlegen` }).click()

    const outerDialog = page.getByRole('dialog', { name: 'Neues Objekt anlegen' })
    for (const [targetType, label] of Object.entries({ object: 'Neues Objekt', entity: 'Neue Entität', place: 'Neuer Ort', occurrence: 'Neue Occurrence', procedure: 'Neuer Vorgang' })) {
      const fieldQuery = `${query}-${targetType}`
      const field = outerDialog.locator(`#field-${fields[targetType].name}`)
      await field.getByPlaceholder(`${targetType} suchen (mind. 2 Zeichen)…`).fill(fieldQuery)
      await expect(page.getByRole('button', { name: `${label} „${fieldQuery}“ anlegen` })).toBeVisible()
    }

    await page.getByRole('button', { name: `Neue Entität „${query}-entity“ anlegen` }).click()
    await expect(page.getByRole('dialog', { name: 'Neue Entität anlegen' })).toBeVisible()
  } finally {
    await deleteRelationFields(page, fields)
  }
})
