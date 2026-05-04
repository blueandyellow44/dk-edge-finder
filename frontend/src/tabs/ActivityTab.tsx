import { useMemo, useState } from 'react'
import { useActivity } from '../api/queries'
import type { ResolvedBet } from '../../../shared/types'
import {
  americanWinAmount,
  formatDayHeader,
  formatMoney,
  formatPercent,
  formatSignedMoney,
} from '../lib/format'

type DayGroup = {
  date: string
  bets: ResolvedBet[]
  wins: number
  losses: number
  pushes: number
  net: number
  totalWagered: number
}

function tierClass(tier: string | undefined): 'high' | 'medium' | 'low' | '' {
  if (!tier) return ''
  const t = tier.toUpperCase()
  if (t === 'HIGH') return 'high'
  if (t === 'MEDIUM') return 'medium'
  if (t === 'LOW') return 'low'
  return ''
}

function groupByDate(bets: ResolvedBet[]): DayGroup[] {
  const map = new Map<string, ResolvedBet[]>()
  for (const b of bets) {
    const list = map.get(b.date)
    if (list) list.push(b)
    else map.set(b.date, [b])
  }
  const groups: DayGroup[] = []
  for (const [date, dayBets] of map) {
    let wins = 0
    let losses = 0
    let pushes = 0
    let net = 0
    let totalWagered = 0
    for (const b of dayBets) {
      if (b.outcome === 'win') wins++
      else if (b.outcome === 'loss') losses++
      else if (b.outcome === 'push') pushes++
      net += b.pnl
      totalWagered += b.wager
    }
    groups.push({ date, bets: dayBets, wins, losses, pushes, net, totalWagered })
  }
  // Most recent date first.
  groups.sort((a, b) => b.date.localeCompare(a.date))
  return groups
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="activity-detail-row">
      <span className="activity-detail-label">{label}</span>
      <span className="activity-detail-value">{value}</span>
    </div>
  )
}

type RowProps = {
  bet: ResolvedBet
  index: number
  expanded: boolean
  onToggle: () => void
}

function ActivityRow({ bet, index, expanded, onToggle }: RowProps) {
  const pnlClass =
    bet.outcome === 'win' ? 'positive' : bet.outcome === 'loss' ? 'negative' : ''
  const win = americanWinAmount(bet.odds, bet.wager)
  const tier = tierClass(bet.tier)
  const hasMetadata =
    bet.market !== undefined ||
    bet.model !== undefined ||
    bet.implied !== undefined ||
    bet.edge !== undefined ||
    bet.tier !== undefined ||
    bet.confidence !== undefined ||
    bet.notes !== undefined

  return (
    <div className={`activity-row${expanded ? ' activity-row-expanded' : ''}`}>
      <button
        type="button"
        className="activity-row-summary"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <div className="activity-row-info">
          <span className="pick-sport">{bet.sport}</span>
          <div className="activity-row-pick">{bet.pick}</div>
          <div className="activity-row-event">
            {bet.event}
            {bet.final_score ? ` • ${bet.final_score}` : ''}
          </div>
        </div>
        <div className="activity-row-meta">
          <span className="activity-row-odds">{bet.odds}</span>
          <span className="activity-row-wager">${formatMoney(bet.wager)}</span>
          <span className={`activity-outcome ${bet.outcome}`}>{bet.outcome}</span>
          <span className={`activity-pnl ${pnlClass}`}>
            {formatSignedMoney(bet.pnl)}
          </span>
          <span className={`activity-row-chevron${expanded ? ' open' : ''}`} aria-hidden>
            ▾
          </span>
        </div>
      </button>
      {expanded && (
        <div className="activity-row-detail">
          <div className="activity-detail-grid">
            {bet.market && <DetailRow label="Market" value={bet.market} />}
            {bet.model !== undefined && (
              <DetailRow label="Model" value={formatPercent(bet.model)} />
            )}
            {bet.implied !== undefined && (
              <DetailRow label="Implied" value={formatPercent(bet.implied)} />
            )}
            {bet.edge !== undefined && (
              <DetailRow label="Edge" value={formatPercent(bet.edge)} />
            )}
            {bet.tier && (
              <DetailRow label="Tier" value={bet.tier} />
            )}
            {bet.confidence && (
              <DetailRow label="Confidence" value={bet.confidence} />
            )}
            <DetailRow label="Wager" value={`$${formatMoney(bet.wager)}`} />
            <DetailRow label="Win amount" value={`$${formatMoney(win)}`} />
            {bet.final_score && (
              <DetailRow label="Final" value={bet.final_score} />
            )}
          </div>
          {bet.notes && (
            <div className={`activity-detail-notes${tier ? ` tier-${tier}` : ''}`}>
              {bet.notes}
            </div>
          )}
          {!hasMetadata && (
            <p className="activity-detail-empty">
              No model details on file for this bet (it predates the
              pick_history join, or was a manual entry).
            </p>
          )}
          {/* index is referenced so the prop is not "unused" in some lint configs;
              also serves as a stable React key in parent. */}
          {index < 0 && null}
        </div>
      )}
    </div>
  )
}

export function ActivityTab() {
  const activity = useActivity()
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const days = useMemo<DayGroup[]>(() => {
    if (!activity.data) return []
    return groupByDate(activity.data.bets)
  }, [activity.data])

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
  if (days.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">No activity yet</div>
        <p>Resolved bets will appear here.</p>
      </div>
    )
  }

  return (
    <div className="activity-days">
      {days.map((day) => (
        <section key={day.date} className="activity-day">
          <header className="activity-day-header">
            <div className="activity-day-date">{formatDayHeader(day.date)}</div>
            <div className="activity-day-stats">
              <span className="activity-day-record">
                {day.wins}W-{day.losses}L
                {day.pushes > 0 ? `-${day.pushes}P` : ''}
              </span>
              <span
                className={`activity-day-net ${
                  day.net > 0 ? 'positive' : day.net < 0 ? 'negative' : ''
                }`}
              >
                {formatSignedMoney(day.net)}
              </span>
            </div>
          </header>
          <div className="activity-day-bets">
            {day.bets.map((bet, i) => {
              const key = `${bet.date}|${bet.event}|${bet.pick}|${i}`
              return (
                <ActivityRow
                  key={key}
                  bet={bet}
                  index={i}
                  expanded={expandedKey === key}
                  onToggle={() =>
                    setExpandedKey(expandedKey === key ? null : key)
                  }
                />
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
