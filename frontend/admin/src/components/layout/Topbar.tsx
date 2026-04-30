import { Bell, Help, Search } from '../ui/Icons'

interface Props {
  crumbs: string[]
}

export function Topbar({ crumbs }: Props) {
  return (
    <div className="tb">
      <div className="cr">
        {crumbs.map((c, i) =>
          i === crumbs.length - 1 ? (
            <b key={i}>{c}</b>
          ) : (
            <span key={i}>{c}<span className="sep"> / </span></span>
          )
        )}
      </div>
      <div className="sp" />
      <div className="gs">
        <Search size={14} />
        <input placeholder="Global suchen — Objekte, Entitäten, Vokabeln…" />
        <span className="kbd">⌘K</span>
      </div>
      <button className="ib" title="Hilfe"><Help size={15} /></button>
      <button className="ib" title="Benachrichtigungen"><Bell size={15} /></button>
    </div>
  )
}
