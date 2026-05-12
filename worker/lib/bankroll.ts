import type { Env } from '../env'
import { BankrollResponseSchema } from '../../shared/schemas'
import type { BankrollResponse } from '../../shared/types'
import { getBalanceOverride, listAllStateRecords } from './state'
import { loadDataJson } from './picks'

// Wager to assume for pre-Bug-2 KV placements that were written before
// schema added the wager field. Matches Max's stated flat stake and the
// same fallback used in scripts/sync_kv_placements.py.
const LEGACY_WAGER_FALLBACK = 14

type BankrollFileShape = {
  starting_bankroll?: unknown
  current_bankroll?: unknown
  balance_override?: unknown
  override_note?: unknown
  last_updated?: unknown
  lifetime_bets?: unknown
  lifetime_wins?: unknown
  lifetime_losses?: unknown
  lifetime_pushes?: unknown
  lifetime_profit?: unknown
  roi_pct?: unknown
}

const num = (v: unknown, fallback = 0): number => (typeof v === 'number' && Number.isFinite(v) ? v : fallback)
const int = (v: unknown, fallback = 0): number => (typeof v === 'number' && Number.isInteger(v) ? v : fallback)

async function loadBankrollFile(env: Env): Promise<BankrollFileShape> {
  const res = await env.ASSETS.fetch(new Request('https://assets.local/bankroll.json'))
  if (!res.ok) throw new Error(`bankroll.json fetch failed: ${res.status}`)
  return (await res.json()) as BankrollFileShape
}

// Sum wagers on bets the user has marked as placed that are not yet
// resolved. Source-of-truth is KV (state:<email>:<scan_date> records)
// because that is where the SPA writes a placement the instant the
// "Mark as placed" button fires; data.json only catches up at the next
// resolve-bets cron tick. Reading from KV closes the SPA-to-bankroll
// freshness gap that caused the displayed "active bets" to sit at $0
// or a stale number until the nightly sync.
//
// Dedupe against data.json.bets[outcome in win/loss/push]: once a
// placement has been graded, it stops being active. Pending entries
// already in data.json are mirrored from a KV placement, so iterating
// over KV alone is the canonical set; the data.json pass is purely a
// resolved-set lookup. Returns 0 on any failure so bankroll keeps
// serving even when KV is unreachable.
async function sumActiveStakes(env: Env, email: string): Promise<number> {
  try {
    const { data } = await loadDataJson(env)
    const rawBets = Array.isArray((data as { bets?: unknown }).bets)
      ? ((data as { bets: unknown[] }).bets)
      : []
    const resolvedKeys = new Set<string>()
    const pendingInData = new Map<string, number>()
    for (const b of rawBets) {
      if (!b || typeof b !== 'object') continue
      const bet = b as {
        date?: unknown
        pick?: unknown
        event?: unknown
        wager?: unknown
        outcome?: unknown
      }
      const date = typeof bet.date === 'string' ? bet.date : ''
      const pick = typeof bet.pick === 'string' ? bet.pick : ''
      const event = typeof bet.event === 'string' ? bet.event : ''
      const tripleKey = `${date}|${pick}|${event}`
      if (bet.outcome === 'win' || bet.outcome === 'loss' || bet.outcome === 'push') {
        if (date && pick && event) resolvedKeys.add(tripleKey)
      } else if (bet.outcome === 'pending') {
        if (date && pick && event && typeof bet.wager === 'number') {
          pendingInData.set(tripleKey, bet.wager)
        }
      }
    }

    const records = await listAllStateRecords(env, email)
    const seenInKV = new Set<string>()
    let total = 0
    for (const r of records) {
      for (const p of r.placements) {
        if (p.action !== 'placed') continue
        const split = p.key.split('|')
        if (split.length < 2) continue
        const pick = split[0]
        const event = split.slice(1).join('|')
        const tripleKey = `${r.scan_date}|${pick}|${event}`
        if (resolvedKeys.has(tripleKey)) continue
        if (seenInKV.has(tripleKey)) continue
        seenInKV.add(tripleKey)
        const wager =
          typeof p.wager === 'number' && Number.isFinite(p.wager)
            ? p.wager
            : LEGACY_WAGER_FALLBACK
        total += wager
      }
    }
    // Catch pending bets that exist only in data.json (e.g. backfilled
    // by an old one-shot script without ever passing through KV).
    for (const [tripleKey, wager] of pendingInData) {
      if (seenInKV.has(tripleKey)) continue
      total += wager
    }
    return total
  } catch {
    return 0
  }
}

export async function getBankrollResponse(env: Env, email: string): Promise<BankrollResponse> {
  const [file, userOverride, activeStakes] = await Promise.all([
    loadBankrollFile(env),
    getBalanceOverride(env, email),
    sumActiveStakes(env, email),
  ])

  const starting = num(file.starting_bankroll, 0)
  const lifetimeProfit = num(file.lifetime_profit, 0)
  const fileCurrent = num(file.current_bankroll, starting + lifetimeProfit)

  const balance_override = userOverride
    ? { amount: userOverride.amount, note: userOverride.note, updated_at: userOverride.updated_at }
    : null

  const baseAvailable = userOverride ? userOverride.amount : fileCurrent
  const available = baseAvailable - activeStakes

  // When a balance override is set, profit = override - starting. Do NOT
  // add active stakes back in: pending wagers are locked stake, not
  // realized P/L. They could resolve as wins or losses. Including them in
  // "profit" makes the headline jump positive whenever you place a few
  // bets (e.g. $498.80 override - $500 start = -$1.20 loss; with $33
  // pending the old formula said +$31.80 profit, which felt broken).
  // The active stakes still appear in the BalanceCard breakdown line
  // (+ $X in N active bets) as a separate piece of context.
  const profit = userOverride ? userOverride.amount - starting : lifetimeProfit

  // Lifetime ROI tracks the same basis as the displayed profit. With an
  // override set, paper ROI (from bankroll.json, model picks only) can
  // contradict the headline: profit -$1.20 alongside ROI +0.4% reads as
  // broken. Derive ROI from (profit / starting) when override is set so
  // the two numbers always agree in sign and direction. Without an
  // override we keep the cron-reconciled bankroll.json ROI, which is the
  // canonical paper-trading metric. Record (W-L-P) stays paper either
  // way — it's a count, not a money number, so it doesn't conflict.
  const roi_pct = userOverride
    ? starting > 0
      ? (profit / starting) * 100
      : 0
    : num(file.roi_pct, 0)

  const response: BankrollResponse = {
    available,
    starting,
    profit,
    lifetime: {
      bets: int(file.lifetime_bets, 0),
      wins: int(file.lifetime_wins, 0),
      losses: int(file.lifetime_losses, 0),
      pushes: int(file.lifetime_pushes, 0),
      profit: lifetimeProfit,
      roi_pct,
    },
    balance_override,
  }

  return BankrollResponseSchema.parse(response)
}
