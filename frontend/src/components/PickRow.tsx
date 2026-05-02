import type { KeyboardEvent } from 'react'
import type { Pick, Placement } from '../../../shared/types'
import { formatMoney, formatPercent, formatStartTime } from '../lib/format'

type PickRowProps = {
  pick: Pick
  index: number
  placement: Placement | undefined
  isPending: boolean
  isExpanded: boolean
  onToggleExpand: () => void
  onMarkPlaced: () => void
  onIgnore: () => void
}

function tierClass(tier: string): 'high' | 'medium' | 'low' {
  const t = tier.toUpperCase()
  if (t === 'HIGH') return 'high'
  if (t === 'MEDIUM') return 'medium'
  return 'low'
}

export function PickRow({
  pick,
  index,
  placement,
  isPending,
  isExpanded,
  onToggleExpand,
  onMarkPlaced,
  onIgnore,
}: PickRowProps) {
  const placed = placement?.action === 'placed'
  const skipped = placement?.action === 'skipped'
  const queued = placed && placement?.dispatch_status === 'queued'
  const acted = placed || skipped
  const startTime = formatStartTime(pick.start_time)

  const handleRowClick = () => {
    if (acted) return
    onToggleExpand()
  }

  const handleRowKeyDown = (e: KeyboardEvent) => {
    if (acted) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onToggleExpand()
    }
  }

  return (
    <div className={`pick-item ${isExpanded ? 'expanded' : ''}`}>
      <div
        className={`pick-row ${acted ? 'acted' : 'clickable'}`}
        onClick={handleRowClick}
        onKeyDown={handleRowKeyDown}
        role={acted ? undefined : 'button'}
        tabIndex={acted ? undefined : 0}
        aria-expanded={acted ? undefined : isExpanded}
      >
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
            <span className={`pick-chevron ${isExpanded ? 'open' : ''}`} aria-hidden="true">
              ▸
            </span>
          )}
        </div>
      </div>

      {isExpanded && !acted && (
        <div className="pick-details">
          <dl className="pick-metrics">
            {pick.market && (
              <div className="pick-metric">
                <dt>Market</dt>
                <dd>{pick.market}</dd>
              </div>
            )}
            <div className="pick-metric">
              <dt>Model</dt>
              <dd>{formatPercent(pick.model)}</dd>
            </div>
            <div className="pick-metric">
              <dt>Implied</dt>
              <dd>{formatPercent(pick.implied)}</dd>
            </div>
            <div className="pick-metric">
              <dt>EV / $</dt>
              <dd>{pick.ev_per_dollar.toFixed(3)}</dd>
            </div>
            {startTime && (
              <div className="pick-metric">
                <dt>Start</dt>
                <dd>{startTime}</dd>
              </div>
            )}
          </dl>
          {pick.notes && <div className="pick-notes">{pick.notes}</div>}
          <div className="pick-actions-expanded">
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={isPending}
              onClick={onMarkPlaced}
            >
              Mark as placed
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={isPending}
              onClick={onIgnore}
            >
              Ignore
            </button>
            {pick.dk_link ? (
              <a
                className="btn btn-dk btn-sm"
                href={pick.dk_link}
                target="_blank"
                rel="noopener noreferrer"
              >
                Place on DraftKings ↗
              </a>
            ) : (
              <button type="button" className="btn btn-dk btn-sm" disabled>
                Place on DraftKings
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
