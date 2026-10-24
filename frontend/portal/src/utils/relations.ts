// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { Relation } from '../api/client'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'

/**
 * Relations the record's own relation fields already show on the detail page.
 * They are left out of the generic relations list so each link appears once.
 */
export function withoutFieldRelations(relations: Relation[], currentId: string, fieldDefs: FieldDefinition[]): Relation[] {
  const shown = new Set(fieldDefs.filter(f => !f.parent_id && f.show_in_detail).map(f => f.name))
  return relations.filter(r => {
    if (r.from_id !== currentId || !r.source_field) return true
    return !shown.has(r.source_field.split('.')[0])
  })
}
