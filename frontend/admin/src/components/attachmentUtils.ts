// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export type AttachmentKind = 'pdf' | 'image' | 'video' | 'audio' | 'other'

export function attachmentKind(mimeType: string): AttachmentKind {
  if (mimeType === 'application/pdf') return 'pdf'
  if (mimeType.startsWith('image/')) return 'image'
  if (mimeType.startsWith('video/')) return 'video'
  if (mimeType.startsWith('audio/')) return 'audio'
  return 'other'
}

/** Locale-aware size using Intl unit formatting ("312 MB", "1,2 MB"). */
export function formatFileSize(bytes: number, language: string): string {
  const units = ['byte', 'kilobyte', 'megabyte', 'gigabyte'] as const
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return new Intl.NumberFormat(language, {
    style: 'unit',
    unit: units[unitIndex],
    unitDisplay: 'short',
    maximumFractionDigits: unitIndex === 0 ? 0 : 1,
  }).format(value)
}
