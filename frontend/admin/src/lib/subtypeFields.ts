// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { FieldDefinition } from '../types'

const hasValue = (value: unknown) =>
  value != null && value !== '' && !(Array.isArray(value) && value.length === 0)

/**
 * Fields shown for a record of `subtype`. A field of another subtype stays visible,
 * as optional, while the record holds stored data for it.
 */
export function fieldsForSubtype(
  fields: FieldDefinition[], subtype: string, stored: Record<string, unknown> = {},
): FieldDefinition[] {
  return fields.flatMap(field => {
    if (!field.target_subtype || field.target_subtype === subtype) return [field]
    if (!hasValue(stored[field.name])) return []
    return [{ ...field, is_required: false, children: field.children?.map(c => ({ ...c, is_required: false })) }]
  })
}
