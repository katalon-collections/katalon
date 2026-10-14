// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TreeFacet } from '../api/client'
import { setLocale } from '../i18n'
import { TreeFacetPanel } from './TreeFacetPanel'

const tree: TreeFacet = {
  nodes: {
    root: [
      { id: 'natur', label: { de: 'Natur' }, count: 12, has_children: true },
      { id: 'musik', label: { de: 'Musik' }, count: 3, has_children: false },
    ],
    natur: [{ id: 'tiere', label: { de: 'Tiere' }, count: 7, has_children: true }],
  },
  paths: { tiere: [{ id: 'natur', label: { de: 'Natur' } }, { id: 'tiere', label: { de: 'Tiere' } }] },
}

describe('TreeFacetPanel', () => {
  beforeEach(() => act(() => setLocale('de')))
  afterEach(cleanup)

  it('shows the top level with counts and expands on demand', () => {
    const onToggle = vi.fn()
    const { rerender } = render(
      <TreeFacetPanel label="Schlagwort" tree={tree} active={[]} expanded={[]} onToggleExpand={onToggle} onSelect={() => {}} />,
    )
    expect(screen.getByText('Natur')).toBeTruthy()
    expect(screen.getByText('12')).toBeTruthy()
    expect(screen.queryByText('Tiere')).toBeNull()
    // Leaf nodes get no toggle.
    expect(screen.getAllByRole('button', { expanded: false })).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { expanded: false }))
    expect(onToggle).toHaveBeenCalledWith('natur')

    rerender(
      <TreeFacetPanel label="Schlagwort" tree={tree} active={[]} expanded={['natur']} onToggleExpand={onToggle} onSelect={() => {}} />,
    )
    expect(screen.getByText('Tiere')).toBeTruthy()
  })

  it('shows the breadcrumb of an active node and clears it', () => {
    const onSelect = vi.fn()
    render(
      <TreeFacetPanel label="Schlagwort" tree={tree} active={['tiere']} expanded={[]} onToggleExpand={() => {}} onSelect={onSelect} />,
    )
    expect(screen.getByText('Natur › Tiere')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Filter entfernen' }))
    expect(onSelect).toHaveBeenCalledWith('tiere')
  })

  it('offers a search field for long lists', () => {
    const many: TreeFacet = {
      nodes: { root: Array.from({ length: 60 }, (_, i) => ({ id: `t${i}`, label: { de: `Begriff ${i}` }, count: 1, has_children: false })) },
      paths: {},
    }
    render(<TreeFacetPanel label="S" tree={many} active={[]} expanded={[]} onToggleExpand={() => {}} onSelect={() => {}} />)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Begriff 42' } })
    expect(screen.getByText('Begriff 42')).toBeTruthy()
    expect(screen.queryByText('Begriff 41')).toBeNull()
  })
})
