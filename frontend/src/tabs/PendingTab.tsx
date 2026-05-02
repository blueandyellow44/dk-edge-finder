import { usePicks, useStateRecord } from '../api/queries'
import {
  useDeleteManualBet,
  useDeletePlacement,
  useRetrySyncQueue,
} from '../api/mutations'
import { formatMoney } from '../lib/format'
import type { Pick } from '../../../shared/types'

export function PendingTab() {
  const picks = usePicks()
  const state = useStateRecord()
  const retry = useRetrySyncQueue()
  const cancel = useDeletePlacement()
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

  const queued = state.data.placements.filter(
    (p) => p.dispatch_status === 'queued',
  )
  const pendingManual = state.data.manual_bets.filter(
    (b) => b.outcome === 'pending',
  )
  const isAnyPending =
    retry.isPending || cancel.isPending || removeManual.isPending

  if (queued.length === 0 && pendingManual.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Nothing pending</div>
        <p>No queued placements and no manual bets awaiting resolution.</p>
      </div>
    )
  }

  const pickByKey = new Map<string, Pick>()
  for (const p of picks.data?.picks ?? []) {
    pickByKey.set(`${p.pick}|${p.event}`, p)
  }

  return (
    <div className="pending-list">
      {queued.length > 0 && (
        <div className="pending-section">
          <div className="pending-section-title">
            Queued retries ({queued.length})
          </div>
          {queued.map((p) => {
            const pick = pickByKey.get(p.key)
            const [pickText, ...eventParts] = p.key.split('|')
            return (
              <div key={p.key} className="pending-row">
                <div className="pending-row-info">
                  <span className="pick-sport">{pick?.sport ?? 'BET'}</span>
                  <span className="pending-row-pick">
                    {pick ? pick.pick : pickText}
                  </span>
                  <span className="pending-row-event">
                    {pick ? pick.event : eventParts.join('|')}
                  </span>
                </div>
                <span className="pick-badge queued">Queued</span>
                <div className="pending-row-actions">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={isAnyPending}
                    onClick={() => retry.mutate({ key: p.key })}
                  >
                    Retry now
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    disabled={isAnyPending}
                    onClick={() => cancel.mutate({ key: p.key })}
                  >
                    Cancel
                  </button>
                </div>
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
                  disabled={isAnyPending}
                  onClick={() => removeManual.mutate({ id: b.id })}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
