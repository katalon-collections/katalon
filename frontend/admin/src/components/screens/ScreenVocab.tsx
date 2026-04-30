import { useState } from 'react'
import { MOCK_VOCABS, MOCK_TERMS } from '../../api/mock-data'
import { ChevD, ChevR, Edit, Plus, Tag, Trash } from '../ui/Icons'

export function ScreenVocab() {
  const [activeVocab, setActiveVocab] = useState(MOCK_VOCABS[0].id)
  const [expanded, setExpanded] = useState<Set<string>>(new Set([MOCK_VOCABS[0].id]))

  const vocab = MOCK_VOCABS.find(v => v.id === activeVocab)
  const terms = MOCK_TERMS.filter(t => t.vocabulary_id === activeVocab)

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="ph">
        <div><h1>Vokabular</h1><div className="sub">Kontrollierte Vokabulare und Terme</div></div>
        <div className="right">
          <button className="btn"><Plus size={13} /> Neues Vokabular</button>
        </div>
      </div>

      <div className="vocab-grid" style={{ flex: 1, minHeight: 0 }}>
        {/* Left: vocab tree */}
        <div className="vocab-tree">
          {MOCK_VOCABS.map(v => (
            <div key={v.id}>
              <div className={`tree-it${activeVocab === v.id ? ' active' : ''}`} onClick={() => setActiveVocab(v.id)}>
                <span className="caret" onClick={e => { e.stopPropagation(); toggleExpand(v.id) }}>
                  {v.is_hierarchical ? (expanded.has(v.id) ? <ChevD size={12} /> : <ChevR size={12} />) : null}
                </span>
                <Tag size={13} className="ic" />
                <span style={{ flex: 1 }}>{v.name}</span>
                <span className="ct">{MOCK_TERMS.filter(t => t.vocabulary_id === v.id).length}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Right: term list */}
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
                  <button className="btn pri"><Plus size={13} /> Neuer Term</button>
                </div>
              </div>

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
                    {terms.length === 0 && (
                      <tr><td colSpan={4} className="empty">Keine Terme.</td></tr>
                    )}
                    {terms.map(t => (
                      <tr key={t.id}>
                        <td className="mono" style={{ maxWidth: 180 }}>{t.term}</td>
                        <td style={{ maxWidth: 220 }}>{t.label.de ?? '—'}</td>
                        <td style={{ color: 'var(--fg-3)', maxWidth: 160 }}>{t.parent_id ?? '—'}</td>
                        <td className="col-act">
                          <div className="row-actions">
                            <button className="btn sm ico gh"><Edit size={12} /></button>
                            <button className="btn sm ico gh dn"><Trash size={12} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
