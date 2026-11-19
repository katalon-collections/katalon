// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export const FIELD_TYPE_LABELS: Record<string, string> = {
  text: 'Text',
  richtext: 'Richtext',
  date: 'Datum',
  number: 'Zahl',
  boolean: 'Boolean',
  vocab: 'Vokabular (strikt)',
  vocab_free: 'Vokabular (Freitext)',
  relation: 'Relation',
  geo: 'Geodaten',
  pid: 'PID',
  url: 'URL (mit Linktitel)',
  authority: 'Normdaten (Authority)',
  file: 'Datei',
  group: 'Containerfeld (Gruppe)',
}

/** Record types that can hold file attachments (backend `AttachmentRecordType`). */
export const FILE_FIELD_TARGET_TYPES: readonly string[] = [
  'object', 'entity', 'place', 'occurrence', 'procedure', 'collection', 'storage_location',
]
