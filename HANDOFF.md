# DK Edge Finder v2 Rebuild Handoff

Running session-handoff doc. Updated at the end of each working session so the next thread can pick up cold. Newest section on top.

---

## 2026-04-30 session 1 (in progress)

### Goal
Rebuild the frontend of [dk-edge-finder.max-sheahan.workers.dev](https://dk-edge-finder.max-sheahan.workers.dev/) with real Google auth and cross-device state. Python model + GitHub Actions cron stay untouched.

### Current branch
`rebuild/v2-frontend`, branched off `main` at `a3efced`. Repo: [blueandyellow44/dk-edge-finder](https://github.com/blueandyellow44/dk-edge-finder), local at `~/Betting Skill`.

### Approved plan
[/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md)

### Decisions on the books
1. **Scope:** Frontend + new backend pieces (Google auth + shared state store). Python scan model untouched.
2. **Location:** In place at `~/Betting Skill`, on `rebuild/v2-frontend`, in a new `frontend/` subfolder (final folder name to be confirmed by file-architect skill).
3. **Stack:** Vite + React for UI. Hono on Cloudflare Workers for API. `@cloudflare/vite-plugin` for the dev loop.
4. **Auth:** Cloudflare Access with Google IdP. Worker reads `cf-access-authenticated-user-email` to identify user.
5. **State store:** Workers KV namespace `EDGE_STATE`. Records keyed by `(user_email, scan_date)` for placements + sync_queue + manual_bets, plus a single `balance_override:{email}` record.
6. **Python output target:** No change. Model continues to write `data.json`, `bankroll.json`, `pick_history.json` to git.

### What shipped this session
1. **Resolver cache-key bug fix.**
   - `8fd86b7 fix(resolver): key scoreboard cache by (sport, date), not just sport`
   - `a3efced data: resolve 110 backlogged NBA paper picks (Apr 5-29)`
   - 110 NBA picks across April 5-29 had been stuck pending for weeks because the cache key was wrong. Fix at `scripts/resolve_bets.py` in `main()` and `resolve_pick_history()`. Branch `fix/resolver-cache-key` merged to main.
2. **NBA playoff discount patch.**
   - `fe63294 fix(model): NBA playoff discount + hard skip on too-good-to-be-true edges`
   - `c08a0e3 data: re-scan today with playoff discount applied (0 edges)`
   - Adds `is_nba_playoff_window()` plus 5 calibration constants. During Apr 15 to Jun 30, NBA edges get a 40% discount, NBA OVER totals an extra 10% penalty, NBA min-edge raised to 8%, and a hard skip on anything still above 10% post-discount. Today's `OVER 212.5 BOS @ PHI` (29.3% raw) was correctly hard-skipped. Branch `fix/nba-playoff-discount` merged to main.
3. **Calibration snapshots captured at:**
   - `/tmp/dk-edge-calibration-BASELINE.txt` (pre-resolver-fix, masked NBA losses)
   - `/tmp/dk-edge-calibration-AFTER-FIX.txt` (post-resolver-fix, true picture)
4. **Detour findings filed in [dk-edge-finder/tasks/lessons.md](dk-edge-finder/tasks/lessons.md) on this branch (not on main):**
   - Resolver cache-key fix [AUTOMATE - DONE]
   - NBA model unprofitable: 44.9% over 178, -$252.63 [BACKLOG]
   - 5-8% edge bucket below break-even at 52.8% over 271 [BACKLOG]
   - Stale-stash awareness rule [MANUAL]
5. **Three running docs created at repo root:** `lessons.md`, `HANDOFF.md` (this file), `CHANGELOG.md`.

### Phase 0.4 done (file-architect output)
All 6 folder-architect questions answered, folder tree scaffolded, committed as `220170f chore(scaffold): pre-scaffold worker/, shared/, docs/adr/ folder tree`.

Recorded answers:
1. Frontend folder: `frontend/` (Vite scaffolds it in Phase 1, NOT pre-created here)
2. Old `index.html`: stays at root during cohabitation, Worker routes around it
3. Shared types: `shared/` at repo root
4. Worker layout: keep folder name `worker/`, split into `worker/index.ts` + `worker/routes/` + `worker/middleware/` + `worker/lib/` (rewrite from .js to .ts in Phase 1)
5. Mockups: existing `mockups/` keeps being the home, prefix new files with `v2-`
6. ADRs: `docs/adr/0001-stack.md`, `0002-auth.md`, `0003-state-schema.md`

Folders created with `.gitkeep`: `worker/routes/`, `worker/middleware/`, `worker/lib/`, `shared/`, `docs/adr/`. Existing `worker/index.js` untouched. Live site continues serving.

### Next step (Phase 0.5)
Invoke the **frontend-to-backend-requirements** skill. ~15-30 min of prompted questions (one at a time per Max's universal rule) to lock the API contract:
- Which endpoints does the React app need? (`/api/me`, `/api/picks`, `/api/state`, `/api/place-bet`, `/api/balance-override`, etc.)
- Request body shapes and Zod validators
- Response shapes
- Error codes and semantics
- Cloudflare Access JWT header expectations

Output is a spec the Hono worker is implemented against. Lands at `shared/schemas.ts` and `shared/types.ts`.

Then Phase 0.6 (database-schema-designer for KV keys) and Phase 0.7 (write the 3 ADRs).

### Open backlog (from this session)
- **Resolver `main()` cache-key bug.** I fixed both `main()` and `resolve_pick_history()`, but the placed-bet path in `main()` had a smaller related issue (extending instead of keying). Fixed. No further action.
- **NBA model recalibration.** Separate work item. Possibly raise min-edge threshold or add NBA-specific cover probability adjustment. See lessons.md backlog entry.
- **5-8% edge bucket policy.** Either raise min-edge to 8% or stiffen the graduated discount. See lessons.md backlog entry.
- **Stale `claude/*` worktree branches** in the repo (e.g., `claude/condescending-lovelace`, `claude/gallant-jemison`). Some are 30+ days old. Worth pruning with `git branch -D` and `git push origin --delete` once we confirm no in-progress work lives on them.
- **GitHub Actions Node 20 deprecation** on June 2, 2026. Bump `actions/checkout@v4` and `actions/setup-python@v5` before then.
- **`/api/place-bets` idempotency.** Current Worker route has no idempotency token, so two simultaneous Place clicks dispatch twice. Worth fixing during the rebuild.
- **Stuck-pending picks.** 106 still pending after the fix. Most are player props the existing resolver can't handle (no player-stat fetcher) plus some MLS games. Building a prop resolver is a separate model-side task.

### Useful paths
- Repo root: `~/Betting Skill`
- Plan file: `/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`
- Current single-file frontend: `~/Betting Skill/index.html` (66 kB, will be replaced)
- Current Worker: `~/Betting Skill/worker/index.js`
- Wrangler config: `~/Betting Skill/wrangler.jsonc`
- Python model: `~/Betting Skill/scripts/`
- Model lessons: `~/Betting Skill/dk-edge-finder/tasks/lessons.md`
- Skill folder: `~/.claude/skills/dk-edge-finder/`
- Stale React/Firebase rebuild attempt (March 17, abandoned): `~/Betting Skill/dk-edge-finder-app/`

### Useful commands
```
# Always before working
cd ~/Betting\ Skill
git stash list           # check for stale stashes FIRST (lesson 2026-04-30)
git stash && git pull --rebase && git stash pop

# Run the model locally
python3 scripts/scan_edges.py --games-only
python3 scripts/resolve_bets.py
python3 scripts/analyze_history.py

# Worker dev loop (post-Phase-1)
wrangler dev

# Inspect cron runs
gh run list --repo blueandyellow44/dk-edge-finder --limit 10
gh run view <run_id> --log
```

### Known live values (snapshot at session start, will drift)
- Live bankroll: $679.34 (per data.json after April 29 Full Scan)
- Record: see analyze_history.py output
- ODDS_API_KEY rotated last on 2026-03-21 (~40 days old, watch for expiry)
- Today's edges: see latest cron commit on main
