// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import '../../../i18n'
import { LidoDeliverySettings, lidoDeliveryConfig, lidoDeliveryState } from './LidoDeliverySettings'

describe('LidoDeliverySettings lido_rec_id_separator', () => {
  it('round-trips lido_rec_id_separator between institution_config and form state', () => {
    const state = lidoDeliveryState({ isil: 'DE-4399', lido_rec_id_separator: '/' })
    expect(state.lido_rec_id_separator).toBe('/')
    expect(lidoDeliveryConfig(state)).toEqual({ lido_rec_id_separator: '/' })

    expect(lidoDeliveryConfig({ lido_rec_id_separator: '   ' })).toEqual({})
    expect(lidoDeliveryConfig({})).toEqual({})
  })

  it('renders the separator input with warning help text and updates state', () => {
    const onChange = vi.fn()
    render(
      <LidoDeliverySettings
        value={{ lido_rec_id_separator: '_' }}
        fields={[]}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText(/Trennzeichen für lidoRecID|Separator for lidoRecID/i) as HTMLInputElement
    expect(input.value).toBe('_')
    expect(input.placeholder).toBe('--')
    expect(screen.getByText(/Permalinks/i)).toBeTruthy()

    fireEvent.change(input, { target: { value: '/' } })
    expect(onChange).toHaveBeenCalledWith({ lido_rec_id_separator: '/' })
  })
})
