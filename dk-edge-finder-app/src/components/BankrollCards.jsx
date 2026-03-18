import { MAX_DAILY_PCT } from '../lib/kelly'

export default function BankrollCards({ bankroll, stats, todayWagers, pendingBets }) {
  if (!bankroll) return null

  const profit = bankroll.current_bankroll - bankroll.starting_bankroll
  const profitSign = profit >= 0 ? '+' : ''

  const totalGames = stats.wins + stats.losses + stats.pushes
  const winRate = totalGames > 0 ? ((stats.wins / totalGames) * 100).toFixed(0) : 0
  const record = `${stats.wins}-${stats.losses}-${stats.pushes}`

  const todayTotal = todayWagers.reduce((s, w) => s + w, 0)
  const todayPct = bankroll.current_bankroll > 0
    ? ((todayTotal / bankroll.current_bankroll) * 100).toFixed(1)
    : '0.0'
  const overLimit = parseFloat(todayPct) > MAX_DAILY_PCT * 100

  const drawdownPct = bankroll.starting_bankroll > 0
    ? ((bankroll.starting_bankroll - bankroll.current_bankroll) / bankroll.starting_bankroll) * 100
    : 0
  const drawdownWarning = drawdownPct >= 20

  return (
    <div className="mb-7">
      <h2 className="text-lg font-semibold mb-3">Bankroll & Tracking</h2>
      {drawdownWarning && (
        <div className="bg-dk-red/10 border border-dk-red rounded-xl p-3 px-4 mb-3 text-dk-red text-sm font-semibold">
          Warning: Bankroll is down {drawdownPct.toFixed(0)}% from starting balance.
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card
          title="Current Bankroll"
          value={`$${bankroll.current_bankroll.toFixed(2)}`}
          color="text-dk-blue"
          sub={`Starting: $${bankroll.starting_bankroll.toFixed(2)} \u2022 ${profitSign}$${Math.abs(profit).toFixed(2)}`}
        />
        <Card
          title="Record"
          value={record}
          color={stats.wins > stats.losses ? 'text-dk-green' : stats.losses > stats.wins ? 'text-dk-red' : 'text-primary'}
          sub={`W-L-P \u2022 ${winRate}% win rate`}
        />
        <Card
          title="Today's Action"
          value={`$${todayTotal.toFixed(2)}`}
          color="text-dk-green"
          sub={`${todayPct}% of bankroll \u2022 ${overLimit ? 'EXCEEDS' : 'Within'} 15% limit ${overLimit ? '\u26A0' : '\u2713'}`}
        />
        <Card
          title="Pending Bets"
          value={pendingBets.length}
          color="text-dk-yellow"
          sub={pendingBets.length > 0 ? pendingBets.map(b => b.pick).join(', ') : 'No unsettled bets'}
        />
      </div>
    </div>
  )
}

function Card({ title, value, color, sub }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <h3 className="text-sm text-muted mb-2">{title}</h3>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-muted text-sm mt-1 truncate">{sub}</div>
    </div>
  )
}
