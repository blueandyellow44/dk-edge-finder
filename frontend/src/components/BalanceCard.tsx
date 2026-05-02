import { useBankroll } from '../api/queries'
import { formatMoney, formatPercent, formatSignedMoney } from '../lib/format'

export function BalanceCard() {
  const bankroll = useBankroll()

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

  const { available, profit, lifetime } = bankroll.data
  const profitClass = profit > 0 ? 'positive' : profit < 0 ? 'negative' : ''
  const roiClass = lifetime.roi_pct > 0 ? 'positive' : lifetime.roi_pct < 0 ? 'negative' : ''

  return (
    <div className="card">
      <div className="card-header">Balance</div>
      <div className="balance-section">
        <div className="balance-label">Available</div>
        <div className="balance-amount">
          <span className="dollar">$</span>
          {formatMoney(available)}
        </div>
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
