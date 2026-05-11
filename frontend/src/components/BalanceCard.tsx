import { useActivity, useBankroll, useStateRecord } from '../api/queries'
import { formatMoney, formatPercent, formatSignedMoney } from '../lib/format'

const LEGACY_WAGER_FALLBACK = 14

export function BalanceCard() {
  const bankroll = useBankroll()
  const activity = useActivity()
  const state = useStateRecord()

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

  // Active bets = wagers on placed-but-not-yet-resolved picks. Compute
  // directly from state.placements (aggregated across all scan_dates) and
  // dedupe against resolved activity bets. This is the same calculation
  // the worker performs server-side when deriving `available`; doing it
  // again client-side gives a stable display number that doesn't bounce
  // when the bankroll endpoint races the state endpoint.
  const resolvedKeys = new Set(
    (activity.data?.bets ?? []).map((b) => `${b.date}|${b.pick}|${b.event}`),
  )
  const placedPlacements = (state.data?.placements ?? []).filter((p) => {
    if (p.action !== 'placed') return false
    const date = p.scan_date ?? state.data?.scan_date ?? ''
    return !resolvedKeys.has(`${date}|${p.key}`)
  })
  // Dedupe by (date, pick, event) — same key the worker uses — so a
  // placement that appears in multiple scan-date records counts once.
  const seen = new Set<string>()
  let activeBets = 0
  let activeBetCount = 0
  for (const p of placedPlacements) {
    const date = p.scan_date ?? state.data?.scan_date ?? ''
    const tripleKey = `${date}|${p.key}`
    if (seen.has(tripleKey)) continue
    seen.add(tripleKey)
    activeBets += typeof p.wager === 'number' ? p.wager : LEGACY_WAGER_FALLBACK
    activeBetCount += 1
  }
  const pendingManualCount = (state.data?.manual_bets ?? []).filter(
    (b) => b.outcome === 'pending',
  ).length
  for (const m of state.data?.manual_bets ?? []) {
    if (m.outcome !== 'pending') continue
    activeBets += m.wager
  }
  const totalActiveCount = activeBetCount + pendingManualCount
  const totalBankroll = available + activeBets

  return (
    <div className="card">
      <div className="card-header">Balance</div>
      <div className="balance-section">
        <div className="balance-label">Available</div>
        <div className="balance-amount">
          <span className="dollar">$</span>
          {formatMoney(available)}
        </div>
        {activeBets > 0.005 && (
          <div className="balance-breakdown">
            <span className="balance-breakdown-piece">
              + ${formatMoney(activeBets)} in {totalActiveCount} active{' '}
              {totalActiveCount === 1 ? 'bet' : 'bets'}
            </span>
            <span className="balance-breakdown-equals">=</span>
            <span className="balance-breakdown-total">
              ${formatMoney(totalBankroll)} bankroll
            </span>
          </div>
        )}
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
