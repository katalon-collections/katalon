// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import '../../../i18n'
import { SourcePicker } from './SourcePicker'

const placeSettingsSchema = {
  properties: {
    include_ancestors: {
      type: 'boolean',
      title: { de: 'Ortspfad ausgeben', en: 'Output place path' },
      description: {
        de: 'Gibt den vollständigen Pfad aus.',
        en: 'Outputs the full path.',
      },
    },
    path_separator: {
      type: 'string',
      title: { de: 'Pfad-Trennzeichen', en: 'Path separator' },
      description: { de: 'Trennzeichen', en: 'Separator' },
      placeholder: ' > ',
      visible_when: 'include_ancestors',
    },
  },
  supports_via: true,
}

describe('SourcePicker boolean and conditional place path settings', () => {
  it('hides path_separator when include_ancestors is off and toggles include_ancestors', () => {
    const onChange = vi.fn()
    render(
      <SourcePicker
        allowedKinds={['relation']}
        fields={[]}
        acceptedFieldTypes={[]}
        settingsSchema={placeSettingsSchema}
        value={{ source_kind: 'relation', source_config: { relation_type: 'fundort' }, settings: {} }}
        onChange={onChange}
      />,
    )

    const checkbox = screen.getByLabelText(/Ortspfad ausgeben|Output place path/i) as HTMLInputElement
    expect(checkbox.checked).toBe(false)
    expect(screen.queryByLabelText(/Pfad-Trennzeichen|Path separator/i)).toBeNull()

    fireEvent.click(checkbox)
    expect(onChange).toHaveBeenCalledWith({
      source_kind: 'relation',
      source_config: { relation_type: 'fundort' },
      settings: { include_ancestors: true },
    })
  })

  it('shows path_separator when include_ancestors is on and preserves whitespace in separator', () => {
    const onChange = vi.fn()
    render(
      <SourcePicker
        allowedKinds={['relation']}
        fields={[]}
        acceptedFieldTypes={[]}
        settingsSchema={placeSettingsSchema}
        value={{
          source_kind: 'relation',
          source_config: { relation_type: 'fundort' },
          settings: { include_ancestors: true },
        }}
        onChange={onChange}
      />,
    )

    const input = screen.getByLabelText(/Pfad-Trennzeichen|Path separator/i) as HTMLInputElement
    expect(input.placeholder).toBe(' > ')

    fireEvent.change(input, { target: { value: ' / ' } })
    fireEvent.blur(input)
    expect(onChange).toHaveBeenCalledWith({
      source_kind: 'relation',
      source_config: { relation_type: 'fundort' },
      settings: { include_ancestors: true, path_separator: ' / ' },
    })
  })
})
