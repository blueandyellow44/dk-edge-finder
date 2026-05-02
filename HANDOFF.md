# DK Edge Finder v2 Rebuild Handoff

Running session-handoff doc. Newest section on top. **Update this file as you work, not only at session end.** Update after every milestone, before any risky push or merge, and any time the context window fills up. A crash mid-session loses everything since the last write.

## Universal rules to read FIRST (every fresh session)

Before any project-specific work, the next thread must load these:

1. `~/.claude/CLAUDE.md` (Max's universal rules: no em-dashes, ask one prompted question at a time via `AskUserQuestion`, trust the user's eyes, do not wrap guesses in the cover of certainty, do not be lazy on visual bug investigations).
2. The approved plan at [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md).
3. This HANDOFF.md in full (you are reading it).
4. `dk-edge-finder/tasks/lessons.md` for model lessons (existing file with full history).
5. `lessons.md` at repo root for rebuild-specific lessons (currently empty template; populate as you work).

## What you are inheriting (2026-05-01 PM, Phase 3 slice 1 in flight)

A live Cloudflare Workers site at https://dk-edge-finder.max-sheahan.workers.dev/ that serves a 66 kB single-file vanilla `index.html` backed by a Python edge-finder model on GitHub Actions cron. **Phase 0 closed. Phase 1 closed (step 8 landed late in session 4 via Max's dashboard click-through). Phase 2 closed (75 vitest tests + Phase 1 step 9's wrangler-dev smoke + step 8's live-URL 302 verification combined to satisfy the quality gate; the live deploy of the new worker is deferred until Phase 3 cutover).** The combined verification rationale: Access intercepts → forwards `cf-access-authenticated-user-email` → worker reads it → returns the expected JSON. Both halves are proven separately (live URL → 302 redirect; wrangler dev with mocked header → all 9 v2 routes green); a live deploy would just stitch them together with no new information expected.

**Step 8 confirmed live as of 2026-05-01.** `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/api/me` returns `HTTP/2 302` with `location: https://sheahan.cloudflareaccess.com/cdn-cgi/access/login/dk-edge-finder.max-sheahan.workers.dev?...&redirect_url=%2Fapi%2Fme` and a `www-authenticate: Cloudflare-Access` header. Cloudflare Access is intercepting `/api/*` and redirecting unauthenticated callers to the team domain `sheahan.cloudflareaccess.com`. Application config: subdomain `dk-edge-finder`, domain `max-sheahan.workers.dev`, path `api/*`, single Allow policy `Allow Max` (rule: emails = `max.sheahan@icloud.com`), Identity providers = "Accept all" (OTP fallback; Google IdP deferred as a polish item).

**Side-effect to be aware of:** with Access on `/api/*`, the legacy single-file `index.html`'s Place button (which POSTs to `/api/place-bets`) will now fail closed. Access blocks the request before the worker sees it. This is the documented tradeoff in [`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md) and is acceptable while Phase 3 cutover is pending. To use the legacy site again, log into Cloudflare Access in the browser first (`https://dk-edge-finder.max-sheahan.workers.dev/` → Access → OTP); the resulting `CF_AppSession` cookie unblocks the Place button until Phase 3 retires the legacy site.

