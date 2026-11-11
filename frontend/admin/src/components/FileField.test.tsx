// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import '../i18n'
import { attachments, HttpStatusError, type AttachmentRef } from '../api/client'
import { FileField } from './FileField'

vi.mock('../api/client', async importOriginal => ({
  ...await importOriginal<typeof import('../api/client')>(),
  attachments: { upload: vi.fn(), link: vi.fn(), fileBlob: vi.fn(), limits: vi.fn() },
}))

const pdf: AttachmentRef = { id: 'a1', filename: 'Leihvertrag.pdf', mime_type: 'application/pdf', size: 482113 }
const video: AttachmentRef = { id: 'a2', filename: 'premiere.mp4', mime_type: 'video/mp4', size: 182000000 }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(attachments.limits).mockResolvedValue({ max_upload_mb: 50 })
})

describe('FileField', () => {
  it('shows the configured upload limit in the hint', async () => {
    render(<FileField recordType="object" recordId="rec-1" repeatable={false} value={undefined} onChange={vi.fn()} />)
    expect(await screen.findByText('PDF, Bild, Audio, Video · max. 50 MB')).toBeTruthy()
  })

  it('rejects a file above the configured limit before uploading', async () => {
    const big = new File(['x'], 'gross.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 51 * 1024 * 1024 })
    const { container } = render(<FileField recordType="object" recordId="rec-1" repeatable={false} value={undefined} onChange={vi.fn()} />)
    await screen.findByText('PDF, Bild, Audio, Video · max. 50 MB')
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [big] } })

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('gross.pdf: Datei zu groß (51 MB, max. 50 MB)')
    expect(attachments.upload).not.toHaveBeenCalled()
  })

  it('omits the number and skips the pre-check while the limit is unknown', async () => {
    // Fresh module instances so the cached limit from the tests above does not apply.
    vi.resetModules()
    await import('../i18n')
    const client = await import('../api/client')
    vi.mocked(client.attachments.limits).mockRejectedValue(new Error('offline'))
    vi.mocked(client.attachments.upload).mockResolvedValue(pdf)
    const { FileField: UnknownLimitField } = await import('./FileField')

    const { container } = render(
      <UnknownLimitField recordType="object" recordId="rec-1" repeatable={false} value={undefined} onChange={vi.fn()} />,
    )
    await waitFor(() => expect(client.attachments.limits).toHaveBeenCalled())
    expect(screen.getByText('PDF, Bild, Audio, Video')).toBeTruthy()

    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['%PDF'], 'klein.pdf', { type: 'application/pdf' })] } })
    await waitFor(() => expect(client.attachments.upload).toHaveBeenCalledTimes(1))
  })

  it('asks for a saved record before uploading', () => {
    render(<FileField recordType="object" recordId={null} repeatable={false} value={undefined} onChange={vi.fn()} />)
    expect(screen.getByText('Zum Hochladen von Dateien den Datensatz zuerst speichern.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Datei auswählen' })).toBeNull()
  })

  it('renders file rows with icon buttons labelled for view and remove', () => {
    render(<FileField recordType="object" recordId="rec-1" repeatable value={[pdf, video]} onChange={vi.fn()} />)
    expect(screen.getByText('Leihvertrag.pdf')).toBeTruthy()
    expect(screen.getByText('premiere.mp4')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Ansehen' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Entfernen' })).toHaveLength(2)
  })

  it('removes only the chosen file from the value without calling the server', () => {
    const onChange = vi.fn()
    render(<FileField recordType="object" recordId="rec-1" repeatable value={[pdf, video]} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Entfernen' })[0])
    expect(onChange).toHaveBeenCalledWith([video])
    expect(attachments.upload).not.toHaveBeenCalled()
  })

  it('shows the backend type error as an alert', async () => {
    vi.mocked(attachments.upload).mockRejectedValue(new HttpStatusError('Unsupported', 415))
    const { container } = render(<FileField recordType="object" recordId="rec-1" repeatable={false} value={undefined} onChange={vi.fn()} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['<html>'], 'notizen.html', { type: 'text/html' })] } })

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('notizen.html: Dateityp nicht erlaubt')
    expect(within(alert).getByRole('button', { name: 'Meldung schließen' })).toBeTruthy()
    await waitFor(() => expect(attachments.upload).toHaveBeenCalledTimes(1))
  })
})
