/**
 * Convert American odds string to implied probability.
 * "-110" → 0.524, "+270" → 0.270
 */
export function impliedProbability(oddsStr) {
  const odds = parseInt(oddsStr, 10)
  if (isNaN(odds)) return 0
  if (odds < 0) return Math.abs(odds) / (Math.abs(odds) + 100)
  return 100 / (odds + 100)
}

/**
 * Convert American odds string to decimal odds.
 * "-110" → 1.909, "+270" → 3.70
 */
export function toDecimalOdds(oddsStr) {
  const odds = parseInt(oddsStr, 10)
  if (isNaN(odds)) return 1
  if (odds < 0) return 1 + 100 / Math.abs(odds)
  return 1 + odds / 100
}

/**
 * Calculate edge: model probability minus implied probability.
 */
export function calcEdge(modelProb, oddsStr) {
  return modelProb - impliedProbability(oddsStr)
}

/**
 * Format a number as American odds string.
 */
export function formatOdds(oddsStr) {
  const odds = parseInt(oddsStr, 10)
  if (isNaN(odds)) return oddsStr
  return odds > 0 ? `+${odds}` : `${odds}`
}