Phase 1 step status (sequence per the bottom of session 2 below):
- [x] **Step 1**: Vite + React + TS scaffolded into `frontend/` (Vite 8, React 19, TS 6).
- [x] **Step 2**: `@cloudflare/vite-plugin` v1.35.0 installed and wired.
- [x] **Step 3**: `worker/index.js` rewritten as `worker/index.ts` mounting Hono 4.12.16. Layout restructured: `package.json`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js` moved from `frontend/` up to the repo root. Vite uses `root: 'frontend'`. ADR 0001 amended to match.
- [x] **Step 4**: `EDGE_STATE` KV namespace created (id `7dca36afc97d4d86bebed2e2948d6e83`), bound in `wrangler.jsonc`, types regenerated. Skipped a separate preview namespace; the Cloudflare Vite plugin uses miniflare for local dev.
- [x] **Step 5**: `worker/middleware/auth.ts` shipped (per ADR 0002). Defined but not yet mounted in `worker/index.ts` at the time. Mount landed in step 6.
- [x] **Step 6**: Zod schemas in `shared/schemas.ts`, type re-exports in `shared/types.ts`, helper libs in `worker/lib/{picks,bankroll,state}.ts`, four read routes in `worker/routes/{me,picks,bankroll,state}.ts`. `requireAuth` mounted on each v2 route (`app.use('*', requireAuth)`). Legacy `/api/health` and `/api/place-bets` mount FIRST in `worker/index.ts` so they stay public until Access goes live in step 8. `npx tsc -b` clean.
- [x] **Step 7**: Write routes shipped. Request schemas added to `shared/schemas.ts` (`PlacementCreateRequestSchema`, `ManualBetCreateRequestSchema`, `SyncQueueRetryRequestSchema`, `BalanceOverrideRequestSchema`, `PlaceBetRequestSchema`, `PlaceBetResponseSchema`). State helpers extended (`removePlacement`, `removeManualBet`, `getBalanceOverride`, `upsertBalanceOverride`, `findSyncQueueEntry`); `upsertSyncQueueEntry` re-keyed from `idempotency_key` to `key` so retry attempts update one row instead of creating new ones. `worker/lib/dispatch.ts` added (GitHub `repository_dispatch` plus 24h-TTL idempotency cache via `dispatch:<email>:<idempotency_key>` KV keys). Five new routes: `state-placements` (POST + DELETE :key), `state-manual-bets` (POST + DELETE :id), `state-sync-queue` (POST /retry), `balance-override` (POST), `place-bet` (POST, singular, idempotent). Legacy `place-bets` (plural, no idempotency) untouched. `npx tsc -b` clean. A small Hono mount-order smoke (one-shot, deleted) confirmed `/api/state/placements` routes to the write subapp without firing stateApp middleware.
- [x] **Step 8**: Cloudflare Access policy live as of 2026-05-01 (session 4 late). Team domain `sheahan.cloudflareaccess.com`. Self-hosted application `dk-edge-finder` protecting `dk-edge-finder.max-sheahan.workers.dev/api/*`. Single Allow policy `Allow Max` with rule emails = `max.sheahan@icloud.com`. Identity providers = "Accept all" (OTP fallback for now; Google IdP deferred). The runbook at [`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md) is **stale for the new Cloudflare Zero Trust UI** (the dashboard moved from a single "Application domain" field to a destinations-per-application model with Subdomain/Domain/Path triplets). Polish item: rewrite the runbook so the next reader doesn't have to reverse-engineer it from screenshots.
- [x] **Step 9**: EMFILE fix landed. Root cause was NOT the asset upload size (`.assetsignore` does not affect the dev watcher); it was the dev watcher walking the entire repo because `wrangler.jsonc` had `assets.directory: "."`. Fixed by narrowing `assets.directory` to `public/` and creating three symlinks inside it pointing one level up at the actual served files (`index.html`, `data.json`, `bankroll.json`). The Python cron still writes to repo root unchanged; symlinks expose the writes transparently. macOS launchd's default per-process file-descriptor cap is 256 (visible via `launchctl limit maxfiles`), which is why the wide watch tree exhausted descriptors despite `ulimit -n` reporting 1M+. `.assetsignore` was added too as defense-in-depth (default-deny, allowlists only the three served files), which has the side benefit of stopping the public site from serving `pick_history.json` (535 KB of model calibration data, no purpose on the public URL). Live `wrangler dev` smoke now passes for all 9 v2 routes (read + write); see commit message for the round-trip details.

Branch `rebuild/v2-frontend` is ahead of origin (commits will increment after step 8/9 commits), not yet pushed. Live site unaffected.

**Dispatch cleanup shipped (2026-05-02 session 7):** Auto-dispatch chain fully retired. Frontend: `usePlacePickBet` + `useRetrySyncQueue` deleted from `mutations.ts`; `PositionsTab` + `PicksTab` both use `useMarkPickAsPlaced` now (manual placement, no GitHub `repository_dispatch`); `PendingTab` rewritten without queued-retries section. Worker routes deleted: `place-bet.ts` (singular), `state-sync-queue.ts`, `place-bets-legacy.ts` (legacy plural). Worker libs deleted: `dispatch.ts`. State helpers `upsertSyncQueueEntry` + `findSyncQueueEntry` dropped from `state.ts`. Schemas dropped: `PlaceBetRequestSchema`, `PlaceBetResponseSchema`, `SyncQueueRetryRequestSchema`. Workflow `.github/workflows/place-bets.yml` deleted (the `repository_dispatch` receiver and only consumer of `dispatch.ts`). Test file lost the dispatch-touching describes (10 tests) and the `vi.stubGlobal('fetch')` helper. The `sync_queue` field stays on `StateRecordSchema` for KV back-compat (existing records may carry entries; read-only via GET /api/state). One-line update note added to ADR 0002. `npx tsc -b` clean, `npm test` 92 / 92 → 82 / 82 across 3 files. Em-dash audit clean. NOT yet committed.

**Picks click-to-expand shipped (2026-05-02 session 6, slice 2):** Picks tab rows now expand on click to reveal three actions: `Mark as placed` (manual placement, no GitHub repository_dispatch — new `useMarkPickAsPlaced` mutation, drops the auto-dispatch chain Max wanted off), `Ignore` (rebadged Skip), `Place on DraftKings ↗` (opens `pick.dk_link` in a new tab; first time `dk_link` has been surfaced in the v2 SPA). Single-row expansion (clicking another row collapses the previous; lifted state into `PicksTab`). Expanded panel shows Market / Model / Implied / EV per $ / Start (formatted via new `formatStartTime` in `lib/format.ts`) plus the pick's `notes` block in a gold-bordered card. Acted-on rows render the existing badge and are NOT click-expandable. Smoke-tested end-to-end against wrangler-dev + miniflare KV: click expand → click `Mark as placed` → POST `/api/state/placements` 201 → query invalidation → row collapses with `Placed` badge. `npx tsc -b` clean, `npm test` 92/92. Frontend-only diff (5 files); the dispatch backend (`/api/place-bet` route, `worker/lib/dispatch.ts`, `place-bet.yml` GH Action) is still wired but now uncalled from the Picks UI; cleanup of those + the Pending tab's "queued retries" section is the natural follow-up. NOT yet committed.

**Phase 3 polish update (2026-05-02 session 6 below):** vitest coverage shipped for `worker/lib/activity.ts`. 17 new tests covering em-dash strip, odds coercion (string passthrough + numeric → `+165` / `-110` + null fallback), outcome filter and coercion (`pending` excluded, unknown coerced to pending then excluded, `win`/`loss`/`push` preserved), date-desc sort, wager/pnl coercion, sparse-bet defaults, and Zod schema validation (malformed/missing date throws via `z.iso.date()`). Test count is now 92 / 92 across 3 files. `npx tsc -b` still clean. Branch state unchanged: `main` is at `4bf4da1`, no commits made (Max gates commit timing). Note for resume: `/data.json` returns 302 to Access now (Access scope is `/*`, not `/api/*`); resume-prompt scripts that curl `/data.json` for JSON will need a `CF_AppSession` cookie or read the local file.

**Phase 3 slices 1 + 2 + 3 + 4 + 5 LIVE (2026-05-02 ~03:55 UTC, session 5 below):** v2 SPA deployed and serving at https://dk-edge-finder.max-sheahan.workers.dev/. `wrangler deploy` from rebuild/v2-frontend. Two real bugs hit and fixed in sequence during the live smoke; both documented below in the "Slice 5 deploy: what shipped + what I broke" section. Final live state: `/api/me` returns 302 to Access (worker hit), `/data.json` returns fresh cron data (2026-05-01, 7 picks, 62 bets), SPA loads at root.

**Phase 3 slices 1 + 2 + 3 + 4 update (2026-05-01 PM, session 5 below):** v2 SPA fully composed. All 5 tabs render real data: Picks, Pending, Activity, Positions, Account. New worker route `/api/activity` ships `data.json.bets[]` filtered to resolved + sorted date desc, with em-dash strip + odds normalization. New mutations: `useDeleteManualBet`, `useRetrySyncQueue`, plus the slice-2 set. Verified locally: Picks empty state + 8-game no-edge collapsible (today is 0 edges), Pending shows existing manual bet from KV with Remove button, Activity shows 62 resolved bets with color-coded WIN/LOSS and signed P/L, Positions shows empty state, Account roundtrips a balance-override save through KV with cross-component refetch. Branch is still 23 ahead of origin. `npx tsc -b` clean, 75/75 tests still pass, `npm run build` clean. Slice 5 (deploy + live smoke) is what's left.

---

## 2026-05-02 session 7 (Dispatch cleanup)

### Goal
Drop the auto-dispatch backend chain that became uncalled from the UI after session 6 slice 2 swapped Picks tab from `usePlacePickBet` to `useMarkPickAsPlaced`.

### Pre-flight
- `git stash list`: empty. `npx tsc -b`: clean. `npm test`: 92 / 92.
- Live URL still v2: `curl -sI .../api/me` returns 302 to `sheahan.cloudflareaccess.com`.
- `origin/cloudflare/workers-autoconfig` was 5 commits behind `origin/main` at session start (slice-2 had not mirrored yet; cron tick at 01 UTC will catch it up).
- Local `data.json`: `2026-05-02`, 8 picks, 62 bets.

### Scope changes (asked Max via AskUserQuestion)
- **Q1: Cleanup depth.** Original instruction said delete `worker/lib/dispatch.ts`, but `worker/routes/state-sync-queue.ts` imports from it and `useRetrySyncQueue` is its only caller. Max chose: also drop `state-sync-queue/retry` route + tests + state.ts helpers; keep the `sync_queue` field in the state-record schema for KV back-compat.
- **Q2: Legacy plural.** `worker/routes/place-bets-legacy.ts` has its OWN inline `repository_dispatch` (separate from `dispatch.ts`) firing the same `place-bets.yml` workflow. Max chose: full retirement. Drop the legacy plural route + its mount + the workflow.

### Decisions made
- **Kept `sync_queue` field on `StateRecordSchema`.** Existing KV records may carry entries from the retired chain. Field stays read-only via `GET /api/state`; no API surface mutates it. Avoids a schema-version bump and the migration a structural drop would imply.
- **Kept `useDeletePlacement` in mutations.ts.** PendingTab no longer imports it (was only used in the queued-retries section), but the export is harmless. A future tab may want it. Per "don't refactor beyond task" rule.
- **Updated `dispatch_status` comment in `PlacementCreateRequestSchema`** to call out that `'queued'` / `'failed'` are vestigial enum values now (back-compat with old KV records). The enum stays so old records still parse.
- **Trimmed two stale comments** during verification: the `Write routes (non-dispatch)` block in `worker/index.test.ts` (which referenced the now-deleted dispatch tests) and the `useMarkPickAsPlaced` doc comment in `mutations.ts` (which contrasted with the now-deleted `usePlacePickBet`).
- **Did NOT commit.** Max gates commit timing.
- **Did NOT touch `scripts/place_bets.py`.** The Python script is now orphaned (its only invoker was the deleted `place-bets.yml` workflow), but deleting it is a separate scope. Listed under "What's next" as optional follow-up.

### Files modified
- `frontend/src/api/mutations.ts` (rewrite: drop `usePlacePickBet`, `useRetrySyncQueue`, `ApiError` + `PlaceBetResponse` imports; trim stale comment on `useMarkPickAsPlaced`).
- `frontend/src/tabs/PendingTab.tsx` (rewrite: drop queued-retries section, `usePicks`, `useDeletePlacement`, `useRetrySyncQueue`, `Pick` import; simpler component with only the manual-bets section).
- `frontend/src/tabs/PositionsTab.tsx` (`usePlacePickBet` → `useMarkPickAsPlaced`; `onPlace` callback drops `pickIndex` arg).
- `worker/index.ts` (drop 3 route imports + 3 mounts: `place-bet`, `state-sync-queue`, `place-bets-legacy`; reflow comments).
- `worker/lib/state.ts` (drop `upsertSyncQueueEntry`, `findSyncQueueEntry`, plus `SyncQueueEntrySchema` + `SyncQueueEntry` imports).
- `shared/schemas.ts` (drop `PlaceBetRequestSchema`, `PlaceBetResponseSchema`, `SyncQueueRetryRequestSchema`; update `dispatch_status` comment).
- `shared/types.ts` (drop the three matching `import` + `export type` lines).
- `worker/index.test.ts` (drop 347 lines: comment block + `stubFetch` helper + `MockFetchResponse` / `RecordedFetchCall` types + the two dispatch-touching describes; drop `afterEach` and `vi` from vitest imports; trim `Write routes (non-dispatch)` section comment).
- `docs/adr/0002-auth.md` (one-line update note about the manual-only flip).
- `HANDOFF.md` (this entry + the bullet in the inheriting snapshot).

### Files deleted
- `worker/routes/place-bet.ts`
- `worker/routes/state-sync-queue.ts`
- `worker/routes/place-bets-legacy.ts`
- `worker/lib/dispatch.ts`
- `.github/workflows/place-bets.yml`

### Verification
- `npx tsc -b`: clean.
- `npm test`: 82 / 82 across 3 files (was 92 / 92; the 10 dropped = 5 from the place-bet describe + 5 from the sync-queue retry describe).
- Em-dash audit on the diff scope: clean. The two `—` matches in `worker/index.test.ts` are pre-existing fixture text + a test assertion that the strip works; not in this diff. HANDOFF.md em-dashes are exempt per the 2026-05-01 CLAUDE.md amendment.
- Orphan-reference grep across `frontend/src worker/ shared/` for `usePlacePickBet`, `useRetrySyncQueue`, `dispatchPlaceBet`, `stubFetch`, `'/api/place-bet'`, `'/api/state/sync-queue/retry'`: clean.

### What's next
1. **Commit if Max signals.** Two-commit shape:
   ```
   git add frontend/src/api/mutations.ts frontend/src/tabs/PendingTab.tsx \
           frontend/src/tabs/PositionsTab.tsx \
           worker/index.ts worker/lib/state.ts worker/index.test.ts \
           shared/schemas.ts shared/types.ts \
           docs/adr/0002-auth.md
   git rm worker/routes/place-bet.ts worker/routes/state-sync-queue.ts \
          worker/routes/place-bets-legacy.ts worker/lib/dispatch.ts \
          .github/workflows/place-bets.yml
   git commit -m "chore(dispatch): retire auto-dispatch chain"
   git add HANDOFF.md
   git commit -m "chore: HANDOFF session 7 (dispatch cleanup)"
   git pull --rebase origin main && git push origin main
   ```
2. **Confirm cron mirror catches up to slice 2 + slice 3** at next tick. Once `origin/cloudflare/workers-autoconfig` matches `origin/main`, hit the live URL and confirm `/api/place-bet`, `/api/state/sync-queue/retry`, and `/api/place-bets` all return 404 (auth-gated 404 since Access scope is `/*`, but no worker route).
3. **Remaining polish (Max picks):**
   - Rewrite `docs/cloudflare-access-setup.md` for the Zero Trust UI.
   - Set up Google IdP (currently OTP-only).
   - Balance-over-time graph in Account tab.
   - Delete `rebuild/v2-frontend` branch (local + origin).
   - Optionally drop `useDeletePlacement` mutation (no UI caller after this slice).
   - Optionally `git rm scripts/place_bets.py` (orphaned after `place-bets.yml` deletion).
   - Defer `worker/lib/normalize.ts` extract until a third consumer.

### If you just have one minute, do this
`cd ~/Betting\ Skill && npx tsc -b && npm test` → expect clean tsc + 82 / 82.

---

## 2026-05-02 session 6 (Phase 3 polish + Picks click-to-expand)

### Goal
Pick up Phase 3 polish backlog item 1 (vitest for `worker/lib/activity.ts`), then Max requested click-to-expand on Picks rows with three actions: mark as placed, ignore, place on DraftKings.

### Pre-flight
- `git stash list`: empty. `npx tsc -b`: clean. `npm test`: 75 / 75.
- Live URL still v2: `curl -sI .../api/me` → 302 to `sheahan.cloudflareaccess.com`. `/data.json` also returns 302 (Access scope is `/*`, as set late in session 5); resume-prompt curl for JSON body would need a session cookie. Local `data.json`: scan_date `2026-05-01`, 7 picks, 62 bets.

### Slice 1: vitest for activity (shipped + pushed)
Commits: `a8b4e16` (test) + `357e4d0` (HANDOFF, post-rebase onto cron). On `main`. Cron mirror to `cloudflare/workers-autoconfig` runs on next tick.

**`worker/lib/activity.test.ts` (NEW, 17 tests).** Mirrors `picks.test.ts` structure (same `makeEnv` helper; `minimalBet` fixture). Coverage:
- Em-dash strip in `sport`, `event`, `pick`, `final_score`.
- Odds string coercion: American string passthrough, `+165` from positive number, `-110` from negative number, `''` from null.
- Outcome handling: `win` / `loss` / `push` preserved, `pending` filtered out, unknown values coerced to `pending` (then filtered).
- Date-desc sort across mixed dates.
- Wager / pnl: numeric passthrough, non-numeric (`'$12.50'`, `'not-a-number'`) falls back to `0` (the activity normalizer is stricter than picks; it does NOT parse currency strings — picks does).
- Missing-field defaults: sparse bet with valid `date` + `outcome` fills string defaults; missing or non-array `bets` returns empty; all-pending returns empty.
- Schema validation: malformed date (`'not-a-date'`) and missing date (`undefined` → empty string) both throw via `ActivityResponseSchema.parse` (because `ResolvedBetSchema.date = z.iso.date()` rejects empty/invalid).

Test count: 75 → 92. Test files: 2 → 3 (added `worker/lib/activity.test.ts`). `npx tsc -b` clean.

### Decisions made
- **Did not extract `worker/lib/normalize.ts` yet.** Handoff polish item #3 says hoist once a third consumer wants `stripEmDash` / `coerceOddsString`. Current consumer count is 2 (picks + activity). Holding the extract until item #3 surfaces.
- **Did not commit.** Max gates commit timing; no auto-commit. Two-commit shape (code + HANDOFF) ready when Max signals.
- **Note on activity vs picks coercion difference:** `worker/lib/picks.ts` parses `'$11.41'` → `11.41` via `coerceNumberDollars`. `worker/lib/activity.ts` does NOT — it requires a number for `wager` and `pnl`, falling back to `0` otherwise. This is intentional: the cron writes `bets[]` with numeric P/L, and the looser pick coercion exists only because the legacy emit shape used `$`-prefixed strings. Captured this asymmetry in the wager/pnl test block; the next normalize.ts extract should preserve the divergence.

### Files modified
- `worker/lib/activity.test.ts` (new, untracked).
- `HANDOFF.md` (this entry + the polish-update line in the inheriting section above).

### Slice 2: Picks click-to-expand (working, not yet committed)

**Behavior.** Picks tab rows are now clickable when the user has not acted on them. Clicking expands a details panel under the summary row with three actions: `Mark as placed` (gold primary), `Ignore` (outlined), and `Place on DraftKings ↗` (green link, `target="_blank"` to `pick.dk_link`). Already-acted rows render the existing `Placed`/`Skipped`/`Queued` badge and are not click-expandable. Single-row expansion is enforced by lifting the expanded-key state into `PicksTab` (`useState<string | null>`); expanding row B collapses row A. The expanded summary row gets a gold-tint background and a 90deg-rotated chevron in the actions slot.

**Expanded panel contents.** A `<dl>` of metrics laid out via `grid-template-columns: repeat(auto-fit, minmax(140px, 1fr))`: Market, Model %, Implied %, EV / $ (3-decimal), Start (formatted via new `formatStartTime` in `lib/format.ts`). The pick's `notes` block, if non-empty, is rendered in a card with a 3px gold left border. Then the three action buttons below.

**New mutation: `useMarkPickAsPlaced`** (in `frontend/src/api/mutations.ts`). POSTs `{ key, action: 'placed', dispatch_status: 'ok', idempotency_key: crypto.randomUUID() }` to `/api/state/placements`. Distinct from `usePlacePickBet`, which fires the `/api/place-bet` GitHub `repository_dispatch` chain. Comment in code spells out the semantics: `dispatch_status: 'ok'` here means "no dispatch attempted, user marked manually" (mirrors the convention `useSkipPick` already uses).

**Auto-dispatch is now uncalled from the UI.** Per Max's choice ("Manual record only, drop auto-dispatch"), `PicksTab` no longer imports `usePlacePickBet`. The mutation function still exists in `mutations.ts`, the worker route `/api/place-bet` is still mounted, `worker/lib/dispatch.ts` and `.github/workflows/place-bet.yml` are untouched. Cleanup is the natural follow-up; see "What's next" below.

**Smoke test.** wrangler-dev (8787) + vite-dev (5173) both running. Loaded today's 8 picks (2026-05-02). Clicked pick #1 (MLS Orlando @ Inter Miami UNDER 3.5, 16.8% edge) — expanded with 5-metric dl, notes block ("Model (DRatings only): ORL 0.8, MIA 2.1..."), and 3 buttons. Inspected the DK link: `href` resolves to `https://sportsbook.draftkings.com/event/34057936?outcomes=0OU84525126U350_3`, `target="_blank"`, `rel="noopener noreferrer"`. Inspected chevron rotation: collapsed = `transform: none`, expanded = `transform: matrix(0, 1, -1, 0, 0, 0)` (= rotate 90deg). Clicked another pick, confirmed first auto-collapsed. Clicked `Mark as placed` on pick #8 (SERIE_A Genoa @ Atalanta OVER 2.5): network shows POST `/api/state/placements` → 201 Created → GET `/api/state` → 200 OK (TanStack Query refetch); pick #8 row collapsed and now shows the `Placed` badge. No console errors.

**Files modified (slice 2).**
- `frontend/src/components/PickRow.tsx` (rewritten as click-to-expand; props now include `isExpanded`, `onToggleExpand`, `onMarkPlaced`, `onIgnore`).
- `frontend/src/tabs/PicksTab.tsx` (lifted expanded-key state, swapped `usePlacePickBet` for `useMarkPickAsPlaced`, wired `onSuccess: () => setExpandedKey(null)`).
- `frontend/src/api/mutations.ts` (added `useMarkPickAsPlaced`).
- `frontend/src/lib/format.ts` (added `formatStartTime`).
- `frontend/src/styles.css` (added `.pick-item`, `.pick-row.clickable`, `.pick-chevron` + `.open` rotation, `.pick-details`, `.pick-metrics`, `.pick-metric` `dt`/`dd`, `.pick-notes`, `.pick-actions-expanded`, `.btn-dk` green variant; `.pick-row:last-child` border-removal moved to `.pick-item:last-child`).

**Slice 2 decisions made.**
- **dispatch_status: 'ok' for manual placements** (vs adding new `'manual'` enum value). Avoids a Zod schema change. Code comment notes the semantic. Acceptable because the badge UX doesn't distinguish manual vs auto-dispatched placements.
- **Lifted expansion state to PicksTab** (vs local state in PickRow). Lets us enforce single-row-expanded UX. State key is the same `placementKey(pick)` already used elsewhere.
- **Did NOT touch the Pending tab.** Pending shows queued retries (failed dispatches) + manual bets. With dispatch dropped from the UI, no new picks will queue, but existing queued items in KV are still rendered. Cleanup is a follow-up slice.
- **Did NOT remove dispatch infra.** `usePlacePickBet`, `/api/place-bet`, `worker/lib/dispatch.ts`, `.github/workflows/place-bet.yml`, `useRetrySyncQueue` are all intact. Removing them is a meaningful diff (touches worker tests + GH Actions); held for explicit confirmation.
- **Chevron glyph reuses `▸`** matching the no-edge-collapsible already in this file. CSS rotates 90deg when expanded. Visually consistent.
- **DK button is green (`--color-positive`)** rather than gold primary. Differentiates the external action ("you'll be leaving the SPA") from the local actions (gold = primary site action).

### What's next
1. **Commit slice 2 if Max signals.** Two-commit shape:
   ```
   git add frontend/src/components/PickRow.tsx frontend/src/tabs/PicksTab.tsx \
           frontend/src/api/mutations.ts frontend/src/lib/format.ts \
           frontend/src/styles.css
   git commit -m "feat(picks): click-to-expand row with mark-as-placed / ignore / DK link"
   git add HANDOFF.md
   git commit -m "chore: HANDOFF session 6 slice 2 (Picks click-to-expand)"
   git pull --rebase origin main && git push origin main
   ```
   The `git pull --rebase` is required because cron pushes regularly to main (4 commits dropped during slice 1 push).
2. **Cleanup slice (Max picks if/when):** drop the now-unused auto-dispatch chain.
   - Remove `usePlacePickBet` and `useRetrySyncQueue` from `frontend/src/api/mutations.ts`.
   - Remove the queued-retries section from `frontend/src/tabs/PendingTab.tsx`.
   - Remove `worker/routes/place-bet.ts` mount + the route file + the singular-vs-plural `/api/place-bet` distinction.
   - Remove `worker/lib/dispatch.ts` and the `dispatch:` KV cache helpers.
   - Remove `.github/workflows/place-bet.yml` (the GH Action that handles `repository_dispatch`).
   - Update `worker/index.test.ts` to drop the `vi.stubGlobal('fetch')` block for `/api/place-bet` dispatch. Remove the place-bet test cases.
   - Add a one-line note to ADR 0002 about the manual-only flip.
3. **Remaining polish (Max picks):**
   - Rewrite `docs/cloudflare-access-setup.md` for the Zero Trust UI.
   - Set up Google IdP (currently OTP-only).
   - Balance-over-time graph in Account tab.
   - Delete `rebuild/v2-frontend` branch (local + origin).
   - Defer `worker/lib/normalize.ts` extract until a third consumer.

### If you just have one minute, do this
`cd ~/Betting\ Skill && npx tsc -b && npm test` → expect clean tsc + 92 / 92. `cat .claude/launch.json` lists `wrangler-dev` (8787) and `vite-dev` (5173); start both via the preview tool, navigate to `localhost:5173`, click any Picks row to see the expansion. Click `Mark as placed` to write a placement to local miniflare KV (idempotent; safe). Production live URL still serves the previous build until slice 2 is committed and the cron mirror picks it up.

---

## 2026-05-01 session 5 (IN PROGRESS, Phase 3 slice 1 done)

### Goal
Phase 3 cutover, slice 1 of 5: replace the Vite welcome scaffold with the v2 SPA shell. Install TanStack Query, wire the read-side query layer against the locked backend contract, ship 5 tab placeholders against the legacy visual language. Slice 2+ fills tab content; this slice proves the architecture compiles and renders.

### Pre-flight
- `git stash list` empty.
- `git fetch origin`: `main` advanced (cron commits, `80052c6..1ef6f3b`); `rebuild/v2-frontend` is 23 ahead, 0 behind, no rebase needed.
- Inherited-state verification: `npm test` 75/75 in 185ms, `npx tsc -b` clean, `curl -sI .../api/me` returns 302 to `sheahan.cloudflareaccess.com`. State holds, ready to build on.

### Slice 1 (foundation): what shipped

**Dep added.** `@tanstack/react-query` (v5 line). 2 new packages after dedup, 0 vulnerabilities.

**`tsconfig.app.json`.** `include` extended from `["frontend/src"]` to `["frontend/src", "shared"]` so the frontend can `import type` from `shared/types.ts`. Worker tsconfig already had `shared/`; this brings the app tsconfig in line.

**Files written under `frontend/src/`.**
- `styles.css` — consolidated, hand-rolled. Legacy palette extracted from the live `index.html` (lines 9-300): gold accent `#c9a633`, gold hover `#b8952a`, gold tint `#fdf8e8`, header bg `#111`, secondary bg `#1a1a1a`, body bg `#f0f0f0`, card `#fff`, positive `#00a651`, negative `#cc0000`, warning `#996600` on `#fff3cd`, pending row `#fffef5`, tabs bg `#fafafa`, borders `#eee`/`#f2f2f2`. Inter font, 1100px container, 52px sticky header, UPPERCASE tabs with gold underline. `.btn`, `.btn-primary`, `.btn-outline`, `.btn-sm` carried over verbatim from legacy so slice 2 has them ready. Transaction-row and position-row classes are intentionally NOT yet here; slice 2 adds `.tx-*` and slice 4 adds `.pos-*`.
- `api/client.ts` — fetch helper. `apiGet<T>`, `apiPost<T>`, `apiDelete`. `ApiError extends Error` with `status` and `body`. `credentials: 'same-origin'` so the `CF_AppSession` cookie rides on every call.
- `api/queries.ts` — TanStack Query read hooks. `useMe`, `usePicks`, `useBankroll`, `useStateRecord`. Types come from `shared/types`. `useMe` has 5min stale time; the others use the global default (30s).
- `components/Header.tsx` — sticky header with brand mark, avatar (image when `picture_url`, otherwise email-initial fallback), email text, sign-out link to `/cdn-cgi/access/logout`. Avatar wrapper has `aria-hidden="true"` so screen readers don't announce the redundant initial.
- `components/TabBar.tsx` — `<nav role="tablist">` with 5 `<button role="tab" aria-selected>`. Tabs render from a passed-in array so `App.tsx` owns the canonical TAB list.
- `tabs/PicksTab.tsx`, `PendingTab.tsx`, `ActivityTab.tsx`, `PositionsTab.tsx`, `AccountTab.tsx` — placeholders that name the tab and which slice wires it.

**Files replaced.**
- `frontend/index.html` — inline gold-on-black favicon (data: URL, matches the legacy site's), Inter font import (preconnect + stylesheet link), title "Edge Finder".
- `frontend/src/main.tsx` — wrapped App in `<QueryClientProvider>`. QueryClient defaults: `staleTime: 30_000`, `refetchOnWindowFocus: true`, `retry: 1`.
- `frontend/src/App.tsx` — AppShell. Sticky header + tab bar + tab panel. `activeTab` is a single `useState<TabId>`. `TabId` is exported from `App.tsx` and consumed via `import type` in `TabBar.tsx` (erased at compile time, no runtime cycle).

**Files deleted.**
- `frontend/src/App.css`, `frontend/src/index.css` — replaced by `styles.css`.
- `frontend/src/assets/` (hero.png, react.svg, vite.svg) — Vite welcome assets.
- `frontend/public/icons.svg`, `frontend/public/favicon.svg` — Vite welcome icons sprite + Vite logo favicon. The new favicon is inline in `index.html`.

**`.claude/launch.json`.** Added a `vite-dev` configuration so the SPA can be previewed locally via `npm run dev` (Vite dev server with `@cloudflare/vite-plugin`) on port 5173 in addition to the existing `wrangler-dev` entry on 8787. Both `~/Betting Skill/.claude/launch.json` and `~/DK3/.claude/launch.json` updated (the preview tool reads the latter because the session's primary CWD is DK3). Wrangler-dev still serves the legacy `index.html` from `public/` symlinks; the v2 SPA is served by Vite dev until cutover wires `assets.directory` to `frontend/dist`.

### Verification

- `npx tsc -b` — clean exit 0.
- `npm test` — 2 files / 75 tests passing in 150ms. No regression on the worker side.
- `npm run build` — Vite + tsc clean. Output: 227.41 kB JS (70.78 kB gzip), 3.28 kB CSS (1.19 kB gzip), 0.96 kB HTML. Built in 421ms.
- `npm run dev` via preview tool, http://localhost:5173. Verified:
  - Header renders: "DK EDGE FINDER" with gold "EDGE", avatar circle (showing "?" because `/api/me` 401s in dev without an Access header), "..." for email placeholder, "Sign out" link.
  - Tab bar shows all 5 tabs UPPERCASE, Picks active with gold underline.
  - Clicking ACCOUNT swaps the panel content and moves the gold underline. Tab navigation works.
  - Console: clean. Only Vite HMR connect messages and the React DevTools nag. No app errors.
  - Accessibility tree: `banner` for header, `tablist` with 5 `tab` children, `main` for content area, `aria-selected` reflects active state, avatar `aria-hidden`.

### Slice 2 (Picks tab): what shipped

**Dev wiring deviation, recorded.** The original plan was to use `npm run dev` (vite dev with `@cloudflare/vite-plugin`) for a single-port HMR + worker dev loop. Empirically that didn't work in v1.35.0 of the plugin — `/api/*` returned 404 from vite dev with no worker activity. wrangler dev on 8787 served `/api/picks` correctly (200 with the mock email header), so the dev loop is now: run `wrangler dev` (port 8787) AND `vite dev` (port 5173) in parallel, with vite proxying `/api/*` to 8787. `vite.config.ts` got a `server.proxy` block to make this clean. The cloudflare plugin stays in vite.config.ts because the production `npm run build` step still uses it (it generates `frontend/dist/wrangler.json` which `wrangler deploy` consumes at cutover). Worth revisiting at slice 5: with the assets-directory swap in cutover, wrangler dev can serve both pieces together for a closer-to-prod dev loop.

**Files added under `frontend/src/`.**
- `lib/format.ts` — `formatMoney`, `formatSignedMoney` (with leading sign for stats), `formatPercent`, `formatAgo` (Xs/Xm/Xh/Xd ago). Uses `Intl.NumberFormat('en-US')` for thousands separators.
- `api/mutations.ts` — three TanStack Query mutations:
  - `usePlacePickBet({ pickIndex, key })` — generates a single `crypto.randomUUID()`, calls `POST /api/place-bet` with that idempotency_key. On 502 (dispatch failed), catches the ApiError and records `dispatch_status: 'queued'`. Otherwise records `'ok'`. Then calls `POST /api/state/placements` (same idempotency_key) so the worker dedupes if a retry sends the same key. Invalidates `['state']` on success.
  - `useSkipPick({ key })` — `POST /api/state/placements` with `action: 'skipped'`, `dispatch_status: 'ok'`, fresh idempotency_key. No dispatch.
  - `useDeletePlacement({ key })` — `DELETE /api/state/placements/<urlencoded-key>`. Wired but not yet used by any UI; held for slice 4 (Pending tab cancel).
- `components/BalanceCard.tsx` — sidebar card. Loading: `$...`. Error: "Failed to load." Success: BALANCE header, "AVAILABLE" label, big tabular `$XXX.XX` (with `.dollar` span for the legacy small-dollar-sign treatment), and 3 stats: Profit (signed, green/red), Lifetime ROI (green/red), W-L-P record (using `lifetime.wins-losses-pushes`).
- `components/PickRow.tsx` — one pick row. 6-column grid: rank, sport+pick+event multiline, odds, edge%, wager$, actions. Edge color-coded by tier (HIGH=green, MEDIUM=amber, LOW=brown). Actions area is a Place + Skip button pair when no placement exists, or a single colored badge ("Placed" green / "Skipped" gray / "Queued" amber) when one does. Buttons disable while ANY mutation is pending across the table (one click at a time UX).

**Files updated.**
- `frontend/src/api/client.ts` — added `devHeaders` const that injects `cf-access-authenticated-user-email: max.sheahan@icloud.com` only when `import.meta.env.DEV`. The conditional erases to `{}` in production builds, so the header never ships. In production, Cloudflare Access strips client-sent `cf-*` headers and re-injects its own verified value, so even if the conditional somehow leaked the header could not be trusted.
- `frontend/src/tabs/PicksTab.tsx` — full implementation. Reads `usePicks()`, `useStateRecord()` for the placement-by-key Map, fires `usePlacePickBet` and `useSkipPick`. Renders: scan-meta dark banner with `scan_subtitle` + relative `scan_age_seconds`, a `stale` modifier when age > 12h. Empty state ("No edges today" + cron explanation) when `picks.length === 0` (today's case). Pick list otherwise. Then the no-edge collapsible at the bottom when `no_edge_games.length > 0`. The collapsible uses native `<details>` / `<summary>` with a custom rotating `▸` triangle so we don't import a chevron icon library for one component.
- `frontend/src/App.tsx` — replaced the single-column shell with a 2-col grid. `<main className="page">` now has `.page-main` (tabs + tab panel) and `.page-side` (BalanceCard) children. Sidebar shows on every tab, not just Picks (matches legacy behavior).
- `frontend/src/styles.css` — added: `.page` 2-col grid (1fr 280px) with `@media (max-width: 880px)` collapse to single column, `.card`/`.card-header`, `.balance-section`/`.balance-amount`/`.balance-stats`/`.balance-stat-*`, `.scan-meta`/`.scan-meta-age`/`.scan-meta.stale`, `.tx-list`/`.tx-header`, `.pick-row`/`.pick-rank`/`.pick-sport`/`.pick-text`/`.pick-event`/`.pick-odds`/`.pick-edge`(.high/.medium/.low)/`.pick-wager`/`.pick-actions`, `.pick-badge`(.placed/.skipped/.queued), `.no-edge`/`.no-edge-summary` (with `::before` rotation on `[open]`)/`.no-edge-row`/`.no-edge-event`/`.no-edge-line`/`.no-edge-reason`. Also added `.btn:disabled` styling. `.tab-panel` got `overflow: hidden` so the dark scan-meta clips inside the panel's bottom-rounded corners.
- `vite.config.ts` — added `server.proxy: { '/api': 'http://localhost:8787' }` so vite dev (5173) hands `/api/*` requests to wrangler dev (8787). Dev-only; `vite build` does not use `server.proxy`.
- `.claude/launch.json` (both `~/Betting Skill/.claude/launch.json` and `~/DK3/.claude/launch.json`) — added a `vite-dev` configuration on port 5173 alongside the existing `wrangler-dev` on 8787.

### Slice 2 verification

- `npx tsc -b` — clean exit 0.
- `npm test` — 75/75 still passing in 163ms. No worker-side regression.
- `npm run build` — 76 modules transformed, 236.07 kB JS (72.89 kB gzip), 7.60 kB CSS (2.07 kB gzip). Built in 69ms.
- Live SPA preview at `http://localhost:5173` (vite dev) backed by `http://localhost:8787` (wrangler dev) with `/api/*` proxied:
  - **Header**: brand, `M` avatar initial (because `picture_url` is null without a Google IdP), `max.sheahan@icloud.com`, Sign out link.
  - **Picks tab**: dark scan-meta banner reads "Thursday, April 30, 2026 - MLB (11), NBA (3), NHL (2)" — em-dash from `data.json`'s `scan_subtitle` is verifiably stripped to a hyphen by the worker normalizer. Empty state ("No edges today / The latest scan found no profitable bets. The next cron tick refreshes data.") renders.
  - **No-edge collapsible**: "▸ NO-EDGE GAMES (8)" expands to ▼ showing all 8 rejected games (NBA NY @ ATL, NBA BOS @ PHI, NBA DEN @ MIN, NHL DAL @ MIN, NHL EDM @ ANA, MLB HOU @ BAL, plus 2 below the fold) with sport badges, line text, and "Edge below 3% threshold" reason.
  - **BalanceCard sidebar**: AVAILABLE `$700.00` (the override left in miniflare KV by session 4 step 9's smoke), PROFIT `+$179.34` (green), LIFETIME ROI `35.9%` (green), RECORD `37-21-1`. Numbers pulled from `bankroll.json` via the worker's `getBankrollResponse`.
  - **2-col layout**: at >= 880px viewport the BalanceCard sits to the right of the tab panel; below 880px it stacks below.
  - **Console**: clean. Only Vite HMR connect messages and the React DevTools nag. No fetch errors, no React warnings.
  - **Tab navigation**: clicking ACCOUNT (slice 1 verification) and switching back to PICKS keeps state correct.

### Where this leaves us
- Slices 1 + 2 functionally complete. Picks tab renders today's empty case and the 8-game no-edge section against real data.
- The live data on hand:
  - `data.json` reflects 0 picks + 8 no-edge games for 2026-04-30 (the playoff-discount calibration is doing its job).
  - `bankroll.json` reflects $679.34 + 37-21-1 lifetime + 35.9% ROI; the displayed `$700.00 available` is from the `balance_override` KV record left over from step 9's smoke.
- No commits yet for slices 1 + 2. Per the established two-commit pattern, code commit + HANDOFF update commit are held until Max signals to ship.
- Branch is still 23 ahead of origin (no new commits this session).

### Slice 3 (Account tab): what shipped

**`api/mutations.ts`.** Added `useSetBalanceOverride({ amount, note })` calling `POST /api/balance-override` and invalidating `['bankroll']` on success.

**`components/BalanceOverrideForm.tsx`.** Local-state form (amount string + note string) pre-filled from `bankroll.balance_override` when present. Submit handler: parses amount via `Number(...)`, no-ops on `!Number.isFinite`, fires the mutation. Status row shows "Saving..." while pending, "Saved." (green) on success, "Save failed." (red) on error. Help text below the inputs shows `Last updated <toLocaleString>` when an override already exists. Submit button disabled while pending or when amount is blank.

**`tabs/AccountTab.tsx`.** Three sections separated by inset borders:
- **Identity**: 56px gold-on-dark avatar (image when `picture_url` present, email-initial fallback), email, "Signed in via Cloudflare Access" subtitle, outline Sign-out button (links to `/cdn-cgi/access/logout`).
- **Balance override**: just the form.
- **Lifetime stats**: 3-column grid (collapses to 2 cols below 600px) with 6 stat cards: Bets, Wins, Losses, Pushes, Profit (signed + green/red), ROI (signed + green/red). Same `lifetime` data the BalanceCard sidebar uses, just the full breakdown.

**`styles.css`.** Added `.account-section` (with last-child border removal), `.account-section-title`, `.identity-row` flex with `.identity-avatar` (56px), `.identity-info`, `.identity-email` (16px, word-break), `.identity-sub`. Form: `.account-form` 12px gap flex column, `.account-form-row`, `.account-form-label` (uppercase, 11px), `.account-form-input` (Inter, tabular-nums, gold focus ring with `box-shadow: 0 0 0 2px rgba(201, 166, 51, 0.2)`). Status: `.account-form-status.success` / `.error`. Stats grid: `.stats-grid` (3 cols → 2 cols at 600px), `.stat`, `.stat-label`, `.stat-value` (with positive/negative variants).

### Slice 3 verification

- `npx tsc -b` — clean exit 0.
- `npm test` — 75/75 passing.
- `npm run build` — 77 modules, 240.05 kB JS (73.58 kB gzip), 9.84 kB CSS (2.40 kB gzip), built in 52ms.
- Live SPA preview at `http://localhost:5173` (vite dev) backed by `http://localhost:8787` (wrangler dev). Verified Account tab:
  - **Identity**: 56px gold-on-dark "M" avatar, `max.sheahan@icloud.com`, "Signed in via Cloudflare Access", outline "Sign out" button.
  - **Balance override pre-fill**: amount `700` and note `smoke test` (the values left over from session 4 step 9), with "Last updated 4/30/2026, 4:09:03 PM" help text.
  - **Lifetime stats**: Bets 43, Wins 37, Losses 21, Pushes 1, Profit `+$179.34` green, ROI `35.9%` green. The 43-vs-37+21+1=59 mismatch is from the model side (bets count differs from resolved-bet sum); not a v2 frontend concern, just rendering what `bankroll.json` carries.
  - **Save flow tested**: changed amount to `725.50`, clicked Save override. Form showed "Saved." (green), help text updated to "Last updated 5/1/2026, 6:53:38 PM", and the BalanceCard sidebar refetched and re-rendered to `$725.50`. Cross-component invalidation flow (`invalidateQueries(['bankroll'])` → both BalanceCard and BalanceOverrideForm refetch) proven.
  - **Console**: no errors at `level: 'error'` filter.

### Where this leaves us
- Slices 1 + 2 + 3 functionally complete and verified end-to-end with real worker data.
- Picks tab and Account tab are "real". Pending, Activity, Positions remain placeholders.
- KV state in miniflare currently holds the `725.50 / smoke test` override from this session's verification. Production KV is untouched (no deploy).
- No commits this session. The two-commit shape is held until Max signals to ship.
- Branch is still 23 ahead of origin.

### Slice 4 (Pending, Activity, Positions tabs): what shipped

**Worker side.**
- `shared/schemas.ts` — added `ResolvedBetSchema` (date, sport, event, pick, odds, wager, outcome win|loss|push|pending, pnl, final_score) and `ActivityResponseSchema { bets: ResolvedBet[] }`.
- `shared/types.ts` — added `ResolvedBet`, `ActivityResponse` exports.
- `worker/lib/activity.ts` — `getActivityResponse(env)` reads `data.json` via the existing `loadDataJson(env)` helper from `worker/lib/picks.ts` (no refactor; just an import). Has its own small `stripEmDash`, `coerceOddsString`, `coerceOutcome`, `normalizeResolvedBet` helpers (duplicated from picks.ts because the picks helpers are file-private; if a third consumer ever shows up, extract to `worker/lib/normalize.ts`). Filters out `outcome === 'pending'` so the Activity tab is strictly "resolved" history. Sorts by `date` desc (lex sort works for ISO YYYY-MM-DD).
- `worker/routes/activity.ts` — `GET /` mounted under `requireAuth`, returns `ActivityResponseSchema.parse(...)` payload.
- `worker/index.ts` — mounts `/api/activity` after the existing v2 routes. Order doesn't matter for this route (no `/api/activity/...` sub-paths), but kept consistent.

**Worker tests deliberately not added this slice.** The bets[] data has known shape mismatches between scan dates (some entries have `odds` as number, others as string; some have `decimal_odds`/`edge` extras, others don't) that would require a fixture-style test setup. The normalizer absorbs all of this, but it's worth a Phase-2-style vitest pass in a follow-up. 75/75 existing tests still pass; the new route is exercised by the live preview.

**Frontend side.**
- `api/queries.ts` — added `useActivity()` hitting `/api/activity`.
- `api/mutations.ts` — added `useDeleteManualBet({ id })` (DELETE `/api/state/manual-bets/:id`, encoded) and `useRetrySyncQueue({ key })` (POST `/api/state/sync-queue/retry` with a fresh idempotency_key per click).
- `components/PositionRow.tsx` — new component. Same data shape as `PickRow` but two-tier layout: a `.position-summary` grid row identical to PickRow, then a `.position-detail` panel below with Market / Implied / Model / Confidence / Sources / Notes. Sources and Notes only render when present.
- `tabs/PositionsTab.tsx` — full impl. Reuses `usePicks()` and the `usePlacePickBet`/`useSkipPick` mutations. Empty state for today (0 picks).
- `tabs/PendingTab.tsx` — full impl. Two sections: "Queued retries" (placements with `dispatch_status === 'queued'`) and "Manual bets" (manual_bets with `outcome === 'pending'`). Looks up pick details by `key` against `usePicks()` to render context; falls back to splitting the key on `|` if the pick has rolled off the latest scan. Per row: Retry Now + Cancel for queued, Remove for manual bets.
- `tabs/ActivityTab.tsx` — full impl. Header row + scrolling list. Per row: date, sport badge, pick + event + final_score (joined with `•`), wager, odds, color-coded outcome, signed P/L (green/red).

**Styles added.** All in `frontend/src/styles.css`:
- `.position-list`, `.position-row`, `.position-summary` (6-col grid), `.position-detail` (2-col grid below summary, light-bg block, indented past the rank column on desktop, single-col + un-indented at <600px), `.position-detail-row`, `.position-detail-label`, `.position-detail-value`.
- `.pending-list`, `.pending-section`, `.pending-section-title`, `.pending-row` (flex layout: info | meta/badge | actions), `.pending-row-info`, `.pending-row-pick`, `.pending-row-event`, `.pending-row-meta`, `.pending-row-actions`.
- `.activity-list`, `.activity-header`, `.activity-row` (6-col grid: 90/1fr/80/80/80/90), `.activity-date`, `.activity-wager`, `.activity-odds`, `.activity-outcome` (.win/.loss/.push/.pending), `.activity-pnl` (.positive/.negative).

### Slice 4 verification

- `npx tsc -b` — clean exit 0.
- `npm test` — 75/75 still passing in 172ms.
- `npm run build` — 78 modules, 247.48 kB JS (74.57 kB gzip), 12.84 kB CSS (2.77 kB gzip), built in 56ms.
- Live preview at vite dev (5173) + wrangler dev (8787 with /api proxy):
  - **Activity tab**: 62 resolved bets render. Top rows are 2026-04-08 (latest resolved date in `data.json.bets[]`). Sport badges (MLB/NHL/UCL/NBA), pick + event + final_score on the second line, wager `$13.50` right-aligned, odds centered, outcome WIN/LOSS uppercase color-coded, P/L `+$22.28` (green) or `-$13.50` (red) right-aligned. Sort confirmed: `2026-04-08 > 2026-04-08 > ...` descending.
  - **Pending tab**: shows the existing manual bet left over from prior smoke (`NBA OVER 212.5 BOS @ PHI -110 • $12.50` with Remove button under "MANUAL BETS (1)" section). No queued placements section visible (no queued state in current KV).
  - **Positions tab**: empty state ("No positions today / The latest scan found no profitable bets.") because today's `picks[]` is empty.
  - **Tab nav**: only one tab gold-active at a time (verified via `getComputedStyle(tab).color` returning `rgb(201, 166, 51)` only for the active tab; muted `rgb(136, 136, 136)` for the others).
  - **Console**: clean, no errors.

### Where this leaves us
- All 5 tabs fully functional. The v2 SPA is feature-complete against the locked backend contract for v2.0.
- 1 missing piece for v2.0: live deploy. Slice 5 is the final mile.
- Worker bundle size: 247 kB JS / 75 kB gzip. Reasonable for the feature set.
- KV state in miniflare currently has: `725.50 / smoke test` balance override and 1 leftover manual bet from prior tests. Production KV is untouched (no deploy this session).
- No commits this session. Two-commit shape held until Max signals.
- Branch is 23 ahead of origin.

### Slice 5 (deploy + live smoke): what shipped + what I broke

**File system changes for the cutover.**
- `wrangler.jsonc` `assets.directory` stays at `"public"` (initially I tried flipping to `"frontend/dist"` but reverted: `frontend/dist/` is gitignored, so Cloudflare's auto-deploy from the `cloudflare/workers-autoconfig` branch wouldn't see it).
- `public/index.html` — replaced the legacy symlink with `frontend/dist/index.html` (the SPA entry).
- `public/assets/` — copied from `frontend/dist/assets/` (CSS + JS bundles).
- `public/.assetsignore` — copied from `frontend/dist/.assetsignore` (excludes `wrangler.json`, `.dev.vars` from being served).
- `public/wrangler.json` — copied from `frontend/dist/wrangler.json` (Cloudflare plugin output, not served thanks to `.assetsignore`).
- `public/data.json` and `public/bankroll.json` — symlinks to repo-root files **kept as-is**, so the cron's repo-root writes still surface live.
- `frontend/public/data.json` and `frontend/public/bankroll.json` — short-lived symlinks added then removed during the flip-flop. Net change zero.

**Bug 1 (APIs returning SPA HTML, caught by Max in live use).** With `not_found_handling: single-page-application` on the assets binding, ANY non-matching path falls back to `/index.html` BEFORE the worker is reached. `/api/me`, `/api/picks`, etc. all returned the SPA HTML, which the React app then tried to JSON.parse and threw "Failed to load" on every tab. Fixed by adding `run_worker_first: ["/api/*"]` to the assets config:

```jsonc
"assets": {
  "directory": "public",
  "binding": "ASSETS",
  "not_found_handling": "single-page-application",
  "run_worker_first": ["/api/*"]
}
```

This tells Cloudflare: for `/api/*` paths, skip the assets dispatcher and run the worker. All other paths use the assets-first behavior with SPA fallback for client-side routing. Verified after re-deploy: `curl -sI .../api/me` returns 302 to `sheahan.cloudflareaccess.com` (worker hit, Access redirected unauth user). `curl .../random-spa-route` still returns 200 SPA HTML.

**Bug 2 (stale data.json deployed, caught by me during post-deploy curl).** Pre-deploy, the live `/data.json` served `scan_date: 2026-05-01, 7 picks` (origin/main's view, served by the cron's auto-deploy). My deploy from `rebuild/v2-frontend` uploaded my LOCAL `data.json`, which was `scan_date: 2026-04-30, 0 picks` because my rebuild branch never pulled origin/main's cron commits. The deploy regressed the live data by one cron tick. Fixed surgically with `git checkout origin/main -- data.json bankroll.json` (no rebase, just grabbed those two files), then re-deployed. Verified: `/data.json` now serves `2026-05-01, 7 picks, 62 bets`.

**Open follow-up (not addressed this session): cron auto-deploy will revert this.** The Cloudflare auto-deploy mechanism reads the `cloudflare/workers-autoconfig` branch (a mirror of `main`). My deploys from `rebuild/v2-frontend` are NOT mirrored to that branch. When the next cron tick runs (game-scan / morning-scan / resolve-bets), it pushes to `main` + mirrors to `workers-autoconfig`, and Cloudflare auto-deploys main's view, which still has the OLD `public/index.html` symlink to the legacy SPA. **This means: the v2 deploy WILL be reverted at next cron tick (next is game-scan at 04 UTC, ~5 min after deploy).** Mitigation: merge `rebuild/v2-frontend` into `main` and push, then cron auto-deploys carry the v2 forward. That merge is held until Max signals ready (per the established two-commit pattern).

### Live deploy verification

- Version IDs: `9b68279d-d8ac-4ebb-b597-873a7ffa49ec` (initial, broken APIs), `c83765fa-58fb-45ce-a3d4-4d0da5570705` (run_worker_first fix), `e6901079-06fa-4b53-aaaa-b2e50eab3741` (fresh data.json).
- `curl -sI .../api/me` → 302 to `sheahan.cloudflareaccess.com/cdn-cgi/access/login/...?redirect_url=%2Fapi%2Fme`.
- `curl -sI .../api/picks` → 302 to Access.
- `curl .../` → SPA HTML (Edge Finder title, Vite-built script + style refs).
- `curl .../some-random-spa-route` → 200 SPA HTML (SPA fallback for client-side routing intact).
- `curl .../data.json` → `scan_date: 2026-05-01, 7 picks, 62 bets`. Fresh.
- Browser SPA + curl with `CF_AppSession` cookie: pending Max's confirmation in this session.

### Where this leaves us
- Slice 5 deploy is technically live but at risk of cron auto-revert. Real fix needs rebuild-branch merge to main.
- All 5 tabs ship in this version. Picks tab will render today's 7 edges (not the 0 my local branch knew about).
- KV state in production is what production already had (untouched by the deploy; the worker writes to KV at runtime, not at deploy time).
- No commits this session. Two-commit shape held; merging to main is the natural next step.

### What's next (continue here on resume)

1. **Land + push rebuild/v2-frontend → main before next cron-induced revert.**
   - This requires committing all the slice 1-5 work. Sub-decisions: one big commit, or commit-per-slice. The `commit-work` skill or just `git add -p` + iterative commits.
   - After commits land: `git checkout main && git merge rebuild/v2-frontend` (or `--ff-only` if rebuild was rebased onto current main first), then `git push origin main`. The push triggers cron's mirror to `cloudflare/workers-autoconfig` on next tick, which then deploys the v2 stably.
   - Or as a faster mitigation: `git push origin main:cloudflare/workers-autoconfig --force-with-lease` directly, immediately syncing the deploy branch. Risky if Cloudflare bot has pushed there since last sync.
2. **OTP-log-in via browser**, then `curl --cookie "CF_AppSession=..." .../api/me /api/picks /api/bankroll /api/state /api/activity` to confirm v2 routes return their JSON shapes against real Cloudflare KV (not miniflare). This closes the deferred Phase 2.3 live smoke.
3. **Polish, deferred items**:
   - Vitest for `worker/lib/activity.ts` (mirrors `picks.test.ts`).
   - Extract shared normalizer helpers to `worker/lib/normalize.ts` once a third consumer wants `stripEmDash` / `coerceOddsString`.
   - Rewrite `docs/cloudflare-access-setup.md` for the new Cloudflare Zero Trust UI.
   - Set up Google IdP (currently OTP-only).
   - Repo-root `.assetsignore` is now inactive (it was for `assets.directory: "."`); leave or delete.

### What's next (alternative path if continuing without merge to main)

1. **Slice 5 (build + deploy + live smoke).** Sequence:
   - `npm run build` → `frontend/dist/` populated.
   - **Decision point**: legacy `index.html` fate. Two options:
     - **(a) Hard cutover**: update `wrangler.jsonc` `assets.directory` from `public` → `frontend/dist`. Legacy site stops working. Pros: simplest, smallest diff. Cons: any in-flight legacy localStorage state Max has on existing browsers is orphaned. The Place button on legacy already breaks when Access gates `/api/*`, so this isn't a new break.
     - **(b) Cohabitation for a week**: move legacy to `legacy/index.html`, add a worker route `/legacy` that serves it via env.ASSETS.fetch. New SPA at `/`. Phase 3 plan section 19 already calls for this.
   - Update `.assetsignore` (the symlink trick in `public/` is no longer needed once `assets.directory: frontend/dist`).
   - `wrangler deploy`. Closes deferred Phase 2.3 live smoke automatically.
   - **Live smoke** (post-deploy):
     - Browser: load `https://dk-edge-finder.max-sheahan.workers.dev/`. Cloudflare Access OTP flow → land on the v2 SPA.
     - Curl with cookie: `CF_APP="$(curl ... | grep CF_AppSession ...)"` then `curl -H "Cookie: CF_AppSession=$CF_APP" .../api/me /api/picks /api/bankroll /api/state /api/activity`. Confirm 200 with expected JSON shapes against real Cloudflare KV (not miniflare).
     - Confirm scan_subtitle in `/api/picks` is em-dash-free.
   - **Two-commit shape**: code commit + HANDOFF update commit. Max pushes when ready (he does not auto-commit).
2. **Polish, deferred items**:
   - Vitest for `worker/lib/activity.ts` (mirrors `picks.test.ts`).
   - Extract shared normalizer helpers to `worker/lib/normalize.ts` once a third consumer wants `stripEmDash` / `coerceOddsString`.
   - Rewrite `docs/cloudflare-access-setup.md` for the new Cloudflare Zero Trust UI.
   - Set up Google IdP (currently OTP-only).

### If you just have one minute, do this
`cd ~/Betting\ Skill && npx tsc -b && npm test` should pass clean. Then `npm run build` should produce `frontend/dist/` with a ~250 kB JS bundle. If all three pass, the v2 SPA is shippable; slice 5 is the deploy mile.

---

## 2026-05-01 session 4 (IN PROGRESS, Phase 2 quality gate)

### Goal
Land Phase 2 (vitest harness for the worker; route tests via direct `app.fetch(new Request(...))`; live smoke against the deployed URL once Access is configured). Step 8 (Access dashboard) is still pending; Max chose to start Phase 2 now using the dev-mock header path and defer the live smoke until step 8 lands.

### Pre-flight
- `git stash list` empty before any work. Skipped `git pull --rebase` because origin is behind (branch is 14 commits ahead, nothing to pull).
- Step 8 detection via `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/api/me` returned `HTTP/2 200` with `content-type: text/html` and no `cf-access-*` headers. Two signals folded into one response: (a) Access is not yet intercepting requests on the live URL (no 302 to `*.cloudflareaccess.com`), and (b) the new worker code is still unpushed (the deployed legacy worker has no `/api/me` route, so the request fell through to the assets binding and served `index.html`).

### Phase 2 step 1 (vitest harness): what shipped

**Tooling.**
- `npm install -D vitest` brought in `vitest@4.1.5` (Node 24 friendly).
- Added `"test": "vitest run"` and `"test:watch": "vitest"` scripts to `package.json`.
- Wrote standalone `vitest.config.ts` at the repo root with `environment: 'node'` and `include: ['worker/**/*.test.ts', 'shared/**/*.test.ts']`. Standalone (rather than inheriting `vite.config.ts`) so vitest does NOT load the Cloudflare Vite plugin, which is meant for `wrangler dev` and would noisily try to read `wrangler.jsonc` during test discovery.

