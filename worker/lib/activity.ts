import type { Env } from '../env'
import { ActivityResponseSchema } from '../../shared/schemas'
import type { ActivityResponse, ResolvedBet } from '../../shared/types'
import {
  loadDataJson,
  loadDailySummaries,
  loadPickHistory,
} from './picks'
import type { DailySummaryEntry, PickHistoryEntry } from './picks'

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

// pick_history.json carries `implied`/`model` as percent-strings ("64.5%")
// but `edge` as a raw number (5.4). Normalize all three to plain numbers
// in 0-100 space so the frontend can format consistently.
function coercePercent(raw: unknown): number | undefined {
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw
  if (typeof raw === 'string') {
    const n = parseFloat(raw.replace('%', '').trim())
    if (Number.isFinite(n)) return n
  }
  return undefined
}

function coerceOptionalString(raw: unknown): string | undefined {
  if (typeof raw === 'string' && raw.length > 0) return stripEmDash(raw)
  return undefined
}

function buildPickHistoryIndex(
  history: PickHistoryEntry[],
): Map<string, PickHistoryEntry> {
  const index = new Map<string, PickHistoryEntry>()
  for (const h of history) {
    const date = typeof h.scan_date === 'string' ? h.scan_date : ''
    const pick = typeof h.pick === 'string' ? stripEmDash(h.pick) : ''
    const event = typeof h.event === 'string' ? stripEmDash(h.event) : ''
    if (!date || !pick || !event) continue
    const key = `${date}|${pick}|${event}`
    // First-write wins: pick_history can have duplicate paper entries
    // (e.g. same pick scanned twice in a day at slightly different odds).
    // Earlier entry usually carries the canonical model output.
    if (!index.has(key)) index.set(key, h)
  }
  return index
}

function normalizeResolvedBet(
  raw: Record<string, unknown>,
  history: Map<string, PickHistoryEntry>,
): ResolvedBet {
  const date = typeof raw.date === 'string' ? raw.date : ''
  const sport = stripEmDash(String(raw.sport ?? ''))
  const event = stripEmDash(String(raw.event ?? ''))
  const pick = stripEmDash(String(raw.pick ?? ''))

  const bet: ResolvedBet = {
    date,
    sport,
    event,
    pick,
    odds: coerceOddsString(raw.odds),
    wager: typeof raw.wager === 'number' ? raw.wager : 0,
    outcome: coerceOutcome(raw.outcome),
    pnl: typeof raw.pnl === 'number' ? raw.pnl : 0,
    final_score: stripEmDash(String(raw.final_score ?? '')),
  }

  // Enrich from pick_history.json when (date, pick, event) matches.
  // Only attach fields that are actually present and parseable.
  const ph = history.get(`${date}|${pick}|${event}`)
  if (ph) {
    const market = coerceOptionalString(ph.market)
    if (market) bet.market = market
    const model = coercePercent(ph.model)
    if (model !== undefined) bet.model = model
    const implied = coercePercent(ph.implied)
    if (implied !== undefined) bet.implied = implied
    const edge = coercePercent(ph.edge)
    if (edge !== undefined) bet.edge = edge
    const tier = coerceOptionalString(ph.tier)
    if (tier) bet.tier = tier
    const confidence = coerceOptionalString(ph.confidence)
    if (confidence) bet.confidence = confidence
    const notes = coerceOptionalString(ph.notes)
    if (notes) bet.notes = notes
  }

  return bet
}

function normalizeSummaries(
  raw: Record<string, DailySummaryEntry>,
): Record<string, { summary: string; generated_at?: string; model?: string }> {
  const out: Record<string, { summary: string; generated_at?: string; model?: string }> = {}
  for (const [date, entry] of Object.entries(raw)) {
    if (!date || !entry || typeof entry !== 'object') continue
    const summary = typeof entry.summary === 'string' ? entry.summary : ''
    if (!summary) continue
    const item: { summary: string; generated_at?: string; model?: string } = {
      summary: stripEmDash(summary),
    }
    if (typeof entry.generated_at === 'string') item.generated_at = entry.generated_at
    if (typeof entry.model === 'string') item.model = entry.model
    out[date] = item
  }
  return out
}

export async function getActivityResponse(env: Env): Promise<ActivityResponse> {
  const [{ data }, history, summariesRaw] = await Promise.all([
    loadDataJson(env),
    loadPickHistory(env),
    loadDailySummaries(env),
  ])
  const historyIndex = buildPickHistoryIndex(history)
  const rawBets = Array.isArray((data as { bets?: unknown }).bets)
    ? ((data as { bets: unknown[] }).bets)
    : []
  const bets = rawBets
    .map((b) => normalizeResolvedBet((b ?? {}) as Record<string, unknown>, historyIndex))
    .filter((b) => b.outcome !== 'pending')
  bets.sort((a, b) => b.date.localeCompare(a.date))
  const summaries = normalizeSummaries(summariesRaw)
  return ActivityResponseSchema.parse({ bets, summaries })
}
