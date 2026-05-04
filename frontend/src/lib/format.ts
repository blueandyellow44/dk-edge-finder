const moneyFmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatMoney(n: number): string {
  return moneyFmt.format(n)
}

export function formatSignedMoney(n: number): string {
  const abs = moneyFmt.format(Math.abs(n))
  if (n > 0) return `+$${abs}`
  if (n < 0) return `-$${abs}`
  return `$${abs}`
}

export function formatPercent(n: number, decimals = 1): string {
  return `${n.toFixed(decimals)}%`
}

export function formatAgo(seconds: number | null): string | null {
  if (seconds === null) return null
  if (seconds < 60) return `${Math.round(seconds)}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`
  return `${Math.round(seconds / 86400)}d ago`
}

export function formatStartTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// "2026-05-03" -> "Sun, May 3" for ActivityTab day-group headers. Uses
// UTC parse so a date string never shifts a day backward in PT.
export function formatDayHeader(yyyymmdd: string): string {
  if (!yyyymmdd || !/^\d{4}-\d{2}-\d{2}$/.test(yyyymmdd)) return yyyymmdd
  const [y, m, d] = yyyymmdd.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  if (isNaN(dt.getTime())) return yyyymmdd
  return dt.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

// American odds → profit on a winning bet (excludes returned stake).
// "+150" with $20 wager wins $30 profit. "-110" with $22 wins $20 profit.
export function americanWinAmount(odds: string, wager: number): number {
  const cleaned = odds.replace(/^\+/, '').trim()
  const n = parseFloat(cleaned)
  if (!Number.isFinite(n) || wager <= 0) return 0
  if (n > 0) return (wager * n) / 100
  if (n < 0) return (wager * 100) / Math.abs(n)
  return 0
}
