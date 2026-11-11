// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { describe, expect, it } from 'vitest'
import type { TreeFacet } from '../api/client'
import { pickTreeNode, treeParents } from './facets'

const label = (name: string) => ({ de: name })
const tree: TreeFacet = {
  nodes: {
    root: [{ id: 'de', label: label('D'), count: 2, has_children: true }, { id: 'fr', label: label('F'), count: 3, has_children: true }],
    fr: [{ id: 'chat', label: label('C'), count: 1, has_children: true }, { id: 'dord', label: label('Do'), count: 2, has_children: false }],
    chat: [{ id: 'vix', label: label('V'), count: 1, has_children: false }],
  },
  paths: {},
}
const parents = treeParents(tree)

describe('pickTreeNode', () => {
  it('replaces a selected parent when a child is picked', () => {
    expect(pickTreeNode(['fr'], 'chat', parents)).toEqual(['chat'])
    expect(pickTreeNode(['fr'], 'vix', parents)).toEqual(['vix'])
  })

  it('replaces selected descendants when an ancestor is picked', () => {
    expect(pickTreeNode(['chat', 'dord'], 'fr', parents)).toEqual(['fr'])
  })

  it('keeps nodes of other branches and clears a picked active node', () => {
    expect(pickTreeNode(['de'], 'chat', parents)).toEqual(['de', 'chat'])
    expect(pickTreeNode(['fr', 'de'], 'fr', parents)).toEqual(['de'])
  })

  it('knows ancestors from the paths of active values too', () => {
    const known = treeParents({ nodes: {}, paths: { x: [{ id: 'a', label: label('A') }, { id: 'b', label: label('B') }] } })
    expect(pickTreeNode(['a'], 'b', known)).toEqual(['b'])
  })
})
