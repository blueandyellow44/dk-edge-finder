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

/**
 * Sport-specific min edge overrides.
 * NBA spreads are 5-7 (41.7%) — model's weakest market.
 */
const NBA_SPREAD_MIN_EDGE = 0.05
const NBA_LARGE_SPREAD_MIN_EDGE = 0.08
const NBA_LARGE_SPREAD_THRESHOLD = 12.0

/**
 * Graduated edge discount for bet sizing.
 * 10%+ edges only hit 58.8% vs 75% for 5-8% edges — model overestimates large edges.
 * We discount large raw edges BEFORE sizing (not before filtering).
 */
const EDGE_DISCOUNT_TIERS = [
  { floor: 0.15, cap: 0.10 },  // 15%+ → size as 10%
  { floor: 0.12, cap: 0.10 },  // 12-15% → size as 10%
  { floor: 0.10, cap: 0.08 },  // 10-12% → size as 8%
]

/**
 * Single-source confidence penalty.
 * Picks with only one model source (e.g. DRatings-only) get 25% Kelly reduction.
 */
const SINGLE_SOURCE_KELLY_DISCOUNT = 0.75

/** Max single bet: 5% of bankroll */
const MAX_BET_PCT = 0.05

/** Max daily exposure: 15% of bankroll */
export const MAX_DAILY_PCT = 0.15

/**
 * Get effective min edge, accounting for sport-specific overrides.
 * @param {string} tier - "High", "Medium", or "Low"
 * @param {object} opts - { sport, market, spreadPoints }
 */
function getMinEdge(tier, opts = {}) {
  const baseMin = TIER_MIN_EDGE[tier] || 0.03
  const { sport, market, spreadPoints } = opts

  // NBA spread override: raised thresholds due to 41.7% win rate
  if (sport === 'NBA' && (market === 'Spread' || market === 'spreads')) {
    const absSpread = Math.abs(spreadPoints || 0)
    if (absSpread > NBA_LARGE_SPREAD_THRESHOLD) {
      return Math.max(baseMin, NBA_LARGE_SPREAD_MIN_EDGE)
    }
    return Math.max(baseMin, NBA_SPREAD_MIN_EDGE)
  }

  return baseMin
}

/**
 * Apply graduated edge discount for sizing.
 * Raw edge is used for filtering; discounted edge is used for Kelly calculation.
 */
function discountEdgeForSizing(edgeFraction) {
  for (const { floor, cap } of EDGE_DISCOUNT_TIERS) {
    if (edgeFraction >= floor) {
      return cap
    }
  }
  return edgeFraction
}

/**
 * Calculate Kelly criterion bet size.
 * @param {number} edgePct - Edge as percentage (e.g. 7.6 for 7.6%)
 * @param {string} oddsStr - American odds string (e.g. "-110")
 * @param {string} tier - "High", "Medium", or "Low"
 * @param {number} bankroll - User's current bankroll in dollars
 * @param {object} opts - Optional: { sport, market, spreadPoints, singleSource }
 * @returns {{ betSize: number, kellyFraction: number, fractionalKelly: number, capped: boolean, discountApplied: boolean, singleSourceDiscount: boolean }}
 */
export function kellyBetSize(edgePct, oddsStr, tier, bankroll, opts = {}) {
  const rawEdge = edgePct / 100
  const minEdge = getMinEdge(tier, opts)
  if (rawEdge < minEdge) {
    return { betSize: 0, kellyFraction: 0, fractionalKelly: 0, capped: false, discountApplied: false, singleSourceDiscount: false }
  }

  // Discount large edges for sizing — model overestimates 10%+ edges
  const sizingEdge = discountEdgeForSizing(rawEdge)
  const discountApplied = sizingEdge < rawEdge

  const decimalOdds = toDecimalOdds(oddsStr)
  const kellyFraction = (sizingEdge * decimalOdds - (1 - sizingEdge)) / (decimalOdds - 1)

  if (kellyFraction <= 0) {
    return { betSize: 0, kellyFraction: 0, fractionalKelly: 0, capped: false, discountApplied, singleSourceDiscount: false }
  }

  let tierMultiplier = TIER_FRACTION[tier] || 0.25

  // Single-source penalty: 25% Kelly reduction when only one model contributes
  const singleSourceDiscount = opts.singleSource === true
  if (singleSourceDiscount) {
    tierMultiplier *= SINGLE_SOURCE_KELLY_DISCOUNT
  }

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
    discountApplied,
    singleSourceDiscount,
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
