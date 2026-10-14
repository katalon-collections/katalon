// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { marked } from 'marked'
import DOMPurify from 'dompurify'

/** Markdown → sanitized HTML for admin-authored portal content (static pages,
 *  homepage text blocks). Allows the `<video>` embeds static pages support.
 *  `breaks` keeps single line breaks, for text blocks that were written as
 *  plain text and used to be shown with `white-space: pre-wrap`. */
export function renderMarkdown(content: string, opts?: { breaks?: boolean }): string {
  return DOMPurify.sanitize(marked.parse(content, { async: false, breaks: opts?.breaks ?? false }), {
    ADD_TAGS: ['video', 'source'],
    ADD_ATTR: ['controls', 'preload', 'loop', 'muted', 'playsinline', 'type', 'poster'],
  })
}
