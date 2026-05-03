import { z } from 'zod'

// ──────────── Common ────────────

export const ScanDateSchema = z.iso.date()
export const TimestampSchema = z.iso.datetime({ offset: true })

// ──────────── Picks (v2 normalized output) ────────────
//
// The Python model emits the raw shape in scripts/scan_edges.py
// (see formatted_picks.append at ~line 1968). Q6 of the locked
// contract reshapes it: numeric edge / wager / implied / ev_per_dollar,
// drops event_short and the empty status/result fields, strips em-dashes
// from every string. PickSchema below describes what the worker returns.

export const PickSchema = z.object({
  rank: z.number().int().nonnegative(),
  sport: z.string(),
  event: z.string(),
  market: z.string(),
  pick: z.string(),
  odds: z.string(),
  implied: z.number(),
  model: z.number(),
  edge: z.number(),
  ev_per_dollar: z.number(),
  tier: z.string(),
  wager: z.number(),
  notes: z.string(),
  sources: z.string(),
  confidence: z.string(),
  dk_link: z.string(),
  type: z.enum(['game', 'prop']),
  start_time: z.string(),
  is_favorite: z.boolean().optional(),
})

export const NoEdgeGameSchema = z.object({
  sport: z.string(),
  event: z.string(),
  line: z.string(),
  reason: z.string(),
})

export const BestBetSchema = z.object({
  title: z.string(),
  desc: z.string(),
})

export const PicksResponseSchema = z.object({
  scan_date: ScanDateSchema,
  scan_subtitle: z.string(),
  scan_age_seconds: z.number().nullable(),
  picks: z.array(PickSchema),
  no_edge_games: z.array(NoEdgeGameSchema),
  games_analyzed: z.number().int().nonnegative(),
  best_bet: BestBetSchema.nullable(),
})

// ──────────── Bankroll ────────────

export const LifetimeStatsSchema = z.object({
  bets: z.number().int().nonnegative(),
  wins: z.number().int().nonnegative(),
  losses: z.number().int().nonnegative(),
  pushes: z.number().int().nonnegative(),
  profit: z.number(),
  roi_pct: z.number(),
})

export const BankrollResponseSchema = z.object({
  available: z.number(),
  starting: z.number(),
  profit: z.number(),
  lifetime: LifetimeStatsSchema,
  balance_override: z
    .object({
      amount: z.number(),
      note: z.string(),
      updated_at: TimestampSchema,
    })
    .nullable(),
})

// ──────────── Identity ────────────

export const MeResponseSchema = z.object({
  email: z.string(),
  picture_url: z.string().nullable(),
})

// ──────────── State (KV blobs + API responses) ────────────
//
// Per ADR 0003 these blobs carry schema_version: 1 so future shape
// changes can upgrade in place on read. Idempotency keys dedupe on
// append-merge.

export const PlacementSchema = z.object({
  key: z.string(),
  action: z.enum(['placed', 'skipped']),
  dispatch_status: z.enum(['ok', 'queued', 'failed']),
  placed_at: TimestampSchema,
  idempotency_key: z.string(),
})

export const SyncQueueEntrySchema = z.object({
  key: z.string(),
  last_attempt_at: TimestampSchema,
  attempt_count: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
  idempotency_key: z.string(),
})

export const ManualBetSchema = z.object({
  id: z.string(),
  sport: z.string(),
  event: z.string(),
  pick: z.string(),
  odds: z.string(),
  wager: z.number(),
  outcome: z.enum(['pending', 'win', 'loss', 'push']),
  placed_at: TimestampSchema,
  idempotency_key: z.string(),
})

export const StateRecordSchema = z.object({
  schema_version: z.literal(1),
  email: z.string(),
  scan_date: ScanDateSchema,
  placements: z.array(PlacementSchema),
  sync_queue: z.array(SyncQueueEntrySchema),
  manual_bets: z.array(ManualBetSchema),
  updated_at: TimestampSchema,
})

export const BalanceOverrideRecordSchema = z.object({
  schema_version: z.literal(1),
  email: z.string(),
  amount: z.number(),
  note: z.string(),
  updated_at: TimestampSchema,
})

export const StateResponseSchema = z.object({
  scan_date: ScanDateSchema,
  placements: z.array(PlacementSchema),
  sync_queue: z.array(SyncQueueEntrySchema),
  manual_bets: z.array(ManualBetSchema),
  updated_at: TimestampSchema.nullable(),
})

// ──────────── Write-route request bodies (Phase 1 step 7) ────────────
//
// These are the POST/DELETE bodies. The worker validates with these and
// then constructs the full domain entry server-side (e.g. placed_at = now,
// dispatch_status defaults set when missing). Names mirror the suggested
// endpoint surface in backend-requirements.md.

export const PlacementCreateRequestSchema = z.object({
  key: z.string(),
  action: z.enum(['placed', 'skipped']),
  // 'queued' / 'failed' are vestigial: pre-existing KV records may still
  // carry them from the retired auto-dispatch chain. New writes are 'ok'.
  dispatch_status: z.enum(['ok', 'queued', 'failed']).default('ok'),
  idempotency_key: z.string().min(1),
})

export const ManualBetCreateRequestSchema = z.object({
  sport: z.string(),
  event: z.string(),
  pick: z.string(),
  odds: z.string(),
  wager: z.number(),
  idempotency_key: z.string().min(1),
})

export const BalanceOverrideRequestSchema = z.object({
  amount: z.number(),
  note: z.string(),
})

// ──────────── Activity (resolved bets from data.json.bets[]) ────────────

export const ResolvedBetSchema = z.object({
  date: ScanDateSchema,
  sport: z.string(),
  event: z.string(),
  pick: z.string(),
  odds: z.string(),
  wager: z.number(),
  outcome: z.enum(['win', 'loss', 'push', 'pending']),
  pnl: z.number(),
  final_score: z.string(),
})

export const ActivityResponseSchema = z.object({
  bets: z.array(ResolvedBetSchema),
})
