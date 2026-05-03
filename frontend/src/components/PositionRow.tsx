import type { Pick, Placement } from '../../../shared/types'
import { formatMoney, formatPercent } from '../lib/format'

type Props = {
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

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="position-detail-row">
      <span className="position-detail-label">{label}</span>
      <span className="position-detail-value">{value}</span>
    </div>
  )
}

export function PositionRow({
  pick,
  index,
  placement,
  isPending,
  onPlace,
  onSkip,
}: Props) {
  const placed = placement?.action === 'placed'
  const skipped = placement?.action === 'skipped'
  const queued = placed && placement?.dispatch_status === 'queued'

  return (
    <div className="position-row">
      <div className="position-summary">
        <div className="pick-rank">#{pick.rank || index + 1}</div>
        <div>
          <span className="pick-sport">{pick.sport}</span>
          {pick.is_favorite !== undefined && (
            <span className={`pick-favdog ${pick.is_favorite ? 'fav' : 'dog'}`}>
              {pick.is_favorite ? 'FAV' : 'DOG'}
            </span>
          )}
          <div className="pick-text">{pick.pick}</div>
          <div className="pick-event">{pick.event}</div>
        </div>
        <div className="pick-odds">{pick.odds}</div>
        <div className={`pick-edge ${tierClass(pick.tier)}`}>
          {formatPercent(pick.edge)}
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
      <div className="position-detail">
        <DetailRow label="Market" value={pick.market || '-'} />
        <DetailRow label="Implied" value={formatPercent(pick.implied)} />
        <DetailRow label="Model" value={formatPercent(pick.model)} />
        <DetailRow label="Confidence" value={pick.confidence || '-'} />
        {pick.sources && <DetailRow label="Sources" value={pick.sources} />}
        {pick.notes && <DetailRow label="Notes" value={pick.notes} />}
      </div>
    </div>
  )
}
