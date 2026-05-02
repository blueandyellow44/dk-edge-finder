import { useActivity } from '../api/queries'
import { formatMoney, formatSignedMoney } from '../lib/format'

export function ActivityTab() {
  const activity = useActivity()

  if (activity.isLoading) {
    return <div className="placeholder">Loading activity...</div>
  }
  if (activity.isError || !activity.data) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Failed to load activity</div>
      </div>
    )
  }

  const bets = activity.data.bets
  if (bets.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">No activity yet</div>
        <p>Resolved bets will appear here.</p>
      </div>
    )
  }

  return (
    <div className="activity-list">
      <div className="activity-header">
        <div>Date</div>
        <div>Pick / Event</div>
        <div className="activity-wager">Wager</div>
        <div className="activity-odds">Odds</div>
        <div className="activity-outcome">Outcome</div>
        <div className="activity-pnl">P/L</div>
      </div>
      {bets.map((b, i) => {
        const pnlClass =
          b.outcome === 'win'
            ? 'positive'
            : b.outcome === 'loss'
              ? 'negative'
              : ''
        return (
          <div key={`${b.date}-${b.event}-${i}`} className="activity-row">
            <div className="activity-date">{b.date}</div>
            <div className="pending-row-info">
              <span className="pick-sport">{b.sport}</span>
              <span className="pending-row-pick">{b.pick}</span>
              <span className="pending-row-event">
                {b.event}
                {b.final_score ? ` • ${b.final_score}` : ''}
              </span>
            </div>
            <div className="activity-wager">${formatMoney(b.wager)}</div>
            <div className="activity-odds">{b.odds}</div>
            <div className={`activity-outcome ${b.outcome}`}>{b.outcome}</div>
            <div className={`activity-pnl ${pnlClass}`}>
              {formatSignedMoney(b.pnl)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
