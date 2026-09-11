// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type { MappingEntry } from '../../../api/client'
import type { FieldDefinition } from '../../../types'
import type { ImportProfile, PendingField, ProfileApplyResult } from './types'

export function buildProfile(
  mapping: Record<string, MappingEntry>,
  options: { record_type: string; mediaSelector: string | null; idnoStrategy: string; upsertStrategy: string; autoPublish: boolean },
  fieldDefs: FieldDefinition[],
): ImportProfile {
  const usedTargets = new Set(Object.values(mapping).map(e => e.target))
  const field_definitions: ImportProfile['field_definitions'] = {}
  for (const fd of fieldDefs) {
    if (usedTargets.has(fd.name)) {
      field_definitions[fd.name] = {
        name: fd.name,
        field_type: fd.field_type,
        label: fd.label,
        is_required: fd.is_required,
        is_repeatable: fd.is_repeatable,
        settings: fd.settings ?? {},
      }
    }
  }
  return { version: 1, ...options, mapping, field_definitions }
}

export function downloadProfile(profile: ImportProfile): void {
  const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `katalon_import_profil_${profile.record_type}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export function applyProfile(
  profile: ImportProfile,
  availableSelectors: string[],
  existingFieldNames: Set<string>,
): ProfileApplyResult {
  const selectorSet = new Set(availableSelectors)
  const appliedMapping: Record<string, MappingEntry> = {}
  const newPendingFields: PendingField[] = []
  const missedSelectors: string[] = []
  const missingFieldNames: string[] = []
  const mediaSelector = profile.mediaSelector && selectorSet.has(profile.mediaSelector)
    ? profile.mediaSelector
    : null

  if (profile.mediaSelector && !mediaSelector) missedSelectors.push(profile.mediaSelector)

  for (const [selector, entry] of Object.entries(profile.mapping)) {
    if (!selectorSet.has(selector)) {
      missedSelectors.push(selector)
      continue
    }
    appliedMapping[selector] = entry
    if (!existingFieldNames.has(entry.target)) {
      const fd = profile.field_definitions[entry.target]
      if (fd) {
        newPendingFields.push({
          csvColumn: selector,
          name: fd.name,
          field_type: fd.field_type,
          label_de: fd.label['de'] ?? fd.name,
          label_en: fd.label['en'] ?? fd.name,
          is_repeatable: fd.is_repeatable,
        })
        missingFieldNames.push(fd.name)
      }
    }
  }

  return { appliedMapping, mediaSelector, newPendingFields, missedSelectors, missingFieldNames }
}

export function applySavedMapping(
  savedMapping: Record<string, MappingEntry>,
  savedMediaSelector: string | null,
  availableSelectors: string[],
  existingFieldNames: Set<string>,
): ProfileApplyResult {
  const selectorSet = new Set(availableSelectors)
  const appliedMapping: Record<string, MappingEntry> = {}
  const newPendingFields: PendingField[] = []
  const missedSelectors: string[] = []
  const missingFieldNames: string[] = []
  const mediaSelector = savedMediaSelector && selectorSet.has(savedMediaSelector)
    ? savedMediaSelector
    : null

  if (savedMediaSelector && !mediaSelector) missedSelectors.push(savedMediaSelector)

  for (const [selector, entry] of Object.entries(savedMapping)) {
    if (!selectorSet.has(selector)) {
      missedSelectors.push(selector)
      continue
    }
    appliedMapping[selector] = entry
    if (!existingFieldNames.has(entry.target)) {
      missingFieldNames.push(entry.target)
    }
  }

  return { appliedMapping, mediaSelector, newPendingFields, missedSelectors, missingFieldNames }
}
