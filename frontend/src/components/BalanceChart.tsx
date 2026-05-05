import { useActivity, useBankroll } from '../api/queries'

const VB_WIDTH = 240
const VB_HEIGHT = 80
const PAD_TOP = 6
const PAD_BOTTOM = 4
const PLOT_HEIGHT = VB_HEIGHT - PAD_TOP - PAD_BOTTOM

type Bet = { date: string; pnl: number }

function buildSeries(
  starting: number,
  bets: Bet[],
): { date: string; balance: number }[] {
  if (bets.length === 0) return []
  const byDate = new Map<string, number>()
  for (const b of bets) {
    byDate.set(b.date, (byDate.get(b.date) ?? 0) + b.pnl)
  }
  const dates = [...byDate.keys()].sort()
  let balance = starting
  return dates.map((date) => {
    balance += byDate.get(date)!
    return { date, balance }
  })
}

function fmtDateShort(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function fmtDollarsFull(n: number): string {
  return `$${n.toFixed(2)}`
}

function CardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="card-header">Balance over time</div>
      {children}
    </div>
  )
}

export function BalanceChart() {
  const activity = useActivity()
  const bankroll = useBankroll()

  if (activity.isLoading || bankroll.isLoading) {
    return (
      <CardShell>
        <div className="balance-chart-empty">Loading...</div>
      </CardShell>
    )
  }
  if (
    activity.isError ||
    bankroll.isError ||
    !activity.data ||
    !bankroll.data
  ) {
    return (
      <CardShell>
        <div className="balance-chart-empty">Failed to load.</div>
      </CardShell>
    )
  }

  const starting = bankroll.data.starting
  const series = buildSeries(starting, activity.data.bets)
  if (series.length < 2) {
    return (
      <CardShell>
        <div className="balance-chart-empty">
          Not enough resolved bets yet.
        </div>
      </CardShell>
    )
  }

  const xVals = series.map((p) => new Date(`${p.date}T00:00:00`).getTime())
  const xMin = xVals[0]
  const xMax = xVals[xVals.length - 1]
  const xRange = xMax - xMin || 1

  const balances = series.map((p) => p.balance)
  const yMinRaw = Math.min(...balances, starting)
  const yMaxRaw = Math.max(...balances, starting)
  const yPad = Math.max(6, (yMaxRaw - yMinRaw) * 0.08)
  const yMin = yMinRaw - yPad
  const yMax = yMaxRaw + yPad
  const yRange = yMax - yMin || 1

  const xScale = (ts: number) => ((ts - xMin) / xRange) * VB_WIDTH
  const yScale = (b: number) =>
    PAD_TOP + ((yMax - b) / yRange) * PLOT_HEIGHT

  const linePath = series
    .map((p, i) => {
      const x = xScale(xVals[i]).toFixed(1)
      const y = yScale(p.balance).toFixed(1)
      return `${i === 0 ? 'M' : 'L'}${x},${y}`
    })
    .join(' ')

  const baseY = (PAD_TOP + PLOT_HEIGHT).toFixed(1)
  const lastX = xScale(xVals[xVals.length - 1]).toFixed(1)
  const firstX = xScale(xVals[0]).toFixed(1)
  const areaPath = `${linePath} L${lastX},${baseY} L${firstX},${baseY} Z`

  // Headline change comes from bankroll.profit (DK-reconciled lifetime P/L),
  // not from the chart series' cumulative. Source-of-truth split on purpose:
  // the line shape shows MODEL-pick trajectory (one bet per data.json.bets[]
  // entry, computed client-side); the headline shows ACTUAL DK lifetime
  // profit (from bankroll.json which is DK-reconciled). The two can diverge
  // when there's untracked DK activity (parlays, props, in-game bets that
  // never flowed through "Mark as placed"). Headline reflects reality;
  // line shows the model-only slice for analysis.
  const finalBalance = series[series.length - 1].balance
  const change = bankroll.data.profit
  const changeClass =
    change > 0 ? 'positive' : change < 0 ? 'negative' : ''
  const changeSign = change >= 0 ? '+' : ''
  const dayCount = series.length

  return (
    <CardShell>
      <div className="balance-chart-section">
        <div className="balance-chart-summary">
          <span className={`balance-chart-change ${changeClass}`}>
            {changeSign}
            {fmtDollarsFull(change)}
          </span>
          <span className="balance-chart-meta">
            over {dayCount} day{dayCount === 1 ? '' : 's'}
          </span>
        </div>
        <svg
          viewBox={`0 0 ${VB_WIDTH} ${VB_HEIGHT}`}
          role="img"
          aria-label={`Balance trajectory: ${fmtDollarsFull(starting)} to ${fmtDollarsFull(finalBalance)} over ${dayCount} days`}
          className="balance-chart-svg"
          preserveAspectRatio="none"
        >
          <path d={areaPath} fill="var(--color-accent-tint)" stroke="none" />
          <path
            d={linePath}
            stroke="var(--color-accent)"
            strokeWidth={1.5}
            fill="none"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div className="balance-chart-axis">
          <span>{fmtDateShort(series[0].date)}</span>
          <span>{fmtDateShort(series[series.length - 1].date)}</span>
        </div>
      </div>
    </CardShell>
  )
}
