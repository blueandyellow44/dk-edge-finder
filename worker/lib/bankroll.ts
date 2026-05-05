import type { Env } from '../env'
import { BankrollResponseSchema } from '../../shared/schemas'
import type { BankrollResponse } from '../../shared/types'
import { getBalanceOverride } from './state'
import { loadDataJson } from './picks'

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

// Sum the wagers on bets in data.json.bets[] still in 'pending' state.
// Reads the canonical resolved/pending list rather than KV state placements
// so legacy pre-session-13 KV records (which lack wager) still count -
// the going-forward sync_kv_placements.py cron step always writes wager
// into the new bets[] entry, falling back to $14 if KV record predates
// the wager-required schema. Returns 0 on any failure so bankroll keeps
// serving.
async function sumActiveStakes(env: Env): Promise<number> {
  try {
    const { data } = await loadDataJson(env)
    const rawBets = Array.isArray((data as { bets?: unknown }).bets)
      ? ((data as { bets: unknown[] }).bets)
      : []
    let total = 0
    for (const b of rawBets) {
      if (!b || typeof b !== 'object') continue
      const bet = b as { wager?: unknown; outcome?: unknown }
      if (bet.outcome !== 'pending') continue
      if (typeof bet.wager === 'number' && Number.isFinite(bet.wager)) {
        total += bet.wager
      }
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
    sumActiveStakes(env),
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
