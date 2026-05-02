import type { Pick, Placement } from '../../../shared/types'
import { formatMoney } from '../lib/format'

type PickRowProps = {
  pick: Pick
  index: number
  placement: Placement | undefined
  isPending: boolean
  onPlace: () => void
  onSkip: () => void
}

function tierClass(tier: string): 'high' | 'medium' | 'low' {
  const t = tier.toUpperCase()
  if (t === 'HIGH') return 'high'
  if (t === 'MEDIUM') return 'medium'
  return 'low'
}

export function PickRow({ pick, index, placement, isPending, onPlace, onSkip }: PickRowProps) {
  const placed = placement?.action === 'placed'
  const skipped = placement?.action === 'skipped'
  const queued = placed && placement?.dispatch_status === 'queued'

  return (
    <div className="pick-row">
      <div className="pick-rank">#{pick.rank || index + 1}</div>
      <div>
        <span className="pick-sport">{pick.sport}</span>
        <div className="pick-text">{pick.pick}</div>
        <div className="pick-event">{pick.event}</div>
      </div>
      <div className="pick-odds">{pick.odds}</div>
      <div className={`pick-edge ${tierClass(pick.tier)}`}>
        {pick.edge.toFixed(1)}%
      </div>
      <div className="pick-wager">${formatMoney(pick.wager)}</div>
      <div className="pick-actions">
        {queued ? (
          <span className="pick-badge queued">Queued</span>
        ) : placed ? (
          <span className="pick-badge placed">Placed</span>
        ) : skipped ? (
          <span className="pick-badge skipped">Skipped</span>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={isPending}
              onClick={onPlace}
            >
              Place
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={isPending}
              onClick={onSkip}
            >
              Skip
            </button>
          </>
        )}
      </div>
    </div>
  )
}
