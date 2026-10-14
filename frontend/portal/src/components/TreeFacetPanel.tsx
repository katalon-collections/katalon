// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import type { TreeFacet, TreeFacetNode } from '../api/client'
import { useI18n } from '../i18n'
import { resolveLabel } from '../utils/facets'

const SEARCH_THRESHOLD = 50

/** Facet over a hierarchical vocabulary: top level with counts, children load
 *  when a node is expanded, selecting a node filters including all narrower
 *  terms. Active values show as a breadcrumb that can be cleared. */
export function TreeFacetPanel({ label, tree, active, expanded, onToggleExpand, onSelect }: {
  label: string
  tree: TreeFacet | undefined
  active: string[]
  expanded: string[]
  onToggleExpand: (id: string) => void
  onSelect: (id: string) => void
}) {
  const { t, locale } = useI18n()
  const roots = tree?.nodes.root ?? []
  if (!roots.length && !active.length) return null

  return (
    <div className="tree-facet" style={{ marginBottom: 20 }}>
      <h3>{label}</h3>
      {active.map(id => {
        const path = tree?.paths[id] ?? []
        return (
          <div key={id} className="tree-facet-crumb">
            <span>{path.map(step => resolveLabel(step.label, locale, step.id)).join(' › ') || id}</span>
            <button type="button" onClick={() => onSelect(id)} aria-label={t('search.removeFilter')}>×</button>
          </div>
        )
      })}
      <TreeLevel
        nodes={roots}
        tree={tree}
        active={active}
        expanded={expanded}
        onToggleExpand={onToggleExpand}
        onSelect={onSelect}
        depth={0}
      />
    </div>
  )
}

function TreeLevel({ nodes, tree, active, expanded, onToggleExpand, onSelect, depth }: {
  nodes: TreeFacetNode[]
  tree: TreeFacet | undefined
  active: string[]
  expanded: string[]
  onToggleExpand: (id: string) => void
  onSelect: (id: string) => void
  depth: number
}) {
  const { t, locale } = useI18n()
  const [filter, setFilter] = useState('')
  const needle = filter.trim().toLowerCase()
  const visible = needle
    ? nodes.filter(node => resolveLabel(node.label, locale, node.id).toLowerCase().includes(needle))
    : nodes
  return (
    <ul className="tree-facet-level" role={depth ? 'group' : undefined}>
      {nodes.length > SEARCH_THRESHOLD && (
        <li>
          <input
            className="tree-facet-search"
            type="search"
            value={filter}
            onChange={event => setFilter(event.target.value)}
            placeholder={t('search.filterTerms')}
            aria-label={t('search.filterTerms')}
          />
        </li>
      )}
      {visible.map(node => {
        const isOpen = expanded.includes(node.id)
        const children = tree?.nodes[node.id]
        const name = resolveLabel(node.label, locale, node.id)
        return (
          <li key={node.id}>
            <div className="tree-facet-row">
              {node.has_children ? (
                <button
                  type="button"
                  className="tree-facet-toggle"
                  aria-expanded={isOpen}
                  aria-label={t(isOpen ? 'search.collapse' : 'search.expand', { name })}
                  onClick={() => onToggleExpand(node.id)}
                >
                  {isOpen ? '▾' : '▸'}
                </button>
              ) : <span className="tree-facet-toggle" aria-hidden="true" />}
              <button
                type="button"
                className="facet-item"
                aria-pressed={active.includes(node.id)}
                style={{ fontWeight: active.includes(node.id) ? 600 : undefined }}
                onClick={() => onSelect(node.id)}
              >
                <span>{name}</span>
                <span className="ct">{node.count}</span>
              </button>
            </div>
            {isOpen && (children
              ? (
                <TreeLevel
                  nodes={children}
                  tree={tree}
                  active={active}
                  expanded={expanded}
                  onToggleExpand={onToggleExpand}
                  onSelect={onSelect}
                  depth={depth + 1}
                />
              )
              : <div className="tree-facet-loading">{t('common.loading')}</div>)}
          </li>
        )
      })}
    </ul>
  )
}