**Picks normalizer tests (`worker/lib/picks.test.ts`).** 31 tests across nine `describe` blocks. The unit under test is `getPicksResponse(env)` (and `loadDataJson` / `getLatestScanDate` as supporting exports). Each test builds a fake `Env` with a hand-rolled `ASSETS.fetch` shim that returns a `Response` with a configurable `data.json` body and an optional `Last-Modified` header. Coverage:

- **Em-dash strip**: `scan_subtitle`, all `Pick` string fields (event/notes/sources), `no_edge_games[]` strings, `best_bet.title|desc`. Asserts both the stripped output AND that `JSON.stringify(...)` of the result contains no `—`.
- **Percent-string coercion**: `"35.7%"` → `35.7` for `implied`/`model`/`edge`. Numeric pass-through. Fallback to `0` for `null`/`undefined`/non-numeric strings. The `implied_prob` and `model_prob` fallback keys (legacy emit shape) are also covered.
- **Dollars-string coercion**: `"$11.41"` → `11.41` for `wager`. The `bet` fallback key (legacy shape) is covered. Numeric pass-through. Embedded-comma strings (`"$1,234.56"`) parse correctly. Missing wager defaults to `0`.
- **Odds string coercion**: passthrough of pre-formatted American strings (`"-110"`); numeric `165` → `"+165"`; numeric `-110` → `"-110"`.
- **Missing-field defaults**: a fully-empty pick object (`{}`) normalizes into a Pick that satisfies the schema with safe defaults across every field. Fallback `rank` from array index is verified. `type` falls back to `'game'` for unknown values; preserves `'prop'` when set. Top-level optional fields (subtitle/games_analyzed/best_bet/picks/no_edge_games) fall back when the model omits them.
- **scan_age_seconds derivation**: with `Last-Modified` 10 minutes ago → ~600 (asserted in a 599-601 window for clock skew). With absent header → `null`. With unparseable header → `null`. With future `Last-Modified` → clamped to `0`.
- **Empty-picks case**: today's actual zero-edges shape (`picks: []`, `no_edge_games: [...]`) round-trips correctly with em-dash stripped from `scan_subtitle`.
- **Schema validation**: a malformed `scan_date` (e.g. `"not-a-date"`) causes `PicksResponseSchema.parse(...)` to throw, which the test asserts via `rejects.toThrow()`.
- **`loadDataJson` / `getLatestScanDate`**: success path returns parsed data + `Last-Modified` Date; non-OK ASSETS response throws `data.json fetch failed: 404`; missing or non-string scan_date returns `''` from `getLatestScanDate`.

