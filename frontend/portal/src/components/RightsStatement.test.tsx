// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { MediaFile } from '../api/client'
import { RightsStatement } from './MediaViewer'

const base: MediaFile = {
  id: 'm1', filename: 'a.jpg', mime_type: 'image/jpeg', category: 'image',
  status: 'ready', is_primary: true, created_at: '2026-10-01T00:00:00',
}

describe('RightsStatement', () => {
  afterEach(cleanup)

  it('shows the credit line next to license and rights holder', () => {
    render(
      <RightsStatement
        label="Rechteangaben"
        media={{
          ...base,
          license_uri: 'http://creativecommons.org/licenses/by-nc/4.0/',
          rights_holder: { name: 'Renate Wachnitz' },
          credit_line: 'Veröffentlichung genehmigt von Renate Wachnitz.',
        }}
      />,
    )
    expect(screen.getByText('Veröffentlichung genehmigt von Renate Wachnitz.')).toBeTruthy()
  })

  it('renders for a credit line alone', () => {
    render(<RightsStatement label="Rechteangaben" media={{ ...base, credit_line: 'Nur mit Genehmigung.' }} />)
    expect(screen.getByText('Nur mit Genehmigung.')).toBeTruthy()
  })

  it('renders nothing without any rights information', () => {
    const { container } = render(<RightsStatement label="Rechteangaben" media={base} />)
    expect(container.innerHTML).toBe('')
  })
})
