import { useActivity, usePicks, useStateRecord } from '../api/queries'
import { useDeleteManualBet } from '../api/mutations'
import { americanWinAmount, formatMoney, formatStartTime } from '../lib/format'
import type { Pick } from '../../../shared/types'

export function PendingTab() {
  const state = useStateRecord()
  const picks = usePicks()
  const activity = useActivity()
  const removeManual = useDeleteManualBet()

  if (state.isLoading || picks.isLoading || activity.isLoading) {
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

  const resolvedKeys = new Set(
    (activity.data?.bets ?? []).map((b) => `${b.pick}|${b.event}`),
  )
  const pickByKey = new Map<string, Pick>()
  for (const pk of picks.data?.picks ?? []) {
    pickByKey.set(`${pk.pick}|${pk.event}`, pk)
  }
  const unresolvedPlacements = state.data.placements.filter(
    (p) => p.action === 'placed' && !resolvedKeys.has(p.key),
  )

  if (pendingManual.length === 0 && unresolvedPlacements.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Nothing pending</div>
        <p>No placed picks or manual bets awaiting resolution.</p>
      </div>
    )
  }

  return (
    <div className="pending-list">
      {unresolvedPlacements.length > 0 && (
        <div className="pending-section">
          <div className="pending-section-title">
            Placed picks ({unresolvedPlacements.length})
          </div>
          {unresolvedPlacements.map((pl) => {
            const pk = pickByKey.get(pl.key)
            const [pickText, eventText] = pl.key.split('|')
            const wager = pl.wager ?? pk?.wager
            const odds = pk?.odds ?? ''
            const gameTime = pk?.start_time ? formatStartTime(pk.start_time) : ''
            const win =
              typeof wager === 'number' && odds ? americanWinAmount(odds, wager) : 0
            const parts = [
              gameTime,
              odds,
              typeof wager === 'number' ? `$${formatMoney(wager)}` : '',
              win > 0 ? `Win $${formatMoney(win)}` : '',
            ].filter(Boolean)
            return (
              <div key={pl.key} className="pending-row">
                <div className="pending-row-info">
                  {pk && <span className="pick-sport">{pk.sport}</span>}
                  <span className="pending-row-pick">{pk?.pick ?? pickText}</span>
                  <span className="pending-row-event">{pk?.event ?? eventText}</span>
                </div>
                <span className="pending-row-meta">{parts.join(' • ')}</span>
              </div>
            )
          })}
        </div>
      )}
      {pendingManual.length > 0 && (
        <div className="pending-section">
          <div className="pending-section-title">
            Manual bets ({pendingManual.length})
          </div>
          {pendingManual.map((b) => {
            const win = americanWinAmount(b.odds, b.wager)
            return (
              <div key={b.id} className="pending-row">
                <div className="pending-row-info">
                  <span className="pick-sport">{b.sport}</span>
                  <span className="pending-row-pick">{b.pick}</span>
                  <span className="pending-row-event">{b.event}</span>
                </div>
                <span className="pending-row-meta">
                  {b.odds} • ${formatMoney(b.wager)}
                  {win > 0 ? ` • Win $${formatMoney(win)}` : ''}
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
            )
          })}
        </div>
      )}
    </div>
  )
}