One test failed on first run (`top-level missing scan fields fall back to safe defaults`) because passing `{}` as data.json defaults `scan_date` to `''`, which fails Zod's ISO-date validator. The Python model always emits `scan_date`; a missing one is a real failure mode (not a graceful default), so the test was retitled and now provides a minimal valid `scan_date`. The schema-validation block keeps a separate negative case for the malformed-date scenario.

### Phase 2 step 2 (route tests via app.fetch): what shipped

**`worker/index.test.ts`**: 17 tests that drive the assembled root `app` (from `worker/index.ts`) via `app.fetch(new Request(...), env)`. Same pattern as the one-shot mount-order smoke from Phase 1 step 7, codified.

Mock env helpers in the file:
- `makeAssets(cfg)` returns an `ASSETS` shim that responds to `/data.json` and `/bankroll.json` with caller-provided fixtures and an optional `Last-Modified`. Anything else → 404.
- `makeKv()` returns a `Map<string, string>`-backed `EDGE_STATE` shim with `get`/`put`/`delete`/`list`. Pre-seeded via direct `env.EDGE_STATE.put(...)` calls in tests that need existing state.
- `makeEnv({ dataJson?, bankrollJson?, dataLastModified? })` composes both bindings + a placeholder `GITHUB_TOKEN`.

