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
