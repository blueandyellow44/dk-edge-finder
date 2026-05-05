import { useActivity, useBankroll } from '../api/queries'
import { formatMoney, formatPercent, formatSignedMoney } from '../lib/format'

export function BalanceCard() {
  const bankroll = useBankroll()
  const activity = useActivity()

  if (bankroll.isLoading) {
    return (
      <div className="card">
        <div className="card-header">Balance</div>
        <div className="balance-section">
          <div className="balance-label">Available</div>
          <div className="balance-amount">
            <span className="dollar">$</span>...
          </div>
        </div>
      </div>
    )
  }

  if (bankroll.isError || !bankroll.data) {
    return (
      <div className="card">
        <div className="card-header">Balance</div>
        <div className="placeholder">Failed to load.</div>
      </div>
    )
  }

  const { available, starting, profit, lifetime } = bankroll.data
  const profitClass = profit > 0 ? 'positive' : profit < 0 ? 'negative' : ''
  const roiClass = lifetime.roi_pct > 0 ? 'positive' : lifetime.roi_pct < 0 ? 'negative' : ''

  // Pending = 5/4 wagers DK has already debited but haven't graded yet.
  // Without surfacing this, "$500 start + $102 profit = $602" doesn't square
  // with "Available $504" - the missing $98 is locked in active bets.
  // Read the activity bets, but the data.json bets[] also includes pending
  // entries (which /api/activity filters out). Use a fallback: pending =
  // starting + profit - available.
  const totalBankroll = starting + profit
  const pending = Math.max(0, totalBankroll - available)
  const activityBets = activity.data?.bets ?? []
  const pendingFromActivity = activityBets.length // resolved only; doesn't help count pending
  // Fallback pending count: try to infer from totalBankroll-available rounding
  // up to typical $14 stake. Better: read pending count from /api/activity if
  // we ever expose it. For now, just show the dollar amount.
  void pendingFromActivity

  return (
    <div className="card">
      <div className="card-header">Balance</div>
      <div className="balance-section">
        <div className="balance-label">Available</div>
        <div className="balance-amount">
          <span className="dollar">$</span>
          {formatMoney(available)}
        </div>
        {pending > 0.005 && (
          <div className="balance-breakdown">
            <span className="balance-breakdown-piece">
              + ${formatMoney(pending)} in active bets
            </span>
            <span className="balance-breakdown-equals">=</span>
            <span className="balance-breakdown-total">
              ${formatMoney(totalBankroll)} bankroll
            </span>
          </div>
        )}
        <div className="balance-stats">
          <div>
            <div className="balance-stat-label">Profit</div>
            <div className={`balance-stat-value ${profitClass}`}>
              {formatSignedMoney(profit)}
            </div>
          </div>
          <div>
            <div className="balance-stat-label">Lifetime ROI</div>
            <div className={`balance-stat-value ${roiClass}`}>
              {formatPercent(lifetime.roi_pct)}
            </div>
          </div>
          <div>
            <div className="balance-stat-label">Record</div>
            <div className="balance-stat-value">
              {lifetime.wins}-{lifetime.losses}
              {lifetime.pushes > 0 && `-${lifetime.pushes}`}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
