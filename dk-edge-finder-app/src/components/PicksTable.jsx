import { useState } from 'react'
import { kellyBetSize } from '../lib/kelly'
import LogBetModal from './LogBetModal'

export default function PicksTable({ picks, bankroll, onBetLogged, isPublic }) {
  const [expandedRow, setExpandedRow] = useState(null)
  const [logPick, setLogPick] = useState(null)

  function toggleRow(i) {
    setExpandedRow(expandedRow === i ? null : i)
  }

  return (
    <div className="mb-7">
      <h2 className="text-lg font-semibold mb-3">Flagged Edges</h2>
      {picks.length === 0 ? (
        <div className="bg-card border border-border rounded-xl p-8 text-center text-muted text-[0.95rem]">
          No edges flagged for today. Check back tomorrow at 6 AM.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                <th className="table-th">#</th>
                <th className="table-th">Sport</th>
                <th className="table-th">Event</th>
                <th className="table-th">Market</th>
                <th className="table-th">Pick</th>
                <th className="table-th">DK Odds</th>
                <th className="table-th">Implied %</th>
                <th className="table-th">Model %</th>
                <th className="table-th">Edge %</th>
                <th className="table-th">Tier</th>
                {!isPublic && <th className="table-th">Bet Size</th>}
                {!isPublic && <th className="table-th"></th>}
              </tr>
            </thead>
            <tbody>
              {picks.map((p, i) => {
                const kelly = bankroll
                  ? kellyBetSize(p.edge_pct, p.odds, p.tier, bankroll.current_bankroll)
                  : null

                return (
                  <PickRow
                    key={p.id}
                    pick={p}
                    index={i}
                    kelly={kelly}
                    expanded={expandedRow === i}
                    onToggle={() => toggleRow(i)}
                    onLogBet={() => setLogPick(p)}
                    isPublic={isPublic}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {logPick && bankroll && (
        <LogBetModal
          pick={logPick}
          bankroll={bankroll}
          onClose={() => setLogPick(null)}
          onBetLogged={onBetLogged}
        />
      )}
    </div>
  )
}

function PickRow({ pick, index, kelly, expanded, onToggle, onLogBet, isPublic }) {
  const p = pick
  const tierClass = p.tier === 'High' ? 'tier-high' : p.tier === 'Medium' ? 'tier-medium' : 'tier-low'

  return (
    <>
      <tr className="border-b border-border hover:bg-white/[0.03] cursor-pointer transition-colors" onClick={onToggle}>
        <td className="table-td">
          <span className={`inline-block transition-transform mr-1.5 text-xs ${expanded ? 'rotate-90' : ''}`}>&#9654;</span>
          {p.rank}
        </td>
        <td className="table-td">{p.sport}</td>
        <td className="table-td">{p.event}</td>
        <td className="table-td">{p.market}</td>
        <td className="table-td font-semibold">{p.pick}</td>
        <td className="table-td font-mono text-sm">{p.odds}</td>
        <td className="table-td">{p.implied_pct}%</td>
        <td className="table-td">{p.model_pct}%</td>
        <td className="table-td font-bold text-dk-green">+{p.edge_pct}%</td>
        <td className="table-td">
          <span className={`inline-block px-2.5 py-0.5 rounded-xl text-xs font-semibold ${tierClass}`}>{p.tier}</span>
        </td>
        {!isPublic && (
          <td className="table-td font-mono text-sm">
            {kelly ? `$${kelly.betSize.toFixed(2)}` : '—'}
            {kelly?.capped && <span className="text-dk-yellow ml-1 text-xs" title="Capped at 5%">cap</span>}
          </td>
        )}
        {!isPublic && (
          <td className="table-td">
            <button
              onClick={(e) => { e.stopPropagation(); onLogBet() }}
              className="text-xs bg-accent/20 text-accent px-3 py-1 rounded-lg hover:bg-accent/30 transition-colors"
            >
              Log Bet
            </button>
          </td>
        )}
      </tr>
      {expanded && (
        <tr className="border-b border-border">
          <td colSpan={isPublic ? 10 : 12} className="px-3 py-2 pl-9 text-muted text-sm leading-relaxed bg-white/[0.02]">
            <strong>Analysis:</strong> {p.notes}<br />
            <strong>Sources:</strong> {p.sources}
          </td>
        </tr>
      )}
    </>
  )
}
