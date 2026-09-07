// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { sparql, adminConfig } from '../../api/client'
import type { SavedSparqlQuery, SparqlQueryResultBinding, SparqlQueryResults, SparqlStatus } from '../../api/client'
import {
  Play,
  Bookmark,
  Sparkles,
  Download,
  Copy,
  Trash,
  Plus,
  Search,
  Check,
  AlertCircle,
  Link as LinkIcon,
  Refresh,
  X,
} from '../ui/Icons'

interface Props {
  onOpenRecord?: (recordType: string, recordId: string) => void
}

const PREFIXES = `PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
PREFIX lrmoo: <http://iflastandards.info/ns/lrm/lrmoo/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
`

const DEFAULT_QUERY = `${PREFIXES}
SELECT DISTINCT ?object ?idno ?title WHERE {
  ?object a lrmoo:F5_Item ;
          crm:P102_has_title ?title .
  OPTIONAL {
    ?object crm:P1_is_identified_by ?idNode .
    ?idNode a crm:E42_Identifier ;
            crm:P190_has_symbolic_content ?idno .
  }
}
ORDER BY ?idno
LIMIT 50
`

export function ScreenSparql({ onOpenRecord }: Props) {
  const { t } = useTranslation('screenSparql')

  // Status & Environment
  const [status, setStatus] = useState<SparqlStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [aiEnabled, setAiEnabled] = useState(false)

  // Query state
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<SparqlQueryResults | null>(null)
  const [executionTimeMs, setExecutionTimeMs] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<'table' | 'raw'>('table')
  const [copied, setCopied] = useState(false)

  // Saved queries
  const [savedQueries, setSavedQueries] = useState<SavedSparqlQuery[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [searchFilter, setSearchFilter] = useState('')
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null)
  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [saveTitle, setSaveTitle] = useState('')
  const [saveDesc, setSaveDesc] = useState('')
  const [saveTags, setSaveTags] = useState('')
  const [saveIsShared, setSaveIsShared] = useState(true)
  const [saving, setSaving] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // NL2SPARQL AI Assistant
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiGeneratedSparql, setAiGeneratedSparql] = useState<string | null>(null)
  const [aiExplanation, setAiExplanation] = useState<string | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const loadStatus = useCallback(async () => {
    setStatusLoading(true)
    try {
      const s = await sparql.status()
      setStatus(s)
    } catch {
      setStatus({
        enabled: false,
        reachable: false,
        triples_count: null,
        endpoint_url: '/sparql',
        require_auth: true,
        query_timeout: 30,
      })
    } finally {
      setStatusLoading(false)
    }
  }, [])

  const loadSavedQueries = useCallback(async () => {
    setSavedLoading(true)
    try {
      const qs = await sparql.listQueries()
      setSavedQueries(qs)
    } catch {
      // Ignored if unconfigured
    } finally {
      setSavedLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatus()
    loadSavedQueries()
    adminConfig.get().then((cfg) => setAiEnabled(!!cfg.ai_enabled)).catch(() => {})
  }, [loadStatus, loadSavedQueries])

  const handleExecute = useCallback(async () => {
    if (!query.trim() || executing) return
    setExecuting(true)
    setError(null)
    const startTime = performance.now()
    try {
      const res = await sparql.query(query)
      setResults(res)
      setExecutionTimeMs(Math.round(performance.now() - startTime))
    } catch (e) {
      setError((e as Error).message)
      setResults(null)
    } finally {
      setExecuting(false)
    }
  }, [query, executing])

  // Keyboard shortcut Ctrl/Cmd + Enter
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleExecute()
    }
    // Tab key indent
    if (e.key === 'Tab') {
      e.preventDefault()
      const ta = textareaRef.current
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const val = ta.value
      ta.value = val.substring(0, start) + '  ' + val.substring(end)
      ta.selectionStart = ta.selectionEnd = start + 2
      setQuery(ta.value)
    }
  }

  const handleInsertPrefixes = () => {
    if (query.includes('PREFIX crm:')) return
    setQuery(PREFIXES + query)
  }

  const handleTemplateSelect = (templateKey: string) => {
    switch (templateKey) {
      case 'allObjects':
        setQuery(`${PREFIXES}
SELECT DISTINCT ?object ?idno ?title WHERE {
  ?object a lrmoo:F5_Item ;
          crm:P102_has_title ?title .
  OPTIONAL {
    ?object crm:P1_is_identified_by ?idNode .
    ?idNode a crm:E42_Identifier ;
            crm:P190_has_symbolic_content ?idno .
  }
}
ORDER BY ?idno
LIMIT 50
`)
        break
      case 'personsWithWorks':
        setQuery(`${PREFIXES}
SELECT DISTINCT ?person ?personName ?object ?title WHERE {
  ?person a crm:E21_Person ;
          rdfs:label ?personName .
  OPTIONAL {
    ?object crm:P14_carried_out_by ?person ;
            crm:P102_has_title ?title .
  }
}
ORDER BY ?personName
LIMIT 50
`)
        break
      case 'placesWithCoordinates':
        setQuery(`${PREFIXES}
SELECT DISTINCT ?place ?placeName ?coord WHERE {
  ?place a crm:E53_Place ;
         rdfs:label ?placeName .
  OPTIONAL {
    ?place crm:P168_place_is_defined_by ?coord .
  }
}
ORDER BY ?placeName
LIMIT 50
`)
        break
      case 'classDistribution':
        setQuery(`${PREFIXES}
SELECT ?type (COUNT(?s) AS ?count) WHERE {
  ?s rdf:type ?type .
}
GROUP BY ?type
ORDER BY DESC(?count)
LIMIT 50
`)
        break
      case 'recentUpdates':
        setQuery(`${PREFIXES}
SELECT DISTINCT ?entity ?type ?label WHERE {
  ?entity a ?type ;
          rdfs:label ?label .
}
LIMIT 50
`)
        break
    }
  }

  const handleOpenSaveModal = () => {
    setSaveTitle('')
    setSaveDesc('')
    setSaveTags('')
    setSaveIsShared(true)
    setSaveModalOpen(true)
  }

  const handleSaveQuery = async () => {
    if (!saveTitle.trim() || !query.trim() || saving) return
    setSaving(true)
    try {
      const tags = saveTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      const created = await sparql.createQuery({
        title: saveTitle.trim(),
        description: saveDesc.trim() || null,
        query: query.trim(),
        tags,
        is_shared: saveIsShared,
      })
      setSavedQueries((prev) => [created, ...prev])
      setSelectedQueryId(created.id)
      setSaveModalOpen(false)
    } catch (e) {
      alert(`Fehler beim Speichern: ${(e as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteSavedQuery = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(t('deleteConfirm'))) return
    try {
      await sparql.deleteQuery(id)
      setSavedQueries((prev) => prev.filter((q) => q.id !== id))
      if (selectedQueryId === id) setSelectedQueryId(null)
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleLoadSavedQuery = (sq: SavedSparqlQuery) => {
    setSelectedQueryId(sq.id)
    setQuery(sq.query)
  }

  const handleAiGenerate = async () => {
    if (!aiPrompt.trim() || aiLoading) return
    setAiLoading(true)
    setAiError(null)
    setAiGeneratedSparql(null)
    setAiExplanation(null)
    try {
      const res = await sparql.nl2sparql(aiPrompt.trim())
      setAiGeneratedSparql(res.sparql)
      setAiExplanation(res.explanation ?? null)
    } catch (e) {
      setAiError((e as Error).message)
    } finally {
      setAiLoading(false)
    }
  }

  const handleApplyAiSparql = () => {
    if (aiGeneratedSparql) {
      setQuery(aiGeneratedSparql)
      setAiPanelOpen(false)
    }
  }

  const handleCopyJson = () => {
    if (!results) return
    navigator.clipboard.writeText(JSON.stringify(results, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownloadCsv = () => {
    if (!results || !results.head.vars.length) return
    const headers = results.head.vars
    const rows = results.results.bindings.map((b) =>
      headers.map((h) => {
        const val = b[h]?.value ?? ''
        // Escape quotes
        return `"${val.replace(/"/g, '""')}"`
      }).join(',')
    )
    const csvContent = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `sparql_results_${Date.now()}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadJson = () => {
    if (!results) return
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `sparql_results_${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const renderCellContent = (cell?: SparqlQueryResultBinding) => {
    if (!cell) return <span style={{ color: 'var(--fg-muted)', fontStyle: 'italic' }}>—</span>
    if (cell.type === 'uri') {
      // Check if internal URI matching /v1/{recordType}/{uuid} or http(s)://.../v1/{recordType}/{uuid}
      const match = cell.value.match(/\/v1\/(objects|entities|places|occurrences|procedures|collections)\/([0-9a-f-]{36})/i)
      if (match && onOpenRecord) {
        const pluralType = match[1]
        const id = match[2]
        const singleType = pluralType === 'objects' ? 'object'
          : pluralType === 'entities' ? 'entity'
          : pluralType === 'places' ? 'place'
          : pluralType === 'occurrences' ? 'occurrence'
          : pluralType === 'procedures' ? 'procedure'
          : 'collection'

        return (
          <button
            onClick={() => onOpenRecord(singleType, id)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              border: 'none',
              background: 'var(--bg-card)',
              color: 'var(--accent)',
              cursor: 'pointer',
              padding: '2px 6px',
              borderRadius: 4,
              fontSize: 12,
              fontFamily: 'inherit',
              textDecoration: 'none',
            }}
            title={cell.value}
          >
            <LinkIcon size={12} />
            <span style={{ textDecoration: 'underline' }}>{`${singleType}/${id.slice(0, 8)}...`}</span>
          </button>
        )
      }

      return (
        <a
          href={cell.value}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--accent)', textDecoration: 'none', wordBreak: 'break-all' }}
          title={cell.value}
        >
          {cell.value}
        </a>
      )
    }

    return (
      <div style={{ wordBreak: 'break-word' }}>
        <span>{cell.value}</span>
        {cell['xml:lang'] && (
          <span style={{ fontSize: 10, color: 'var(--fg-muted)', marginLeft: 4, padding: '1px 3px', background: 'var(--bg-card)', borderRadius: 3 }}>
            @{cell['xml:lang']}
          </span>
        )}
        {cell.datatype && (
          <span style={{ fontSize: 10, color: 'var(--fg-muted)', marginLeft: 4 }}>
            ^^&lt;{cell.datatype.split('#').pop() || cell.datatype}&gt;
          </span>
        )}
      </div>
    )
  }

  const filteredQueries = savedQueries.filter((q) => {
    if (!searchFilter.trim()) return true
    const term = searchFilter.toLowerCase()
    return (
      q.title.toLowerCase().includes(term) ||
      (q.description && q.description.toLowerCase().includes(term)) ||
      (q.tags && q.tags.some((tg) => tg.toLowerCase().includes(term)))
    )
  })

  // Zero-Clutter Check: If Oxigraph is disabled
  if (!statusLoading && status && !status.enabled) {
    return (
      <div className="screen-wrap" style={{ padding: 24 }}>
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: 24,
            maxWidth: 680,
            margin: '40px auto',
          }}
        >
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
            <AlertCircle size={24} style={{ color: 'var(--fg-muted)' }} />
            <h2 style={{ margin: 0, fontSize: 18 }}>{t('disabledTitle')}</h2>
          </div>
          <p style={{ color: 'var(--fg-muted)', lineHeight: 1.5, margin: 0 }}>
            {t('disabledDescription')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="screen-wrap" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Top Header */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg)',
          flexShrink: 0,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>{t('title')}</h1>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>{t('subtitle')}</div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {aiEnabled && (
            <button
              className="btn"
              onClick={() => setAiPanelOpen(!aiPanelOpen)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: aiPanelOpen ? 'var(--accent-subtle, rgba(59, 130, 246, 0.1))' : undefined,
                borderColor: aiPanelOpen ? 'var(--accent)' : undefined,
              }}
            >
              <Sparkles size={14} />
              <span>{t('aiAssistant')}</span>
            </button>
          )}

          <button
            className="btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: sidebarOpen ? 'var(--accent-subtle, rgba(59, 130, 246, 0.1))' : undefined,
              borderColor: sidebarOpen ? 'var(--accent)' : undefined,
            }}
            title={t('savedQueries')}
          >
            <Bookmark size={14} />
            <span>{t('savedQueries')}</span>
            {savedQueries.length > 0 && (
              <span style={{ fontSize: 11, background: 'var(--border)', padding: '1px 5px', borderRadius: 10 }}>
                {savedQueries.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Main Content: Split editor/results and saved queries drawer */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Workspace Column */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          {/* AI Assistant Banner / Slide-down */}
          {aiPanelOpen && aiEnabled && (
            <div
              style={{
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-card)',
                padding: '14px 20px',
                flexShrink: 0,
              }}
            >
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                <Sparkles size={15} style={{ color: 'var(--accent)' }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>{t('aiAssistant')}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="text"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAiGenerate()
                  }}
                  placeholder={t('aiPromptPlaceholder')}
                  style={{
                    flex: 1,
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    fontSize: 13,
                    background: 'var(--bg)',
                    color: 'var(--fg)',
                  }}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleAiGenerate}
                  disabled={aiLoading || !aiPrompt.trim()}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  {aiLoading ? <Refresh size={14} className="spin" /> : <Sparkles size={14} />}
                  <span>{aiLoading ? t('aiGenerating') : t('aiGenerate')}</span>
                </button>
              </div>

              {aiError && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger, #ef4444)' }}>
                  {aiError}
                </div>
              )}

              {aiGeneratedSparql && (
                <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
                  {aiExplanation && (
                    <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 8 }}>
                      <strong>{t('aiExplanation')}:</strong> {aiExplanation}
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono, monospace)' }}>
                      {aiGeneratedSparql.split('\n')[0]}...
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={handleApplyAiSparql}
                      style={{ fontSize: 12, padding: '4px 10px' }}
                    >
                      {t('aiApply')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Toolbar */}
          <div
            style={{
              padding: '8px 20px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
              background: 'var(--bg-card)',
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                className="btn btn-primary"
                onClick={handleExecute}
                disabled={executing || !query.trim()}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {executing ? <Refresh size={14} className="spin" /> : <Play size={14} />}
                <span>{executing ? t('running') : t('run')}</span>
                <span style={{ fontSize: 10, opacity: 0.75, marginLeft: 2 }}>({t('runShortcut')})</span>
              </button>

              <button
                className="btn"
                onClick={handleInsertPrefixes}
                style={{ fontSize: 12 }}
                title={t('insertPrefixes')}
              >
                {t('prefixes')}
              </button>

              <select
                className="btn"
                onChange={(e) => {
                  if (e.target.value) {
                    handleTemplateSelect(e.target.value)
                    e.target.value = ''
                  }
                }}
                defaultValue=""
                style={{ fontSize: 12 }}
              >
                <option value="" disabled>
                  {t('templates')}...
                </option>
                <option value="allObjects">{t('templatesList.allObjects')}</option>
                <option value="personsWithWorks">{t('templatesList.personsWithWorks')}</option>
                <option value="placesWithCoordinates">{t('templatesList.placesWithCoordinates')}</option>
                <option value="classDistribution">{t('templatesList.classDistribution')}</option>
                <option value="recentUpdates">{t('templatesList.recentUpdates')}</option>
              </select>

              <button
                className="btn"
                onClick={handleOpenSaveModal}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}
                title={t('saveQuery')}
              >
                <Bookmark size={12} />
                <span>{t('saveQuery')}</span>
              </button>
            </div>
          </div>

          {/* Editor Area */}
          <div style={{ flex: '0 0 220px', position: 'relative', borderBottom: '1px solid var(--border)' }}>
            <textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                outline: 'none',
                padding: '12px 20px',
                fontSize: 13,
                lineHeight: 1.5,
                fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                background: 'var(--bg)',
                color: 'var(--fg)',
                resize: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Results Bar */}
          <div
            style={{
              padding: '8px 20px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'var(--bg-card)',
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
              <span style={{ fontWeight: 600, color: 'var(--fg)' }}>{t('results')}</span>
              {results && (
                <>
                  <span>
                    {results.results.bindings.length} {t('rows')}
                  </span>
                  {executionTimeMs != null && (
                    <span>
                      {executionTimeMs} ms
                    </span>
                  )}
                </>
              )}
            </div>

            {results && results.results.bindings.length > 0 && (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <div style={{ display: 'inline-flex', border: '1px solid var(--border)', borderRadius: 5, overflow: 'hidden' }}>
                  <button
                    onClick={() => setViewMode('table')}
                    style={{
                      border: 'none',
                      padding: '3px 8px',
                      fontSize: 11,
                      cursor: 'pointer',
                      background: viewMode === 'table' ? 'var(--accent)' : 'var(--bg)',
                      color: viewMode === 'table' ? '#fff' : 'var(--fg)',
                    }}
                  >
                    {t('viewTable')}
                  </button>
                  <button
                    onClick={() => setViewMode('raw')}
                    style={{
                      border: 'none',
                      padding: '3px 8px',
                      fontSize: 11,
                      cursor: 'pointer',
                      background: viewMode === 'raw' ? 'var(--accent)' : 'var(--bg)',
                      color: viewMode === 'raw' ? '#fff' : 'var(--fg)',
                    }}
                  >
                    {t('viewRaw')}
                  </button>
                </div>

                <button
                  className="btn"
                  onClick={handleCopyJson}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '3px 8px' }}
                  title={t('copyJson')}
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  <span>{copied ? t('copied') : t('copyJson')}</span>
                </button>

                <button
                  className="btn"
                  onClick={handleDownloadCsv}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '3px 8px' }}
                  title={t('downloadCsv')}
                >
                  <Download size={12} />
                  <span>CSV</span>
                </button>

                <button
                  className="btn"
                  onClick={handleDownloadJson}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '3px 8px' }}
                  title={t('downloadJson')}
                >
                  <Download size={12} />
                  <span>JSON</span>
                </button>
              </div>
            )}
          </div>

          {/* Results Table / Output */}
          <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
            {error && (
              <div
                style={{
                  margin: 20,
                  padding: 16,
                  borderRadius: 6,
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid var(--danger, #ef4444)',
                  color: 'var(--danger, #ef4444)',
                  fontSize: 13,
                  fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                  whiteSpace: 'pre-wrap',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 6 }}>{t('error')}</div>
                {error}
              </div>
            )}

            {!error && !results && !executing && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                {t('noResults')}
              </div>
            )}

            {!error && results && results.results.bindings.length === 0 && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                {t('emptyBindings')}
              </div>
            )}

            {!error && results && results.results.bindings.length > 0 && viewMode === 'raw' && (
              <pre
                style={{
                  margin: 0,
                  padding: 16,
                  fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                  fontSize: 12,
                  lineHeight: 1.5,
                  overflow: 'auto',
                }}
              >
                {JSON.stringify(results, null, 2)}
              </pre>
            )}

            {!error && results && results.results.bindings.length > 0 && viewMode === 'table' && (
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 13,
                  textAlign: 'left',
                }}
              >
                <thead>
                  <tr style={{ background: 'var(--bg-card)', position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ width: 40, padding: '8px 12px', borderBottom: '1px solid var(--border)', color: 'var(--fg-muted)', fontSize: 11 }}>
                      #
                    </th>
                    {results.head.vars.map((v) => (
                      <th
                        key={v}
                        style={{
                          padding: '8px 12px',
                          borderBottom: '1px solid var(--border)',
                          fontWeight: 600,
                          fontSize: 12,
                          color: 'var(--fg)',
                          fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                        }}
                      >
                        ?{v}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.results.bindings.map((row, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.015)',
                      }}
                    >
                      <td style={{ padding: '8px 12px', color: 'var(--fg-muted)', fontSize: 11 }}>
                        {idx + 1}
                      </td>
                      {results.head.vars.map((v) => (
                        <td key={v} style={{ padding: '8px 12px', verticalAlign: 'top' }}>
                          {renderCellContent(row[v])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Saved Queries Sidebar Drawer */}
        {sidebarOpen && (
          <div
            style={{
              width: 280,
              borderLeft: '1px solid var(--border)',
              background: 'var(--bg-card)',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
            }}
          >
            <div
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600 }}>{t('savedQueries')}</div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <button
                  className="btn"
                  onClick={handleOpenSaveModal}
                  style={{ padding: '2px 6px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 2 }}
                  title={t('saveQuery')}
                >
                  <Plus size={12} />
                </button>
                <button
                  className="btn"
                  onClick={() => setSidebarOpen(false)}
                  style={{ padding: '2px 6px', fontSize: 11, display: 'inline-flex', alignItems: 'center' }}
                  title="Schließen"
                  aria-label="Schließen"
                >
                  <X size={12} />
                </button>
              </div>
            </div>

            <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                <Search size={13} style={{ position: 'absolute', left: 8, color: 'var(--fg-muted)' }} />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder={t('searchQueries')}
                  style={{
                    width: '100%',
                    border: '1px solid var(--border)',
                    borderRadius: 5,
                    padding: '5px 8px 5px 26px',
                    fontSize: 12,
                    background: 'var(--bg)',
                    color: 'var(--fg)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '6px 8px' }}>
              {savedLoading && (
                <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
                  Lade Abfragen...
                </div>
              )}

              {!savedLoading && filteredQueries.length === 0 && (
                <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
                  {t('noSavedQueries')}
                </div>
              )}

              {!savedLoading &&
                filteredQueries.map((sq) => (
                  <div
                    key={sq.id}
                    onClick={() => handleLoadSavedQuery(sq)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 6,
                      marginBottom: 4,
                      cursor: 'pointer',
                      background: selectedQueryId === sq.id ? 'var(--border)' : 'transparent',
                      border: '1px solid',
                      borderColor: selectedQueryId === sq.id ? 'var(--accent)' : 'transparent',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--fg)' }}>{sq.title}</div>
                      <button
                        onClick={(e) => handleDeleteSavedQuery(sq.id, e)}
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--fg-muted)',
                          cursor: 'pointer',
                          padding: 2,
                        }}
                        title={t('delete')}
                      >
                        <Trash size={12} />
                      </button>
                    </div>

                    {sq.description && (
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {sq.description}
                      </div>
                    )}

                    {sq.tags && sq.tags.length > 0 && (
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                        {sq.tags.map((tag) => (
                          <span
                            key={tag}
                            style={{
                              fontSize: 10,
                              background: 'var(--bg)',
                              border: '1px solid var(--border)',
                              borderRadius: 3,
                              padding: '1px 4px',
                              color: 'var(--fg-muted)',
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Save Query Modal */}
      {saveModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setSaveModalOpen(false)}
        >
          <div
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 20,
              width: 440,
              maxWidth: '90%',
              boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>{t('saveQueryTitle')}</h3>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
                {t('queryTitle')} *
              </label>
              <input
                type="text"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                placeholder={t('queryTitlePlaceholder')}
                style={{
                  width: '100%',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '7px 10px',
                  fontSize: 13,
                  background: 'var(--bg-card)',
                  color: 'var(--fg)',
                  boxSizing: 'border-box',
                }}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
                {t('queryDescription')}
              </label>
              <textarea
                value={saveDesc}
                onChange={(e) => setSaveDesc(e.target.value)}
                placeholder={t('queryDescriptionPlaceholder')}
                rows={2}
                style={{
                  width: '100%',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '7px 10px',
                  fontSize: 13,
                  background: 'var(--bg-card)',
                  color: 'var(--fg)',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
                {t('queryTags')}
              </label>
              <input
                type="text"
                value={saveTags}
                onChange={(e) => setSaveTags(e.target.value)}
                placeholder={t('queryTagsPlaceholder')}
                style={{
                  width: '100%',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '7px 10px',
                  fontSize: 13,
                  background: 'var(--bg-card)',
                  color: 'var(--fg)',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
              <input
                type="checkbox"
                id="isShared"
                checked={saveIsShared}
                onChange={(e) => setSaveIsShared(e.target.checked)}
              />
              <label htmlFor="isShared" style={{ fontSize: 13, cursor: 'pointer' }}>
                {t('isShared')}
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setSaveModalOpen(false)}>
                {t('cancel')}
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveQuery}
                disabled={saving || !saveTitle.trim()}
              >
                {saving ? t('saving') : t('save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
