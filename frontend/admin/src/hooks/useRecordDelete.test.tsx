// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { objects, ConflictError } from '../api/client'
import { useRecordDelete } from './useRecordDelete'
import '../i18n'

function Harness({ onDeleted }: { onDeleted: (id: string) => void }) {
  const { requestDelete, dialogs } = useRecordDelete('object', 'Objekt', onDeleted)
  return <><button onClick={() => requestDelete('1')}>start</button>{dialogs}</>
}

describe('useRecordDelete', () => {
  it('asks again for linked records and then forces the delete', async () => {
    const remove = vi.spyOn(objects, 'delete')
      .mockRejectedValueOnce(new ConflictError('verknüpft', 1, 0))
      .mockResolvedValueOnce(undefined)
    const onDeleted = vi.fn()
    render(<Harness onDeleted={onDeleted} />)
    const confirm = () => fireEvent.click(screen.getAllByRole('button').at(-1)!)
    fireEvent.click(screen.getByText('start'))
    confirm()
    await screen.findByText(/verknüpft/)
    expect(onDeleted).not.toHaveBeenCalled()
    confirm()
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith('1'))
    expect(remove).toHaveBeenLastCalledWith('1', true)
  })
})
