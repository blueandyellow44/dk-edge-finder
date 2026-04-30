# DK Edge Finder v2 Rebuild Handoff

Running session-handoff doc. Newest section on top. **Update this file as you work, not only at session end.** Update after every milestone, before any risky push or merge, and any time the context window fills up. A crash mid-session loses everything since the last write.

## Universal rules to read FIRST (every fresh session)

Before any project-specific work, the next thread must load these:

1. `~/.claude/CLAUDE.md` (Max's universal rules: no em-dashes, ask one prompted question at a time via `AskUserQuestion`, trust the user's eyes, do not wrap guesses in the cover of certainty, do not be lazy on visual bug investigations).
2. The approved plan at [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md).
3. This HANDOFF.md in full (you are reading it).
4. `dk-edge-finder/tasks/lessons.md` for model lessons (existing file with full history).
5. `lessons.md` at repo root for rebuild-specific lessons (currently empty template; populate as you work).

## What you are inheriting (2026-04-30 PM, end of session 2: Phase 0 closed)

A live Cloudflare Workers site at https://dk-edge-finder.max-sheahan.workers.dev/ that serves a 66 kB single-file vanilla `index.html` backed by a Python edge-finder model on GitHub Actions cron. **Phase 0 of the v2 rebuild is fully closed.** All four sub-phases shipped:
- Phase 0.4: folder-tree scaffold
- Phase 0.5: API contract at `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`
- Phase 0.6: KV state schema ADR at `docs/adr/0003-state-schema.md`
- Phase 0.7: stack + auth ADRs at `docs/adr/0001-stack.md` and `docs/adr/0002-auth.md`

Branch `rebuild/v2-frontend` is up to date with origin and ready for Phase 1 (implementation). Zero implementation code has shipped yet. Live site unaffected.

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
