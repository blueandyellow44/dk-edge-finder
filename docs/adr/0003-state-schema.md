# ADR 0003: Cross-device state schema in Workers KV

Status: **Accepted** (2026-04-30, Phase 0.6 of v2 rebuild)
Supersedes: nothing
Related: [`0001-stack.md`](0001-stack.md) (Vite + React + Hono), [`0002-auth.md`](0002-auth.md) (Cloudflare Access), [`backend-requirements.md`](../../.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md)

## Context

The DK Edge Finder v2 frontend needs cross-device state. Today the live site stores placements, sync queue, manual bets, and balance override in `localStorage`, so iPhone Safari and Mac Chrome are silos. The v2 fixes that by moving the same state into a Cloudflare Workers KV namespace so any signed-in device sees the same view.

The locked API contract (Phase 0.5, see `backend-requirements.md`) decided:
- Append-merge write semantics. Frontend POSTs single events; the worker reads the existing record, merges, writes back.
- Single-user today (Cloudflare Access scoped to `max.sheahan@icloud.com`), but key shape must allow more emails later without migration.
- Latest-scan-only display. The user does not navigate to past scan dates from the Picks tab. State records for older scan dates still exist (so Pending and Activity can show bets that haven't resolved yet).

This ADR defines the KV namespace name, key shapes, value blobs, write protocol, and migration path.

## Decision

### Namespace

One KV namespace, bound to the worker as `EDGE_STATE`. Created via `wrangler kv:namespace create EDGE_STATE`. Bound in `wrangler.jsonc` under `kv_namespaces`.

### Key shapes

Two record types, two key prefixes.

**Per-(user, scan_date) state record**
```
state:<email>:<scan_date>
```
Example: `state:max.sheahan@icloud.com:2026-04-30`.

**Per-user balance override record**
```
balance_override:<email>
```
Example: `balance_override:max.sheahan@icloud.com`.

### Email canonicalization

Always lowercase before keying. Cloudflare Access returns whatever case Google sent during the OAuth handshake, which varies. Worker middleware does:
```ts
const email = c.req.header('cf-access-authenticated-user-email')?.toLowerCase()
if (!email) return c.text('Unauthorized', 401)
```

No further encoding. Workers KV keys accept any UTF-8 byte. The `@` and `.` characters are safe in keys; they do not collide with the `:` separator we use.

### Scan_date format

ISO 8601 calendar date: `YYYY-MM-DD`. Matches the existing `data.json.scan_date` field exactly. Lexicographic sort equals chronological sort, so `list({ prefix: "state:" + email + ":" })` returns scan dates in chronological order with no extra logic.

### Value shape: state record

```ts
type StateRecord = {
  schema_version: 1
  email: string                // for ops sanity-check; redundant with the key
  scan_date: string            // YYYY-MM-DD
  placements: Placement[]
  sync_queue: SyncQueueEntry[]
  manual_bets: ManualBet[]
  updated_at: string           // ISO 8601 with timezone
}

type Placement = {
  key: string                  // "pick|event"
  action: "placed" | "skipped"
  dispatch_status: "ok" | "queued" | "failed"
  placed_at: string            // ISO 8601
  idempotency_key: string      // client-generated, dedupes inside placements[]
}

type SyncQueueEntry = {
  key: string                  // matches a Placement.key
  last_attempt_at: string
  attempt_count: number
  last_error: string | null
  idempotency_key: string
}

type ManualBet = {
  id: string                   // client-generated UUID
  sport: string
  event: string
  pick: string
  odds: string                 // American format, e.g. "+165"
  wager: number                // dollars
  outcome: "pending" | "win" | "loss" | "push"
  placed_at: string
  idempotency_key: string
}
```

### Value shape: balance_override record

```ts
type BalanceOverride = {
  schema_version: 1
  email: string
  amount: number               // dollars
  note: string                 // free text, e.g. "DK app balance $679.34 as of April 10"
  updated_at: string
}
```

### Write protocol (append-merge)

For every write, the worker:
1. Reads the existing record (or initializes an empty one if absent).
2. Applies the event:
   - Placements: dedupe by `idempotency_key`. If the key already exists in `placements[]`, it is a retry; do nothing extra. Otherwise append.
   - Sync queue: dedupe by `idempotency_key`. Replace the entry on retry (so `attempt_count` and `last_attempt_at` advance).
   - Manual bets: dedupe by `idempotency_key`. Append on first write; update outcome on later writes.
3. Sets `updated_at = new Date().toISOString()`.
4. Writes the merged record back via `EDGE_STATE.put(key, JSON.stringify(record))`.

Concurrency tolerance: for the single-user real usage (one device active at a time, occasional concurrent open), KV's eventual consistency window (a few seconds) is acceptable. Two concurrent worker requests racing on the same key fall back to last-write-wins on the array contents. The idempotency keys mean a duplicate event is never appended twice even if both writers see the same pre-merge state.

### List-by-prefix

Reading the user's full state across recent scan dates is supported via `list({ prefix: "state:" + email + ":" })`. This returns metadata only (keys + size). The worker then issues parallel `get()` calls for the keys it actually needs. We use this for Pending (which spans recent scan dates) and for any future Activity-by-date view.

We do not paginate by default; the `list` cursor exists if we ever need it. Daily scans for a year produce at most 365 keys per user, well under any KV list limit.

### TTL policy

No TTL. KV records are tiny (a state record with a full day of placements is well under 10 KB) and we want late-resolving bets to keep showing in Pending until manually resolved. If we ever need to cap retention, a separate scheduled worker can delete records older than N days.

### Schema versioning + migration path

Every value blob carries `schema_version: 1`. On future shape changes the worker reads the version on each access and either:
- Upgrades in place: read v1, transform to v2, write back. Self-healing as users hit endpoints.
- Or: ship a one-shot migration worker that lists all keys, reads, transforms, writes. Cloudflare Workers Cron Triggers can run this off-peak.

We will use the in-place upgrade pattern unless a migration is destructive. Schema versions are bumped only when a value field is renamed, removed, or has its semantic meaning changed.

## Consequences

### What we accept

- KV's eventual consistency. A write from iPhone may take a few seconds to appear on Mac. Acceptable for the Pending tab cadence.
- Read-modify-write race window. Two concurrent writes to the same key can lose one event's append (the idempotency check protects against duplicates but not against two distinct events writing simultaneously). For single user, the practical risk is essentially zero.
- One read + one write per event POST. Each costs one KV operation. Cloudflare's free tier is 100k reads/day and 1k writes/day; even heavy use stays well within limits.
- Email canonicalization is the worker's responsibility. Anywhere we read `cf-access-authenticated-user-email`, we lowercase before keying. Tests must cover this.
- The `email` and `scan_date` fields are duplicated in both the key and the value blob. Slight redundancy bought for ops sanity (KV blobs read in isolation are self-describing).

### What we deliberately do not get

- Multi-user atomic transactions. Not needed; each user's state is independent.
- Cross-user queries. Not needed; we do not join across users.
- Strong consistency. Not needed for the single-user case. If we ever go multi-user with shared state (a syndicate), we revisit Durable Objects.

### What we lose by not picking SQL (D1)

- SQL queries. We trade query power for simplicity. KV's only operations are `get`, `put`, `delete`, `list`. That is enough for the v2 access patterns.
- Joins across record types. We avoid them by composing state in the worker (read state record + read balance_override + compose response).

## Alternatives considered

### A. Cloudflare D1 (SQL on SQLite)

Pros: SQL queries, joins, transactions, indexes, schema migrations via DDL.
Cons: Heavier dev loop, more code in the worker, more migration ceremony for a single-user app. Our access patterns are all primary-key reads and one list-by-prefix. SQL buys nothing for that.

Decision: not chosen. Revisit if we go multi-user with shared state across users (e.g., a leaderboard or shared bankroll) where SQL queries become useful.

### B. Per-event KV keys instead of single-record-per-(user, scan_date)

Shape: `placement:<email>:<scan_date>:<idempotency_key>`, `manual_bet:<email>:<scan_date>:<id>`, etc.

Pros: No read-modify-write race (each event is its own atomic put). Cleaner write code.
Cons: Reading the Pending tab requires `list` + N parallel `get` operations every refresh. KV charges per `get`; on a busy day with 8 placements + 2 manual bets, every state read costs 10+ KV ops. Worse latency than one `get`.

Decision: not chosen. The R-M-W race is theoretical for single user. The cost of N reads per Pending refresh is real.

### C. Durable Objects

Pros: Strong consistency. One Object per user gives serialized read-modify-write with no race.
Cons: More expensive (Durable Objects bill differently from KV). Adds a stateful layer that complicates the dev loop. Overkill for single user.

Decision: not chosen. Reconsider if multi-user shared state ever lands.

### D. Storing state inside `data.json` (the static asset)

Decision: explicitly rejected. The Python model writes `data.json` on every cron tick and would clobber any user state we put there. The single biggest existing data-integrity rule (`bets[]` is sacred, see lessons.md 2026-03-18) exists to protect against this category of bug. The user's per-device state must live in a place the cron does not touch.

## Implementation notes (for Phase 1)

- KV namespace creation: `npx wrangler kv:namespace create EDGE_STATE`. Take the namespace ID, paste into `wrangler.jsonc` under `kv_namespaces`. Also create a `EDGE_STATE_PREVIEW` for `wrangler dev` if needed.
- Worker helper: `worker/lib/state.ts` exports `readState(email, scan_date)`, `writeState(email, scan_date, record)`, `appendPlacement(email, scan_date, p)`, `appendManualBet(email, scan_date, b)`, etc. Centralizes the read-modify-write logic so route handlers stay thin.
- Validation: every value blob round-trips through Zod schemas before write. Catches drift early. Schemas live in `shared/schemas.ts` so frontend and worker share types.
- Tests: in-memory KV stub for unit tests. The worker runtime ships one for `wrangler dev`; for unit tests we can use `@cloudflare/workers-types` or a hand-rolled `Map<string, string>` shim.
