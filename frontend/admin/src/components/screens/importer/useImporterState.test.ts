// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { expect, it } from 'vitest'
import { buildInitialState, importerReducer } from './useImporterState'

const idCol = 'lido:repositorySet/lido:workID'
const mapping = { [idCol]: { target: '__idno__' }, 'lido:title': { target: 'title' } }

it('takes the ID column from a loaded profile mapping', () => {
  const state = importerReducer({ ...buildInitialState(null), sourceType: 'xml' }, {
    type: 'PROFILE_APPLIED',
    payload: { mapping, mediaSelector: null, pendingFields: [], upsertStrategy: 'skip', autoPublish: true, idnoStrategy: 'column' },
  })
  expect(state.idnoColumn).toBe(idCol)
})

it('takes the ID column from a loaded saved template', () => {
  const state = importerReducer({ ...buildInitialState(null), idnoStrategy: 'auto' }, {
    type: 'SAVED_MAPPING_APPLIED',
    payload: { mapping, mediaSelector: null, mappingId: 'm1', savedMappingName: 'LIDO' },
  })
  expect(state.idnoStrategy).toBe('column')
  expect(state.idnoColumn).toBe(idCol)
})

it('forgets the loaded template when a new file is uploaded', () => {
  const loaded = importerReducer(buildInitialState(null), {
    type: 'SAVED_MAPPING_APPLIED',
    payload: { mapping, mediaSelector: null, mappingId: 'm1', savedMappingName: 'LIDO' },
  })
  const state = importerReducer(loaded, {
    type: 'UPLOADED',
    payload: { upload_id: 'u2', headers: ['Label'], row_count: 1, preview: [], suggestions: {} },
  })
  expect(state.mappingId).toBeNull()
  expect(state.savedMappingName).toBeNull()
})
