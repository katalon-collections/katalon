// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { PortalFieldDefinition } from '../api/client'
import { typeLabel } from '../i18n'
import { renderFieldValue } from './renderFieldValue'

/** Subtitle line for a record card outside the search page (homepage grids),
 *  built from the same `subtitle_fields` configuration as the search result
 *  list. Fields without a resolvable display value (group fields, inherited
 *  facets that are not part of the record's own metadata) are skipped; with no
 *  configuration the subtitle is empty rather than showing raw values. */
export function recordSubtitle(
  record: { status: string | null; idno?: string | null; metadata_: Record<string, unknown> },
  recordType: string,
  fields: string[] | undefined,
  fieldDefs: PortalFieldDefinition[],
  locale: string,
): string {
  return (fields ?? [])
    .map(field => {
      if (field === 'record_type') return typeLabel(recordType)
      if (field === 'status') return record.status
      if (field === 'idno') return record.idno ?? null
      const def = fieldDefs.find(d => d.name === field && !d.parent_id)
      if (!def || def.field_type === 'group') return null
      return renderFieldValue(record.metadata_?.[field], locale, def.field_type)
    })
    .filter((v): v is string => !!v)
    .join(' · ')
}
