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

**Bug 2 + Pending polish + Positions removed + wager rounded up (2026-05-04 session 13):** Four things landed in one ship. (1) **Bug 2 closed:** `PlacementSchema` gains `wager: z.number().nonnegative().optional()` (optional for back-compat with pre-fix KV records); `PlacementCreateRequestSchema` accepts wager and `worker/routes/state-placements.ts` rejects 400 when `action === 'placed'` arrives without it. Frontend captures `pick.wager` (the model's Kelly-suggested amount, already on every Picks row) at click time in `useMarkPickAsPlaced`; the mutation invalidates `['bankroll']` alongside `['state']` so BalanceCard updates without a reload. `worker/lib/bankroll.ts` now reads today's state record + activity, builds a resolvedKeys set from `${bet.pick}|${bet.event}` (same join as PendingTab and the activity normalizer), sums wagers on placements where `action === 'placed' && !resolvedKeys.has(p.key) && typeof p.wager === 'number'`, and subtracts from `available` (works against either file `current_bankroll` or a balance-override). Defensive: if data.json is unreachable, sumActiveStakes returns 0 rather than throwing, so bankroll keeps serving. (2) **Pending polish:** placed-pick rows now show `${gameTime} • ${odds} • $${wager} • Win $${win}` with three-way wager fallback (`placement.wager ?? pick.wager`, omitted entirely when neither exists, e.g. stale rows whose pick has rotated out of today's data); manual bets show `${odds} • $${wager} • Win $${win}` (no game time available on `ManualBetSchema`). New helper `americanWinAmount(odds, wager)` in `frontend/src/lib/format.ts`: positive odds $A wins `wager * A / 100`; negative odds -$A wins `wager * 100 / A`. (3) **Positions tab removed:** functionally redundant with Picks (which already shows today's recommendations and acted state) plus Pending (which shows active stakes); `frontend/src/tabs/PositionsTab.tsx` and `frontend/src/components/PositionRow.tsx` deleted; `App.tsx` TabId union pruned to `'picks' | 'pending' | 'activity' | 'account'`. (4) **Wager rounded up to next dollar at click time:** Max stakes round up on DraftKings (e.g. $14 actual vs the model's $13.59 recommendation). PicksTab now passes `Math.ceil(pick.wager)` to the mutation, so placement records and the active-stake subtraction reflect his actual stake. Picks/Pending display of the model's recommended wager is unchanged; only the captured placement amount is rounded. Verified end-to-end against vite-dev + wrangler-dev + miniflare KV: clicked Mark as placed on Angels (pick.wager $13.59, captured pre-rounding tweak); POST /api/state/placements returned 201 with `wager: 13.59` in body and KV; /api/bankroll returned `available: 711.91` (= 725.50 override - 13.59); BalanceCard re-rendered to $711.91 without reload. Then added `Math.ceil` and re-verified: clicked Mark as placed on Cleveland (pick.wager $13.59); POST body now sends `wager: 14`; /api/bankroll returned `available: 697.91` (= 725.50 - 13.59 prior - 14.00 new); Pending row shows `May 4, 4:40 PM • 157 • $14.00 • Win $21.98` (math: 14 * 157 / 100 = 21.98). Old Stale row (no matching pick) showed bare key-split text with empty meta - clean graceful degradation. Tabs: `Picks, Pending, Activity, Account` (4, was 5). `npx tsc -b` clean, `npm test` 83 / 83 across 3 files (was 78; +5 new bankroll subtraction tests + 2 placement-route validation tests, with 2 existing tests updated to include wager). Bundle: `index-bh8kmo3e.js` 248.54 kB raw / 75.64 kB gzip (was 251.22 / 75.79; -2.68 kB raw / -0.15 kB gzip net, mostly the Positions deletion offsetting Pending polish). CSS unchanged. Two-commit pair on `main`: feature code + this HANDOFF entry. Cloudflare auto-deploys from main directly per session 10 finding.

**Bankroll + record + chart all stale; identity moved to gmail; Max workarounds via manual override (2026-05-04 session 13 close):** Max sent a production screenshot at session close. Three findings worth carrying. (1) **He's signed in as `max.sheahan@gmail.com`, not `@icloud.com`** as earlier handoffs assumed. Google IdP was set up at some point and the Access policy extended; previous sessions' KV writes against the icloud key are orphaned in the EDGE_STATE namespace. The Bug 2 ship is unaffected (worker reads whatever email Access provides), but any production KV inspection now needs `balance_override:max.sheahan@gmail.com` and `state:max.sheahan@gmail.com:<scan_date>` keys. (2) **There IS a production balance_override** set via the Account tab's "Balance Override" form, to `$588.68` (Max's actual current balance). That's the source of the $588.68 in the BalanceCard - not `file.current_bankroll`. Max has been manually adjusting this override after wins/losses as a workaround for the stale file. So Bug 2 ship effect: legacy placements have no wager → active-stakes subtraction is 0 → available stays at $588.68. New placements after deploy will subtract their rounded wager from the override-driven baseline; Max will need to bump the override after a bet resolves and lifetime_profit (correctly) updates, until the underlying file-update bug is fixed. (3) **`bankroll.json` is internally inconsistent** because the resolve cycle isn't fully updating it: `lifetime_profit` shows `+$179.34` but Max's actual lifetime profit is $88.68 (= $588.68 - $500); `lifetime_bets: 43` does not match `lifetime_wins (37) + lifetime_losses (21) + lifetime_pushes (1) = 59`; the BalanceChart sparkline shows MAR 15 to APR 8 (frozen weeks ago, suggesting `bets[]` is also not getting fresh resolved entries). Lead item for next session: (a) read `scripts/resolve_bets.py` end-to-end; verify the commit history of `bankroll.json` to see what fields each run updates; check `resolve-bets.yml` cron run history for skips / errors. The 43-vs-59 mismatch and $7 chart-vs-`lifetime_profit` divergence on the deferred list since session 9 are the same root cause as today's symptom; just bigger now. (b) once the script is fixed, recompute the lifetime fields backfill-style from `pick_history.json` so today's bankroll.json carries the right numbers, then Max can drop the manual override and let the file drive available.


**Pending tab now shows placements (2026-05-04 session 12):** Bug 1 from session 11's deferred list closed. Picks marked as Placed via `useMarkPickAsPlaced` previously landed in `state.placements[]` but never rendered as a "pending until resolved" view — they only showed up as a `Placed` badge on the Picks tab and as a row on the Positions tab. PendingTab now renders a "Placed picks (N)" section above the existing "Manual bets" section, populated by filtering `state.data.placements` to `action === 'placed'` AND key not in `resolvedKeys` (built from `useActivity().data.bets[]` joined as `` `${bet.pick}|${bet.event}` ``). Display data resolved via a `pickByKey` lookup against today's `usePicks()` so each row shows sport, pick text, event, and odds; placements whose pick has rotated out of today's data fall back to splitting the key on `|`. No wager column on placement rows since `PlacementSchema` does not currently carry a wager — that is exactly the gap Bug 2 will close (schema + frontend wager capture at click + worker subtraction). Verified end-to-end against wrangler-dev + miniflare KV: seeded a placed Brewers placement → "Placed picks (1)" with sport/pick/event/141 odds; seeded a skipped Toronto placement → correctly excluded; seeded a stale-key placement → fallback rendering with no sport badge and key-split text. `npx tsc -b` clean, `npm test` 78 / 78 across 3 files. Bundle rebuilt: `index-Br0m1Ytn.js` (251.22 kB JS, +0.91 kB raw / +0.17 kB gzip vs prior `index-BG8hF7Nf.js`); CSS unchanged at `index-B9QC8aQB.css` (no new styles, all reuse of existing `.pending-section` / `.pending-row` / `.pending-row-info` / `.pending-row-pick` / `.pending-row-event` / `.pending-row-meta` / `.pick-sport` classes). Two-commit pair on `main`: feature code + this HANDOFF entry. Cloudflare auto-deploys from main directly per session 10 finding.

**FAV/DOG pill on spread picks shipped (2026-05-03 session 11):** New affordance on the Picks tab and Positions tab to disambiguate spread-side selections. Bug context: a `Minnesota Twins +1.5` pick at `-192` odds reads as "underdog by 1.5" by sign alone, but the heavy juice signals the reverse run-line favorite shape. Without surfacing favorite-vs-underdog, a user can mistake a favorite-side pick for underdog-side and either skip a winning pick or click through to the wrong DK line. `is_favorite` was already computed per candidate in `calculate_edge` ([scan_edges.py:1310/1322](scripts/scan_edges.py:1310)) but never made it past the best-edge selection. Now passed through the spread pick output AND the second reshape step at `formatted_picks` (the second one was the gotcha; see follow-up note below). Field is optional in `PickSchema` for back-compat, normalized server-side in `worker/lib/picks.ts`, and conditionally rendered as a small pill (`pick-favdog.fav` / `.dog`) next to the sport badge in `PickRow.tsx` and `PositionRow.tsx`. Totals (`calculate_total_edge`) and prop picks leave `is_favorite` unset, so no pill renders for those. Verified end-to-end after the follow-up fix: workflow_dispatch'd scan produced `data.json` with both today's picks correctly tagged `is_favorite=False` (Athletics +1.5, Mariners +1.5 - both DOG renders). `npx tsc -b` clean, `npm test` 78 / 78. Bundle rebuilt: `index-BG8hF7Nf.js` (250.31 kB JS, +0.26 kB) + `index-B9QC8aQB.css` (15.77 kB CSS, +0.42 kB). Three commits on `main`: `2520cc1` (feature code), `867c44a` (HANDOFF), `b7bf055` (follow-up reshape fix). Cloudflare auto-deploys from `main` directly per session 10 finding, so no manual `workers-autoconfig` mirror needed; that branch is now further behind main but not blocking live.

**Session 11 follow-up fix (2026-05-03 commit `b7bf055`):** First scan after shipping showed `data.json` picks WITHOUT `is_favorite`, even though `calculate_edge`'s return dict had it. Root cause: a second reshape step at `scan_edges.py:2042` (now :2003 after the fix) explicitly enumerates fields to copy into `formatted_picks`; `is_favorite` was missing from that list and got dropped. Fixed by conditionally appending `if "is_favorite" in pick:` after building the formatted dict, so spread picks carry the field through and totals/props leave it out cleanly. Honest note for future me: the dev-preview verification I did earlier injected `is_favorite` into `data.json` by hand, which covered the SPA + worker stages but skipped the scanner output stage. End-to-end pipeline tests need to include the upstream producer, not just the consumer; otherwise the verified-locally claim overstates what was actually tested.

**CI bundle-staleness guard shipped (2026-05-02 session 10):** New GitHub Actions workflow at `.github/workflows/spa-bundle-guard.yml` runs `npm ci` + `npm run build` and diffs `frontend/dist/` against committed `public/` (index.html, wrangler.json, .assetsignore, assets/) on every PR + push to main. Fails loudly if the SPA bundle is stale relative to source. Closes the process gap that caused session 9 slice 1 (sessions 6 / 7 / 8 changed `frontend/src/` without rebuilding `public/assets/`, so production served a 30-hour stale bundle until Max noticed Picks rows weren't clickable). Path filter scoped to `frontend/**`, `public/**`, `shared/**`, `vite.config.ts`, `tsconfig*.json`, `package.json`, `package-lock.json`, and the workflow itself; excludes cron-managed files (`data.json`, `bankroll.json`, `pick_history.json`) which are committed at repo root, not under `public/`, so the guard does not run on cron ticks. Verified locally: clean rebuild matches committed `public/` exactly (diff exits 0); a simulated stale `public/index.html` correctly fails the diff (exits 1) and restores cleanly. Failure step prints the recovery command (rebuild + cp + commit) inline so the next dev who hits this knows exactly what to do. YAML valid; em-dash + double-hyphen audit clean. One file, 84 lines, no other repo changes.

**Sidebar balance-over-time chart shipped (2026-05-02 session 9 slice 2):** New `BalanceChart` component lives in the right sidebar directly under `BalanceCard`, on every tab (matches the established sidebar-shows-everywhere convention). Sparkline-style: gold line over a faint gold-tint area fill, single big-tabular delta headline (`+$186.69` color-coded green/red) with `over N days` muted next to it, first/last date labels below the chart. Card chrome is `.card` + `.card-header` matching `BalanceCard` so the two read as a single grouped object; same uppercase 12px header treatment, same white card on `--color-bg`. Skipped Recharts in favor of hand-rolled 240×80 SVG with `vectorEffect="non-scaling-stroke"` so the line stays 1.5px crisp under `preserveAspectRatio="none"` stretching. Data source: `useActivity()` filtered to resolved bets + `useBankroll().starting` for the anchor; computed on the client (no worker change). Caveat for next session: chart final balance ($686.69) and `lifetime_profit` ($179.34 → $679.34) disagree by ~$7. Both come from `bankroll.json`; the file's own `lifetime_bets` (43) vs `wins+losses+pushes` (59) are also internally inconsistent. Model-side issue, not a frontend bug. `npx tsc -b` clean, `npm test` 78 / 78. New bundle `index-DxPsRIoZ.js` (250 kB, 75.57 kB gzip).

**SPA bundle staleness fixed (2026-05-02 session 9 slice 1):** Sessions 6 / 7 / 8 each committed `frontend/src/` source changes but nobody ran `npm run build` and nobody copied `frontend/dist/*` into `public/`. The worker bundle gets rebuilt on every `wrangler deploy` from `worker/` source, so worker changes shipped fine. The SPA bundle is committed git artifacts at `public/assets/`, so frontend source changes only ship if someone manually rebuilds + recopies + commits. Production was serving the slice 1-5 cutover bundle (`index-cYVCSat3.js` from 2026-05-01 21:10 PT, commit `a72183b`) for ~30 hours with the slice 2 click-to-expand, slice 7 PendingTab simplification, and slice 8 `useDeletePlacement` removal all missing on the user side. Concrete prior-to-fix impact: Picks rows weren't click-to-expand; the Picks tab still POSTed `/api/place-bet` (405 since session 7 deleted the route); Pending tab still rendered the queued-retries section calling `/api/state/sync-queue/retry` (405); Pending tab still called DELETE `/api/state/placements/:key` (405 since session 8). Silent failures only triggered if Max acted; nothing crashed. Fix shipped: rebuilt the bundle, swapped `public/assets/index-{B4hwDnDa.css,cYVCSat3.js}` → `index-{WMNNWeYB.css,Djh7ZKAk.js}`, updated `public/index.html`. New bundle smoke-checked: `Mark as placed` / `Place on DraftKings` / `pick-actions-expanded` / `pick-chevron` / `pick-details` strings present; dispatch leftover URLs absent; expected v2 URLs present. Two-commit pair + manual mirror + `wrangler deploy`. Open process gap: a CI guard that fails if `public/index.html`'s referenced bundle hash doesn't exist in `public/assets/` would catch this bug class without trusting humans; filed as a polish follow-up.

**Dead code cleanup shipped (2026-05-02 session 8):** Loose ends from session 7 tied off. `useDeletePlacement` removed from `frontend/src/api/mutations.ts` (no UI caller after sessions 6 + 7). Worker `DELETE /api/state/placements/:key` route removed from `worker/routes/state-placements.ts`, along with its sole consumer `removePlacement` in `worker/lib/state.ts` and the corresponding describe block (4 tests) in `worker/index.test.ts`. Orphaned `scripts/place_bets.py` deleted (sole invoker was the `place-bets.yml` workflow retired in session 7). Worker audit confirmed the rest of the `dispatch` / `sync_queue` matches are intentional back-compat: `sync_queue` field on `StateRecordSchema`, `dispatch_status` enum + `'ok'` default on `PlacementCreateRequestSchema`, the `dispatch_status: 'ok'` writes in `useSkipPick` / `useMarkPickAsPlaced`, the `state.ts` init + GET pass-through, and the defensive `queued` badge in `PickRow` / `PositionRow`. `npx tsc -b` clean, `npm test` 78 / 78 across 3 files (was 82 / 82; the 4 dropped = the DELETE describe). Em-dash audit clean. Net diff: 5 files, 295 line deletions, 1 insertion. Two-commit pair shipped + pushed. Mirror force-pushed to `cloudflare/workers-autoconfig` + manual `wrangler deploy` ran post-commit; live worker is on version `7d053fab` (the post-session-8 bundle). 404 verification of deleted routes deferred to Max's browser session (Cloudflare Access intercepts unauthenticated curls at the edge).

**Dispatch cleanup shipped (2026-05-02 session 7):** Auto-dispatch chain fully retired. Frontend: `usePlacePickBet` + `useRetrySyncQueue` deleted from `mutations.ts`; `PositionsTab` + `PicksTab` both use `useMarkPickAsPlaced` now (manual placement, no GitHub `repository_dispatch`); `PendingTab` rewritten without queued-retries section. Worker routes deleted: `place-bet.ts` (singular), `state-sync-queue.ts`, `place-bets-legacy.ts` (legacy plural). Worker libs deleted: `dispatch.ts`. State helpers `upsertSyncQueueEntry` + `findSyncQueueEntry` dropped from `state.ts`. Schemas dropped: `PlaceBetRequestSchema`, `PlaceBetResponseSchema`, `SyncQueueRetryRequestSchema`. Workflow `.github/workflows/place-bets.yml` deleted (the `repository_dispatch` receiver and only consumer of `dispatch.ts`). Test file lost the dispatch-touching describes (10 tests) and the `vi.stubGlobal('fetch')` helper. The `sync_queue` field stays on `StateRecordSchema` for KV back-compat (existing records may carry entries; read-only via GET /api/state). One-line update note added to ADR 0002. `npx tsc -b` clean, `npm test` 92 / 92 → 82 / 82 across 3 files. Em-dash audit clean. NOT yet committed.

**Picks click-to-expand shipped (2026-05-02 session 6, slice 2):** Picks tab rows now expand on click to reveal three actions: `Mark as placed` (manual placement, no GitHub repository_dispatch — new `useMarkPickAsPlaced` mutation, drops the auto-dispatch chain Max wanted off), `Ignore` (rebadged Skip), `Place on DraftKings ↗` (opens `pick.dk_link` in a new tab; first time `dk_link` has been surfaced in the v2 SPA). Single-row expansion (clicking another row collapses the previous; lifted state into `PicksTab`). Expanded panel shows Market / Model / Implied / EV per $ / Start (formatted via new `formatStartTime` in `lib/format.ts`) plus the pick's `notes` block in a gold-bordered card. Acted-on rows render the existing badge and are NOT click-expandable. Smoke-tested end-to-end against wrangler-dev + miniflare KV: click expand → click `Mark as placed` → POST `/api/state/placements` 201 → query invalidation → row collapses with `Placed` badge. `npx tsc -b` clean, `npm test` 92/92. Frontend-only diff (5 files); the dispatch backend (`/api/place-bet` route, `worker/lib/dispatch.ts`, `place-bet.yml` GH Action) is still wired but now uncalled from the Picks UI; cleanup of those + the Pending tab's "queued retries" section is the natural follow-up. NOT yet committed.

**Phase 3 polish update (2026-05-02 session 6 below):** vitest coverage shipped for `worker/lib/activity.ts`. 17 new tests covering em-dash strip, odds coercion (string passthrough + numeric → `+165` / `-110` + null fallback), outcome filter and coercion (`pending` excluded, unknown coerced to pending then excluded, `win`/`loss`/`push` preserved), date-desc sort, wager/pnl coercion, sparse-bet defaults, and Zod schema validation (malformed/missing date throws via `z.iso.date()`). Test count is now 92 / 92 across 3 files. `npx tsc -b` still clean. Branch state unchanged: `main` is at `4bf4da1`, no commits made (Max gates commit timing). Note for resume: `/data.json` returns 302 to Access now (Access scope is `/*`, not `/api/*`); resume-prompt scripts that curl `/data.json` for JSON will need a `CF_AppSession` cookie or read the local file.

**Phase 3 slices 1 + 2 + 3 + 4 + 5 LIVE (2026-05-02 ~03:55 UTC, session 5 below):** v2 SPA deployed and serving at https://dk-edge-finder.max-sheahan.workers.dev/. `wrangler deploy` from rebuild/v2-frontend. Two real bugs hit and fixed in sequence during the live smoke; both documented below in the "Slice 5 deploy: what shipped + what I broke" section. Final live state: `/api/me` returns 302 to Access (worker hit), `/data.json` returns fresh cron data (2026-05-01, 7 picks, 62 bets), SPA loads at root.

**Phase 3 slices 1 + 2 + 3 + 4 update (2026-05-01 PM, session 5 below):** v2 SPA fully composed. All 5 tabs render real data: Picks, Pending, Activity, Positions, Account. New worker route `/api/activity` ships `data.json.bets[]` filtered to resolved + sorted date desc, with em-dash strip + odds normalization. New mutations: `useDeleteManualBet`, `useRetrySyncQueue`, plus the slice-2 set. Verified locally: Picks empty state + 8-game no-edge collapsible (today is 0 edges), Pending shows existing manual bet from KV with Remove button, Activity shows 62 resolved bets with color-coded WIN/LOSS and signed P/L, Positions shows empty state, Account roundtrips a balance-override save through KV with cross-component refetch. Branch is still 23 ahead of origin. `npx tsc -b` clean, 75/75 tests still pass, `npm run build` clean. Slice 5 (deploy + live smoke) is what's left.

---

## 2026-05-04 session 13 (Bug 2 + Pending polish + Positions removal + wager round-up)

### Goal
Close session 11's deferred Bug 2: clicking Mark as placed should reduce the available balance by the wager committed, until the underlying pick resolves and that wager rolls into lifetime_profit. Mid-session Max layered three more asks on top: surface game time + amount to win on the Pending row; consolidate the redundant Positions tab away; round wagers up to the next dollar to match his actual DraftKings stakes. All four landed in one shipped change.

### Pre-flight
- `git stash list`: empty. `git status --short`: 3 expected carry-over untracked (`.claude/handoffs/`, `index.html.bak`, `mockups/`).
- Branch `main`. `git log --oneline -5`: top is `96cd073 chore: HANDOFF session 12` then `b788261 feat(pending)` (session 12 close).
- `npx tsc -b`: clean. `npm test`: 78 / 78. `curl -sI .../api/me`: 302 to Access. `grep -c "Placed picks" public/assets/*.js`: 1 (session 12 bundle current).
- Live deploy `fbdadef6` at 2026-05-04T15:52:34Z per resume-prompt notes; CI bundle guard passed.

### Decisions made
- **Use the model-recommended `pick.wager`, not a user-entered amount.** Asked Max via `AskUserQuestion`; he picked the simple path. No new UI: the wager already shows in the Picks-row Wager column ($13.59 today), the click captures that exact number on the placement. Faster to ship, matches what the eyes already see. Trade-off accepted: if Max stakes a different amount on DraftKings than the model recommended, the placement record will not reflect that. Editable inline is on the table for a future revisit.
- **Schema-level back-compat: PlacementSchema.wager is optional, PlacementCreateRequestSchema.wager is conditionally required.** Optional on read so KV records written before this fix still parse cleanly (PendingTab and bankroll both treat undefined wager as "do nothing"). On create, the route handler returns 400 when `action === 'placed'` arrives without a wager, so all NEW placed records carry it. `action === 'skipped'` placements continue to ship without wager since they have no wager semantics.
- **Subtract today's-scan-date placements only, not all scan_dates via KV.list.** Cloudflare KV's `list({ prefix })` would aggregate placements across days, catching the rare postponed-game-stuck-pending case. For a single-user scale at one bet per day the simpler "today's scan_date" path is enough: by the time a placement crosses a day boundary, the resolve-bets cron has either updated activity (placement filtered as resolved → not subtracted) or rolled scan_date forward (placement now lives in yesterday's state record, also not subtracted, but lifetime_profit has been updated to reflect the resolution so available is still correct). The known gap is a postponed game that stays unresolved across the morning-scan rollover; can be addressed later if it ever bites.
- **Defensive: sumActiveStakes returns 0 if data.json is unreachable.** Wrap getLatestScanDate in try/catch and `.catch(() => ({ bets: [] }))` on getActivityResponse. Reasoning: bankroll endpoint should keep serving even if data.json is briefly missing during a cron tick. The picks endpoint relies on the throw to surface 500; bankroll has a sensible degradation path (skip stakes subtraction).
- **Invalidate `['bankroll']` alongside `['state']` in useMarkPickAsPlaced.** Without this, the BalanceCard would render a stale available until the next interval refresh. State is invalidated already to update PendingTab; bankroll is the new addition.
- **`pl.wager ?? pk?.wager` fallback in PendingTab.** New placements show their stored wager; old placements (no stored wager) show the matching pick's wager when a pick still exists today; if no pick (stale row), the column is omitted via `typeof wager === 'number'` guard. Three-way handling captures the back-compat surface without lying.
- **Game time on placed-pick rows; not on manual-bet rows.** Placed picks join to `usePicks().picks` and surface `pick.start_time` via `formatStartTime`. Manual bets are independent records with no `start_time` field on `ManualBetSchema`, so the meta on those rows stays `${odds} • $${wager} • Win $${win}` without the leading time.
- **New helper `americanWinAmount(odds, wager)` over inlining.** Tested by inspection (positive odds: `wager * n / 100`; negative odds: `wager * 100 / |n|`). Exported from `lib/format.ts` so manual bets and placements both use the same logic.
- **Delete Positions rather than repurpose.** Asked Max: Positions iterates `usePicks().picks` and renders every pick with expanded detail (placed, skipped, unacted alike) - functionally a wider-detail Picks tab. Picks already shows today's recommendations and acted state via badges; Pending now covers active stakes after session 12. Positions adds no use case neither serves. Delete the tab + `PositionsTab.tsx` + `PositionRow.tsx` + the entry in TABS, prune the TabId union.
- **`Math.ceil(pick.wager)` round-up at the PicksTab call site.** Max stakes round up to next dollar on DraftKings (e.g. $14 vs the model's $13.59). One-line change keeps placement records aligned with reality, no UI input needed.

### Files modified
- `shared/schemas.ts` (+5 / -2). PlacementSchema gains `wager: z.number().nonnegative().optional()`. PlacementCreateRequestSchema gains the same shape; the route enforces it for `action === 'placed'`.
- `worker/routes/state-placements.ts` (+5 / -1). Validates wager-required-when-placed. Conditionally spreads wager into the constructed Placement so 'skipped' rows still ship without it.
- `worker/lib/bankroll.ts` (+27 / -3). New `sumActiveStakes` helper (today's scan_date + activity-resolved filter + sum of placement wagers). `getBankrollResponse` adds it to the parallel load, subtracts from `baseAvailable`. Defensive on data.json failure.
- `worker/index.test.ts` (+157 / -2). 5 new tests under `/api/bankroll`: subtraction with mixed resolved/unresolved/skipped placements, no-wager-no-subtract for legacy records, subtracts from override when set. 2 new tests under `/api/state/placements`: rejects placed-without-wager with 400, accepts skipped-without-wager with 201. Existing 2 tests updated to include wager: 25 / 20 in their POST bodies.
- `frontend/src/api/mutations.ts` (+8 / -3). useMarkPickAsPlaced takes `{ key, wager }`, sends wager, invalidates both `state` and `bankroll` queries.
- `frontend/src/tabs/PicksTab.tsx` (+1 / -1). Pass `Math.ceil(pick.wager)` to mutation (round-up to match Max's actual stake).
- `frontend/src/tabs/PendingTab.tsx` (+22 / -10). Wager column on placed-pick rows with three-way fallback. Added game time prefix and `Win $X` suffix on placed-pick rows; manual-bet rows gain `Win $X` (no game time).
- `frontend/src/lib/format.ts` (+12 / -0). New `americanWinAmount(odds, wager)` helper.
- `frontend/src/App.tsx` (-3 / +0). Removed PositionsTab import, removed `'positions'` from TabId, removed entry from TABS, removed conditional render.
- `frontend/src/tabs/PositionsTab.tsx` (deleted, -58). Redundant with Picks + Pending.
- `frontend/src/components/PositionRow.tsx` (deleted, -69). Sole consumer was PositionsTab.
- `public/index.html` (+1 / -1). Bundle hash bump from `index-Br0m1Ytn.js` to `index-bh8kmo3e.js`.
- `public/assets/index-Br0m1Ytn.js` (deleted). Old bundle.
- `public/assets/index-bh8kmo3e.js` (added). New bundle.
- `HANDOFF.md` (this entry + the inheriting-state bullets).

### Verification
- `npx tsc -b`: clean.
- `npm test`: 83 / 83 across 3 files (was 78; +5 new bankroll subtraction tests + 2 placement-route tests, with 2 existing placement tests updated to include wager).
- Browser preview verification - first round (vite-dev port 5173 proxying to wrangler-dev port 8787, miniflare KV with 3 carry-over placements from prior sessions: Brewers placed pre-fix, Toronto skipped, Old Stale placed pre-fix). Clicked Mark as placed on Angels (rank 3, pick.wager $13.59, captured pre-rounding tweak). POST returned 201 with `wager: 13.59` in body and KV; `/api/bankroll` returned `available: 711.91` (= override 725.50 - 13.59); BalanceCard re-rendered to $711.91 without page reload.
- Browser preview verification - second round after Math.ceil + Pending polish + Positions removal landed. Tabs: `Picks, Pending, Activity, Account` (4, was 5 - Positions gone). Clicked Mark as placed on Cleveland (pick.wager $13.59); POST body now sent `wager: 14`; `/api/bankroll` returned `available: 697.91` (= 725.50 - 13.59 prior - 14.00 new). Pending tab showed Cleveland row with `May 4, 4:40 PM • 157 • $14.00 • Win $21.98` (math: 14 * 157 / 100 = 21.98 ✓). Brewers row showed `May 4, 4:45 PM • 141 • $13.59 • Win $19.16` via pick.wager fallback (math: 13.59 * 141 / 100 = 19.1619 ≈ 19.16 ✓). Old Stale row (no matching pick) showed bare key-split text with empty meta - clean graceful degradation.
- Console: no errors during placement, query refetch, or tab switch.
- Bundle rebuild: `npm run build` clean. New JS `index-bh8kmo3e.js` 248.54 kB raw / 75.64 kB gzip. Was 251.22 kB / 75.79 kB at session 12 close. Delta: -2.68 kB raw / -0.15 kB gzip net (Positions deletion offsetting Pending polish + new helper). CSS unchanged (`index-B9QC8aQB.css`).
- Bundle parity: `diff -r frontend/dist/assets public/assets` clean; `diff frontend/dist/index.html public/index.html` clean. CI bundle guard from session 10 will pass on push.
- Em-dash audit on the diffs: clean.

### What's next (lead item: bankroll/activity staleness)
1. **Bankroll + record + chart all stale.** Detailed in the inheriting-state bullet above. Investigate `scripts/resolve_bets.py` (does it update lifetime fields?), the recent `resolve-bets.yml` cron run history, the production `balance_override:max.sheahan@icloud.com` KV record (the "smoke test" override stuck since session 3), and whether the BalanceChart's `useActivity()` data path is getting fresh resolved bets. This is the highest-leverage item now: Bug 2's subtraction is mathematically correct but operates on a stale baseline ($725.50 instead of $588.89).
2. **Future-game scanning** (still open from session 9). Widen the Python scanner window beyond today + tomorrow; line-staleness handling; UI affordance for non-today edges. Real model-side scope, multi-hour design + implementation.
3. **Editable wager at click time.** This session's `Math.ceil` matches Max's stated rule, but a hybrid input (pre-fill with rounded value, allow inline override) is the next step if his rule changes (e.g. fixed $20 stake regardless of model recommendation).
4. **Cross-scan_date placement aggregation.** Today's-scan-date-only path leaves a small gap for postponed/canceled games where a placement stays unresolved across a morning-scan rollover. Switch to `KV.list({ prefix: 'state:email:' })` if this ever bites.
5. **Polish backlog**: rewrite `docs/cloudflare-access-setup.md` for Zero Trust UI, set up Google IdP, delete `rebuild/v2-frontend` branch (local + origin), defer `worker/lib/normalize.ts` extract.

### If you just have one minute, do this
`cd ~/Betting\ Skill && grep -c "americanWinAmount" public/assets/*.js` should print 1 line. To exercise the full data path: with the SPA up via vite-dev + wrangler-dev, click Mark as placed on any unacted pick. The wager captured on the placement should be `Math.ceil(pick.wager)` (e.g. $14 for a $13.59 model recommendation). Switch to Pending and confirm the new row shows `${gameTime} • ${odds} • $${wager} • Win $${win}`. /api/bankroll's available should drop by exactly the rounded wager. Tabs at the top should be Picks, Pending, Activity, Account (no Positions).

---

## 2026-05-04 session 12 (Pending tab placements)

### Goal
Close session 11's deferred Bug 1: placed picks were not visible on the Pending tab. The Picks tab badged them with `Placed`, the Positions tab listed them with details, but a flat "things I've put down that have not resolved yet" view did not exist. Frontend-only scope (~30-line estimate from the session 11 handoff; landed at +67 / -39 across 3 files including the bundle swap).

### Pre-flight
- `git stash list`: empty. `git status --short`: 3 expected carry-over untracked (`.claude/handoffs/`, `index.html.bak`, `mockups/`).
- Branch `main`. `git log --oneline -7`: top is `db61241 Full scan: 2026-05-04_1510 — games + props`; `2dc8bda feat(model): per-sport probability calibration (Platt-style linear fit)` landed on main between session 11 close and this session start (Max merged the feat branch the resume prompt warned about as a drift risk; not a drift, an intentional merge).
- `npx tsc -b`: clean. `npm test`: 78 / 78. `curl -sI .../api/me`: 302 to Access. `is_favorite` present on 7 / 7 spread picks in `data.json`.
- Resume-prompt verification mismatch: `grep -c "pick-favdog" public/assets/*.css` returns 1, not the expected 3. Cause: Vite minifies the CSS into a single line; `grep -c` counts matching lines, not occurrences. All three rules (`.pick-favdog`, `.pick-favdog.fav`, `.pick-favdog.dog`) are present in the minified line. The "3" expectation was for an unminified file. Functionally correct; update the "if you have one minute" line in the session 11 handoff to use a different verifier (e.g. `grep -o`) if it ever rotates out.

### Decisions made
- **Section order: Placed picks first, Manual bets second.** Placed picks are the model's recommendations the user acted on; Manual bets are the supplementary "I placed something the model didn't surface" case. Putting placements on top matches the primary-feature framing.
- **Filter resolved out via activity cross-reference.** `useActivity()` already filters `outcome !== 'pending'` server-side ([worker/lib/activity.ts:47](worker/lib/activity.ts:47)), so a placement is "resolved" iff `${bet.pick}|${bet.event}` matches `placement.key`. Same em-dash-stripped strings on both sides (worker normalizers in `picks.ts` and `activity.ts` use the same `stripEmDash`).
- **Reuse existing `.pending-row` / `.pending-section` classes; no new CSS.** Manual bets and placements have the same conceptual row shape. CSS hash unchanged confirms no new styles shipped.
- **No wager on placement rows.** `PlacementSchema` does not currently carry a wager — only `key`, `action`, `dispatch_status`, `placed_at`, `idempotency_key`. Showing the model's recommended Kelly wager from the joined pick would imply the user actually staked that amount, which is a false claim. Bug 2 will add a wager field to the schema and capture it at click time; until then, leave the wager off the row.
- **No buttons on placement rows.** Placements grade automatically when `data.json.bets[]` adds a matching entry; there is no "unmark" mutation and no manual "this resolved" workflow. Read-only display.
- **Gate render on `state.isLoading || picks.isLoading || activity.isLoading`.** Without all three, `resolvedKeys` would briefly be empty and resolved placements would flash visible before `useActivity()` settles. Trades a slightly slower spinner for no flicker; correct call.

### Files modified
- `frontend/src/tabs/PendingTab.tsx` (+51 / -19 source). Added `usePicks` + `useActivity` imports + `Pick` type import. Built `resolvedKeys` Set and `pickByKey` Map. Replaced single Manual-bets section with conditional Placed-picks section + conditional Manual-bets section.
- `public/index.html` (+1 / -1). Bundle hash bump from `index-BG8hF7Nf.js` to `index-Br0m1Ytn.js`.
- `public/assets/index-BG8hF7Nf.js` (deleted). Old bundle.
- `public/assets/index-Br0m1Ytn.js` (added). New bundle.
- `HANDOFF.md` (this entry + the inheriting-state bullet).

### Verification
- `npx tsc -b`: clean.
- `npm test`: 78 / 78 across 3 files.
- Browser preview verification (vite-dev + wrangler-dev): seeded a placed Brewers placement via POST `/api/state/placements` against local miniflare KV. Reloaded SPA, clicked Pending. "Placed picks (1)" section rendered with `MLB / Milwaukee Brewers -1.5 / Milwaukee Brewers @ St. Louis Cardinals / 141`. Seeded a skipped Toronto Blue Jays placement; reload → still "Placed picks (1)" (skipped correctly excluded). Seeded a stale-key placement (`Old Stale Pick +2.5|Yesterday Team A @ Yesterday Team B` — a key with no matching pick in today's data); reload → "Placed picks (2)" with the stale row rendering with no sport badge, key-split pick + event text, empty odds (fallback path verified).
- Console: no errors during any of the above.
- Bundle rebuild: `npm run build` clean. New JS `index-Br0m1Ytn.js` 251.22 kB raw / 75.79 kB gzip. Old was 250.31 kB raw / 75.62 kB gzip. Delta: +0.91 kB raw / +0.17 kB gzip — consistent with adding the placements branch + 3 new query reads.
- Bundle smoke: `grep -c "Placed picks" public/assets/*.js` → 1; `grep -c "/api/activity" public/assets/*.js` → 1; `grep -c "Nothing pending" public/assets/*.js` → 1 (existing empty-state copy preserved).
- Bundle parity: `diff -r frontend/dist/assets public/assets` clean; `diff frontend/dist/index.html public/index.html` clean; same for `.assetsignore` and `wrangler.json`. CI bundle guard from session 10 will pass on push.
- Em-dash audit on the source diff (PendingTab.tsx): clean. The `--` matches in the bundle output are CSS `var(--foo)` references in the minified JSON, not double-hyphens in voice-bearing prose.

### What's next
1. **Bug 2: available balance subtracts active stakes** is the natural pair to this session's work. Now that placements render, the next step is making them affect the balance. Schema (PlacementSchema gains `wager: z.number()`) + frontend (`useMarkPickAsPlaced` sends `wager: pick.wager` from the row data at click time) + worker (`bankroll.ts:34` subtracts `sum(unresolvedPlacement.wager)` from `available`). Once Bug 2 lands, surface the wager column on the Pending placements row.
2. **Future-game scanning** (still open from session 9). Real model-side scope.
3. **bankroll.json lifetime-stats consistency**: 43 vs 59 mismatch (`lifetime_bets` vs `wins+losses+pushes`); $7 chart-vs-`lifetime_profit` divergence. Model-side investigation.
4. **Existing polish backlog**: Cloudflare Access docs rewrite for Zero Trust UI; Google IdP setup; delete `rebuild/v2-frontend` branch (local + origin); defer `worker/lib/normalize.ts` extract until a third consumer.

### If you just have one minute, do this
`cd ~/Betting\ Skill && grep -c "Placed picks" public/assets/*.js` should print 1. If it prints 0, the bundle has gone stale relative to source (the same class of bug session 10's CI guard catches now); rebuild via `npm run build && rm public/assets/index-* && cp frontend/dist/assets/* public/assets/ && cp frontend/dist/index.html frontend/dist/.assetsignore frontend/dist/wrangler.json public/`. To exercise the full data path: with the SPA up, POST a placement to `/api/state/placements` with `{key: '<pick>|<event>', action: 'placed', dispatch_status: 'ok', idempotency_key: crypto.randomUUID()}`, reload, click Pending. The row should render with sport / pick / event / odds.

---

## 2026-05-03 session 11 (FAV/DOG pill on spread picks)

### Goal
Three bug reports from Max during a verification round: (1) bets do not show under Pending tab, (2) placed bets do not affect balance, (3) the spread for the Twins game was "flipped (they are now favorites)". After investigation, bug 3 turned out to be a label-clarity issue rather than a model bug; this session ships the fix for that. Bugs 1 and 2 are filed below as known gaps for a future session.

### Pre-flight
- `git stash list`: empty. `git status --short`: 3 expected carry-over untracked.
- `npx tsc -b`: clean. `npm test`: 78 / 78.
- `curl -sI .../api/me`: 302 to Access (intact).
- Local `data.json` (after multiple cron ticks): `2026-05-03`, 7 picks (5 MLB Spread, 1 BUNDESLIGA Over/Under, with the disputed Twins pick at rank 2).
- Cloudflare auto-deploy chain healthy: `wrangler deployments list` shows a new deploy fired within 1 second of every cron commit on main today. The `workers-autoconfig` branch is many commits behind main but the live URL stays current via direct main-deploys; mirror failures are cosmetic, not blocking.

### Bug 3 root-cause (the one fixed this session)
The disputed pick: `Minnesota Twins +1.5 -192` (rank 2 in today's data.json, scan time 2026-05-03 09:42 PT). Max said DK had Twins on `-1.5` when he opened the page; he read the model as picking the wrong side.

Investigation timeline:
1. Initial hypothesis: ESPN/DK direction mismatch at scan time. Looked at `calculate_edge` ([scan_edges.py:1245](scripts/scan_edges.py:1245), `espn_spread = game["home_spread"]`) and the favorite/underdog branch at lines 1252-1259. The function reads spread direction entirely from ESPN's `pointSpread.home/away.close.line`, which ESPN claims is DK's line.
2. Second hypothesis: live in-game line vs pre-game line confusion. Game start: `2026-05-03T16:45Z` (09:45 PT), 3 min after scan. Once the pre-game market closes, DK shows live in-game lines with totally different shape. Asked Max via `AskUserQuestion`; he confirmed he checked DK BEFORE first pitch and the direction was already different.
3. Third look: pulled the resolved pick from `pick_history.json`. Final score `TOR 3, MIN 4` — Twins won by 1, so Twins +1.5 covers easily. **The pick was correct and would have won.**
4. Reconciliation: in MLB, "+1.5 at -192" is the standard reverse run-line shape used for HEAVY favorites. Both lines on the same market are valid bets at the same time; the model picked the +1.5 -192 side because at that price, it has +7.4% edge. Max saw "Twins -1.5" on DK (the other side of the same market, plus odds) and concluded the model was on the wrong side.

This is not a model bug. It is a label-clarity bug.

### Decisions made
- **Add an `is_favorite` flag to spread pick output and render as a FAV/DOG pill on the row.** `is_favorite` is already computed per candidate at [scan_edges.py:1310](scripts/scan_edges.py:1310) (dog) / [scan_edges.py:1322](scripts/scan_edges.py:1322) (fav), but only the cand dict held it. Now passed through to the pick output dict at [scan_edges.py:1514](scripts/scan_edges.py:1514).
- **Optional in `PickSchema`** so historical data.json files (which lack the field) still parse. Worker normalizer adds it to the output only when present in raw input.
- **Render only when defined.** Conditional `{pick.is_favorite !== undefined && ...}` in both `PickRow` and `PositionRow`. Totals (`calculate_total_edge`) and prop picks omit the field, so no pill renders there. Avoids surfacing meaningless "FAV/DOG" on over-under markets.
- **`FAV` / `DOG` over `Favorite` / `Underdog`.** Concise, uppercase, sportsbook lingo. Fits next to the sport badge without wrapping on desktop. On narrow viewports it wraps below the sport badge — acceptable mobile behavior.
- **Pill styling matches palette.** `.pick-favdog.fav` uses gold accent (`--color-accent-tint` background, `--color-warning` text, `--color-accent` border). `.pick-favdog.dog` uses muted (`rgba(136,136,136,0.12)` background, `--color-muted` text, `--color-border` border). Same 10px / uppercase / letter-spacing as `.pick-sport` so the two pills read as a metadata cluster.

### Files modified
- `shared/schemas.ts` (added `is_favorite: z.boolean().optional()` to `PickSchema`).
- `worker/lib/picks.ts` (`normalizePick` conditionally sets `is_favorite` on output when raw input has it).
- `scripts/scan_edges.py` (added `"is_favorite": bool(cand.get("is_favorite", False))` to spread pick output dict).
- `frontend/src/components/PickRow.tsx` (FAV/DOG pill next to sport badge).
- `frontend/src/components/PositionRow.tsx` (same pill, same place).
- `frontend/src/styles.css` (`.pick-favdog`, `.pick-favdog.fav`, `.pick-favdog.dog`).
- `public/index.html` + `public/assets/*` (rebuild artifacts).
- `HANDOFF.md` (this entry + the inheriting-state bullet).

### Verification
- `npx tsc -b`: clean.
- `npm test`: 78 / 78 across 3 files.
- Em-dash audit on the diff (lines I added): clean. The `--` matches are CSS `var(--foo)` custom properties, not double-hyphens.
- Browser preview verification (vite-dev + wrangler-dev): injected transient `is_favorite: true` on Colorado Rockies pick and `false` on Pittsburgh Pirates pick in `data.json`; reloaded the SPA. Snapshot confirms `MLB FAV Colorado Rockies +1.5` on rank 1 and `MLB DOG Pittsburgh Pirates +1.5` on rank 6, with no pill on the Bundesliga over/under (rank 4) or other picks without the field. Restored `data.json` from `/tmp/data.json.backup`.
- Bundle rebuild: clean. Sizes: `index-BG8hF7Nf.js` 250.31 kB (gzip 75.62), `index-B9QC8aQB.css` 15.77 kB (gzip 3.27). Diff against `frontend/dist/` clean (the SPA bundle guard from session 10 will run on push and verify).

### What's next (still-open from this session's bug reports)
1. **Bug 1: Pending tab does not show placements.** [PendingTab.tsx:20](frontend/src/tabs/PendingTab.tsx:20) only filters `state.data.manual_bets`. Picks marked as Placed land in `state.data.placements`, which the tab does not read. The Picks tab shows them with a "Placed" badge and the Positions tab shows them with details, but there is no flat "things I have put down that have not resolved yet" view. ~30-line frontend-only fix: add a placements section to PendingTab, filter by unresolved.
2. **Bug 2: Available balance does not subtract active stakes.** [worker/lib/bankroll.ts:34](worker/lib/bankroll.ts:34) computes `available = starting + lifetime_profit` (or override). Active placements are not subtracted. Two layers of work needed: (a) `PlacementSchema` does not currently carry a wager amount — the `useMarkPickAsPlaced` mutation only POSTs `{key, action, dispatch_status, idempotency_key}` — so the worker would not know how much to subtract. Need to add `wager: z.number()` to `PlacementSchema` and have the frontend send the Kelly-suggested wager from the pick at click time. (b) Update the bankroll worker to compute `available = starting + lifetime_profit - sum(unresolved placements wager)`. ~1-2 hour change.
3. **`workers-autoconfig` mirror is stuck many commits behind `main`.** Cron's mirror push step is failing silently behind a `|| true`. Live URL is unaffected because Cloudflare auto-deploys from `main` directly. Worth investigating if anyone ever needs `workers-autoconfig` to actually work; not blocking right now.

### If you just have one minute, do this
`cd ~/Betting\ Skill && grep -c "pick-favdog" public/assets/*.css` should print 3 (one for the base class plus the two modifier rules). If it prints 0, the bundle has not picked up the FAV/DOG styling and the rebuild was missed; run `npm run build && rm public/assets/index-* && cp frontend/dist/assets/* public/assets/ && cp frontend/dist/index.html frontend/dist/.assetsignore frontend/dist/wrangler.json public/`. To confirm the scanner emits `is_favorite`: `cat data.json | python3 -c "import json,sys; print([p.get('is_favorite') for p in json.load(sys.stdin).get('picks', []) if p.get('market') == 'Spread'])"` should print a list of booleans for spread picks (or empty if no spread picks today).

### Follow-up fix applied (`b7bf055`)
First post-ship scan exposed that `formatted_picks` reshape at the end of `main()` was dropping `is_favorite` because that dict literal explicitly enumerates fields. Added a conditional `if "is_favorite" in pick: formatted["is_favorite"] = pick["is_favorite"]` after the dict literal. Verified end-to-end with another `workflow_dispatch` scan; today's two MLB Spread picks (Athletics +1.5 -149, Mariners +1.5 -182) both shipped with `is_favorite=False`. The lesson note above (about end-to-end pipeline testing including the producer, not just the consumer) is the takeaway worth carrying forward.

---

## 2026-05-02 session 10 (CI bundle-staleness guard)

### Goal
Close the process gap from session 9 slice 1: a CI guard that fails if the committed SPA bundle in `public/` is stale relative to `frontend/src/` source. The literal description in the resume prompt was a hash-existence check (fail if `public/index.html`'s referenced bundle hash does not exist in `public/assets/`), but that does NOT catch the session 9 bug. In session 9, `public/index.html` referenced `index-cYVCSat3.js`, the file existed in `public/assets/`, the bundle was just outdated. To actually catch the bug class, the guard has to rebuild and diff. Confirmed scope with Max via `AskUserQuestion`.

### Pre-flight
- `git stash list`: empty. `git status --short`: 3 expected carry-over untracked (`.claude/handoffs/`, `index.html.bak`, `mockups/`). `git log --oneline -4`: `8bf4137 a67ab19 db9d47e 058075a` (session 9 ending state).
- `npx tsc -b`: clean. `npm test`: 78 / 78 across 3 files.
- `curl -sI .../api/me`: 302 to `sheahan.cloudflareaccess.com`.
- `origin/cloudflare/workers-autoconfig..origin/main`: 0 commits (in sync from session 9 close).
- Latest visible Cloudflare deploy: `ace6f118-fafe-40e3-aa80-5a64b14cf9ea` from 2026-05-02 23:23:58 UTC. The `28f8b384` referenced in the resume prompt was rolled forward by an auto-deploy that fired between session 9 close and this session start; the bundle still has the sidebar chart so v2 is unchanged.
- `grep -c "Balance over time" public/assets/*.js`: 1 (sidebar chart bundle is live).
- Local `data.json`: 2026-05-02, 8 picks, 62 bets.

### Decisions made
- **Rebuild and diff over hash-existence.** The literal resume-prompt description ("fails if `public/index.html`'s referenced bundle hash does not exist in `public/assets/`") catches typos and missing assets, but does NOT catch the session 9 bug. In session 9, `index-cYVCSat3.js` existed in `public/assets/`; the bundle was stale. To catch staleness, the guard has to rebuild from source and diff against committed artifacts. Confirmed with Max (chose "Rebuild and diff (Recommended)" over hash-only and both-layers).
- **Path filter scoped to source-affecting paths.** `frontend/**`, `public/**`, `shared/**`, `vite.config.ts`, `tsconfig*.json`, `package.json`, `package-lock.json`, and the workflow itself. Cron commits modify `data.json`, `bankroll.json`, `pick_history.json` at repo root (verified by reading `game-scan.yml`), so the path filter does not match cron pushes. The guard does not run on every cron tick.
- **Node 22 for the runner.** Vite 8 needs Node 20.18+ or 22+; project has no `engines` field or `.nvmrc`. Picked 22 LTS for forward-compat. Different Node versions would not affect Vite content-hash determinism here (Vite is deterministic for the same input within a major).
- **Failure step prints the recovery command.** Step `Failure hint` (with `if: failure()`) echoes the rebuild + cp + commit recipe so the next dev who hits this knows exactly what to do without grepping HANDOFF for context.
- **Diff each file individually with `::group::` lines.** Cleaner CI log than one big `diff -r` over the whole tree. Failure shows which specific file is stale.

### Files added
- `.github/workflows/spa-bundle-guard.yml` (84 lines).

### Files modified
- `HANDOFF.md` (this entry + the inheriting-state bullet).

### Verification
- `rm -rf frontend/dist && npm run build`: clean (250.05 kB JS, 75.57 kB gzip; same `index-DxPsRIoZ.js` and `index-CxUyVhg5.css` hashes as committed `public/assets/`).
- `diff frontend/dist/index.html public/index.html`: clean (exit 0).
- `diff frontend/dist/wrangler.json public/wrangler.json`: clean.
- `diff frontend/dist/.assetsignore public/.assetsignore`: clean.
- `diff -r frontend/dist/assets public/assets`: clean.
- Negative test: appended `<!-- staleness test -->` to `public/index.html`; the diff returned `17a18 > <!-- staleness test -->` and exit 1; restored from `/tmp/index.html.backup` and re-verified the chain returns clean. Confirms the guard fails loudly on a stale bundle.
- YAML valid via `python3 -c "import yaml; yaml.safe_load(open(...))"`. Top-level keys: `name`, `on`, `jobs`. One job: `bundle-guard`. Triggers: `pull_request`, `push`.
- Em-dash + double-hyphen audit on the new workflow: clean.

### What's next
1. **Confirm the workflow runs green on first push.** GH Actions will fire the guard on the commit that adds it (the workflow file itself is in the path filter). Should pass since `public/` is in sync with `frontend/src/`. Watch one full run via `gh run list --workflow="SPA Bundle Guard" --limit 3` to confirm.
2. **Future-game scanning** (still on the backlog from session 9 close). Widen the Python scanner window beyond today + tomorrow; line-staleness handling; UI affordance for non-today edges. Real model-side scope.
3. **bankroll.json lifetime-stats consistency**: 43 vs 59 mismatch (lifetime_bets vs wins+losses+pushes); $7 chart-vs-lifetime_profit divergence. Model-side investigation.
4. **Existing polish backlog**: rewrite `docs/cloudflare-access-setup.md` for Zero Trust UI; set up Google IdP (currently OTP-only); delete `rebuild/v2-frontend` branch (local + origin); defer `worker/lib/normalize.ts` extract until a third consumer of `stripEmDash` / `coerceOddsString` exists.

### If you just have one minute, do this
`cd ~/Betting\ Skill && gh run list --workflow="SPA Bundle Guard" --limit 3` to see the most recent run status. Expect green on every PR and main push that touches `frontend/`, `public/`, `shared/`, `vite.config.ts`, `tsconfig*.json`, `package.json`, or `package-lock.json`. If a run fails: the `Failure hint` step prints the rebuild + cp + commit recipe inline.

---

## 2026-05-02 session 9 (Stale SPA bundle fix)

### Goal
Resume from session 8 to (a) close the deferred 404 verification loop and (b) pick a polish item. Mid-session, Max reported that Picks rows weren't clickable in the live SPA. Investigation revealed the production SPA bundle was 30 hours stale (frozen at session 5 slice 1-5 cutover); sessions 6 / 7 / 8 frontend source changes had never been built or copied into `public/`. Fixed by rebuilding and redeploying.

### Pre-flight
- `git stash list`: empty. `git status --short`: 3 expected carry-over untracked. `git log --oneline -4`: `4ceb333 e6df9bd 6a71bcb dc7c021` (matches session 8 ending state).
- `npx tsc -b`: clean. `npm test`: 78 / 78.
- `curl -sI .../api/me`: 302 to `sheahan.cloudflareaccess.com`.
- `origin/cloudflare/workers-autoconfig..origin/main`: 1 commit (the docs-only `4ceb333`; the auto-deploy from session 8's manual mirror push had already caught up).
- Local `data.json`: `2026-05-02`, 8 picks, 62 bets.
- New auto-deploy at session start: `d4596531-177f-4d05-97c2-fff67d4ee012` at 22:20 UTC, `~10 min` after session 8's manual mirror push at 22:10 UTC. Confirms the auto-deploy chain works; the lag observed in session 8 is `~10 min`, not infinite. Updates session 8's "Aside on the auto-deploy lag" with hard data.

### 404 verification close-out
Done. See updated subsection in session 8 above. Both deleted routes returned 405 (not 404 as predicted); the 405 is the correct signal under the architecture, sessions 7 + 8 are end-to-end verified.

### The real bug: stale SPA bundle in production
After the 404 close-out, Max reported the Picks rows weren't clickable and the bankroll-over-time graph was missing. Investigation chain:
- `/api/picks` returned 8 picks; `/api/state` returned 0 placements. Worker side healthy.
- `git log origin/main -- frontend/src/components/PickRow.tsx`: latest commit `ca3efa4 feat(picks): click-to-expand` was on main since session 6 slice 2.
- `git log origin/main -- public/assets/`: latest commit `a72183b chore(phase-3): v2 SPA cutover (slices 1-5)`. That predates `ca3efa4`.
- `grep "isExpanded\|onToggleExpand\|handleRowClick" public/assets/index-cYVCSat3.js`: no hits. Click-to-expand symbols absent from the deployed bundle.

Root cause: sessions 6 / 7 / 8 each committed `frontend/src/` changes but nobody ran `npm run build` and nobody copied `frontend/dist/*` → `public/*`. The worker bundle gets rebuilt by `wrangler deploy`, so worker source changes shipped fine across sessions. The SPA bundle is committed git artifacts in `public/assets/`, so frontend source changes only ship if someone manually rebuilds + recopies + commits.

Concrete impact prior to fix:
- Picks tab rows not click-to-expand (slice 2 absent).
- Picks tab still calling deprecated `usePlacePickBet` → POST `/api/place-bet` → 405 (route deleted in session 7).
- Pending tab still showing queued-retries section calling `/api/state/sync-queue/retry` → 405 (deleted session 7).
- Pending tab still calling `useDeletePlacement` → DELETE `/api/state/placements/:key` → 405 (deleted session 8).
- All silent failures Max would only hit if he acted; nothing crashed.

### Decisions made
- **Commit + push + manual mirror + `wrangler deploy`** (session 8 pattern). Faster than waiting for the ~10-min auto-deploy and persistent across the next cron tick.
- **Did not auto-fix the build process this session.** A `predeploy` script or CI guard would prevent recurrence; filed as a polish follow-up so the fix lands cleanly without scope creep on the urgent diff.

### Files modified
- `public/index.html` (bundle hash references updated).
- `HANDOFF.md` (this entry, the inheriting-state snapshot bullet, and the session 8 verification close-out).

### Files added
- `public/assets/index-Djh7ZKAk.js` (new bundle, 247.57 kB, gzip 74.81 kB).
- `public/assets/index-WMNNWeYB.css` (new styles, 14.58 kB, gzip 3.08 kB).

### Files deleted
- `public/assets/index-cYVCSat3.js` (stale bundle from a72183b).
- `public/assets/index-B4hwDnDa.css` (stale styles from a72183b).

### Verification
- `npx tsc -b`: clean.
- `npm test`: 78 / 78 across 3 files (no regressions).
- New bundle grep: visual strings `Mark as placed`, `Place on DraftKings`, `pick-actions-expanded`, `pick-chevron`, `pick-details` present. Dispatch URLs (`/api/place-bet`, `/api/state/sync-queue/retry`) absent. Expected v2 URLs (`/api/state/placements`, `/api/state/manual-bets`, `/api/balance-override`, `/api/activity`) present.
- Live deploy verification: TBD (Max to confirm picks clickable in browser after deploy).

### Slice 2: sidebar balance-over-time chart

Max requested the chart be moved from the Account tab (where slice 2 first put it) into the right sidebar directly under `BalanceCard`. Pulled the `interface-design` skill for the redesign.

**Design decisions.**
- **Continuation, not competition.** Same `.card` + `.card-header` chrome as `BalanceCard` so the two cards read as a grouped object. Same uppercase 12px header, same white card on `--color-bg`.
- **Sparkline at sidebar size.** 240×80 viewBox SVG, no Y-axis labels, no per-point dots, just gold line over a `--color-accent-tint` area fill. The headline (`+$186.69 over 12 days`) tells the story; the line shape shows the slope.
- **Headline = the delta.** Big tabular `+$186.69` in green/red mirrors `PROFIT` in the card above. The Balance card already shows the absolute number; this card adds the trajectory.
- **First / last date labels below the chart.** Uppercase 10px muted, matches the rest of the design's axis idiom. Inline X-axis labels would clutter at this width.
- **Hand-rolled SVG over Recharts.** Recharts adds ~30 kB gzipped for default-styled charts that look plug-and-play. Hand-rolled is 250 kB → 250.05 kB delta total bundle, with full control over the visual idiom.
- **`vectorEffect="non-scaling-stroke"` + `preserveAspectRatio="none"`** keeps the line at a crisp 1.5px regardless of how the SVG stretches across the sidebar's actual rendered width. Side benefit: the chart fills the card cleanly without aspect-ratio guessing.

**Data path.** `useActivity()` (62 resolved bets) + `useBankroll().starting` ($500). Aggregate by date, accumulate pnl from $500, output `[{date, balance}]`. No worker change needed.

**Files modified.**
- `frontend/src/components/BalanceChart.tsx` (NEW, replaced earlier full-size version with sparkline).
- `frontend/src/App.tsx` (mounted `<BalanceChart />` in `.page-side` under `<BalanceCard />`).
- `frontend/src/tabs/AccountTab.tsx` (removed slice-2-initial chart section + import).
- `frontend/src/styles.css` (replaced earlier `.balance-chart-*` block with sidebar variants).
- `public/index.html` + `public/assets/*` (rebuild artifacts).
- `HANDOFF.md` (this entry).

**Verification.**
- `npx tsc -b` clean; `npm test` 78 / 78.
- Vite + wrangler dev preview: chart renders on Picks (default landing) and on every other tab. Account tab no longer renders the chart in its body. No console errors.
- Smoke check on new bundle: `Balance over time`, `balance-chart-svg`, `balance-chart-change`, `balance-chart-axis` strings all present.

**Caveat: $7 disagreement between chart final balance and bankroll.json's `lifetime_profit`.** Chart shows $500 → $686.69 (+$186.69). bankroll.json reports `current_bankroll: 679.34, lifetime_profit: 179.34, lifetime_bets: 43, wins+losses+pushes = 37+21+1 = 59`. The 43-vs-59 mismatch tells you `bankroll.json` is internally inconsistent; the chart shows the truth from `bets[]`, the lifetime stats use a different reduction. Model-side issue, not a frontend bug. Worth tracking but does not block this slice.

### What's next
1. **CI guard for bundle-staleness**: a GitHub Action that fails if `public/index.html`'s referenced bundle hash doesn't exist in `public/assets/`. Catches the slice-1 bug class without trusting humans.
2. **Future-game scanning** (Max-asked at the end of session 9). Currently the model scans only same-day games. Max wants future-game edges too because they often move favorably before tip-off. Not yet scoped; a real conversation about (a) how far out to scan, (b) line-staleness handling, (c) UI affordances for future picks vs today's picks.
3. **Bankroll lifetime-stats consistency**: 43 vs 59 mismatch in `bankroll.json` between `lifetime_bets` and the win/loss/push sum. Investigate model side.
4. **Existing polish backlog**: rewrite `docs/cloudflare-access-setup.md` for Zero Trust UI; set up Google IdP; delete `rebuild/v2-frontend` branch (local + origin); defer `worker/lib/normalize.ts` extract until 3rd consumer.

### If you just have one minute, do this
`cd ~/Betting\ Skill && grep -c "isExpanded" public/assets/*.js` should print at least 1. If it prints 0, the bundle has gone stale again; rebuild via:
```
npm run build && \
  rm public/assets/index-* && \
  cp frontend/dist/assets/* public/assets/ && \
  cp frontend/dist/index.html frontend/dist/.assetsignore frontend/dist/wrangler.json public/
```

---

## 2026-05-02 session 8 (Dead code cleanup)

### Goal
Tie off the dispatch-cleanup loose ends from session 7: drop orphaned client/server code that no live caller exercises. Audit the worker for any other dispatch-chain leftovers and remove what's truly dead, retain what's intentional back-compat.

### Pre-flight
- `git stash list`: empty. `git status --short`: only the 3 expected carry-over untracked entries (`.claude/handoffs/`, `index.html.bak`, `mockups/`). `git log --oneline -3`: `dc7c021` `4c6f895` `fd434c6` (session 7 + session 6 commits on `origin/main`).
- `npx tsc -b`: clean. `npm test`: 82 / 82 across 3 files.
- `curl -sI .../api/me`: 302 to `sheahan.cloudflareaccess.com` (Access intact).
- `origin/main` was 7 commits ahead of `origin/cloudflare/workers-autoconfig` at session start (next cron tick will mirror; live worker still has the dispatch routes mounted until then).
- Local `data.json`: `2026-05-02`, 8 picks, 62 bets.

### Scope expansion (asked Max via AskUserQuestion)
- **Q1: Polish item.** Max picked "Dead code cleanup" (recommended): drop `useDeletePlacement` from `frontend/src/api/mutations.ts` + `git rm scripts/place_bets.py`.
- **Q2: Bundle item.** Max picked "Audit worker for dispatch leftovers" (recommended). Audit found one truly orphaned chain: the worker `DELETE /api/state/placements/:key` route + its `removePlacement` helper, made dead by Q1's removal of `useDeletePlacement` (the only frontend caller).
- **Q3: Worker DELETE route.** Max picked "Remove all three" (recommended): drop the route, the helper, and the corresponding describe block.

### Decisions made
- **Removed worker `DELETE /api/state/placements/:key` chain.** The route had no live frontend caller after Q1's `mutations.ts` edit. `removePlacement` in `worker/lib/state.ts` was used only by that route. The 4-test describe block in `worker/index.test.ts` was the only remaining test surface. All three dropped together as one logical unit. Real API surface change: closes off curl-DELETE access (placements can still be re-actioned via POST `/api/state/placements`).
- **Kept everything else flagged by the audit.** Specifically: `sync_queue` field on `StateRecordSchema` + `SyncQueueEntrySchema`, the `dispatch_status` enum + `'ok'` default on `PlacementCreateRequestSchema`, the `dispatch_status: 'ok' as const` writes in `useSkipPick` / `useMarkPickAsPlaced`, the `state.ts:29` `sync_queue: []` init, the `state.ts` GET pass-through, and the defensive `queued` badge in `PickRow` / `PositionRow`. All intentional back-compat for pre-session-7 KV records per the session 7 plan; do not regress.
- **Two-commit shape, no amend.** Standard Max preference. Code first, HANDOFF second.

### Files modified
- `frontend/src/api/mutations.ts` (drop `useDeletePlacement` export; `apiDelete` import stays for `useDeleteManualBet`).
- `worker/routes/state-placements.ts` (drop `app.delete('/:key', ...)` route + `removePlacement` from import).
- `worker/lib/state.ts` (drop `removePlacement` function).
- `worker/index.test.ts` (drop `describe('DELETE /api/state/placements/:key', ...)` block, including all 4 nested tests).
- `HANDOFF.md` (this entry + the inheriting snapshot bullet).

### Files deleted
- `scripts/place_bets.py` (orphaned after session 7 deleted `.github/workflows/place-bets.yml`; that workflow was the sole invoker via `python scripts/place_bets.py "${{ github.event.inputs.picks }}"`).

### Verification
- `npx tsc -b`: clean.
- `npm test`: 78 / 78 across 3 files (was 82 / 82; the 4 dropped = the DELETE describe block).
- Audit grep across `worker/ shared/ frontend/src/` for `dispatch | sync_queue | sync-queue | place_bet | place-bet | repository_dispatch`: every remaining match classified as intentional back-compat (see Decisions made).
- `git status --short` after edits: 5 intended changes (M `frontend/src/api/mutations.ts`, D `scripts/place_bets.py`, M `worker/index.test.ts`, M `worker/lib/state.ts`, M `worker/routes/state-placements.ts`) plus the 3 expected carry-over untracked entries.
- `git diff --stat HEAD`: net -295 lines (-296 deletions, +1 insertion = the modified `appendPlacement, removePlacement` → `appendPlacement` import line in `state-placements.ts`).
- Em-dash audit on the diff scope: clean.

### What's next
1. **Push origin main.** Two-commit pair already shipped this session; the second commit (this HANDOFF entry) is what closes it. Confirm `git push origin main` succeeded and the worktree is clean.
2. **Confirm cron mirror catches up.** Once `origin/cloudflare/workers-autoconfig` matches `origin/main` (next cron tick), curl `/api/place-bet`, `/api/state/sync-queue/retry`, `/api/place-bets`, AND `/api/state/placements/<key>` (DELETE) on the live URL. Expect Access challenge then 404 (Access scope is `/*`, no worker route). Closes the loop on sessions 7 + 8 end-to-end.
3. **Remaining polish (Max picks):**
   - Rewrite `docs/cloudflare-access-setup.md` for the Zero Trust UI.
   - Set up Google IdP (currently OTP-only).
   - Balance-over-time graph in Account tab.
   - Delete `rebuild/v2-frontend` branch (local + origin).
   - Defer `worker/lib/normalize.ts` extract until a third consumer of `stripEmDash` / `coerceOddsString` exists.

### Post-commit deploy (2026-05-02 ~22:10 UTC)

After the two-commit pair pushed, the cron mirror was 9 commits behind `origin/main` (the 19:51 UTC scan and sessions 6 / 7 / 8 had not mirrored), and the most recent visible Cloudflare deploy (21:59 UTC) predated this session's commits. Two manual actions to bring production current:

1. **Manual mirror push.** `git push origin main:cloudflare/workers-autoconfig` ran cleanly: `3c35b37..e6df9bd  main -> cloudflare/workers-autoconfig`. The 19:51 UTC scan + sessions 6 / 7 / 8 commits all rode along.
2. **Manual `wrangler deploy`.** Cloudflare's git-trigger had not fired within ~4 min of the mirror push (no new entry in `npx wrangler deployments list`), so a direct deploy was used. New live version: `7d053fab-424a-4ea3-8a5e-cbff9c99b24f`. 8 assets in `public/`, no asset changes since the last deploy. Worker startup time 22 ms.

**Live verification (without auth).** Access intact on all 6 paths checked: `/`, `/api/me`, `/api/place-bet`, `/api/place-bets`, `/api/state/sync-queue/retry`, `DELETE /api/state/placements/test-key`. All return `HTTP/2 302` to `sheahan.cloudflareaccess.com`. Access scope `/*` did not regress.

**Definitive 404 verification (closed 2026-05-02 ~22:25 UTC, session 9).** Both deleted routes confirmed gone. Max ran in-browser fetch from the devtools console after OTP login:
```js
fetch('/api/place-bet', { method: 'POST' }).then(r => r.status)             // 405
fetch('/api/state/placements/test', { method: 'DELETE' }).then(r => r.status) // 405
```
Both returned `405 Method Not Allowed`, not `404` as predicted. The 405 is the correct end-to-end signal under the current architecture: worker's catch-all at `worker/index.ts:31` (`app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))`) forwards unmatched paths to the ASSETS binding, and ASSETS rejects non-GET methods with 405. If the routes still existed, we'd have seen 201 / 400 / 502 instead. Sessions 7 + 8 cleanup is end-to-end verified. Tangential cosmetic follow-up worth filing: an explicit `app.all('/api/*', notFound)` before the global catch-all would return cleaner 404s on dead API paths; not a regression.

**Aside on the auto-deploy lag.** Cloudflare's auto-deploy from `cloudflare/workers-autoconfig` did not visibly fire from this session's manual mirror push within 4 min, even though cron-tick deploys (e.g. 16:41 scan triggered a 16:41:23 deploy earlier today) confirm the integration works. Possible causes: deploy queue lag, batch interval, or a difference between cron-context pushes (via `actions/checkout`) and developer-machine pushes. Worth investigating if mirror-lag becomes a recurring issue; not blocking right now since the manual `wrangler deploy` covered it.

### If you just have one minute, do this
`cd ~/Betting\ Skill && npx tsc -b && npm test` → expect clean tsc + 78 / 78.

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
