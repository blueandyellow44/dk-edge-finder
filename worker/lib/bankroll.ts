import type { Env } from '../env'
import {
  BankrollResponseSchema,
  BalanceOverrideRecordSchema,
} from '../../shared/schemas'
import type { BankrollResponse } from '../../shared/types'

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

function balanceOverrideKey(email: string): string {
  return `balance_override:${email}`
}

async function readUserOverride(env: Env, email: string) {
  const raw = await env.EDGE_STATE.get(balanceOverrideKey(email))
  if (!raw) return null
  try {
    return BalanceOverrideRecordSchema.parse(JSON.parse(raw))
  } catch {
    return null
  }
}

export async function getBankrollResponse(env: Env, email: string): Promise<BankrollResponse> {
  const [file, userOverride] = await Promise.all([loadBankrollFile(env), readUserOverride(env, email)])

  const starting = num(file.starting_bankroll, 0)
  const lifetimeProfit = num(file.lifetime_profit, 0)
  const fileCurrent = num(file.current_bankroll, starting + lifetimeProfit)

  const balance_override = userOverride
    ? { amount: userOverride.amount, note: userOverride.note, updated_at: userOverride.updated_at }
    : null

  const available = userOverride ? userOverride.amount : fileCurrent

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
