import type { FieldDefinition } from '../../types'
import { RECORD_TYPES, STEPS } from './importer/types'
import { useImporterState } from './importer/useImporterState'
import { StepDryRun } from './importer/StepDryRun'
import { StepMapping } from './importer/StepMapping'
import { StepMedia } from './importer/StepMedia'
import { StepResult } from './importer/StepResult'
import { StepUpload } from './importer/StepUpload'
import { useState } from 'react'

const IMPORTER_TABS = [
  { id: 'metadata', label: 'Metadaten' },
  { id: 'media',    label: 'Medien' },
]

function StepBar({ step }: { step: number }) {
  return (
    <div className="steps">
      {STEPS.map((s, i) => (
        <div key={s} className={`step${i === step ? ' active' : i < step ? ' done' : ''}`}>
          <div className="num">{i < step ? '✓' : i + 1}</div>
          {s}
        </div>
      ))}
    </div>
  )
}

export function ScreenImporter() {
  const [activeTab, setActiveTab] = useState<'metadata' | 'media'>('metadata')

  const {
    state, dispatch, fields, availableSubtypes,
    mappedCount, ignoredCount, missingRequired, idnoMissing,
    handleFile, handleDryRun, handleImport,
  } = useImporterState()

  function reset() {
    dispatch({ type: 'RESET' })
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Importer</h1><div className="sub">Daten in Katalon übernehmen</div></div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-soft)', padding: '0 24px' }}>
        {IMPORTER_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as 'metadata' | 'media')}
            style={{
              padding: '10px 20px', fontSize: 14, fontWeight: 500, background: 'none', border: 'none',
              borderBottom: activeTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              color: activeTab === t.id ? 'var(--fg-1)' : 'var(--fg-3)',
              cursor: 'pointer', marginBottom: -1,
            }}
          >{t.label}</button>
        ))}
      </div>

      {/* ===== METADATA TAB ===== */}
      {activeTab === 'metadata' && (
        <div style={{ padding: '24px' }}>
          {/* Record type selector */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: availableSubtypes.length > 0 ? 8 : 16 }}>
            <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Typ:</span>
            {RECORD_TYPES.map(t => (
              <button
                key={t.id}
                className={`btn sm${state.recordType === t.id ? ' pri' : ' gh'}`}
                onClick={() => dispatch({ type: 'SET_RECORD_TYPE', payload: t.id })}
              >{t.label}</button>
            ))}
          </div>

          {/* Subtype selector */}
          {availableSubtypes.length > 0 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
              <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Subtyp:</span>
              <select
                className="fld" style={{ height: 28, fontSize: 12, width: 220 }}
                value={state.subtype ?? ''}
                onChange={e => dispatch({ type: 'SET_SUBTYPE', payload: e.target.value || null })}
              >
                <option value="">— kein Subtyp —</option>
                {availableSubtypes.map(s => (
                  <option key={s.id} value={s.name}>{s.label?.de ?? s.label?.en ?? s.name}</option>
                ))}
              </select>
            </div>
          )}

          <StepBar step={state.step} />

          <div style={{ marginTop: 24 }}>
            {state.step === 0 && (
              <StepUpload
                uploaded={state.uploaded}
                uploading={state.uploading}
                uploadErr={state.uploadErr}
                onFile={handleFile}
              />
            )}

            {state.step === 1 && state.uploaded && (
              <StepMapping
                uploaded={state.uploaded}
                fields={fields}
                mapping={state.mapping}
                onMappingChange={m => dispatch({ type: 'MAPPING_CHANGED', payload: m })}
                recordType={state.recordType}
                idnoStrategy={state.idnoStrategy}
                idnoColumn={state.idnoColumn}
                onIdnoStrategyChange={(strategy, column) =>
                  dispatch({ type: 'IDNO_STRATEGY_CHANGED', payload: { strategy, column } })
                }
                pendingFields={state.pendingFields}
                onPendingFieldsChange={(pending, _withVirtual) =>
                  dispatch({ type: 'PENDING_FIELDS_CHANGED', payload: pending })
                }
                missingRequired={missingRequired}
                idnoMissing={idnoMissing}
                mappedCount={mappedCount}
                ignoredCount={ignoredCount}
                dryRunning={state.dryRunning}
                onDryRun={handleDryRun}
                onBack={reset}
              />
            )}

            {state.step === 2 && state.dryResult && (
              <StepDryRun
                dryResult={state.dryResult}
                upsertStrategy={state.upsertStrategy}
                onUpsertStrategyChange={s => dispatch({ type: 'OPTIONS_CHANGED', payload: { upsertStrategy: s } })}
                autoPublish={state.autoPublish}
                onAutoPublishChange={v => dispatch({ type: 'OPTIONS_CHANGED', payload: { autoPublish: v } })}
                idnoStrategy={state.idnoStrategy}
                onImport={handleImport}
                onBack={() => dispatch({ type: 'STEP_SET', payload: 1 })}
              />
            )}

            {state.step === 3 && (
              <StepResult
                taskStatus={state.taskStatus}
                taskId={state.taskId}
                onBack={() => dispatch({ type: 'STEP_SET', payload: 1 })}
                onReset={reset}
              />
            )}
          </div>
        </div>
      )}

      {/* ===== MEDIA TAB ===== */}
      {activeTab === 'media' && <StepMedia />}
    </div>
  )
}
