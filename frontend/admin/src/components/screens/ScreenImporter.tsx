import { useEffect, useState } from 'react'
import { RECORD_TYPES, STEPS, STEPS_XML } from './importer/types'
import { useImporterState } from './importer/useImporterState'
import { StepDryRun } from './importer/StepDryRun'
import { StepMapping } from './importer/StepMapping'
import { StepMedia } from './importer/StepMedia'
import { StepResult } from './importer/StepResult'
import { StepUpload } from './importer/StepUpload'
import { StepXmlRecordSelector } from './importer/StepXmlRecordSelector'

const IMPORTER_TABS = [
  { id: 'metadata', label: 'Metadaten' },
  { id: 'media',    label: 'Medien' },
]

function StepBar({ step, isXml }: { step: number; isXml: boolean }) {
  const steps = isXml ? STEPS_XML : STEPS
  return (
    <div className="steps">
      {steps.map((s, i) => (
        <div key={s} className={`step${i === step ? ' active' : i < step ? ' done' : ''}`}>
          <div className="num">{i < step ? '✓' : i + 1}</div>
          {s}
        </div>
      ))}
    </div>
  )
}

type Props = { initialTab?: string | null; onTabChange?: (tab: 'metadata' | 'media') => void }

export function ScreenImporter({ initialTab, onTabChange }: Props = {}) {
  const [activeTab, setActiveTab] = useState<'metadata' | 'media'>(initialTab === 'media' ? 'media' : 'metadata')
  const [focusMediaHeading, setFocusMediaHeading] = useState(false)

  const {
    state, needsReupload, dispatch, fields, availableSubtypes,
    mappedCount, ignoredCount, missingRequired, idnoMissing,
    profileWarnings,
    handleFile, handleXmlRecordXpath, handleDryRun, applyVocabCluster, handleImport,
    handleProfileLoaded, handleProfileExport,
  } = useImporterState()

  const isXml = state.sourceType === 'xml'

  useEffect(() => {
    setActiveTab(initialTab === 'media' ? 'media' : 'metadata')
    setFocusMediaHeading(false)
  }, [initialTab])

  // Step numbers differ between XML (5 steps) and CSV/Excel (4 steps)
  // XML:     0=Upload  1=Element  2=Mapping  3=DryRun  4=Import
  // CSV/Excel: 0=Upload  1=Mapping  2=DryRun  3=Import
  const mappingStep   = isXml ? 2 : 1
  const dryRunStep    = isXml ? 3 : 2
  const resultStep    = isXml ? 4 : 3

  function reset() { dispatch({ type: 'RESET' }) }

  function selectTab(tab: 'metadata' | 'media', focusHeading = false) {
    setFocusMediaHeading(focusHeading)
    setActiveTab(tab)
    onTabChange?.(tab)
  }

  return (
    <div className="scroll">
      <div className="ph">
        <div><h1>Importer</h1><div className="sub">Daten in Katalon übernehmen</div></div>
      </div>

      {/* Tabs */}
      <div className="importer-tabs" style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-soft)', padding: '0 24px' }}>
        {IMPORTER_TABS.map(t => (
          <button
            key={t.id}
            aria-pressed={activeTab === t.id}
            aria-label={`${t.label}-Import anzeigen`}
            onClick={() => selectTab(t.id as 'metadata' | 'media')}
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
        <div className="importer-content">
          {/* Record type selector */}
          <div className="importer-types" style={{ marginBottom: availableSubtypes.length > 0 ? 8 : 16 }}>
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
            <div className="importer-subtype">
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

          <StepBar step={state.step} isXml={isXml} />

          <div style={{ marginTop: 24 }}>
            {/* Step 0: Upload (all formats) */}
            {state.step === 0 && (
              <StepUpload
                uploaded={state.uploaded}
                uploading={state.uploading}
                uploadErr={state.uploadErr}
                needsReupload={needsReupload}
                onFile={handleFile}
                onProfileLoaded={handleProfileLoaded}
              />
            )}

            {/* Step 1 (XML only): Record element selector */}
            {state.step === 1 && isXml && state.xmlElementLevels && (
              <StepXmlRecordSelector
                elementLevels={state.xmlElementLevels}
                loading={state.xmlSelectorsLoading}
                onSelect={handleXmlRecordXpath}
              />
            )}

            {/* Mapping step */}
            {state.step === mappingStep && state.uploaded && (
              <StepMapping
                uploaded={state.uploaded}
                fields={fields}
                mapping={state.mapping}
                onMappingChange={m => dispatch({ type: 'MAPPING_CHANGED', payload: m })}
                recordType={state.recordType}
                mediaSelector={state.mediaSelector}
                onMediaSelectorChange={selector => dispatch({ type: 'MEDIA_SELECTOR_CHANGED', payload: selector })}
                idnoStrategy={state.idnoStrategy}
                idnoColumn={state.idnoColumn}
                onIdnoStrategyChange={(strategy, column) =>
                  dispatch({ type: 'IDNO_STRATEGY_CHANGED', payload: { strategy, column } })
                }
                pendingFields={state.pendingFields}
                onPendingFieldsChange={(pending) =>
                  dispatch({ type: 'PENDING_FIELDS_CHANGED', payload: pending })
                }
                missingRequired={missingRequired}
                idnoMissing={idnoMissing}
                mappedCount={mappedCount}
                ignoredCount={ignoredCount}
                dryRunning={state.dryRunning}
                onDryRun={handleDryRun}
                onBack={() => dispatch({ type: 'STEP_SET', payload: isXml ? 1 : 0 })}
                onProfileExport={handleProfileExport}
                profileWarnings={profileWarnings}
                xmlSelectors={isXml ? (state.xmlSelectors ?? undefined) : undefined}
              />
            )}

            {/* Dry run step */}
            {state.step === dryRunStep && state.dryResult && (
              <StepDryRun
                dryResult={state.dryResult}
                upsertStrategy={state.upsertStrategy}
                onUpsertStrategyChange={s => dispatch({ type: 'OPTIONS_CHANGED', payload: { upsertStrategy: s } })}
                autoPublish={state.autoPublish}
                onAutoPublishChange={v => dispatch({ type: 'OPTIONS_CHANGED', payload: { autoPublish: v } })}
                idnoStrategy={state.idnoStrategy}
                onImport={handleImport}
                onApplyCluster={applyVocabCluster}
                onBack={() => dispatch({ type: 'STEP_SET', payload: mappingStep })}
              />
            )}

            {/* Result step */}
            {state.step === resultStep && (
              <StepResult
                taskStatus={state.taskStatus}
                taskId={state.taskId}
                onBack={() => dispatch({ type: 'STEP_SET', payload: mappingStep })}
                onReset={reset}
                onOpenMedia={() => selectTab('media', true)}
                mediaReferencesSelected={state.mediaSelector !== null}
              />
            )}
          </div>
        </div>
      )}

      {/* ===== MEDIA TAB ===== */}
      {activeTab === 'media' && (
        <div>
          <StepMedia focusHeading={focusMediaHeading} />
        </div>
      )}
    </div>
  )
}
