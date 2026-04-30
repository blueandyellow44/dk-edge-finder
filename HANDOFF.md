# DK Edge Finder v2 Rebuild Handoff

Running session-handoff doc. Newest section on top. **Update this file as you work, not only at session end.** Update after every milestone, before any risky push or merge, and any time the context window fills up. A crash mid-session loses everything since the last write.

## Universal rules to read FIRST (every fresh session)

Before any project-specific work, the next thread must load these:

1. `~/.claude/CLAUDE.md` (Max's universal rules: no em-dashes, ask one prompted question at a time via `AskUserQuestion`, trust the user's eyes, do not wrap guesses in the cover of certainty, do not be lazy on visual bug investigations).
2. The approved plan at [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md).
3. This HANDOFF.md in full (you are reading it).
4. `dk-edge-finder/tasks/lessons.md` for model lessons (existing file with full history).
5. `lessons.md` at repo root for rebuild-specific lessons (currently empty template; populate as you work).

## What you are inheriting (2026-04-30 PM)

A live Cloudflare Workers site at https://dk-edge-finder.max-sheahan.workers.dev/ that serves a 66 kB single-file vanilla `index.html` backed by a Python edge-finder model on GitHub Actions cron. The previous session shipped two model fixes (resolver cache-key bug + NBA playoff discount) and finished Phase 0.4 of an approved frontend rebuild plan. The rebuild branch `rebuild/v2-frontend` carries running docs and a folder-tree scaffold but zero implementation code. Live site is unaffected by the rebuild work. Today's `data.json` shows 0 picks because the patched scan correctly hard-skipped the playoff-bait NBA OVER and MLB lines moved.

---

## 2026-04-30 session 1 (PAUSED, ~13:00 PT, resuming at Phase 0.5)

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

### If you just have one minute, do this
Run Phase 0.5: invoke the **frontend-to-backend-requirements** skill to lock the API contract. The skill prompts ~6 to 10 questions one at a time. Output is the spec the Hono worker is implemented against, landing as code in `shared/schemas.ts` and `shared/types.ts` during Phase 1. Before invoking the skill, confirm you are on `rebuild/v2-frontend` and run `git stash list && git pull --rebase` to bring the branch up to date with any cron commits.

### Next step (Phase 0.5)
Endpoints expected (subject to skill confirmation):
- `GET /api/me` returns `{ email, picture_url }` from the Cloudflare Access JWT header
- `GET /api/picks?scan_date=...` proxies the static `data.json`
- `GET /api/bankroll` returns `bankroll.json`
- `GET /api/state?scan_date=...` returns the user's KV record
- `POST /api/state` upserts placements + sync_queue + manual_bets
- `POST /api/balance-override` writes the user's balance override into KV
- `POST /api/place-bet` keeps the existing GitHub-dispatch behavior

Then Phase 0.6 (database-schema-designer for KV keys) and Phase 0.7 (write the 3 ADRs via engineering:architecture skill).

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