Coverage:
- **Auth gating** (5 tests): every v2 read route returns 401 without `cf-access-authenticated-user-email`. The middleware lowercases the email; verified by passing `Max.Sheahan@iCloud.com` and asserting `/api/me` returns `email: "max.sheahan@icloud.com"`.
- **`GET /api/health`** (1 test): public, returns `{ ok: true, time: "2026-..." }` without auth.
- **`GET /api/me`** (4 tests): happy path returns the lowercased email. JWT picture extraction works for both top-level `picture` and `custom.picture` claim shapes (test builds a fake JWT with hand-rolled base64url helper using `btoa` to keep `@types/node` out of the worker tsconfig). Malformed JWT yields `picture_url: null` rather than throwing.
- **`GET /api/picks`** (2 tests): normalized payload returned, em-dash stripped from `scan_subtitle`, schema-validated. Asset 404 on `data.json` propagates as a 500 (Hono's default error handler).
- **`GET /api/bankroll`** (2 tests): file values flow through when no KV override exists. Per-user override pre-seeded via `EDGE_STATE.put('balance_override:<email>', ...)` overrides `available` AND populates the `balance_override` envelope.
- **`GET /api/state`** (2 tests): empty KV returns empty arrays + `null updated_at` + the current `scan_date`. Pre-seeded record at `state:<email>:<scan_date>` round-trips through the merged response.
- **Mount-order regression** (1 test): `POST /api/state/placements` with an empty body returns 400 (Zod validation error from the placements subapp), NOT 404 (which would mean the broader `/api/state` router swallowed the path). This codifies the smoke from step 7.

**Initial run.** All 48 tests passed first try. `npx tsc -b` flagged one issue: my JWT helper used `Buffer.from(...).toString('base64')`, but the worker tsconfig doesn't include `@types/node` (correct; the worker shouldn't reach for Node APIs). Switched to `btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')` which works in both the Workers runtime and Node. `tsc -b` and `npm test` both clean afterward.

### Phase 2 step 2 extension (write-route tests, non-dispatch): what shipped

After the first commit pair landed, extended `worker/index.test.ts` with 17 more tests (65 total) covering the write routes that only touch KV. The dispatch-touching routes (`POST /api/state/sync-queue/retry`, `POST /api/place-bet`) are deliberately deferred: they need a fetch-injection seam in `worker/lib/dispatch.ts` before they can be unit-tested without a real GitHub `repository_dispatch` call. A comment in the test file flags the deferral so a future thread doesn't think coverage is just missing.

Coverage by route:

- **POST /api/state/placements** (5 tests): happy-path 201 with server-stamped `placed_at`, idempotency dedupe (same `idempotency_key` twice = one entry in the merged record), `dispatch_status` defaulting to `'ok'` when omitted from the body, 400 with Zod issues on bad body, 401 without auth header.
- **DELETE /api/state/placements/:key** (4 tests): 204 No Content on success with empty body, 404 when no state record exists at all, 404 when the key is not present in `placements[]`, URL-decoding of special chars (`|`, `%20`, `%40`) confirmed via a key like `NYY +1.5|NYY @ BOS`.
- **POST /api/state/manual-bets** (3 tests): 201 with server-assigned `id = idempotency_key` and `outcome: 'pending'`, idempotency dedupe, 400 on bad body.
- **DELETE /api/state/manual-bets/:id** (2 tests): 204 on success, 404 on missing id.
- **POST /api/balance-override** (3 tests): 200 with persisted record, subsequent POST overwrites the previous override (upsert semantics), `/api/bankroll` reflects the override after the POST (cross-route side-effect verified), 400 on bad body.

All 65 tests passed first run. `npx tsc -b` clean.

### Phase 2 step 2 final (dispatch-touching write routes): what shipped

The deferred dispatch-touching routes (`POST /api/state/sync-queue/retry`, `POST /api/place-bet`) turned out to be testable without modifying `worker/lib/dispatch.ts` at all: vitest's `vi.stubGlobal('fetch', ...)` patches `globalThis.fetch` directly, so the existing `dispatchPlaceBet` function (which calls the global `fetch` to POST to GitHub) runs unchanged but the network call is intercepted. The original "needs an injection seam" plan from the prior session was a real option, but it would have changed production code; stubbing the global is cleaner.

A `stubFetch(responses)` helper at the top of the dispatch-test blocks queues `Response`s in order and records every fetch call. Tests assert on the recorded call list (URL, method, body) so a missing dispatch fails loudly. The helper handles the Fetch-spec rule that 204/205/304 responses must not have a body. Passing an empty string body to a 204 makes undici's `Response` constructor throw `Invalid response status code 204`. This bit me on the first run for the cache-hit and successful-retry tests; the helper now passes `null` for those statuses.

Coverage by route:

- **POST /api/place-bet** (5 tests): successful dispatch (mock GitHub returns 204) returns 202 with `dispatch_id` echoing the idempotency key, with the correct `event_type: 'place-bets'`, `client_payload.picks: '0,1'`, and `client_payload.source: 'v2-frontend'`; result is cached at `dispatch:<email>:<idempotency_key>`. Failed dispatch (GitHub 500) returns 502 with `error: 'GitHub dispatch 500: ...'`, still cached. Cache-hit second call returns 200 with no second fetch (helper would throw if a second call landed). 400 on bad body (empty `pick_indices`). Missing `GITHUB_TOKEN` returns the `Server misconfigured: GITHUB_TOKEN secret not set` error without firing fetch.
- **POST /api/state/sync-queue/retry** (5 tests): successful retry returns 202, increments `attempt_count` from 1 → 2 (verified by pre-seeding a prior sync_queue entry), clears `last_error`, rotates `idempotency_key` to the new attempt's, and uses `client_payload.source: 'v2-sync-retry'`. Failed retry returns 502 and writes the dispatch error string to `last_error`. Pick missing from current scan returns 404 without firing fetch and writes a sync_queue entry with `last_error: 'Pick no longer in current scan'`. Cache-hit second call returns 200 without re-dispatching AND without mutating the sync_queue (verified by reading the record before/after). 400 on bad body.

