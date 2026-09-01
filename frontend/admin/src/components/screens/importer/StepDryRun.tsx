// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { DryRunResult } from '../../../api/client'
import { UPSERT_STRATEGIES } from './types'

const PAGE = 50

interface Props {
  dryResult: DryRunResult
  upsertStrategy: string
  onUpsertStrategyChange: (s: string) => void
  autoPublish: boolean
  onAutoPublishChange: (v: boolean) => void
  idnoStrategy: string
  onImport: () => void
  onApplyCluster: (field: string, canonical: string, variants: string[]) => void
  onBack: () => void
}

export function StepDryRun({
  dryResult, upsertStrategy, onUpsertStrategyChange,
  autoPublish, onAutoPublishChange, idnoStrategy, onImport, onApplyCluster, onBack,
}: Props) {
  const { t } = useTranslation('screenImporter')
  const [page, setPage] = useState(0)

  // Group errors by message to avoid rendering tens of thousands of rows
  const grouped = Object.values(
    dryResult.errors.reduce<Record<string, { message: string; rows: number[]; count: number }>>((acc, e) => {
      const key = e.message
      if (!acc[key]) acc[key] = { message: key, rows: [], count: 0 }
      acc[key].count++
      if (acc[key].rows.length < 5) acc[key].rows.push(e.row ?? 0)
      return acc
    }, {})
  ).sort((a, b) => b.count - a.count)

  const totalPages = Math.ceil(grouped.length / PAGE)
  const pageItems = grouped.slice(page * PAGE, (page + 1) * PAGE)

  return (
    <>
      <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ fontWeight: 600 }}>{t('dryRun.totalLines', { count: dryResult.total })}</div>
        <div style={{ fontWeight: 600, color: '#166534' }}>{t('dryRun.valid', { count: dryResult.valid })}</div>
        {dryResult.errors.length > 0 && (
          <div style={{ fontWeight: 600, color: '#b91c1c' }}>{t('dryRun.errors', { count: dryResult.errors.length })}</div>
        )}
        {dryResult.warnings.length > 0 && (
          <div style={{ fontWeight: 600, color: '#92400e' }}>{t('dryRun.warnings', { count: dryResult.warnings.length })}</div>
        )}
      </div>

      {dryResult.warnings.length > 0 && (
        <div role="status" style={{ marginBottom: 12 }}>
          {dryResult.warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 4, padding: '6px 10px', marginBottom: 4 }}>
              {w.row ? t('dryRun.row', { row: w.row }) : ''}{w.message}
            </div>
          ))}
        </div>
      )}

      {dryResult.media_references && (
        <div className="card" style={{ marginBottom: 16 }} role="status">
          <div className="hd">{t('dryRun.mediaHeading')}</div>
          <div className="bd" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13 }}>
            <span><b>{dryResult.media_references.objects}</b> {t('dryRun.mediaObjects', { count: dryResult.media_references.objects })}</span>
            <span><b>{dryResult.media_references.files}</b> {t('dryRun.mediaFiles', { count: dryResult.media_references.files })}</span>
            <span><b>{dryResult.media_references.empty}</b> {t('dryRun.mediaEmpty', { count: dryResult.media_references.empty })}</span>
            {dryResult.media_references.conflicts.length > 0 && (
              <span style={{ color: '#b91c1c' }}>
                <b>{dryResult.media_references.conflicts.length}</b> {t('dryRun.mediaConflicts', { count: dryResult.media_references.conflicts.length })}
              </span>
            )}
          </div>
        </div>
      )}

      {grouped.length > 0 && (
        <div className="tw" style={{ marginBottom: 12 }} role="alert">
          <table className="tbl">
            <thead><tr><th>{t('dryRun.errorTableHeading')}</th><th style={{ width: 80, textAlign: 'right' }}>{t('dryRun.errorTableRows')}</th><th>{t('dryRun.errorTableSampleRows')}</th></tr></thead>
            <tbody>
              {pageItems.map((g, i) => (
                <tr key={i}>
                  <td style={{ color: '#b91c1c', fontSize: 12 }}>{g.message}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{g.count}</td>
                  <td className="mono" style={{ fontSize: 11, color: '#6b7280' }}>
                    {g.rows.filter(r => r > 0).join(', ')}{g.count > 5 ? ' …' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, fontSize: 12 }}>
              <button className="btn sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>‹</button>
              <span>{t('dryRun.errorPagination', { page: page + 1, totalPages, count: grouped.length })}</span>
              <button className="btn sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}>›</button>
            </div>
          )}
        </div>
      )}

      {dryResult.vocab_warnings && dryResult.vocab_warnings.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {dryResult.vocab_warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 12, background: w.high_cardinality ? '#fff7ed' : '#f0fdf4', border: `1px solid ${w.high_cardinality ? '#fed7aa' : '#bbf7d0'}`, borderRadius: 4, padding: '6px 10px', marginBottom: 4 }}>
              {w.high_cardinality
                ? t('dryRun.vocabHighCardinality', { label: w.label, uniqueCount: w.unique_count, newCount: w.new_count })
                : t('dryRun.vocabNewTerms', { label: w.label, uniqueCount: w.unique_count, newCount: w.new_count })
              }
            </div>
          ))}
        </div>
      )}

      {dryResult.vocab_clusters && dryResult.vocab_clusters.some(fc => fc.clusters.length > 0) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hd">{t('dryRun.spellingVariants')}</div>
          <div className="bd" style={{ display: 'grid', gap: 8 }}>
            {dryResult.vocab_clusters.flatMap(fc => fc.clusters.map((c, i) => (
              <div key={`${fc.field}-${i}`} style={{
                fontSize: 12, border: '1px solid var(--border-soft)', borderRadius: 4,
                padding: '6px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
              }}>
                <span>
                  <b>{fc.label}</b>: {c.variants.map(v => `"${v}" (${c.counts[v]})`).join(', ')} → <b>„{c.canonical}"</b>
                </span>
                <button className="btn sm pri" onClick={() => onApplyCluster(fc.field, c.canonical, c.variants)}>
                  {t('dryRun.merge')}
                </button>
              </div>
            )))}
          </div>
        </div>
      )}

      {dryResult.errors.length === 0 && (
        <div style={{ fontSize: 13, color: '#166534', marginBottom: 12 }}>
          {t('dryRun.noErrors', { count: dryResult.valid })}
        </div>
      )}

      {/* Import options */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hd">{t('dryRun.importOptions')}</div>
        <div className="bd" style={{ display: 'grid', gap: 12 }}>
          <div>
            <label className="lbl">{t('dryRun.existingRecords')}</label>
            <select className="fld" value={upsertStrategy} onChange={e => onUpsertStrategyChange(e.target.value)}>
              {UPSERT_STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" className="ck" id="auto-publish" checked={autoPublish} onChange={e => onAutoPublishChange(e.target.checked)} />
              <label htmlFor="auto-publish" style={{ fontSize: 13, cursor: 'pointer' }}>
                {t('dryRun.autoPublish')}
              </label>
            </div>
            {autoPublish && idnoStrategy === 'skip' && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#b91c1c' }}>
                {t('dryRun.autoPublishWarning')}
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn" onClick={onBack}>{t('dryRun.back')}</button>
        <button className="btn pri" onClick={onImport} disabled={dryResult.valid === 0}>
          {t('dryRun.importNow', { count: dryResult.valid })}
        </button>
      </div>
    </>
  )
}
