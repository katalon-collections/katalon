// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import type * as React from 'react'

/**
 * JSX typing for the `@google/model-viewer` web component.
 * The package registers the custom element in `HTMLElementTagNameMap`
 * but does not ship `JSX.IntrinsicElements` for React.
 */
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        src?: string
        alt?: string
        poster?: string
        'camera-controls'?: boolean
        'auto-rotate'?: boolean
        'auto-rotate-delay'?: number
        'rotation-per-second'?: string
        'shadow-intensity'?: string
        'environment-image'?: string
        'exposure'?: string
        'tone-mapping'?: string
        'ar-modes'?: string
        ar?: boolean
        loading?: string
        reveal?: string
      }
    }
  }
}

export {}
