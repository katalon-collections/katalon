import { useState, useEffect, useCallback } from 'react'
import { vocabularies } from '../../api/client'
import type { Vocabulary, VocabularyTerm } from '../../types'
import { ChevD, Edit, Plus, Tag, Trash, X } from '../ui/Icons'

export function ScreenVocab() {
  const [vocabs, setVocabs] = useState<Vocabulary[]>([])
  const [terms, setTerms] = useState<VocabularyTerm[]>([])
  const [activeVocab, setActiveVocab] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [termsLoading, setTermsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // new vocab form
  const [showNewVocab, setShowNewVocab] = useState(false)
  const [newVocabName, setNewVocabName] = useState('')
  const [newVocabHierarchical, setNewVocabHierarchical] = useState(false)
  const [savingVocab, setSavingVocab] = useState(false)

  // new term form
  const [showNewTerm, setShowNewTerm] = useState(false)
  const [newTermTerm, setNewTermTerm] = useState('')
  const [newTermLabelDe, setNewTermLabelDe] = useState('')
  const [savingTerm, setSavingTerm] = useState(false)

  // edit term inline
  const [editTermId, setEditTermId] = useState<string | null>(null)
  const [editTermTerm, setEditTermTerm] = useState('')
  const [editTermLabelDe, setEditTermLabelDe] = useState('')
  const [savingEditTerm, setSavingEditTerm] = useState(false)

  const loadVocabs = useCallback(() => {
    setLoading(true)
    vocabularies.list()
      .then(data => {
        setVocabs(data)
        if (data.length > 0 && !activeVocab) {
          setActiveVocab(data[0].id)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeVocab])

  useEffect(() => { loadVocabs() }, [])

  const loadTerms = useCallback(() => {
    if (!activeVocab) return
    setTermsLoading(true)
    vocabularies.listTerms(activeVocab)
      .then(setTerms)
      .catch(console.error)
      .finally(() => setTermsLoading(false))
  }, [activeVocab])

  useEffect(() => { loadTerms() }, [loadTerms])

  async function createVocab() {
    if (!newVocabName.trim()) return
    setSavingVocab(true)
    try {
      const v = await vocabularies.create({ name: newVocabName.trim(), is_hierarchical: newVocabHierarchical })
      setVocabs(prev => [...prev, v])
      setActiveVocab(v.id)
      setNewVocabName('')
      setNewVocabHierarchical(false)
      setShowNewVocab(false)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingVocab(false)
    }
  }

  async function createTerm() {
    if (!activeVocab || !newTermTerm.trim()) return
    setSavingTerm(true)
    try {
      await vocabularies.createTerm(activeVocab, {
        vocabulary_id: activeVocab,
        term: newTermTerm.trim(),
        label: { de: newTermLabelDe.trim() },
        parent_id: null,
      })
      setNewTermTerm('')
      setNewTermLabelDe('')
      setShowNewTerm(false)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingTerm(false)
    }
  }

  function startEditTerm(t: VocabularyTerm) {
    setEditTermId(t.id)
    setEditTermTerm(t.term)
    setEditTermLabelDe(t.label.de ?? '')
  }

  async function saveEditTerm(t: VocabularyTerm) {
    setSavingEditTerm(true)
    try {
      await vocabularies.updateTerm(t.id, {
        vocabulary_id: activeVocab!,
        term: editTermTerm.trim(),
        label: { de: editTermLabelDe.trim() },
        parent_id: t.parent_id,
      })
      setEditTermId(null)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setSavingEditTerm(false)
    }
  }

  async function deleteTerm(id: string) {
    if (!window.confirm('Term wirklich löschen?')) return
    try {
      await vocabularies.deleteTerm(id)
      loadTerms()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  const vocab = vocabs.find(v => v.id === activeVocab)

  if (loading) {
    return (
      <div className="scroll">
        <div className="empty" style={{ paddingTop: 80 }}>Lade…</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Vokabular</h1><div className="sub">Kontrollierte Vokabulare und Terme</div></div>
        <div className="right">
          <button className="btn" onClick={() => setShowNewVocab(v => !v)}><Plus size={13} /> Neues Vokabular</button>
        </div>
      </div>

      {error && <div style={{ padding: '8px 24px', color: '#b91c1c', fontSize: 13 }}>{error}</div>}

      {showNewVocab && (
        <div className="card" style={{ margin: '0 24px 12px', flexShrink: 0 }}>
          <div className="bd">
            <div className="fg-2">
              <div className="field">
                <div className="lbl">Name</div>
                <input className="fld" value={newVocabName} onChange={e => setNewVocabName(e.target.value)} placeholder="Vokabular-Name" autoFocus />
              </div>
              <div className="field" style={{ paddingTop: 20 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" className="ck" checked={newVocabHierarchical} onChange={e => setNewVocabHierarchical(e.target.checked)} />
                  <span style={{ fontSize: 13 }}>Hierarchisch</span>
                </label>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn pri" onClick={createVocab} disabled={savingVocab}>Anlegen</button>
              <button className="btn gh" onClick={() => setShowNewVocab(false)}><X size={12} /></button>
            </div>
          </div>
        </div>
      )}

      <div className="vocab-grid" style={{ flex: 1, minHeight: 0 }}>
        <div className="vocab-tree">
          {vocabs.map(v => (
            <div key={v.id}>
              <div className={`tree-it${activeVocab === v.id ? ' active' : ''}`} onClick={() => setActiveVocab(v.id)}>
                <span className="caret">
                  {v.is_hierarchical ? <ChevD size={12} /> : null}
                </span>
                <Tag size={13} className="ic" />
                <span style={{ flex: 1 }}>{v.name}</span>
                {activeVocab === v.id && !termsLoading && <span className="ct">{terms.length}</span>}
              </div>
            </div>
          ))}
          {vocabs.length === 0 && <div className="empty" style={{ padding: 12, fontSize: 12 }}>Keine Vokabulare.</div>}
        </div>

        <div style={{ overflow: 'auto', padding: '18px 24px' }}>
          {vocab && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{vocab.name}</div>
                  <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>
                    {terms.length} Terme · {vocab.is_hierarchical ? 'Hierarchisch' : 'Flach'}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                  <button className="btn pri" onClick={() => setShowNewTerm(v => !v)}><Plus size={13} /> Neuer Term</button>
                </div>
              </div>

              {showNewTerm && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <div className="bd">
                    <div className="fg-2">
                      <div className="field">
                        <div className="lbl">Term (intern)</div>
                        <input className="fld mono" value={newTermTerm} onChange={e => setNewTermTerm(e.target.value)} placeholder="z.B. silbergelatine" autoFocus />
                      </div>
                      <div className="field">
                        <div className="lbl">Label DE</div>
                        <input className="fld" value={newTermLabelDe} onChange={e => setNewTermLabelDe(e.target.value)} placeholder="Anzeigetext" />
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button className="btn pri" onClick={createTerm} disabled={savingTerm}>Anlegen</button>
                      <button className="btn gh" onClick={() => setShowNewTerm(false)}><X size={12} /></button>
                    </div>
                  </div>
                </div>
              )}

              <div className="tw">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Term</th>
                      <th>Label DE</th>
                      <th>Übergeordnet</th>
                      <th className="col-act" />
                    </tr>
                  </thead>
                  <tbody>
                    {termsLoading && <tr><td colSpan={4} className="empty">Lade…</td></tr>}
                    {!termsLoading && terms.length === 0 && (
                      <tr><td colSpan={4} className="empty">Keine Terme.</td></tr>
                    )}
                    {!termsLoading && terms.map(t => (
                      <tr key={t.id}>
                        {editTermId === t.id ? (
                          <>
                            <td><input className="fld mono" value={editTermTerm} onChange={e => setEditTermTerm(e.target.value)} style={{ maxWidth: 160 }} /></td>
                            <td><input className="fld" value={editTermLabelDe} onChange={e => setEditTermLabelDe(e.target.value)} style={{ maxWidth: 200 }} /></td>
                            <td style={{ color: 'var(--fg-3)' }}>{t.parent_id ?? '—'}</td>
                            <td className="col-act">
                              <div className="row-actions">
                                <button className="btn sm pri" onClick={() => saveEditTerm(t)} disabled={savingEditTerm}>OK</button>
                                <button className="btn sm gh" onClick={() => setEditTermId(null)}><X size={12} /></button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="mono" style={{ maxWidth: 180 }}>{t.term}</td>
                            <td style={{ maxWidth: 220 }}>{t.label.de ?? '—'}</td>
                            <td style={{ color: 'var(--fg-3)', maxWidth: 160 }}>{t.parent_id ?? '—'}</td>
                            <td className="col-act">
                              <div className="row-actions">
                                <button className="btn sm ico gh" onClick={() => startEditTerm(t)}><Edit size={12} /></button>
                                <button className="btn sm ico gh dn" onClick={() => deleteTerm(t.id)}><Trash size={12} /></button>
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {!vocab && vocabs.length > 0 && (
            <div className="empty">Vokabular auswählen.</div>
          )}
        </div>
      </div>
    </div>
  )
}