All 75 tests now pass. `npx tsc -b` clean.

### Where this leaves us at end of session
- 75 tests passing across 2 files (`worker/lib/picks.test.ts` 31, `worker/index.test.ts` 44).
- `npx tsc -b` clean.
- Phase 2 code-side is closed. Only Phase 2.3 (live smoke against deployed URL) remains, blocked on step 8.
- No outstanding Phase 2 internal gap. The `dispatch.ts` fetch-injection refactor is no longer needed since `vi.stubGlobal` is sufficient for tests.
- Five commits this session: `4175694` (vitest + picks + read routes), `dffc87b` (HANDOFF update), `634ba8f` (non-dispatch write routes), `581e34b` (HANDOFF update), then the next pair lands when the dispatch tests + this HANDOFF update commit.

### What's next (continue here on resume)

1. **Phase 3 cutover** (build the v2 React frontend, route the live URL to it, retire `index.html`). Plan in [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md). When that lands, `wrangler deploy` ships the new worker too, which simultaneously closes the deferred Phase 2.3 live smoke. No need to do them separately.
2. Polish (small, low risk): rewrite [`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md) for the new Cloudflare Zero Trust UI. The current runbook describes the legacy single-domain form; the dashboard now uses Subdomain + Domain + Path triplets per destination. Worth dropping in a few of session 4's screenshots so future-you has visual anchors. Should take 15 min.
3. Polish (medium): Google IdP. Currently OTP-only. ADR 0002's intended setup is Google as the primary IdP. Set up at console.cloud.google.com → OAuth 2.0 Web application credentials → wire in Zero Trust → Settings → Authentication → Add new → Google.
4. Side-effect to manage today: the legacy site's Place button (POST `/api/place-bets`) is now Access-gated. To use it, load the site in a browser, complete the Cloudflare OTP flow once, and the resulting `CF_AppSession` cookie keeps it working until Phase 3 retires the legacy frontend.

### If you just have one minute, do this
Run `cd ~/Betting\ Skill && npm test` to confirm 75/75 pass and `npx tsc -b` to confirm types are clean. Then `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/api/me` to confirm Access is still intercepting (302 to `sheahan.cloudflareaccess.com`). If all three pass, you're ready for Phase 3 cutover.

### Session 4 closing addendum (step 8 landed)

After the Phase 2 commit pairs landed and the dispatch-test commit pair landed, Max picked option 1 ("Step 8 dashboard click-through") over the dispatch-injection refactor / Phase 3 prep / runbook update alternatives. We walked through the new Cloudflare Zero Trust UI together (the runbook was stale; the new UI uses Subdomain + Domain dropdown + Path triplets per destination, with up to five destinations per application, and a separate Authentication section that defaults to "Accept all available identity providers"). One real bug fix mid-walkthrough: my first instruction said `dk-edge-finder.max-sheahan` for the Subdomain field, which would have produced a doubled `max-sheahan` in the URL because `max-sheahan.workers.dev` is the namespace in the Domain dropdown, not generic `workers.dev`. Caught and corrected from a screenshot. Final live URL is `dk-edge-finder.max-sheahan.workers.dev/api/*`. Curl confirmed Access intercepts.

Branch is at 22 commits ahead of origin after step 8 + Phase 2 closing HANDOFF updates (the +2 over the 20-ahead Phase 2 endpoint are commits cbcd107 step-8 and 028a91d Phase-2-closed). The audit-fix HANDOFF commit will take it to 23. Still unpushed.

---

## 2026-04-30 session 3 (PAUSED, Phase 1 implementation)

### Goal
Land Phase 1: scaffold the Vite app, wire Hono in TypeScript, create the KV namespace, ship the auth middleware and route handlers, configure Cloudflare Access. Live site stays untouched throughout.

### What shipped this session so far

**Phase 1 step 1 (scaffold).** Ran `npx -y create-vite@latest frontend --template react-ts` from repo root. Output: `frontend/` with React 19.2.5, Vite 8.0.10, TypeScript 6.0.2, ESLint 10. `frontend/.gitignore` covers `node_modules/` and `dist/`. The repo's root `.gitignore` also covers them; double-coverage is fine.

**Phase 1 step 2 (Cloudflare plugin + vite.config).** `npm install` then `npm install -D @cloudflare/vite-plugin` in `frontend/` (190 packages total, 0 vulns). Installed version `@cloudflare/vite-plugin@1.35.0`. The plugin exports a named `cloudflare(pluginConfig?: PluginConfig): vite.Plugin[]`; `PluginConfig` extends `EntryWorkerConfig` which includes `configPath?: string`.

`frontend/vite.config.ts` final shape:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cloudflare } from '@cloudflare/vite-plugin'

export default defineConfig({
  plugins: [
    react(),
    cloudflare({ configPath: '../wrangler.jsonc' }),
  ],
})
```

`tsc --noEmit` clean against both `tsconfig.app.json` and `tsconfig.node.json`. Did NOT yet attempt `npm run dev` because step 9 (`.assetsignore` + `assets.directory` fix) still needs to land before `wrangler dev` can start without EMFILE.

**Decisions locked in this session (carried forward into HANDOFF):**

1. **Single `package.json`, located at `frontend/`.** All deps (frontend AND worker) live in `frontend/package.json`. Per ADR 0001's repo-layout block. The cloudflare-vite-plugin will bundle the worker via Vite using the same node_modules tree, so `hono` and `zod` (added in step 3) get installed there too. No root `package.json`, no workspaces.
2. **wrangler.jsonc stays at the repo root.** Vite plugin reads it from `../wrangler.jsonc`. The worker entry path inside it (`main: "worker/index.js"` today, will become `worker/index.ts` in step 3) resolves relative to wrangler.jsonc's own directory (root), so existing path stays correct.

### Open questions surfaced this session (to address before step 7)

- **Legacy `/api/place-bets` (plural) vs new `/api/place-bet` (singular).** The existing Worker at `worker/index.js` exposes `/api/place-bets`. The locked contract calls for `/api/place-bet` with idempotency. Plan: keep both working through cohabitation. Old `index.html` keeps hitting `/api/place-bets`; new v2 frontend hits `/api/place-bet`. After cutover, deprecate the plural. Worth confirming with Max before writing the singular endpoint in step 7.

### Phase 1 step 3 (worker rewrite + layout shift): what shipped

**Layout shift (deviation from ADR 0001 as originally written).** ADR 0001's repo-layout block placed `package.json` inside `frontend/`. When I tried to typecheck `worker/*.ts` with imports of `hono` and `zod`, TypeScript could not resolve them: `worker/` is a sibling of `frontend/`, and the standard module resolution (even in `bundler` mode) walks up from each file looking for `node_modules`. From `worker/index.ts`, walking up never reaches `frontend/node_modules`. Two fix options were considered (paths mapping in `tsconfig.worker.json` with deprecated TS 6 `baseUrl`, vs moving `package.json` to the repo root). Asked Max via `AskUserQuestion`; chose the canonical CF Workers + Vite layout: package.json at the repo root.

**Files moved from `frontend/` to repo root:**
- `package.json`
- `package-lock.json`
- `vite.config.ts`
- `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `tsconfig.worker.json`
- `eslint.config.js`

**Files left in `frontend/`:** `src/`, `public/`, `index.html` (Vite's HTML entry), `README.md`. `frontend/node_modules` deleted; `node_modules` reinstalled at the repo root via `npm install`.

**Config updates that paired with the move:**
- `vite.config.ts`: `root: 'frontend'` so Vite finds `frontend/index.html`. `cloudflare()` plugin no longer needs `configPath` since `wrangler.jsonc` is at the same level.
- `tsconfig.app.json`: `include` changed from `["src"]` to `["frontend/src"]`.
- `tsconfig.worker.json`: paths in `include` no longer prefixed with `../`. Dropped the `baseUrl` + `paths` workaround that I had attempted before the layout shift (deprecated in TS 6).
- `eslint.config.js`: `globalIgnores` extended to `['dist', 'frontend/dist', 'node_modules', '.wrangler']`.

**Worker rewrite (TS + Hono).** Under `worker/`:
- `worker/env.ts`: `Env extends CloudflareBindings` with `GITHUB_TOKEN: string` (the secret is not in wrangler.jsonc, so `wrangler types` does not generate it).
- `worker/index.ts`: `Hono<{ Bindings: Env }>` app that mounts `app.route('/api/health', healthApp)`, `app.route('/api/place-bets', placeBetsLegacyApp)`, and falls through with `app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))`.
- `worker/routes/health.ts`: tiny health endpoint, identical behavior to the JS original.
- `worker/routes/place-bets-legacy.ts`: 1:1 port of the existing JS handler. CORS allowlist, origin check, body parse, `normalizePicks`, GitHub `repository_dispatch`. Live behavior preserved.
- `wrangler.jsonc`: `main` updated from `worker/index.js` to `worker/index.ts`.
- `worker/index.js` and `worker/routes/.gitkeep` deleted.
- `worker-configuration.d.ts` regenerated via `npx wrangler types --env-interface CloudflareBindings`. Lives at the repo root, ~500 KB; committed for editor type support. Re-run after any wrangler.jsonc binding change (the wrangler CLI prints a reminder).

`npx tsc -b` from the repo root passes clean across all three project references (app, node, worker).

### Decisions locked this session

1. **Single `package.json`, located at the repo root** (revises ADR 0001's layout). Matches the canonical CF Workers + Vite template.
2. **wrangler.jsonc stays at the repo root.** Now sibling to `vite.config.ts`, so the Cloudflare Vite plugin auto-detects it.
3. **Worker has its own tsconfig (`tsconfig.worker.json`).** Wires `worker/**/*.ts`, `shared/**/*.ts`, and the generated `worker-configuration.d.ts`. ESM module resolution mode `bundler`, no DOM lib, strict.
4. **Legacy `/api/place-bets` (plural) preserved verbatim** as a 1:1 TS port. The new `/api/place-bet` (singular, with idempotency) lands in step 7.

### Open questions surfaced this session (unchanged, still open for step 7)

- **Legacy `/api/place-bets` (plural) vs new `/api/place-bet` (singular).** Plan: keep both during cohabitation. Old `index.html` keeps hitting the plural path; new v2 frontend hits the singular path. After cutover, deprecate the plural. Worth confirming with Max before writing the singular endpoint in step 7.

### TODOs surfaced (non-blocking, address in later steps or polish pass)

- `eslint.config.js` applies `globals.browser` to `**/*.{ts,tsx}` including `worker/`. Worker code does not run in a browser. Split the rules into a frontend block (browser globals + react) and a worker block (no DOM). Polish item; not blocking.
- `worker-configuration.d.ts` is committed at ~500 KB. Common practice is to either commit it (as the canonical CF template does) or gitignore + regenerate via `predev`/`prebuild`. Currently committed. Revisit if it gets noisy.
- ESLint, Vitest, and full deploy scripts are not wired into `package.json` yet beyond the Vite scaffold defaults. Step 9 (cohabitation + EMFILE) is a natural place to add `deploy`, `types`, and worker-aware scripts.

### Phase 1 step 4 (KV namespace): what shipped

Ran `npx wrangler kv namespace create EDGE_STATE` from the repo root. Cloudflare returned namespace id `7dca36afc97d4d86bebed2e2948d6e83`. Wrangler offered to auto-edit `wrangler.jsonc` but in non-interactive mode defaulted to "no", so the binding was added by hand:

```jsonc
"kv_namespaces": [
  { "binding": "EDGE_STATE", "id": "7dca36afc97d4d86bebed2e2948d6e83" }
]
```

`npx wrangler types --env-interface CloudflareBindings` regenerated `worker-configuration.d.ts`. `Cloudflare.Env` now contains `EDGE_STATE: KVNamespace`, which `worker/env.ts`'s `Env extends CloudflareBindings` picks up automatically.

Skipped the separate `_PREVIEW` namespace. The Cloudflare Vite plugin runs miniflare for local dev and simulates KV in memory; a remote preview namespace is only needed if `wrangler dev --remote` against real Cloudflare KV becomes the workflow. Add later if so.

`npx tsc -b` clean.

### Phase 1 step 5 (auth middleware): what shipped

`worker/middleware/auth.ts`:
```ts
import { createMiddleware } from 'hono/factory'
import type { Env, Variables } from '../env'

export const requireAuth = createMiddleware<{
  Bindings: Env
  Variables: Variables
}>(async (c, next) => {
  const email = c.req.header('cf-access-authenticated-user-email')?.toLowerCase()
  if (!email) return c.text('Unauthorized', 401)
  c.set('email', email)
  await next()
})
```

`worker/env.ts` gains a `Variables` type export so consumers of `requireAuth` can construct a typed Hono app:
```ts
new Hono<{ Bindings: Env; Variables: Variables }>()
```

`worker/middleware/.gitkeep` removed.

**Not yet mounted in `worker/index.ts`.** Mounting on `/api/*` would 401 the legacy `/api/place-bets` path that the live `index.html` still calls (the live site does not yet route through Cloudflare Access, so it has no `cf-access-authenticated-user-email` header). Step 6 will mount `requireAuth` on each new v2 read route as it lands. Once Cloudflare Access is configured in step 8, the same header will populate for legacy traffic too, but until then the cohabitation worker has to keep legacy paths public.

### Phase 1 step 6 (read routes + shared schemas): what shipped

**`shared/schemas.ts`** — Zod 4 schemas for the locked contract. One block per concern:
- `PickSchema` (v2 normalized output), `NoEdgeGameSchema`, `BestBetSchema`, `PicksResponseSchema`.
- `LifetimeStatsSchema`, `BankrollResponseSchema`.
- `MeResponseSchema`.
- `PlacementSchema`, `SyncQueueEntrySchema`, `ManualBetSchema`, `StateRecordSchema`, `BalanceOverrideRecordSchema`, `StateResponseSchema`.

Schema choices grounded in the actual emit shape from `scripts/scan_edges.py:1968-1990`:
- Q6 normalization is opinionated. The Python model emits `implied: "35.7%"` (string with %) and `bet: "$11.41"` (formatted dollars). The schema requires `implied: number` and `wager: number`; the normalizer in `worker/lib/picks.ts` does the coercion. `event_short` and the empty `status`/`result` fields are dropped at the boundary.
- Em-dash strip is universal across every string the worker returns (per the contract's "Display contracts" section, which is a hard rule, not a suggestion).
- Used Zod 4's top-level `z.iso.date()` and `z.iso.datetime({ offset: true })` for ISO date/timestamp validation; `z.string().email()` is deprecated in v4.

**`shared/types.ts`** — `import type { z } from 'zod'` plus `import type { ... } from './schemas'`, then `type Pick = z.infer<typeof PickSchema>` etc. for every schema. Worker and (future) frontend share these types from one source.

**`worker/lib/picks.ts`** — `loadDataJson(env)`, `getLatestScanDate(env)`, `getPicksResponse(env)`. Reads `/data.json` via `c.env.ASSETS.fetch(new Request('https://assets.local/data.json'))`. `scan_age_seconds` is derived from the response's `Last-Modified` header (null if absent). Coercion helpers: `coerceNumberPercent` (strips `%`), `coerceNumberDollars` (strips `$`), `coerceOddsString` (number → American format string with `+`/`-` prefix), `stripEmDash` (replaces `—` with `-` everywhere). Final `PicksResponseSchema.parse()` validates the normalized shape before returning, so a model regression that breaks the contract surfaces as a 500 with a Zod error rather than malformed JSON.

**`worker/lib/bankroll.ts`** — `getBankrollResponse(env, email)`. Reads `/bankroll.json` via ASSETS in parallel with the per-user `balance_override:<email>` KV record. If the user has a KV override, that wins for both `available` and the `balance_override` envelope; otherwise `available` falls back to `current_bankroll` from the file and `balance_override` is `null`. Lifetime stats always come from the file.

**`worker/lib/state.ts`** — `readState(env, email, scan_date)`, `writeState(env, record)`, `appendPlacement(env, email, scan_date, p)`, `appendManualBet(env, email, scan_date, b)`, `upsertSyncQueueEntry(env, email, scan_date, entry)`. Append-merge semantics with idempotency-key dedupe per ADR 0003. The append helpers will land in active use during step 7 (write routes); they are written now so the lib layer stays cohesive.

**`worker/routes/me.ts`** — JWT decode of `cf-access-jwt-assertion` (no signature verification; Access already guards the path per ADR 0002 Section "What we accept"). Extracts `picture` claim if present, falls back to `null`. Returns `{ email, picture_url }`.

**`worker/routes/picks.ts`** — thin: calls `getPicksResponse(c.env)`, returns it.

**`worker/routes/bankroll.ts`** — thin: calls `getBankrollResponse(c.env, c.get('email'))`, returns it.

**`worker/routes/state.ts`** — reads latest `scan_date` from `data.json`, then `readState(env, email, scan_date)`. If null, returns empty arrays + `updated_at: null` (per the open-question default in `backend-requirements.md`). Includes `scan_date` in the response so the frontend can display which scan the state belongs to.

**Mount order in `worker/index.ts`** — legacy `/api/health` and `/api/place-bets` mount FIRST so the live `index.html` keeps working without a Cloudflare Access header. v2 read routes mount after; each route's own `app.use('*', requireAuth)` provides the 401 gate. Once Access goes live in step 8, the same header will populate for legacy traffic too and we can either tighten the legacy routes or leave them as the cohabitation fallback.

`npx tsc -b` clean. Manual `wrangler dev` smoke deferred to after step 9 (EMFILE).

### Decisions locked at the step 6 / step 7 handoff

- **Singular `/api/place-bet` vs plural `/api/place-bets`** — Max confirmed (2026-04-30, end of step 6): **both coexist during cohabitation.** Legacy plural stays wired for the live `index.html`. The new singular endpoint adds idempotency via a client-generated UUID in the request body. Plural deprecates after cutover (step 9 / Phase 3 territory).

### Phase 1 step 7 (write routes): what shipped

**Schemas (`shared/schemas.ts`).** Six new request/response shapes, all with `idempotency_key: z.string().min(1)` where applicable:

- `PlacementCreateRequestSchema { key, action, dispatch_status, idempotency_key }` — `dispatch_status` defaults to `'ok'` so the frontend can record skipped placements without specifying it. The frontend reports the dispatch outcome alongside the placement so the worker stays stateless about the place-bet flow.
- `ManualBetCreateRequestSchema { sport, event, pick, odds, wager, idempotency_key }` — server assigns `id = idempotency_key` so retries dedupe cleanly.
- `SyncQueueRetryRequestSchema { key, idempotency_key }` — `idempotency_key` is for THIS retry attempt's dispatch dedupe, not the original placement.
- `BalanceOverrideRequestSchema { amount, note }`.
- `PlaceBetRequestSchema { pick_indices: number[].min(1), idempotency_key }`.
- `PlaceBetResponseSchema { status: 'ok'|'failed', dispatch_id?, error? }` — `dispatch_id` echoes the idempotency_key so the client can correlate.

Re-exported as TS types in `shared/types.ts`.

**State lib (`worker/lib/state.ts`).** Extended:
- `removePlacement(env, email, scan_date, key)` and `removeManualBet(env, email, scan_date, id)` filter the array, write back, return `{ removed, record }`.
- `getBalanceOverride(env, email)` and `upsertBalanceOverride(env, email, amount, note)` operate on the `balance_override:<email>` KV key. `lib/bankroll.ts` was deduped to call `getBalanceOverride` instead of carrying its own copy of the read logic.
- `upsertSyncQueueEntry` was re-keyed: dedupe is now by `entry.key` (Placement.key), not `idempotency_key`. Each retry rotates the entry's `idempotency_key` field; per-key dedupe means one row per failed placement, updated in place. Added `findSyncQueueEntry(record, key)` helper.

**Dispatch lib (`worker/lib/dispatch.ts`).** New file. Three exports:
- `dispatchPlaceBet(env, pickIndices, source)` — POSTs `repository_dispatch` to GitHub. Returns `{ status: 'ok' }` on 2xx, `{ status: 'failed', error }` otherwise. Source string lets us distinguish `'v2-frontend'` from `'v2-sync-retry'` in the GitHub payload.
- `getCachedDispatchResult(env, email, idempotency_key)` and `cacheDispatchResult(...)` use `dispatch:<email>:<idempotency_key>` KV keys with a 24h `expirationTtl`. Same idempotency_key on a retry returns the cached result; a fresh idempotency_key is treated as a new attempt. ADR 0003's "no TTL" rule is for state records; the dispatch cache is a separate concern with a bounded retry window.

**Routes.** Five new files, each mounting `app.use('*', requireAuth)` and using `safeParse` so a bad body returns 400 with Zod issues instead of throwing.

- `worker/routes/state-placements.ts` — `POST /` validates the body, builds the full Placement (server-stamped `placed_at`), calls `appendPlacement`, returns the merged entry as 201. `DELETE /:key` URL-decodes the key and calls `removePlacement`, returning 204 on success or 404 if no record / no match.
- `worker/routes/state-manual-bets.ts` — same shape. Server-assigned `id = idempotency_key`. `outcome` defaults to `'pending'`.
- `worker/routes/state-sync-queue.ts` — `POST /retry`: idempotency cache check first, then look up the pick in `data.json.picks[]` by `pick + "|" + event === key`. If not found, write a 'Pick no longer in current scan' error to the queue entry and return 404. Otherwise fire `dispatchPlaceBet`, cache the result, write the queue entry with `attempt_count: prior + 1` and `last_error: result.error || null`. Returns 202 on success, 502 on dispatch failure.
- `worker/routes/balance-override.ts` — thin wrapper over `upsertBalanceOverride`. Returns the persisted record.
- `worker/routes/place-bet.ts` — POST /: idempotency cache check, then `dispatchPlaceBet(pick_indices, 'v2-frontend')`, cache, return 202 on success / 502 on failure.

**Mount order (`worker/index.ts`).** Legacy first (`/api/health`, `/api/place-bets`), then v2 read routes, then v2 write routes. More-specific `/api/state/*` paths are mounted BEFORE `/api/state` itself for defensive readability, though a one-shot Hono smoke test confirmed the order does not actually matter (Hono scopes wildcard middleware to its own subapp, not the broader prefix). The smoke test was deleted after confirming.

**Verification.** `npx tsc -b` clean. Live `wrangler dev` smoke still blocked by EMFILE from session 2; deferred to step 9.

### Phase 1 step 8 (Cloudflare Access dashboard): runbook drafted

[`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md) is the click-by-click. Recommended path scope is `/api/*` for cohabitation (legacy `index.html` keeps loading at the root path; new v2 API routes are auth-gated). Expand to `/*` after step 9 cutover. The runbook includes verification steps, IdP setup if Google is not yet configured on the account, and rollback. Worker code does not change; this step is pure dashboard config.

### Phase 1 step 9 (EMFILE fix): what shipped

**Root cause.** Two layers had to be teased apart:

1. `wrangler.jsonc` had `assets.directory: "."`, which made the wrangler dev file watcher walk the whole repo (worker source, node_modules, `.git`, `.claude/worktrees/*`, scripts, mockups, every Python module). On macOS, launchd's default per-process file-descriptor soft limit is **256** even when `ulimit -n` reports 1M+ for the shell (`launchctl limit maxfiles` confirms). The wide watch tree exhausted descriptors and crashed with EMFILE within seconds of `wrangler dev` start.
2. `.assetsignore` controls which files wrangler **uploads** at deploy and **serves** from the assets binding. It does NOT affect the dev watcher. Adding `.assetsignore` alone did not resolve EMFILE; verified empirically before settling on the right fix.

**Fix.**
- Created `public/` with three **symlinks** pointing one level up: `public/index.html → ../index.html`, `public/data.json → ../data.json`, `public/bankroll.json → ../bankroll.json`. Symlinks (not hardlinks) so future code that writes via temp+rename still resolves correctly via the symlink at access time.
- Updated `wrangler.jsonc` `assets.directory: "."` → `"public"`. Watcher now walks 3 entries instead of thousands.
- The Python cron writes to repo-root `data.json` and `bankroll.json` unchanged; symlinks make the writes visible to the worker without touching the model code.
- `.assetsignore` added as defense-in-depth: default-deny posture, allowlists only `index.html`, `data.json`, `bankroll.json`. Side benefit: stops the public site from serving `pick_history.json` (535 KB of model calibration data) which had no reason to be on the public URL.

**Verification.** `wrangler dev` now starts in ~1 second (READY at iteration 1, no EMFILE). Smoked all 9 v2 routes against the local server with a mocked `cf-access-authenticated-user-email` header:

- `GET /api/health` → 200 `{"ok":true,"time":"..."}` (legacy, no auth needed)
- `GET /api/me` without header → 401. With header → 200 `{"email":"...","picture_url":null}`.
- `GET /api/picks` → 200 with normalized payload. **`scan_subtitle` is "Thursday, April 30, 2026 - MLB (11), NBA (3), NHL (2)"** (em-dash stripped to hyphen, confirmed against the source `—` in the symlinked data.json).
- `GET /api/bankroll` → 200 `{"available":679.34,"starting":500,"profit":179.34,"lifetime":{...},"balance_override":null}`. After POST `/api/balance-override {"amount":700,"note":"smoke test"}` → `available:700` and `balance_override:{...}` populated. KV merge confirmed.
- `GET /api/state` → 200 empty arrays + `updated_at:null` initially. After POST `/api/state/placements` (same idempotency_key sent twice) → only ONE placement in the merged record. Idempotency dedupe confirmed.
- `POST /api/state/manual-bets` → 201 with server-assigned `id = idempotency_key`, `outcome:"pending"`.
- `DELETE /api/state/placements/<URL-encoded-key>` → 204 No Content. URL decoding of `%20`, `%2B`, `%7C`, `%40` works.
- Bad body to any POST → 400 with detailed Zod issues array.

The local KV writes during the smoke live in `.wrangler/` (miniflare, not real Cloudflare KV). `.gitignore` covers `.wrangler/`.

### What's next (continue here on resume)

**Phase 1 wraps when Max completes step 8 in the dashboard.** No more code work needed for Phase 1 itself; the runbook at `docs/cloudflare-access-setup.md` is the input.

**Phase 2 (quality gate)** is the next code work block:
1. Vitest harness for `lib/picks.ts` normalizer (covers em-dash strip, percent-string coercion, dollars-string coercion, missing-field defaults, scan_age_seconds calculation). The empty-picks case is also worth a test since today's data.json is exactly that.
2. Route tests with `wrangler unstable_dev` (or just direct `app.fetch(new Request(...))` calls like the one-shot Hono smoke from step 7) for at least the read routes. Write routes are harder to test in isolation because of the GitHub dispatch side effect; mock or skip for now.
3. Smoke against the live URL post-Access via the Cloudflare access JWT (or by curling with the dev mock locally and trusting parity). Live smoke should hit `/api/me`, `/api/picks`, `/api/bankroll`, `/api/state` and confirm 200 + correct shape.

**Phase 3 (cutover)** is later:
1. Build the v2 frontend (`npm run build`) and place output at `public/` (replaces or coexists with the legacy `index.html` symlink).
2. Move legacy `index.html` to `legacy/index.html` for one-week fallback at `/legacy`.
3. Remove the legacy `/api/place-bets` (plural) route after one week of v2 SPA stability.
4. Tighten Cloudflare Access policy from `/api/*` to `/*` once root is the v2 SPA.

---

## 2026-04-30 session 2 (PAUSED, end-of-session, ready for Phase 1)

### Goal
Close Phase 0 of the v2 frontend rebuild. Done. Phase 1 (Vite scaffold + Hono routes + KV namespace + Cloudflare Access policy) starts in the next session.

### What shipped this session

**Phase 0.5: API contract locked.** Ran the `frontend-to-backend-requirements` skill in a 7-question prompted interview. Output at `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`. Two commits: `728d93c` (doc + launch.json), `467d23b` (HANDOFF update).

Decisions (all 7 confirmed via AskUserQuestion):
1. **v2 UX scope**: like-for-like rebuild + auth + cross-device sync. Same 5 tabs, same actions per tab.
2. **Scan-date navigation**: latest scan only, no date picker. /api/picks does not need a scan_date param.
3. **5th tab**: renamed Settings to **Account**. Scope: identity, balance override, sign-out, lifetime stats. No model config.
4. **Sync conflict**: append-merge. Frontend POSTs single events; worker merges into KV. No whole-state PUTs.
5. **Place-bet failure UX**: "queued for retry" badge per row, KV-backed sync_queue, cross-device synced. Retry Now button.
6. **/api/picks shape**: reshape into clean v2 types. Worker normalizes numerics, drops redundant fields, strips em-dashes.
7. **Manual bets**: same narrow scope as today (Place button on rejected no-edge rows + wager prompt). No freeform off-platform logging.

Suggested endpoint surface (subject to backend confirmation in Phase 1):
- `GET /api/me`, `GET /api/picks`, `GET /api/bankroll`, `GET /api/state`
- `POST /api/state/placements`, `DELETE /api/state/placements/:key`
- `POST /api/state/manual-bets`, `DELETE /api/state/manual-bets/:id`
- `POST /api/state/sync-queue/retry`
- `POST /api/balance-override`
- `POST /api/place-bet` (existing GitHub dispatch + idempotency token)

**Phase 0.6: KV state schema.** Wrote `docs/adr/0003-state-schema.md` directly (the database-schema-designer skill is SQL-focused; relevant context fit in the ADR). Decisions:
- KV namespace `EDGE_STATE`, two key prefixes: `state:<email>:<scan_date>` and `balance_override:<email>`.
- Email is lowercased in keys (Cloudflare Access returns whatever case Google sent).
- `scan_date` is ISO `YYYY-MM-DD`. Lex sort equals chrono sort, list-by-prefix comes for free.
- Value blobs carry `schema_version: 1`. Future shape changes upgrade in-place on read.
- No TTL (records are tiny, late-resolving bets need to stick around).
- Append-merge with client-generated idempotency keys for dedupe.
- Alternatives considered (rejected): D1, per-event keys, Durable Objects, storing state in data.json (the cron would clobber it; the bets[] sanctity rule from lessons.md 2026-03-18 explicitly protects against that pattern).

Wrangler dev dev-server config exists in `.claude/launch.json` (alongside `site` on 8080 and `mockups` on 8090) but currently fails with `EMFILE: too many open files, watch` because `assets.directory: "."` makes wrangler watch the entire repo (node_modules + 535 kB pick_history.json). Documented in commit `728d93c`. Fix is a Phase-1 concern (add `.assetsignore` or pin assets to a `public/` subdir). Skipped for this session per Max's call.

### Pre-flight ran
`git stash list` empty before pull. `git fetch && git pull --rebase` clean (already up to date). Branch was 5 ahead of origin/main, 0 behind. Stash list confirmed empty afterward.

### Resolved this session
Nothing model-side. Pure planning + ADR work.

### Phase 0.7 done. Phase 0 is closed.
Wrote the remaining two ADRs directly (no skill needed; both decisions were already in the plan):
- `docs/adr/0001-stack.md` (Vite + React + TypeScript; Hono on Cloudflare Workers; @cloudflare/vite-plugin for the dev loop; TanStack Query for server state; Zod for shared schemas; hand-rolled CSS). Alternatives rejected: Next.js, Remix, SvelteKit, plain HTML/JS, MUI, Tailwind.
- `docs/adr/0002-auth.md` (Cloudflare Access with Google IdP; worker reads `cf-access-authenticated-user-email` from request header, lowercases in middleware before keying KV; sign-out via `/cdn-cgi/access/logout`). Alternatives rejected: Firebase Auth (tried in March, abandoned), Auth0/Clerk, custom OAuth, Sign in with Apple, anonymous.

Commit: `79287b3 chore(phase-0.7): add ADRs 0001 (stack) and 0002 (auth)`.

### Next is Phase 1 (implementation)
Phase 1 has no skill ceremony; it is real code. Sequence:
1. From repo root: `npm create vite@latest frontend -- --template react-ts`. Vite scaffolds `frontend/`.
2. `cd frontend && npm install` then `npm install -D @cloudflare/vite-plugin`. Configure `vite.config.ts` to use the plugin.
3. Rewrite `worker/index.js` as `worker/index.ts` mounting Hono. Install `hono` + `zod`. Move route handlers into `worker/routes/*.ts` per the folder shape Phase 0.4 scaffolded.
4. Create the KV namespace: `npx wrangler kv:namespace create EDGE_STATE`. Paste the namespace id into `wrangler.jsonc` under `kv_namespaces`. Also create `EDGE_STATE_PREVIEW` for `wrangler dev`.
5. Add `worker/middleware/auth.ts` per ADR 0002. Mount via `app.use('/api/*', requireAuth)`.
6. Implement the route handlers per the locked contract. Start with read paths (`/api/me`, `/api/picks`, `/api/bankroll`, `/api/state`), then write paths (`/api/state/*`, `/api/balance-override`, `/api/place-bet`).
7. Configure the Cloudflare Access policy in the dashboard: app at `dk-edge-finder.max-sheahan.workers.dev/*`, IdP = Google, allow `max.sheahan@icloud.com`. Verify in a private browser window.
8. Wire `wrangler.jsonc` for cohabitation: serve the new build under `/v2/*` and the old `index.html` everywhere else until cutover.
9. Address the wrangler-dev `EMFILE` issue from this session: add `.assetsignore` to skip `dk-edge-finder-app/`, `pick_history.json`, dashboard HTML files, etc., OR pin `assets.directory` to a `frontend/dist/` subdir.

Phase 2 (quality gate) and Phase 3 (cutover) follow per the plan file.

### If you just have one minute, do this
Open the three ADRs in `docs/adr/` to confirm they read correctly. Then run step 1 above (`npm create vite@latest frontend -- --template react-ts`) when you are ready to start Phase 1. The ADRs are the input; Phase 1 is the build.

---

## 2026-04-30 session 1 (paused earlier, ~13:00 PT, picked up by session 2)

### Goal
Rebuild the frontend of [dk-edge-finder.max-sheahan.workers.dev](https://dk-edge-finder.max-sheahan.workers.dev/) with real Google auth and cross-device state. Python model + GitHub Actions cron stay untouched.

### Current branch
`rebuild/v2-frontend` at `52665ab`, branched off `main` and last rebased onto `c08a0e3`. Repo: [blueandyellow44/dk-edge-finder](https://github.com/blueandyellow44/dk-edge-finder), local at `~/Betting Skill`. Branch is pushed to origin.

`main` is at `c08a0e3` and in sync with origin.

### Approved plan
[/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md)

### Decisions on the books
1. **Scope:** Frontend + new backend pieces (Google auth + shared state store). Python scan model untouched.
2. **Location:** In place at `~/Betting Skill`, on `rebuild/v2-frontend`, frontend folder named `frontend/`.
3. **Stack:** Vite + React for UI. Hono on Cloudflare Workers for API. `@cloudflare/vite-plugin` for the dev loop.
4. **Auth:** Cloudflare Access with Google IdP. Worker reads `cf-access-authenticated-user-email` to identify user.
5. **State store:** Workers KV namespace `EDGE_STATE`. Records keyed by `(user_email, scan_date)` for placements + sync_queue + manual_bets, plus a single `balance_override:{email}` record.
6. **Python output target:** No change. Model continues to write `data.json`, `bankroll.json`, `pick_history.json` to git.

### What shipped this session (8 commits)

**Model fixes on main:**
1. `8fd86b7 fix(resolver): key scoreboard cache by (sport, date), not just sport`
2. `a3efced data: resolve 110 backlogged NBA paper picks (Apr 5-29)`
3. `fe63294 fix(model): NBA playoff discount + hard skip on too-good-to-be-true edges`
4. `c08a0e3 data: re-scan today with playoff discount applied (0 edges)`

**Rebuild scaffolding on rebuild/v2-frontend:**
5. `2945fea chore: add v2 rebuild scaffolding docs (lessons, handoff, changelog)`
6. `8e98eb8 chore: update HANDOFF + CHANGELOG with NBA playoff discount fix`
7. `220170f chore(scaffold): pre-scaffold worker/, shared/, docs/adr/ folder tree`
8. `52665ab chore: update HANDOFF.md, Phase 0.4 done, next is Phase 0.5`

Detail on the model fixes:
- **Resolver cache-key bug.** `scripts/resolve_bets.py` was caching scoreboards under `all_games[sport]`, which silently reused the wrong date's scoreboard for second-and-later pending picks of the same sport. 110 NBA picks across April 5-29 had been stuck pending for weeks. Fix lives in both `main()` and `resolve_pick_history()`. Branch `fix/resolver-cache-key` merged.
- **NBA playoff discount.** Adds `is_nba_playoff_window()` plus 5 calibration constants. During Apr 15 to Jun 30: NBA edge reduced 40%, NBA OVER totals reduced an additional 10%, NBA min-edge raised to 8%, hard skip on anything still above 10% post-discount. Today's `OVER 212.5 BOS @ PHI` (29.3% raw) was correctly hard-skipped. Branch `fix/nba-playoff-discount` merged.

### Resolved this session (do NOT re-open)
- **Resolver `main()` cache-key bug.** Fixed alongside `resolve_pick_history()`. The placed-bet path also had the smaller related issue. Both paths now key by `(sport, date)`.

### Calibration snapshots captured
- `/tmp/dk-edge-calibration-BASELINE.txt` (pre-resolver-fix, masked NBA losses)
- `/tmp/dk-edge-calibration-AFTER-FIX.txt` (post-resolver-fix, true picture, NBA at 44.9% / -$252.63 over 178 picks)

### Detour findings filed in [dk-edge-finder/tasks/lessons.md](dk-edge-finder/tasks/lessons.md) (this branch only)
1. Resolver cache-key fix [AUTOMATE - DONE]
2. NBA model unprofitable: 44.9% over 178, paper P/L -$252.63 [BACKLOG]
3. 5-8% edge bucket below break-even at 52.8% over 271 [BACKLOG]
4. Stale-stash awareness rule [MANUAL]

### Phase 0.4 done (file-architect output)
All 6 folder-architect questions answered, folder tree scaffolded.

Recorded answers:
1. Frontend folder: `frontend/` (Vite scaffolds it in Phase 1, NOT pre-created here)
2. Old `index.html`: stays at root during cohabitation, Worker routes around it
3. Shared types: `shared/` at repo root
4. Worker layout: keep folder name `worker/`, split into `worker/index.ts` + `worker/routes/` + `worker/middleware/` + `worker/lib/` (rewrite from .js to .ts in Phase 1)
5. Mockups: existing `mockups/` keeps being the home, prefix new files with `v2-`
6. ADRs: `docs/adr/0001-stack.md`, `0002-auth.md`, `0003-state-schema.md`

Folders created with `.gitkeep`: `worker/routes/`, `worker/middleware/`, `worker/lib/`, `shared/`, `docs/adr/`. Existing `worker/index.js` untouched. Live site continues serving from it.

### Phase 0.5 (closed in session 2)
Was: invoke the `frontend-to-backend-requirements` skill, lock the API contract. Done. Locked decisions and the 11 suggested endpoints (more than the original 7-endpoint sketch below) live in `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`. The original endpoint sketch from this session-1 record is superseded:
- `GET /api/me`, `GET /api/picks`, `GET /api/bankroll`, `GET /api/state` (no scan_date param needed by default, Q2)
- `POST /api/state/placements`, `DELETE /api/state/placements/:key` (append-merge, Q4)
- `POST /api/state/manual-bets`, `DELETE /api/state/manual-bets/:id`
- `POST /api/state/sync-queue/retry` (cross-device retry, Q5)
- `POST /api/balance-override`
- `POST /api/place-bet` (idempotency token added; addresses HIGH backlog)

### Open backlog (priorities are proposals, correct as needed)

**HIGH (do during the rebuild)**
- **`/api/place-bet` idempotency.** Current Worker route has no idempotency token, so two simultaneous Place clicks dispatch twice. Worth fixing during the rebuild before the new frontend ships its retry logic. File: `worker/index.js:36-159`.
- **GitHub Actions Node 20 deprecation on June 2, 2026.** Bump `actions/checkout@v4` and `actions/setup-python@v5` to versions that support Node.js 24. All four `.github/workflows/*.yml` files affected. Hard deadline.

**MEDIUM (next 2-4 weeks)**
- **NBA model recalibration.** The tactical playoff-discount patch shipped today is not a real recalibration. Real fix: pull historical NBA playoff data, train a separate playoff-aware model, compare to RS model, tune discount factors. Filed in `dk-edge-finder/tasks/lessons.md` as [BACKLOG].
- **5-8% edge bucket policy.** Sits at 52.8% / -$156.32 over 271, just below the 52.4% break-even at -110 odds. Either raise base min-edge from 5% to 8% or stiffen the graduated discount. Filed in `dk-edge-finder/tasks/lessons.md` as [BACKLOG].
- **Stuck-pending picks (props).** 106 still pending after the resolver fix. Most are player props the existing resolver cannot handle (no per-player stat fetcher). Building a prop resolver is a separate model-side task.

**LOW (whenever)**
- **Stale `claude/*` worktree branches.** `claude/condescending-lovelace`, `claude/gallant-jemison`, `claude/silly-varahamihira`, `claude/tender-haslett`, `claude/tender-mahavira`, `claude/tender-villani`, `claude/tender-wiles`, `claude/trusting-bassi`, plus `claude/laughing-brown`. Some are 30+ days old. Worth pruning with `git branch -D` and `git push origin --delete` after confirming nothing in-progress lives on them.
- **ODDS_API_KEY rotation.** Last rotated 2026-03-21 (~40 days old). No expiry signal yet. Low priority but worth tracking.

### Useful paths
- Repo root: `~/Betting Skill`
- Plan file: `/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`
- Rebuild lessons (root): `~/Betting Skill/lessons.md`
- Model lessons: `~/Betting Skill/dk-edge-finder/tasks/lessons.md`
- Changelog: `~/Betting Skill/CHANGELOG.md`
- Current single-file frontend: `~/Betting Skill/index.html` (66 kB, will be replaced at cutover)
- Current Worker: `~/Betting Skill/worker/index.js`
- Wrangler config: `~/Betting Skill/wrangler.jsonc`
- Python model: `~/Betting Skill/scripts/`
- Skill folder: `~/.claude/skills/dk-edge-finder/`
- Stale React/Firebase rebuild attempt (March 17, abandoned): `~/Betting Skill/dk-edge-finder-app/`

### Useful commands
```
# ALWAYS before working, and ALWAYS list stashes first (lesson 2026-04-30)
cd ~/Betting\ Skill
git stash list           # if anything is here, decide whether to drop BEFORE pulling
git stash && git pull --rebase && git stash pop
git stash list           # confirm clean afterwards

# Run the model locally (free APIs, no Odds API credit cost)
python3 scripts/scan_edges.py --games-only
python3 scripts/resolve_bets.py
python3 scripts/analyze_history.py

# Worker dev loop (post-Phase-1)
wrangler dev

# Inspect cron runs
gh run list --repo blueandyellow44/dk-edge-finder --limit 10
gh run view <run_id> --log

# Compare local main to remote (for stale-checkout drift detection)
git fetch origin main && git rev-list --left-right --count main...origin/main
```

### Known live values (snapshot, will drift over time)
- Snapshot timestamp: **2026-04-30 13:00 PT**
- Live bankroll on origin/main: $679.34 (per April 29 Full Scan, may have moved if cron picks were resolved overnight; check `git show HEAD:bankroll.json | jq .balance_override` to verify)
- Today's edges on origin/main: **0** (correctly empty after the playoff discount + line movement; next cron at 19 UTC will refresh)
- Resolved-record after the resolver fix: 415W-315L on 730 resolved picks
- ODDS_API_KEY age: ~40 days old (last rotated 2026-03-21)
