// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useTranslation } from 'react-i18next'
import type { ExportTargetCapability } from '../../../types'
import { HelpPopover } from '../../ui/HelpPopover'

export function MappingHelp({ target }: { target: ExportTargetCapability }) {
  const { t, i18n } = useTranslation('screenExport')
  const lang = i18n.language.startsWith('en') ? 'en' : 'de'
  return (
    <HelpPopover
      title={target.label[lang]}
      ariaLabel={t('helpAriaLabel', { target: target.label[lang] })}
      content={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>{target.help[lang]}</div>
          <div style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--fg-3)' }}>{t('xpathLabel')}:</span>
            <code style={{ fontFamily: 'monospace', background: 'var(--bg-2, #f1f5f9)', padding: '2px 5px', borderRadius: 4, color: 'var(--fg-1)' }}>
              {target.key.startsWith('mods:note') ? 'mods:note' : target.key}
            </code>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            {target.cardinality === 'many' ? t('helpCardinalityMany') : t('helpCardinalityOne')}
            {target.required ? ` · ${t('helpRequired')}` : ''}
          </div>
        </div>
      }
    />
  )
}
