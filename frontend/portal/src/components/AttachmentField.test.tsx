// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PortalFieldDefinition } from '../api/client'
import { setLocale } from '../i18n'
import { AttachmentList } from './AttachmentField'

vi.mock('../hooks/usePortalConfig', () => ({ usePortalConfig: () => ({ facet_kinds: {} }) }))
vi.mock('../hooks/useRelationTypeLabels', () => ({ useRelationTypeLabels: () => (code: string) => code }))

const { DetailPageLayout } = await import('./DetailPageLayout')

// jsdom does not implement the native dialog methods; mirror their open state.
beforeAll(() => {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '')
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.removeAttribute('open')
      this.dispatchEvent(new Event('close'))
    }
  }
})

const files = [
  { id: 'f1', filename: 'Leihvertrag.pdf', mime_type: 'application/pdf', size: 471_000 },
  { id: 'f2', filename: 'premiere.mp4', mime_type: 'video/mp4', size: 174_000_000 },
  { id: 'f3', filename: 'foto.jpg', mime_type: 'image/jpeg', size: 2_048 },
]

function def(id: string, name: string, field_type: string, extra: Partial<PortalFieldDefinition> = {}): PortalFieldDefinition {
  return {
    id, name, field_type, label: { de: name, en: name }, is_repeatable: false, is_searchable: false, is_facet: false,
    parent_id: null, settings: {}, show_in_detail: true, detail_slot: 'sidebar', detail_role: 'none', ...extra,
  }
}

describe('file field rendering', () => {
  beforeEach(() => setLocale('de'))
  afterEach(cleanup)

  it('renders top-level files with a download link named after the file', () => {
    render(
      <MemoryRouter>
        <DetailPageLayout
          fieldDefs={[def('a', 'Vertrag', 'file', { detail_slot: 'main' })]}
          metadata={{ Vertrag: files }}
          locale="de"
          recordType="procedure"
          sidebarPosition="right"
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('Leihvertrag.pdf')).toBeTruthy()
    expect(screen.getByText('premiere.mp4')).toBeTruthy()
    const download = screen.getByRole('link', { name: 'Leihvertrag.pdf herunterladen' })
    expect(download.getAttribute('href')).toBe('/portal/v1/attachments/f1/file')
    expect(download.hasAttribute('download')).toBe(true)
    expect(download.getAttribute('title')).toBe('Herunterladen')
  })

  it('renders file sub-fields inside their group entry, never the raw id', () => {
    const fieldDefs = [
      def('g', 'Fan-Content', 'group'),
      def('t', 'Titel', 'text', { parent_id: 'g' }),
      def('d', 'Datei', 'file', { parent_id: 'g' }),
    ]
    const { container } = render(
      <MemoryRouter>
        <DetailPageLayout
          fieldDefs={fieldDefs}
          metadata={{ 'Fan-Content': [{ Titel: 'Mitschnitt', Datei: files[1] }] }}
          locale="de"
          recordType="occurrence"
          sidebarPosition="right"
        />
      </MemoryRouter>,
    )
    const entry = container.querySelector('.group-entry')
    expect(entry?.textContent).toContain('premiere.mp4')
    expect(entry?.textContent).not.toContain('f2')
    expect(screen.getByRole('link', { name: 'premiere.mp4 herunterladen' })).toBeTruthy()
  })

  it('opens the lightbox on click, navigates within the list and closes back to the trigger', () => {
    const { container } = render(<AttachmentList files={files} />)
    const dialog = container.querySelector('dialog') as HTMLDialogElement
    expect(dialog.open).toBe(false)

    const trigger = screen.getByRole('button', { name: /Leihvertrag\.pdf/ })
    fireEvent.click(trigger)
    expect(dialog.open).toBe(true)
    expect(dialog.querySelector('iframe')?.getAttribute('title')).toBe('Leihvertrag.pdf')
    expect(dialog.textContent).toContain('1 von 3')

    fireEvent.keyDown(dialog, { key: 'ArrowRight' })
    expect(dialog.textContent).toContain('2 von 3')
    expect(dialog.querySelector('video')?.getAttribute('src')).toBe('/portal/v1/attachments/f2/file')

    fireEvent.keyDown(dialog, { key: 'ArrowLeft' })
    fireEvent.keyDown(dialog, { key: 'ArrowLeft' })
    expect(dialog.textContent).toContain('1 von 3')

    fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))
    expect(dialog.open).toBe(false)
    expect(document.activeElement).toBe(trigger)
  })

  it('shows the image in the lightbox and an open-in-new-tab link', () => {
    const { container } = render(<AttachmentList files={files} />)
    fireEvent.click(screen.getByRole('button', { name: /foto\.jpg/ }))
    const dialog = container.querySelector('dialog') as HTMLDialogElement
    expect(dialog.querySelector('img')?.getAttribute('alt')).toBe('foto.jpg')
    const external = screen.getByRole('link', { name: 'In neuem Tab öffnen' })
    expect(external.getAttribute('target')).toBe('_blank')
    expect(external.getAttribute('rel')).toContain('noopener')
  })
})
