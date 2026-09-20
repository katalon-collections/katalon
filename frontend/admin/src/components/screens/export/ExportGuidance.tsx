// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevD, ChevU, Globe, Info } from '../../ui/Icons'

const VALIDATORS = [
  {
    nameKey: 'validatorEuropeana',
    url: 'https://metis.europeana.eu/',
    formats: ['lido', 'oai_dc'],
  },
  {
    nameKey: 'validatorLoc',
    url: 'https://www.loc.gov/standards/mods/',
    formats: ['mets_mods'],
  },
  {
    nameKey: 'validatorW3cRdf',
    url: 'https://json-ld.org/playground/',
    formats: ['json_ld'],
  },
  {
    nameKey: 'validatorW3cXml',
    url: 'https://www.w3.org/2001/03/webdata/xsv',
    formats: ['lido', 'mets_mods', 'oai_dc'],
  },
]

export function ExportGuidance({ formatKey }: { formatKey: string }) {
  const { t } = useTranslation('screenExport')
  const [open, setOpen] = useState(false)

  const relevantValidators = VALIDATORS.filter(v => v.formats.includes(formatKey))
  const isLido = formatKey === 'lido'

  return (
    <div className="settings-card" style={{ marginBottom: 16, borderLeft: '4px solid var(--accent)' }}>
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          textAlign: 'left',
          color: 'inherit',
        }}
        aria-expanded={open}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Info size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>
            {t('guidanceHeadline')}
          </h3>
        </div>
        {open ? <ChevU size={15} /> : <ChevD size={15} />}
      </button>

      {open && (
        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 14, fontSize: 13, lineHeight: 1.5 }}>
          {isLido && (
            <div style={{ background: 'var(--panel-2, #f8fafc)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--fg-1)' }}>
                {t('guidanceLidoTitle')}
              </div>
              <p style={{ margin: '0 0 8px', color: 'var(--fg-2)' }}>
                {t('guidanceLidoEventCentric')}
              </p>
              <p style={{ margin: '0 0 10px', color: 'var(--fg-2)' }}>
                {t('guidanceLidoEvents')}
              </p>

              <div style={{
                background: 'var(--bg-1, #fff)',
                border: '1px solid var(--border-s)',
                borderRadius: 6,
                padding: '8px 12px',
                marginBottom: 10,
                fontSize: 12,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--fg-2)', marginBottom: 4 }}>
                  {t('guidanceLidoExampleTitle')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 10px', color: 'var(--fg-3)' }}>
                  <span style={{ fontWeight: 500 }}>•</span>
                  <span>{t('guidanceLidoExampleObject')}</span>
                  <span style={{ fontWeight: 500 }}>•</span>
                  <span>{t('guidanceLidoExampleProduction')}</span>
                  <span style={{ fontWeight: 500 }}>•</span>
                  <span>{t('guidanceLidoExampleActor')}</span>
                  <span style={{ fontWeight: 500 }}>•</span>
                  <span>{t('guidanceLidoExamplePlace')}</span>
                  <span style={{ fontWeight: 500 }}>•</span>
                  <span>{t('guidanceLidoExampleCollection')}</span>
                </div>
              </div>

              <p style={{ margin: '0 0 8px', color: 'var(--fg-2)' }}>
                {t('guidanceLidoMappingSummary')}
              </p>
              <div style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)', fontStyle: 'italic', borderLeft: '2px solid var(--border)', paddingLeft: 8 }}>
                {t('guidanceLidoCoreVsQuality')}
              </div>
            </div>
          )}

          {isLido && (
            <div style={{ background: 'var(--panel-2, #f8fafc)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--fg-1)' }}>
                {t('guidanceDdbMdsTitle')}
              </div>
              <p style={{ margin: '0 0 8px', color: 'var(--fg-2)' }}>
                {t('guidanceDdbMdsIntro')}
              </p>
              <ol style={{ margin: 0, paddingLeft: 20, color: 'var(--fg-2)' }}>
                {(['guidanceDdbMdsInstitution', 'guidanceDdbMdsTitleField', 'guidanceDdbMdsWorkType', 'guidanceDdbMdsProduction', 'guidanceDdbMdsRights', 'guidanceDdbMdsLink'] as const).map(key => (
                  <li key={key} style={{ marginBottom: 3 }}>{t(key)}</li>
                ))}
              </ol>
            </div>
          )}

          <div>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              {t('guidanceValidatorsTitle')}
            </div>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--fg-3)' }}>
              {t('guidanceValidatorsDesc')}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {(relevantValidators.length > 0 ? relevantValidators : VALIDATORS).map(v => (
                <a
                  key={v.nameKey}
                  href={v.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    color: 'var(--accent)',
                    textDecoration: 'none',
                    fontSize: 12.5,
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.textDecoration = 'underline' }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.textDecoration = 'none' }}
                >
                  <Globe size={13} style={{ flexShrink: 0 }} />
                  <span>{t(v.nameKey)}</span>
                  <span style={{ fontSize: 11, color: 'var(--fg-4)' }}>↗</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
