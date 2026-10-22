// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmModal } from './ConfirmModal'

describe('ConfirmModal', () => {
  it('blocks duplicate confirmation and dismissal while the action is pending', async () => {
    const user = userEvent.setup()
    const pending = Promise.withResolvers<void>()
    const onConfirm = vi.fn(() => pending.promise)
    const onCancel = vi.fn()
    render(<ConfirmModal message="Delete record?" confirmLabel="Delete" cancelLabel="Cancel" onConfirm={onConfirm} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getByRole('dialog'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
    expect((screen.getByRole('button', { name: 'Delete' }) as HTMLButtonElement).disabled).toBe(true)

    await act(async () => pending.resolve())
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('dismisses on the backdrop but not on message content', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(<ConfirmModal message="Delete record?" confirmLabel="Delete" cancelLabel="Cancel" onConfirm={onConfirm} onCancel={onCancel} />)
    await user.click(screen.getByText('Delete record?'))
    expect(onCancel).not.toHaveBeenCalled()
    await user.click(screen.getByRole('dialog'))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
