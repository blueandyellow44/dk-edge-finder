import { toDecimalOdds } from './odds'

/**
 * Fractional Kelly multipliers by confidence tier.
 */
const TIER_FRACTION = {
  High: 0.5,
  Medium: 0.25,
  Low: 0.125,
}

/**
 * Minimum edge required per tier.
 */
const TIER_MIN_EDGE = {
  High: 0.03,
  Medium: 0.05,
  Low: 0.08,
}

/** Max single bet: 5% of bankroll */
const MAX_BET_PCT = 0.05

/** Max daily exposure: 15% of bankroll */
export const MAX_DAILY_PCT = 0.15

/**
 * Calculate Kelly criterion bet size.
 * @param {number} edgePct - Edge as percentage (e.g. 7.6 for 7.6%)
 * @param {string} oddsStr - American odds string (e.g. "-110")
 * @param {string} tier - "High", "Medium", or "Low"
 * @param {number} bankroll - User's current bankroll in dollars
 * @returns {{ betSize: number, kellyFraction: number, fractionalKelly: number, capped: boolean }}
 */
export function kellyBetSize(edgePct, oddsStr, tier, bankroll) {
  const edge = edgePct / 100
  const minEdge = TIER_MIN_EDGE[tier] || 0.03
  if (edge < minEdge) {
    return { betSize: 0, kellyFraction: 0, fractionalKelly: 0, capped: false }
  }

  const decimalOdds = toDecimalOdds(oddsStr)
  const kellyFraction = (edge * decimalOdds - (1 - edge)) / (decimalOdds - 1)

  if (kellyFraction <= 0) {
    return { betSize: 0, kellyFraction: 0, fractionalKelly: 0, capped: false }
  }

  const tierMultiplier = TIER_FRACTION[tier] || 0.25
  const fractionalKelly = kellyFraction * tierMultiplier

  const maxBet = bankroll * MAX_BET_PCT
  const rawBet = fractionalKelly * bankroll
  const betSize = Math.min(rawBet, maxBet)
  const capped = rawBet > maxBet

  return {
    betSize: Math.round(betSize * 100) / 100,
    kellyFraction,
    fractionalKelly,
    capped,
  }
}

/**
 * Calculate total daily exposure from a list of wagers.
 */
export function dailyExposure(wagers, bankroll) {
  const total = wagers.reduce((sum, w) => sum + w, 0)
  return {
    total,
    pct: bankroll > 0 ? total / bankroll : 0,
    overLimit: bankroll > 0 && total / bankroll > MAX_DAILY_PCT,
  }
}
