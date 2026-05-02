# Backend Requirements: DK Edge Finder v2 Frontend

Status: **LOCKED** as of 2026-04-30 PM, after a 7-question prompted interview. Subject to revision when Phase 1 implementation surfaces gaps.
Authoring skill: `frontend-to-backend-requirements`. Lives at `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`.

This is the contract the Vite + React frontend expects from the Hono worker. It lands as code in `shared/schemas.ts` and `shared/types.ts` during Phase 1.

## Context

We are rebuilding the frontend of [dk-edge-finder.max-sheahan.workers.dev](https://dk-edge-finder.max-sheahan.workers.dev/). The current site is a 66 kB single-file vanilla `index.html` reading a static `data.json` produced by a Python edge-finder model on a GitHub Actions cron. State (placed bets, sync queue, manual bets, balance override) lives entirely in `localStorage`, so iPhone Safari and Mac Chrome are silos.

The v2 frontend is Vite + React, served by the same Cloudflare Worker. Auth is Cloudflare Access with Google IdP. The worker exposes a Hono API. Cross-device state lives in a Workers KV namespace `EDGE_STATE`. The Python model is unchanged.

## Decisions locked in this interview

| # | Question | Answer |
|---|---|---|
| Q1 | v2 UX scope | Like-for-like rebuild + auth + cross-device sync. Same 5 tabs, same actions per tab. |
| Q2 | Scan-date navigation | Latest scan only. No date picker. /api/picks does not need a scan_date param for the default view. |
| Q3 | 5th tab role | Renamed Settings → **Account**. Scope: signed-in identity (email + Google avatar), balance override + note, sign-out, lifetime stats + ROI. No model config knobs. |
| Q4 | Sync conflict semantics | Append-merge. Frontend never PUTs whole state. Posts events (placement, manual bet, sync-queue retry, balance-override edit). Worker append-merges into KV. Server is source of truth. |
| Q5 | Place-bet failure UX | "Queued for retry" badge on the bet row, KV-backed sync_queue cross-device synced. Retry Now button per row. iPhone failures appear on Mac. |
| Q6 | /api/picks shape | Reshape into clean v2 types. Worker normalizes: numeric edge / wager / implied / ev_per_dollar, drops redundant fields (event_short, empty status/result), strips em-dash from scan_subtitle. |
| Q7 | Manual bets scope | Same narrow scope as today: Place button on rejected no-edge rows prompts for wager and logs to KV manual_bets[]. No freeform off-platform logging. |

## Screens

### Picks
**Purpose**: Today's bettable edges from the latest scan.

**Data the UI needs**:
- `picks[]`: model-emitted picks for the current scan. Fields: sport, event (full + short forms acceptable since reshape can drop event_short), market, pick text, odds, edge percent (number), implied probability (number), model probability (number), suggested wager (number, dollars), confidence tier (HIGH / MEDIUM / LOW), DK deep link, start time, market type (game / prop), notes.
- `no_edge_games[]`: games the model rejected. Fields: sport, event, line, reason. Shown in a collapsible "rejected" section with a Place button that triggers the manual-bet flow.
- `scan_date` and `scan_subtitle` (em-dash stripped).
- `bankroll` snapshot at top of screen.
- For each pick: whether the user has already placed it (so the row swaps Place → Placed). Source: KV state.placements.

**Actions**:
- **Place** (single pick): mark placement locally, fire GitHub dispatch, append to KV state.placements. If dispatch fails, append to KV state.sync_queue and show "queued for retry" badge.
- **Place All**: batch version, dispatches all unplaced picks at once.
- **Skip**: mark placement locally as skipped. No server-side action needed for skipped picks (placements record can hold action: 'placed' | 'skipped' for UI state).
- **Open DK link**: external nav, no API.
- **Manual-place a no-edge game**: prompt for wager, append to KV state.manual_bets.

**States**:
- **Empty (zero edges)**: `picks.length === 0` (today is exactly this case).
- **Loading**: initial fetch.
- **Stale**: scan timestamp is more than 12 hours old.
- **Error**: scan file missing or unparseable.

### Pending
**Purpose**: Bets the user has marked Placed that have not yet resolved.

**Data the UI needs**:
- All pending bets across recent scan dates (placements not yet resolved + manual bets with outcome 'pending').
- Per bet: original pick, wager, odds, event, sport, start time.
- Per bet: dispatch status (succeeded / queued for retry / failed). Sync queue entries surface here as a badge.
- Total dollars at risk + total to win.

**Actions**:
- **Retry Now** on any sync-queued bet → re-fires GitHub dispatch.
- **Cancel/withdraw** a placement that was queued but not actually placed at DK (DELETE the placement from KV).
- **Remove a manual bet** (× button, current site behavior; DELETE from KV manual_bets).

### Activity
**Purpose**: Historical record of resolved bets.

**Data the UI needs**:
- Resolved bets ordered by date desc (read from `data.json.bets[]` filtered to outcome ≠ 'pending'). Currently 62 entries today; not large enough to need pagination.
- Lifetime aggregates: bets, wins, losses, pushes, profit, ROI %. Sourced from bankroll endpoint.
- Per row: pick, event, sport, wager, odds, outcome, P/L, final score (if available), running balance.

**Actions**: read-only. (Sort/filter UI can be added without contract changes.)

**States**:
- **Empty**: no resolved bets.

### Positions
**Purpose**: Detailed view of today's open picks (rank, market, implied, model, confidence, sources, notes, edge tier). Same data source as Picks tab (`picks[]`), just rendered with more detail per row and expand/collapse.

**Data the UI needs**: same as Picks. Adds `sources` (e.g. "oddsshark + sagarin + actionnetwork") and `notes` (model commentary).

**Actions**: same Place / Skip buttons as Picks.

### Account (renamed from Settings)
**Purpose**: User identity + money management. No model config.

**Data the UI needs**:
- Signed-in email + picture URL from /api/me.
- Current balance override value + note + last-updated timestamp.
- Lifetime stats (bets, wins, losses, pushes, profit, ROI %).

**Actions**:
- **Update balance override** → POST balance override (amount, note).
- **Sign out** → redirect to Cloudflare Access logout endpoint (`/cdn-cgi/access/logout`).

## Cross-device state shape

Per-user, per-scan-date record (one record per `(email, scan_date)`):
- `placements[]` entries: `{key: "pick|event", action: "placed"|"skipped", scan_date, dispatch_status: "ok"|"queued"|"failed", placed_at}`
- `sync_queue[]` entries: `{key, scan_date, last_attempt_at, attempt_count, last_error}`
- `manual_bets[]` entries: `{id, sport, event, pick, odds, wager, scan_date, outcome: "pending"|"win"|"loss"|"push", placed_at}`

Per-user, scan-date-independent record:
- `balance_override`: `{amount, note, updated_at}`

**Write semantics**: append-merge. Frontend POSTs single events; worker reads existing record, merges, writes back. Last-write-wins on individual fields when concurrent merges occur (acceptable for single-user real usage). Each event includes a client-generated `idempotency_key` so re-tries don't double-insert.

## Suggested endpoint surface

Backend may push back on names / shapes. This is a starting frame derived from the locked answers above.

**Auth + identity**
- `GET /api/me` → `{ email, picture_url }`. Reads `cf-access-authenticated-user-email` and the Google IdP avatar URL from the JWT. 401 if header missing.

**Read paths**
- `GET /api/picks` → `{ scan_date, scan_subtitle, scan_age_seconds, picks: Pick[], no_edge_games: NoEdgeGame[], games_analyzed, best_bet }`. Em-dash stripped, numeric coercions applied.
- `GET /api/bankroll` → `{ available, starting, profit, lifetime: {bets, wins, losses, pushes, profit, roi_pct}, balance_override: {amount, note, updated_at} | null }`.
- `GET /api/state` → `{ placements: Placement[], sync_queue: SyncQueueEntry[], manual_bets: ManualBet[], updated_at }` for `(current_user, latest_scan_date)`.

**Write paths (append-merge)**
- `POST /api/state/placements` body `{ key, action, idempotency_key }` → 201 with the merged placement entry.
- `DELETE /api/state/placements/:key` → removes a placement (cancel/withdraw).
- `POST /api/state/manual-bets` body `{ sport, event, pick, odds, wager, idempotency_key }` → 201 with the new entry.
- `DELETE /api/state/manual-bets/:id` → removes a manual bet.
- `POST /api/state/sync-queue/retry` body `{ key, idempotency_key }` → re-runs the place dispatch and updates queue entry.
- `POST /api/balance-override` body `{ amount, note }` → upserts the per-user balance override.

**Place-bet (existing GitHub dispatch)**
- `POST /api/place-bet` body `{ pick_indices: number[], idempotency_key }` → fires `repository_dispatch` to trigger `place-bets.yml`. Returns `{ status: "ok"|"failed", dispatch_id?, error? }`. If failed, the client appends to sync_queue.

## Display contracts

- **Em-dash policy**: every string the worker returns to the frontend must be em-dash-free. Universal rule, not optional.
- **Money formatting**: numbers, not formatted strings. Frontend does its own `Intl.NumberFormat`.
- **Percentages**: numbers (e.g. `29.3` for 29.3%), not strings.
- **Odds**: keep the American format string ("+165", "-110") since the UI renders them that way and the math is well-defined regardless. Add a numeric `decimal_odds` alongside if convenient for sizing math.
- **Timestamps**: ISO 8601 with timezone (UTC or local with offset, frontend converts).

## Auth model

- Cloudflare Access policy: app at the worker domain, IdP = Google, allow `max.sheahan@icloud.com` (single-user today, future emails added in dashboard).
- Worker rejects every `/api/*` request that lacks `cf-access-authenticated-user-email`.
- Sign-out: link to `/cdn-cgi/access/logout`. No client-side token to clear.

## Open questions for backend (i.e., me wearing the worker hat during Phase 1)

These are implementation-shape questions the contract leaves open:

- **Idempotency key shape**: client-generated UUID v7? Hash of (event_type + key + scan_date)? Locked during /api/place-bet implementation. Re-uses across all POSTs.
- **/api/state response when KV has no record yet**: empty arrays + null updated_at, or 404? (Suggest empty-arrays for ergonomics.)
- **/api/picks scan_age_seconds**: derived from data.json's git mtime, or from a timestamp inside the file? Either works.
- **Dispatch retry policy on /api/state/sync-queue/retry**: hard-cap at N attempts, then mark failed and surface a different UI badge. N TBD.
- **Schema for KV blobs**: JSON-encoded value. Single record per key, atomic read-modify-write inside the worker (KV is eventually consistent but a single KV namespace serializes per key acceptably for this scale).

## Out of scope for v2.0

- Past-scan-date navigation / date picker.
- Freeform off-platform bet logging.
- Model config knobs in the UI (Kelly fraction, sport filters, min-edge floor).
- Multi-user team features. Single user today (Cloudflare Access scoped to one email), KV keying anticipates multi-user later.
- pick_history.json visualization. The 393 kB file is for ad-hoc model calibration, not user-facing UI.

## Discussion Log

- **2026-04-30 PM**: Q1 through Q7 answered in a one-at-a-time prompted interview. Contract locked at the level of "screens, data needs, actions, write-path semantics." Endpoint shapes are a suggestion, subject to backend confirmation during Phase 1 implementation. The doc moves to `[LOCKED]` and is the input to Phase 0.6 (database-schema-designer for KV keys) and Phase 0.7 (ADRs).
