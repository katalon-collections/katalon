// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

/** One public file of a `file` field: the attachment id, name, MIME type and size in bytes. */
export interface AttachmentFile {
  id: string
  filename: string
  mime_type: string
  size?: number
}

export type AttachmentKind = 'pdf' | 'image' | 'video' | 'audio' | 'file'

/** Field values of a `file` field: a single entry or a list. Malformed entries are skipped. */
export function attachmentFiles(value: unknown): AttachmentFile[] {
  const entries = Array.isArray(value) ? value : [value]
  return entries.flatMap(entry => {
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) return []
    const { id, filename, mime_type: mimeType, size } = entry as Record<string, unknown>
    if (typeof id !== 'string' || typeof filename !== 'string' || !filename) return []
    return [{
      id,
      filename,
      mime_type: typeof mimeType === 'string' ? mimeType : '',
      size: typeof size === 'number' ? size : undefined,
    }]
  })
}

export function attachmentKind(mimeType: string): AttachmentKind {
  if (mimeType === 'application/pdf') return 'pdf'
  if (mimeType.startsWith('image/')) return 'image'
  if (mimeType.startsWith('video/')) return 'video'
  if (mimeType.startsWith('audio/')) return 'audio'
  return 'file'
}

/** Locale-aware size using SI units (kB, MB, GB) via Intl, so no unit strings are hard-coded. */
export function formatFileSize(bytes: number, locale: string): string {
  const units = ['byte', 'kilobyte', 'megabyte', 'gigabyte'] as const
  let scaled = bytes
  let index = 0
  while (scaled >= 1000 && index < units.length - 1) {
    scaled /= 1000
    index++
  }
  return new Intl.NumberFormat(locale, {
    style: 'unit',
    unit: units[index],
    maximumFractionDigits: index === 0 ? 0 : 1,
  }).format(scaled)
}
