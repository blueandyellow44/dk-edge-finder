import { useStateRecord } from '../api/queries'
import { useDeleteManualBet } from '../api/mutations'
import { formatMoney } from '../lib/format'

export function PendingTab() {
  const state = useStateRecord()
  const removeManual = useDeleteManualBet()

  if (state.isLoading) {
    return <div className="placeholder">Loading pending...</div>
  }
  if (state.isError || !state.data) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Failed to load pending</div>
      </div>
    )
  }

  const pendingManual = state.data.manual_bets.filter(
    (b) => b.outcome === 'pending',
  )

  if (pendingManual.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Nothing pending</div>
        <p>No manual bets awaiting resolution.</p>
      </div>
    )
  }

  return (
    <div className="pending-list">
      <div className="pending-section">
        <div className="pending-section-title">
          Manual bets ({pendingManual.length})
        </div>
        {pendingManual.map((b) => (
          <div key={b.id} className="pending-row">
            <div className="pending-row-info">
              <span className="pick-sport">{b.sport}</span>
              <span className="pending-row-pick">{b.pick}</span>
              <span className="pending-row-event">{b.event}</span>
            </div>
            <span className="pending-row-meta">
              {b.odds} • ${formatMoney(b.wager)}
            </span>
            <div className="pending-row-actions">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                disabled={removeManual.isPending}
                onClick={() => removeManual.mutate({ id: b.id })}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
