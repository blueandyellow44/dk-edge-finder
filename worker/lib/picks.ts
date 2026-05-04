import type { Env } from '../env'
import { PicksResponseSchema } from '../../shared/schemas'
import type { Pick, NoEdgeGame, BestBet, PicksResponse } from '../../shared/types'

// Replace em-dashes with hyphens. Per Q6 of the locked contract, every
// string the worker returns to the frontend must be em-dash-free.
const EM_DASH_RE = /—/g
function stripEmDash(s: string): string {
  return s.replace(EM_DASH_RE, '-')
}

function coerceNumberPercent(raw: unknown): number {
  if (typeof raw === 'number') return raw
  if (typeof raw === 'string') {
    const n = parseFloat(raw.replace('%', '').trim())
    return Number.isFinite(n) ? n : 0
  }
  return 0
}

function coerceNumberDollars(raw: unknown): number {
  if (typeof raw === 'number') return raw
  if (typeof raw === 'string') {
    const n = parseFloat(raw.replace(/[^0-9.\-]/g, ''))
    return Number.isFinite(n) ? n : 0
  }
  return 0
}

function coerceOddsString(raw: unknown): string {
  if (typeof raw === 'string') return raw
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw > 0 ? `+${raw}` : String(raw)
  }
  return ''
}

function coercePickType(raw: unknown): 'game' | 'prop' {
  return raw === 'prop' ? 'prop' : 'game'
}

function normalizePick(raw: Record<string, unknown>, fallbackRank: number): Pick {
  const out: Pick = {
    rank: typeof raw.rank === 'number' ? raw.rank : fallbackRank,
    sport: stripEmDash(String(raw.sport ?? '')),
    event: stripEmDash(String(raw.event ?? '')),
    market: stripEmDash(String(raw.market ?? '')),
    pick: stripEmDash(String(raw.pick ?? '')),
    odds: coerceOddsString(raw.odds),
    implied: coerceNumberPercent(raw.implied ?? raw.implied_prob),
    model: coerceNumberPercent(raw.model ?? raw.model_prob),
    edge: coerceNumberPercent(raw.edge),
    ev_per_dollar: typeof raw.ev_per_dollar === 'number' ? raw.ev_per_dollar : 0,
    tier: stripEmDash(String(raw.tier ?? '')),
    wager: coerceNumberDollars(raw.wager ?? raw.bet),
    notes: stripEmDash(String(raw.notes ?? '')),
    sources: stripEmDash(String(raw.sources ?? '')),
    confidence: stripEmDash(String(raw.confidence ?? '')),
    dk_link: typeof raw.dk_link === 'string' ? raw.dk_link : '',
    type: coercePickType(raw.type),
    start_time: typeof raw.start_time === 'string' ? raw.start_time : '',
  }
  if (typeof raw.is_favorite === 'boolean') {
    out.is_favorite = raw.is_favorite
  }
  return out
}

function normalizeNoEdgeGame(raw: Record<string, unknown>): NoEdgeGame {
  return {
    sport: stripEmDash(String(raw.sport ?? '')),
    event: stripEmDash(String(raw.event ?? '')),
    line: stripEmDash(String(raw.line ?? '')),
    reason: stripEmDash(String(raw.reason ?? '')),
  }
}

function normalizeBestBet(raw: unknown): BestBet | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  return {
    title: stripEmDash(String(o.title ?? '')),
    desc: stripEmDash(String(o.desc ?? '')),
  }
}

type DataJsonShape = {
  scan_date?: unknown
  scan_subtitle?: unknown
  games_analyzed?: unknown
  best_bet?: unknown
  picks?: unknown
  no_edge_games?: unknown
}

async function fetchAsset(env: Env, path: string): Promise<Response> {
  return env.ASSETS.fetch(new Request(`https://assets.local${path}`))
}

export async function loadDataJson(env: Env): Promise<{ data: DataJsonShape; lastModified: Date | null }> {
  const res = await fetchAsset(env, '/data.json')
  if (!res.ok) {
    throw new Error(`data.json fetch failed: ${res.status}`)
  }
  const lastModifiedHeader = res.headers.get('last-modified')
  const lastModified = lastModifiedHeader ? new Date(lastModifiedHeader) : null
  const data = (await res.json()) as DataJsonShape
  return { data, lastModified: lastModified && !isNaN(lastModified.getTime()) ? lastModified : null }
}

export async function getLatestScanDate(env: Env): Promise<string> {
  const { data } = await loadDataJson(env)
  return typeof data.scan_date === 'string' ? data.scan_date : ''
}

// pick_history.json is the model's paper-trading log. Used by /api/activity
// to enrich resolved bets with model metadata (market, edge, tier, notes)
// for the Positions-style click-to-expand detail in ActivityTab. Defensive:
// returns [] on any failure so /api/activity keeps serving with bare bets.
export type PickHistoryEntry = {
  scan_date?: unknown
  sport?: unknown
  event?: unknown
  market?: unknown
  pick?: unknown
  odds?: unknown
  implied?: unknown
  model?: unknown
  edge?: unknown
  tier?: unknown
  confidence?: unknown
  type?: unknown
  notes?: unknown
  outcome?: unknown
  final_score?: unknown
  pnl_if_bet?: unknown
}

export async function loadPickHistory(env: Env): Promise<PickHistoryEntry[]> {
  try {
    const res = await fetchAsset(env, '/pick_history.json')
    if (!res.ok) return []
    const raw = (await res.json()) as unknown
    return Array.isArray(raw) ? (raw as PickHistoryEntry[]) : []
  } catch {
    return []
  }
}

// daily_summaries.json: dict keyed on YYYY-MM-DD with AI-generated
// commentary. Generated by scripts/generate_daily_summary.py in the
// resolve-bets cron when ANTHROPIC_API_KEY is set. Defensive: returns
// empty dict on any failure.
export type DailySummaryEntry = {
  summary: unknown
  generated_at?: unknown
  model?: unknown
}

export async function loadDailySummaries(
  env: Env,
): Promise<Record<string, DailySummaryEntry>> {
  try {
    const res = await fetchAsset(env, '/daily_summaries.json')
    if (!res.ok) return {}
    const raw = (await res.json()) as unknown
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as Record<string, DailySummaryEntry>
    }
    return {}
  } catch {
    return {}
  }
}

export async function getPicksResponse(env: Env): Promise<PicksResponse> {
  const { data, lastModified } = await loadDataJson(env)

  const rawPicks = Array.isArray(data.picks) ? data.picks : []
  const rawNoEdge = Array.isArray(data.no_edge_games) ? data.no_edge_games : []

  const picks = rawPicks.map((p, i) =>
    normalizePick((p ?? {}) as Record<string, unknown>, i + 1),
  )
  const no_edge_games = rawNoEdge.map((g) =>
    normalizeNoEdgeGame((g ?? {}) as Record<string, unknown>),
  )

  const scan_age_seconds = lastModified
    ? Math.max(0, Math.floor((Date.now() - lastModified.getTime()) / 1000))
    : null

  const response: PicksResponse = {
    scan_date: typeof data.scan_date === 'string' ? data.scan_date : '',
    scan_subtitle: stripEmDash(typeof data.scan_subtitle === 'string' ? data.scan_subtitle : ''),
    scan_age_seconds,
    picks,
    no_edge_games,
    games_analyzed: typeof data.games_analyzed === 'number' ? data.games_analyzed : 0,
    best_bet: normalizeBestBet(data.best_bet),
  }

  return PicksResponseSchema.parse(response)
}
