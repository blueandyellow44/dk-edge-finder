import { useState } from 'react'
import { doc, updateDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { useAuth } from '../contexts/AuthContext'
import { toDecimalOdds } from '../lib/odds'

export default function BetHistory({ bets, bankroll, onBetResolved }) {
  return (
    <div className="mb-7">
      <h2 className="text-lg font-semibold mb-3">Placed Bets &mdash; All Time</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="table-th">Date</th>
              <th className="table-th">Sport</th>
              <th className="table-th">Event</th>
              <th className="table-th">Pick</th>
              <th className="table-th">Odds</th>
              <th className="table-th">Edge</th>
              <th className="table-th">Wager</th>
              <th className="table-th">Result</th>
              <th className="table-th">P/L</th>
            </tr>
          </thead>
          <tbody>
            {bets.map(bet => (
              <BetRow key={bet.id} bet={bet} bankroll={bankroll} onBetResolved={onBetResolved} />
            ))}
            {bets.length === 0 && (
              <tr>
                <td colSpan={9} className="table-td text-center text-muted py-8">No bets logged yet. Use the "Log Bet" button on any pick to get started.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <BetsSummary bets={bets} />
    </div>
  )
}

function BetRow({ bet, bankroll, onBetResolved }) {
  const { user } = useAuth()
  const [resolving, setResolving] = useState(false)

  async function handleResolve(outcome) {
    setResolving(true)
    const decOdds = bet.decimal_odds || toDecimalOdds(bet.odds)
    let pnl = 0
    if (outcome === 'win') pnl = bet.wager * (decOdds - 1)
    else if (outcome === 'loss') pnl = -bet.wager

    // Update bet document in user's bets subcollection
    await updateDoc(doc(db, 'users', user.uid, 'bets', bet.id), { outcome, pnl })

    // Update bankroll on user document
    if (bankroll) {
      const newBankroll = bankroll.current_bankroll + pnl
      await updateDoc(doc(db, 'users', user.uid), {
        'bankroll.current': Math.round(newBankroll * 100) / 100,
        'bankroll.last_updated': serverTimestamp(),
      })
    }

    setResolving(false)
    onBetResolved()
  }

  const outcomeClasses = {
    win: 'bg-dk-green/10 text-dk-green',
    loss: 'bg-dk-red/10 text-dk-red',
    push: 'bg-dk-yellow/10 text-dk-yellow',
    pending: 'bg-dk-blue/10 text-dk-blue',
  }

  const pnlDisplay = () => {
    if (bet.outcome === 'pending') return <span className="text-muted font-mono font-bold">---</span>
    if (bet.pnl > 0) return <span className="text-dk-green font-mono font-bold">+${bet.pnl.toFixed(2)}</span>
    if (bet.pnl < 0) return <span className="text-dk-red font-mono font-bold">-${Math.abs(bet.pnl).toFixed(2)}</span>
    return <span className="text-muted font-mono font-bold">$0.00</span>
  }

  return (
    <tr className="border-b border-border hover:bg-white/[0.03] transition-colors">
      <td className="table-td">{bet.date}</td>
      <td className="table-td">{bet.sport}</td>
      <td className="table-td">{bet.event}</td>
      <td className="table-td font-semibold">{bet.pick}</td>
      <td className="table-td font-mono text-sm">{bet.odds}</td>
      <td className="table-td font-bold text-dk-green">{bet.edge_pct}%</td>
      <td className="table-td font-mono text-sm">${bet.wager.toFixed(2)}</td>
      <td className="table-td">
        {bet.outcome === 'pending' ? (
          resolving ? (
            <span className="text-muted text-xs">Saving...</span>
          ) : (
            <select
              defaultValue=""
              onChange={e => { if (e.target.value) handleResolve(e.target.value) }}
              className="bg-bg border border-border rounded-lg px-2 py-1 text-xs text-primary cursor-pointer focus:outline-none focus:border-accent"
            >
              <option value="" disabled>Resolve...</option>
              <option value="win">Win</option>
              <option value="loss">Loss</option>
              <option value="push">Push</option>
            </select>
          )
        ) : (
          <span className={`inline-block px-3 py-0.5 rounded-xl text-xs font-bold uppercase ${outcomeClasses[bet.outcome]}`}>
            {bet.outcome}
          </span>
        )}
      </td>
      <td className="table-td">{pnlDisplay()}</td>
    </tr>
  )
}

function BetsSummary({ bets }) {
  let totalWagered = 0, totalPnl = 0, wins = 0, losses = 0, pushes = 0, pending = 0

  bets.forEach(bet => {
    totalWagered += bet.wager
    if (bet.outcome === 'win') { totalPnl += (bet.pnl || 0); wins++ }
    else if (bet.outcome === 'loss') { totalPnl += (bet.pnl || 0); losses++ }
    else if (bet.outcome === 'push') { pushes++ }
    else { pending++ }
  })

  const roi = totalWagered > 0 ? ((totalPnl / totalWagered) * 100).toFixed(1) : '0.0'
  const pnlColor = totalPnl > 0 ? 'text-dk-green' : totalPnl < 0 ? 'text-dk-red' : 'text-muted'
  const pnlSign = totalPnl >= 0 ? '+' : ''

  return (
    <div className="mt-3 px-4 py-3 bg-card border border-border rounded-xl text-sm text-muted flex gap-6 flex-wrap">
      <span><strong>Record:</strong> {wins}W-{losses}L-{pushes}P{pending ? ` (${pending} pending)` : ''}</span>
      <span><strong>Total Wagered:</strong> ${totalWagered.toFixed(2)}</span>
      <span><strong>Net P/L:</strong> <span className={`font-bold ${pnlColor}`}>{pnlSign}${Math.abs(totalPnl).toFixed(2)}</span></span>
      <span><strong>ROI:</strong> <span className={`font-bold ${pnlColor}`}>{roi}%</span></span>
    </div>
  )
}
