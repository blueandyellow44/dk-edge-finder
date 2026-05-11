import { useState } from 'react'
import { useActivity, usePicks, useStateRecord } from '../api/queries'
import { useDeleteManualBet } from '../api/mutations'
import { americanWinAmount, formatMoney, formatStartTime } from '../lib/format'
import type { Pick } from '../../../shared/types'

export function PendingTab() {
  const state = useStateRecord()
  const picks = usePicks()
  const activity = useActivity()
  const removeManual = useDeleteManualBet()
  const [expandedId, setExpandedId] = useState<string | null>(null)

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

  // Resolved bets are keyed by (date, pick, event) since the same pick can
  // re-appear across days (e.g. Padres -1.5 on Tuesday AND Thursday). Without
  // the date in the key, today's placement gets hidden the moment yesterday's
  // identical pick resolves.
  const resolvedKeys = new Set(
    (activity.data?.bets ?? []).map((b) => `${b.date}|${b.pick}|${b.event}`),
  )
  const scanDate = state.data.scan_date
  const pickByKey = new Map<string, Pick>()
  for (const pk of picks.data?.picks ?? []) {
    pickByKey.set(`${pk.pick}|${pk.event}`, pk)
  }
  const unresolvedPlacements = state.data.placements.filter((p) => {
    if (p.action !== 'placed') return false
    const placementDate = p.scan_date ?? scanDate
    return !resolvedKeys.has(`${placementDate}|${p.key}`)
  })

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
            const placementDate = pl.scan_date ?? scanDate
            const rowId = `placed:${placementDate}|${pl.key}`
            const expanded = expandedId === rowId
            const wager = pl.wager ?? pk?.wager
            const odds = pk?.odds ?? ''
            const gameTime = pk?.start_time ? formatStartTime(pk.start_time) : ''
            const win =
              typeof wager === 'number' && odds ? americanWinAmount(odds, wager) : 0
            const sport = pk?.sport ?? ''
            const placedAt = new Date(pl.placed_at)
            const placedAtLabel = isNaN(placedAt.getTime())
              ? ''
              : placedAt.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })
            return (
              <div
                key={rowId}
                className={`pending-row${expanded ? ' pending-row-expanded' : ''}`}
              >
                <button
                  type="button"
                  className="pending-row-summary"
                  onClick={() => setExpandedId(expanded ? null : rowId)}
                  aria-expanded={expanded}
                >
                  <div className="pending-row-info">
                    {sport && <span className="pick-sport">{sport}</span>}
                    <span className="pending-row-pick">{pk?.pick ?? pickText}</span>
                    <span className="pending-row-event">{pk?.event ?? eventText}</span>
                  </div>
                  <div className="pending-row-meta">
                    {odds && <span className="pending-meta-piece">{odds}</span>}
                    {typeof wager === 'number' && (
                      <span className="pending-meta-piece">${formatMoney(wager)}</span>
                    )}
                    {win > 0 && (
                      <span className="pending-meta-piece pending-meta-win">
                        Win ${formatMoney(win)}
                      </span>
                    )}
                    <span
                      className={`pending-row-chevron${expanded ? ' open' : ''}`}
                      aria-hidden
                    >
                      ▾
                    </span>
                  </div>
                </button>
                {expanded && (
                  <div className="pending-row-detail">
                    <div className="pending-detail-grid">
                      {gameTime && (
                        <DetailPair label="Game time" value={gameTime} />
                      )}
                      {placedAtLabel && (
                        <DetailPair label="Placed" value={placedAtLabel} />
                      )}
                      {pk?.market && (
                        <DetailPair label="Market" value={pk.market} />
                      )}
                      {pk && (
                        <DetailPair
                          label="Model"
                          value={`${pk.model.toFixed(1)}%`}
                        />
                      )}
                      {pk && (
                        <DetailPair
                          label="Edge"
                          value={`${pk.edge.toFixed(1)}%`}
                        />
                      )}
                      {pk?.tier && (
                        <DetailPair label="Tier" value={pk.tier} />
                      )}
                      {typeof wager === 'number' && (
                        <DetailPair
                          label="Wager"
                          value={`$${formatMoney(wager)}`}
                        />
                      )}
                      {win > 0 && (
                        <DetailPair
                          label="Win amount"
                          value={`$${formatMoney(win)}`}
                        />
                      )}
                    </div>
                    {pk?.notes && (
                      <div className="pending-detail-notes">{pk.notes}</div>
                    )}
                    {!pk && (
                      <p className="pending-detail-empty">
                        Pick details unavailable - this placement is from an
                        older scan that has rotated out.
                      </p>
                    )}
                  </div>
                )}
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
            const rowId = `manual:${b.id}`
            const expanded = expandedId === rowId
            const win = americanWinAmount(b.odds, b.wager)
            const placedDate = new Date(b.placed_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })
            return (
              <div
                key={b.id}
                className={`pending-row${expanded ? ' pending-row-expanded' : ''}`}
              >
                <button
                  type="button"
                  className="pending-row-summary"
                  onClick={() => setExpandedId(expanded ? null : rowId)}
                  aria-expanded={expanded}
                >
                  <div className="pending-row-info">
                    <span className="pick-sport">{b.sport}</span>
                    <span className="pending-row-pick">{b.pick}</span>
                    <span className="pending-row-event">{b.event}</span>
                  </div>
                  <div className="pending-row-meta">
                    <span className="pending-meta-piece">{b.odds}</span>
                    <span className="pending-meta-piece">${formatMoney(b.wager)}</span>
                    {win > 0 && (
                      <span className="pending-meta-piece pending-meta-win">
                        Win ${formatMoney(win)}
                      </span>
                    )}
                    <span
                      className={`pending-row-chevron${expanded ? ' open' : ''}`}
                      aria-hidden
                    >
                      ▾
                    </span>
                  </div>
                </button>
                {expanded && (
                  <div className="pending-row-detail">
                    <div className="pending-detail-grid">
                      <DetailPair label="Placed" value={placedDate} />
                      <DetailPair label="Odds" value={b.odds} />
                      <DetailPair
                        label="Wager"
                        value={`$${formatMoney(b.wager)}`}
                      />
                      {win > 0 && (
                        <DetailPair
                          label="Win amount"
                          value={`$${formatMoney(win)}`}
                        />
                      )}
                    </div>
                    <div className="pending-row-actions">
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        disabled={removeManual.isPending}
                        onClick={(e) => {
                          e.stopPropagation()
                          removeManual.mutate({ id: b.id })
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function DetailPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="pending-detail-row">
      <span className="pending-detail-label">{label}</span>
      <span className="pending-detail-value">{value}</span>
    </div>
  )
}
