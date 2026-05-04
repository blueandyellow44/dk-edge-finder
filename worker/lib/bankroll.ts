import type { Env } from '../env'
import { BankrollResponseSchema } from '../../shared/schemas'
import type { BankrollResponse } from '../../shared/types'
import { getBalanceOverride, readState } from './state'
import { getActivityResponse } from './activity'
import { getLatestScanDate } from './picks'

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

// Sum the wagers on placements that were 'placed' (not 'skipped') and whose
// underlying pick has not yet shown up as a resolved bet in activity.
// Mirrors PendingTab's resolved-key join (`${pick}|${event}`).
// Returns 0 if data.json is unreachable: bankroll should still serve.
async function sumActiveStakes(env: Env, email: string): Promise<number> {
  let scan_date: string
  try {
    scan_date = await getLatestScanDate(env)
  } catch {
    return 0
  }
  if (!scan_date) return 0
  const [record, activity] = await Promise.all([
    readState(env, email, scan_date),
    getActivityResponse(env).catch(() => ({ bets: [] as { pick: string; event: string }[] })),
  ])
  if (!record) return 0
  const resolvedKeys = new Set(activity.bets.map((b) => `${b.pick}|${b.event}`))
  let total = 0
  for (const p of record.placements) {
    if (p.action !== 'placed') continue
    if (resolvedKeys.has(p.key)) continue
    if (typeof p.wager === 'number') total += p.wager
  }
  return total
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

  const response: BankrollResponse = {
    available,
    starting,
    profit: lifetimeProfit,
    lifetime: {
      bets: int(file.lifetime_bets, 0),
      wins: int(file.lifetime_wins, 0),
      losses: int(file.lifetime_losses, 0),
      pushes: int(file.lifetime_pushes, 0),
      profit: lifetimeProfit,
      roi_pct: num(file.roi_pct, 0),
    },
    balance_override,
  }

  return BankrollResponseSchema.parse(response)
}
