// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin
import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import '../../i18n'
import { RelationCounterpartHint } from './RelationCounterpartHint'

const counterpart = {
  id: 'c1', name: 'expression', label: { de: 'Expression' },
  target_subtype: 'work', relation_target_subtype: 'expression', parent_name: null,
}

it('names the existing counter-direction field and its subtype', () => {
  render(<RelationCounterpartHint counterparts={[counterpart]} targetTypeLabel="Vorkommnis" />)
  expect(screen.getByRole('status').textContent).toContain(
    'Diese Beziehung existiert bereits in Gegenrichtung: Feld „Expression“ an Vorkommnis (Subtyp „work“).',
  )
})

it('says all subtypes when the existing field has no subtype', () => {
  render(<RelationCounterpartHint counterparts={[{ ...counterpart, target_subtype: null }]} targetTypeLabel="Vorkommnis" />)
  expect(screen.getByRole('status').textContent).toContain('an Vorkommnis (alle Subtypen).')
})

it('renders nothing without counterparts', () => {
  const { container } = render(<RelationCounterpartHint counterparts={[]} targetTypeLabel="Vorkommnis" />)
  expect(container.innerHTML).toBe('')
})
