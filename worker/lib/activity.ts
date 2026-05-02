import type { Env } from '../env'
import { ActivityResponseSchema } from '../../shared/schemas'
import type { ActivityResponse, ResolvedBet } from '../../shared/types'
import { loadDataJson } from './picks'

const EM_DASH_RE = /—/g
function stripEmDash(s: string): string {
  return s.replace(EM_DASH_RE, '-')
}

function coerceOddsString(raw: unknown): string {
  if (typeof raw === 'string') return raw
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw > 0 ? `+${raw}` : String(raw)
  }
  return ''
}

function coerceOutcome(raw: unknown): 'win' | 'loss' | 'push' | 'pending' {
  if (raw === 'win' || raw === 'loss' || raw === 'push' || raw === 'pending') {
    return raw
  }
  return 'pending'
}

function normalizeResolvedBet(raw: Record<string, unknown>): ResolvedBet {
  return {
    date: typeof raw.date === 'string' ? raw.date : '',
    sport: stripEmDash(String(raw.sport ?? '')),
    event: stripEmDash(String(raw.event ?? '')),
    pick: stripEmDash(String(raw.pick ?? '')),
    odds: coerceOddsString(raw.odds),
    wager: typeof raw.wager === 'number' ? raw.wager : 0,
    outcome: coerceOutcome(raw.outcome),
    pnl: typeof raw.pnl === 'number' ? raw.pnl : 0,
    final_score: stripEmDash(String(raw.final_score ?? '')),
  }
}

export async function getActivityResponse(env: Env): Promise<ActivityResponse> {
  const { data } = await loadDataJson(env)
  const rawBets = Array.isArray((data as { bets?: unknown }).bets)
    ? ((data as { bets: unknown[] }).bets)
    : []
  const bets = rawBets
    .map((b) => normalizeResolvedBet((b ?? {}) as Record<string, unknown>))
    .filter((b) => b.outcome !== 'pending')
  bets.sort((a, b) => b.date.localeCompare(a.date))
  return ActivityResponseSchema.parse({ bets })
}
