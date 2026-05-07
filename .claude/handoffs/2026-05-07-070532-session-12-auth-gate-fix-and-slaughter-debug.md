# Handoff: Session 12 — Auth-gate fix on legacy index.html + slaughter investigation + dk-edge-finder skill refactor

## Session Metadata
- Created: 2026-05-07 07:05:32 UTC
- Project: /Users/maxsheahan/Betting Skill
- Branch: main (uncommitted index.html change in working tree)
- Session duration: ~2 hours, spanned 2026-05-06 evening through 2026-05-07 morning

### Recent Commits (for context)
  - 2995adb feat(balance): show pending breakdown so Available + Profit reconcile
  - cc744f9 fix(bankroll): reconcile to DK transaction history
  - c69e8a8 chore: HANDOFF session 14 close (override dropped + balance reconciled)
  - c020ba7 fix(bankroll): drop override + reconcile Available/Profit/Chart
  - 14dbdb4 chore: HANDOFF session 14 (bankroll fix + Activity redesign + AI + KV bridge)

## Handoff Chain

- **Continues from**: [2026-05-03-133035-session-11-fav-dog-pill-shipped-bugs-1-2-deferred.md](./2026-05-03-133035-session-11-fav-dog-pill-shipped-bugs-1-2-deferred.md)
  - Previous title: Sessions 10 + 11 shipped (CI bundle guard + FAV/DOG pill); bugs 1 + 2 deferred
- **Supersedes**: None

> Review the previous handoff for full context before filling this one.

## Current State Summary

Session split between three independent threads. (1) Max reported "we got slaughtered the past two days" and asked to investigate. Investigation showed May 3 was a real left-tail day for the model (43% hit rate on 21 picks, Max placed 6 and lost $39.58). May 4's 7 MLB run-line bets are STILL pending in `data.json` despite games finishing 36+ hours ago. May 5 has zero bets logged at all. (2) Diagnosed the May 5 silent-fail: legacy `index.html`'s Place button POSTs to `/api/place-bets`, which is now Cloudflare Access-gated; without a valid `CF_AppSession` cookie the cross-origin redirect fails CORS, the fetch rejects as a generic "network error," and `queueFailedSync()` quietly stashes the bet in localStorage with a misleading toast. Patched `index.html` (+115/-23) with a preflight auth check, an opaqueredirect-detecting Place fetch, and a queue display that no longer hides cross-day entries. NOT deployed and NOT verified with `wrangler dev`. (3) Earlier in the session, refactored the standalone `dk-edge-finder` domain skill at `~/.claude/skills/dk-edge-finder/scripts/` (engine merge, calibration loop, closing-line capture). That skill is example/teaching code, NOT the production scanner.

**Corrected mid-session**: I initially asserted the resolver and scanner cron had stopped at 2026-05-04 16:30 UTC based on local file mtimes. That was wrong. After actually running `gh run list`, the cron has been running successfully throughout. The local clone is 11 commits behind `origin/main`; commit `d56281b` "Auto-resolve: 2026-05-05 bet results" already settled the 5/4 MLB bets and updated bankroll/daily_summaries/pick_history. Resolve Bets ran successfully on 5/5 07:19, 5/6 07:35, 5/7 07:43. The one real failure was a transient GitHub Actions runner availability issue on the 2026-05-05 15:05 Full Scan (annotation: "The job was not acquired by Runner of type hosted"); self-recovered on the next schedule. **First thing the next session should do is `git pull` from `~/Betting Skill/`** to bring local in sync. Then re-read `data.json`, `bankroll.json`, and `daily_summaries.json` for the actual current state.

## Codebase Understanding

### Architecture Overview

Two repos in play:

1. **`~/Betting Skill/`** is the production system. Frontend served by a Cloudflare Worker (`worker/index.ts` + Hono routes), backend Python on GitHub Actions cron (`scripts/scan_edges.py`, `scripts/resolve_bets.py`, etc.), state in Cloudflare KV namespace `EDGE_STATE`. Live URL: https://dk-edge-finder.max-sheahan.workers.dev/. Cloudflare Access guards the entire site (not just `/api/*` as HANDOFF.md and prior memory notes claim, see Gotchas below). Active branch is `main`; `rebuild/v2-frontend` is the in-progress Vite + React + Hono replacement. Phase 0.4 done, Phase 0.5 next.

2. **`~/.claude/skills/dk-edge-finder/`** is the standalone domain-knowledge skill that ships with Max's Claude Code config. SKILL.md plus `scripts/{edge_calculator,fetch_odds,settle_picks,capture_closing_lines,model_engine,prop_model}.py`. This is where the model concepts live (Skellam, Kelly, calibration, sport references). It is NOT invoked by the production cron; it provides context to Claude when discussing the topic. The session 12 work refactored these scripts but the changes are independent of the live site.

### Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `~/Betting Skill/index.html` | Legacy single-file frontend served at `/` by the Worker | Has uncommitted +115/-23 auth-gate fix in working tree; needs wrangler dev verify + deploy |
| `~/Betting Skill/scripts/resolve_bets.py` | Cron that grades bets nightly at 05 UTC | Has not run since 2026-05-04 16:30 UTC; first thing to debug next session |
| `~/Betting Skill/scripts/scan_edges.py` | Main scanner with April 2026 calibration overrides + NBA playoff discount block | Per memory the scan also stopped after 5/4 16:30 UTC (16 UTC scan cron) |
| `~/Betting Skill/data.json` | Live state read by the legacy frontend; `bets[]` includes status, scan_date | mtime 2026-05-04 16:30 UTC; 7 MLB run-line bets pending, $98 wagered, all 5/4 |
| `~/Betting Skill/bankroll.json` | Resolver output, lifetime P/L | mtime 2026-05-04 17:26 UTC; $602.68 current bankroll, +$102.68 / +10.18% lifetime |
| `~/Betting Skill/daily_summaries.json` | AI daily summary cron output | 3 bytes, empty; daily summary cron also broken |
| `~/Betting Skill/pick_history.json` | Every model pick across ~6 weeks (n=930, 904 settled) | Source for `analyze_history.py` calibration breakdown |
| `~/Betting Skill/scripts/analyze_history.py` | Production calibration analyzer | Already exists, runs cleanly; surfaces NBA/5-8pp/HIGH-tier issues |
| `~/Betting Skill/HANDOFF.md` | Single source of truth, newest-on-top | This new section needs to be prepended after the handoff is finalized |
| `~/.claude/skills/dk-edge-finder/scripts/edge_calculator.py` | Canonical edge engine (post-merge) | New fields edge/edge_pp/ev_per_dollar/is_strong_edge; alt-line key fix |
| `~/.claude/skills/dk-edge-finder/scripts/fetch_odds.py` | Live data pipeline (post-merge) | Delegates to edge_calculator; sharp consensus indexed by (name, point) |
| `~/.claude/skills/dk-edge-finder/scripts/settle_picks.py` | New: settles + calibration + CLV | h2h/spreads/totals only; props/SGPs/futures stay manual |
| `~/.claude/skills/dk-edge-finder/scripts/capture_closing_lines.py` | New: snapshots DK odds within window of game start | Designed for cron; pairs with settle_picks for CLV |

### Key Patterns Discovered

- **Cloudflare Access drops same-origin POSTs as cross-origin redirects.** A `fetch('/api/place-bets', {redirect:'follow'})` from an unauthenticated browser hits Access, gets a 302 to `sheahan.cloudflareaccess.com`, and the cross-origin follow fails CORS. The fetch rejects in the catch handler, which looks identical to a real network failure. Use `redirect: 'manual'` and check `res.type === 'opaqueredirect'` to distinguish the two.
- **Live-site Access policy is broader than HANDOFF claims.** The `www-authenticate` header on `GET /` (with `redirect_url=%2F`) shows the policy now covers the entire origin. The HANDOFF section "Step 8 confirmed live as of 2026-05-01" only mentioned `path 'api/*'`. Either the policy was tightened post-May 1 or it was always broader. Implications: the legacy index.html only loads when you are already authed, so the preflight `checkAuth()` in the new fix is mostly insurance against mid-session cookie expiry rather than first-load gating.
- **Sharp-consensus model is profitable lifetime, fragile day-to-day.** 57.1% across 904 paper picks but day-level variance ranges 33% to 87%. One losing day in 6 is normal. Two consecutive bad days look catastrophic in the moment but are within sample variance.
- **Three calibration signals jumped out from `analyze_history.py`** that should drive future model work, separate from any short-run slump:
  - NBA: 46.8% on 205 picks, paper P/L $-240.72. Real systematic loser.
  - 5-8pp edge bucket: 53.1% on 324 picks, paper P/L $-225.43. Threshold should rise to 8% minimum or the edge calc in this band needs review.
  - HIGH confidence tier: 53.9%, $-29.88 (n=230). MEDIUM is 59.8%, $+686 (n=465). Tiers are inverted; the label is meaningless or wrong.

## Work Completed

### Tasks Finished

- [x] Diagnosed the silent-Place-button bug (Cloudflare Access + cross-origin redirect + opaque rejection in catch).
- [x] Edited `~/Betting Skill/index.html` with the auth-gate fix (preflight, opaqueredirect detection on dispatch, cross-day queue surfacing). Brace balance 209/209. `node --check` exit 0.
- [x] Investigated "we got slaughtered" by reading `bankroll.json`, `data.json`, and running `scripts/analyze_history.py`. Concluded May 3 was a real losing day, May 4 is stuck in pending due to a broken resolver cron, May 5 is invisible (auth-gate bug or no bets placed).
- [x] Surfaced three lifetime calibration issues separate from the slump (NBA, 5-8pp bucket, HIGH-vs-MEDIUM tier inversion).
- [x] Refactored `~/.claude/skills/dk-edge-finder/scripts/`: merged duplicate edge engines into `edge_calculator.py` as canonical, fixed alt-line key collision, added prefix-aware tier classification, added new fields (`edge`, `edge_pp`, `ev_per_dollar`, `is_strong_edge`).
- [x] Wrote `~/.claude/skills/dk-edge-finder/scripts/settle_picks.py` (settlement + calibration + CLV) and `capture_closing_lines.py` (closing-line snapshotter). Updated SKILL.md with merged Step 7/8.
- [x] Smoke tests passed for the dk-edge-finder skill scripts (mock-fixture calibration, 14-case grader unit test).

### Files Modified

| File | Changes | Rationale |
|------|---------|-----------|
| `~/Betting Skill/index.html` | +115 / -23 (uncommitted) | Auth-gate preflight, opaqueredirect detection, cross-day queue display |
| `~/.claude/skills/dk-edge-finder/scripts/edge_calculator.py` | edits | Canonical engine; new fields; alt-line key includes point; prefix-aware tier classification |
| `~/.claude/skills/dk-edge-finder/scripts/fetch_odds.py` | rewrite | Delegates to edge_calculator; sharp consensus by (name, point); duplicate Kelly tables removed |
| `~/.claude/skills/dk-edge-finder/scripts/settle_picks.py` | new file | Score-based settlement, calibration report by tier/edge bucket/sport, CLV when closing_odds present |
| `~/.claude/skills/dk-edge-finder/scripts/capture_closing_lines.py` | new file | Snapshots DK odds within ±N min of commence_time; designed for cron |
| `~/.claude/skills/dk-edge-finder/SKILL.md` | edits | Removed two-engine confusion; Step 7 (capture closing lines) and Step 8 (settle + calibrate + CLV) added |

### Decisions Made

| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| Use `redirect: 'manual'` + opaqueredirect detection rather than `redirect: 'error'` | manual vs error vs follow-then-inspect | manual gives an inspectable Response; error rejects with a generic TypeError that loses signal |
| Preflight `/api/me` on page load AND defensive check on Place fetch | preflight only / Place check only / both | Belt and suspenders; mid-session cookie expiry is real, page load isn't enough |
| Drop `scan_date === currentDate` filter on getFailedSyncQueue | keep filter / loosen / drop | Yesterday's bets vanishing on today's reload was a primary contributor to "they didn't log" feeling |
| Edit `main` branch directly, not `rebuild/v2-frontend` | main vs rebuild branch | Legacy `index.html` lives on main and is what's currently deployed; rebuild branch will replace this whole file |
| Investigate slaughter via local data.json/bankroll.json/analyze_history.py rather than v2 KV | local files / KV via wrangler / DK bet history screenshots | Local files were the fastest path; resolver was broken so KV would have been stale anyway |
| Don't deploy index.html fix this session | deploy now / verify locally first / both | Wrangler dev never came up this session; user pivoted to investigation. Fix is in working tree, ready when verified |
| Provide both per-session handoff doc AND prepend to HANDOFF.md | one or the other | Skill convention plus Max's project convention coexist; both readers exist |

## Pending Work

## Immediate Next Steps

1. **Pull origin/main into the local clone.** From `~/Betting Skill/`, run `git pull --ff-only`. Local is 11 commits behind. The uncommitted `index.html` auth-gate fix is the only WIP and the cron commits don't touch `index.html`, so a fast-forward pull is clean. After pull, re-read `data.json`, `bankroll.json`, `daily_summaries.json`, then run `python3 scripts/analyze_history.py` for the corrected calibration view including 5/4 + 5/5 settled outcomes. Note: the 5/5 morning Full Scan failure (transient runner unavailability) means the 5/5 prop refresh is missing; if Max wants those props, manually re-trigger the workflow via `gh workflow run` or accept the gap.
2. **(Was: manually re-run resolve_bets for 5/4+5/5.) NO LONGER NEEDED — already done by cron on 5/5 07:19.**
3. **Verify the auth-gate fix with wrangler dev.** From `~/Betting Skill/` run `npx wrangler dev`. In incognito: load localhost:8787, expect red banner; click Sign in, complete OTP, return; banner gone, Place buttons live; click Place on a real pick; success toast appears; then in DevTools delete `CF_AppSession` cookie, reload, banner returns; force a Place click via the disabled button (DevTools), confirm "Sign in required, bet was NOT placed" toast not "Sync failed (network)".
4. **If wrangler dev verify passes, deploy:** `npx wrangler deploy`.
5. **Recover yesterday's localStorage queue.** Walk Max through opening DevTools on the live site after re-auth, running `JSON.parse(localStorage.getItem('dk-edge-sync-queue'))`, pasting the JSON. Reconstruct any 5/5 bets that the auth-gate ate.

### Blockers/Open Questions

- [ ] Why did `wrangler dev` not come up when Max tried? Could be `npm install` not run on a recent dependency change, port 8787 already taken, or wrangler not on PATH. Worth running `which wrangler` and checking dependencies before assuming it's broken.
- [ ] Is the broken cron just GitHub Actions, or also a Cloudflare Worker scheduled trigger? Confirm where the cron actually runs. Memory says GitHub Actions but worth verifying via wrangler.jsonc.
- [ ] Did Max actually place bets on 5/5? If yes, the localStorage queue should have them (now visible in the new UI). If no, the slaughter feeling was about 5/3 alone plus 5/4 staying in pending limbo (subjectively unresolved).

### Deferred Items

- **Dropping NBA from the model.** This is the single highest-EV change but politically charged and requires confirming the lifetime sample (n=205) is still recent enough to be diagnostic. Some of those NBA picks may be from a different model version.
- **Raising the 5-8pp edge floor to 8pp.** Same caveat: lifetime data may include older model versions whose edge calculation differs.
- **HIGH-vs-MEDIUM tier inversion investigation.** The label is broken; either the assignment logic is reversed or the threshold definitions changed and historical picks are tagged with stale labels.
- **v2 rebuild Phase 0.5 (frontend-to-backend-requirements skill).** Per the original HANDOFF.md, this is the next planned phase. Untouched this session.
- **HANDOFF.md prepend.** This handoff doc was created; the project convention also requires a new section prepended to `~/Betting Skill/HANDOFF.md`. Done as a separate step after this file is validated.

## Context for Resuming Agent

## Important Context

The single most important thing to know: **`~/Betting Skill/` local is 11 commits behind `origin/main`**. Until you `git pull`, every assertion you make about `data.json`, `bankroll.json`, `daily_summaries.json`, or `pick_history.json` is reading 2-day-old state. The cron is fine; it's the local clone that's stale. Don't repeat my mid-session mistake of inferring "cron broken" from local file mtimes. Run `gh run list` to confirm cron health before drawing conclusions.

Second: **Cloudflare Access now covers `/`, not just `/api/*`**. The HANDOFF.md memory section about Step 8 says `path 'api/*'`. That's no longer accurate — `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/` returns 302 with `redirect_url=%2F` and `www-authenticate: Cloudflare-Access resource_metadata=".../.well-known/cloudflare-access-protected-resource/"` (no `/api/` segment). Implication: the auth-gate fix's preflight is mostly redundant for first-page-load (you can't load the page if you're not already authed), but the dispatch-fetch opaqueredirect check still matters for mid-session cookie expiry and for any future change that re-narrows Access coverage.

Third: **the dk-edge-finder skill at `~/.claude/skills/dk-edge-finder/` is NOT the production scanner**. The production scanner is at `~/Betting Skill/scripts/`. Refactoring the skill scripts does not change Max's live betting behavior. Don't conflate them.

Fourth: **the slaughter Max referenced was mostly variance plus visibility loss, not model failure**. May 3 model went 9W-12L (43%), Max placed 6 of those bets and lost $39.58. May 4 looks like nothing because the resolver hasn't graded those bets yet. May 5 has zero entries because of the auth-gate silent-fail (now patched). Lifetime is still +10.18% ROI / +$102.68. The model isn't broken.

### Assumptions Made

- Today's date is 2026-05-07 per system metadata.
- Memory file `reference_dk_edge_paths.md` is 6 days old; the live URL and broad architecture are still correct, but specific commit SHAs and exact paths were verified against the working tree before being asserted.
- The auth-gate fix's behavior on the actual live OTP flow has NOT been verified end-to-end. Reasoning is based on Cloudflare Access docs and curl output. A real Cloudflare-Access OTP cycle in a browser is the missing test.
- `pick_history.json` is the same scoring as Max's actual placed bets at $10/bet standardized. Actual placed bets are in `data.json bets[]` with $14/bet, partial selection (Max picks a subset of model picks).

### Potential Gotchas

- **`bankroll.json` and `data.json` disagree on profit** ($102.68 vs $179.34). One counts pending differently. Don't quote one without checking the other.
- **Em-dash rule**: do not introduce em-dashes (—, &mdash;, --) in any user-facing output. Existing toast strings in `index.html` that already contain em-dashes are Max's prior voice; leave them. The session-handoff doc itself is allowed to use em-dashes per the `~/.claude/CLAUDE.md` exception, but this doc avoided them by habit.
- **Max prefers prompted questions one at a time via `AskUserQuestion`**. Do not batch multiple decisions into a single prose blob. Recommended option first, marked "(Recommended)".
- **The two existing `dk-edge-dashboard-2026-03-*.html` files** in `~/Betting Skill/` are old snapshots, not active. Ignore.
- **`index.html.bak` is untracked** and predates this session. Not from this work.
- **The dk-edge-finder skill has TWO copies on disk**: `~/.claude/skills/dk-edge-finder/` (the global skill, which we refactored) and `~/Betting Skill/dk-edge-finder/` (the project copy referenced by `tasks/lessons.md` and `tasks/todo.md`). They are NOT in sync. Confirm which one a future session is editing.
- **`redirect: 'manual'` returns `Response.type === 'opaqueredirect'` with status 0, headers locked, body unreadable.** The only signal you can read is `type` and `status`. Don't try to introspect headers or body on those responses — they will appear empty.

## Environment State

### Tools/Services Used

- **Cloudflare Workers** at `dk-edge-finder.max-sheahan.workers.dev`. Worker is `worker/index.ts` (Phase 1 step 3 rewrote `worker/index.js` to TypeScript + Hono). v2 routes are mounted at `/v2/*` until Phase 3 cutover.
- **Cloudflare Access** application: `dk-edge-finder` on `max-sheahan.workers.dev`, single Allow policy `Allow Max` (rule: emails = `max.sheahan@icloud.com`), Identity providers = "Accept all" (OTP fallback).
- **Cloudflare KV** namespace `EDGE_STATE` (id `7dca36afc97d4d86bebed2e2948d6e83`).
- **GitHub Actions** for cron, repo `blueandyellow44/dk-edge-finder`. Schedules per memory: game-scan every 3h (04, 16, 19, 01 UTC), morning-scan daily 13 UTC, resolve-bets nightly 05 UTC, place-bets manual dispatch only.
- **The Odds API** for odds + scores.
- **Anthropic SDK** for the AI daily summary cron (currently broken, daily_summaries.json is 3 bytes).

### Active Processes

- None at session close. `wrangler dev` was never started.

### Environment Variables

- `ODDS_API_KEY` (Worker secret, last rotated 2026-03-21; suspect candidate for the broken cron)
- `GITHUB_TOKEN` (Worker secret)
- `ANTHROPIC_API_KEY` (assumed for AI daily summary)
- Anything in `~/Betting Skill/.env` (46 bytes, contents not inspected this session)

## Related Resources

- Live site: https://dk-edge-finder.max-sheahan.workers.dev/
- GitHub repo: https://github.com/blueandyellow44/dk-edge-finder
- Approved rebuild plan: `/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`
- Project HANDOFF.md: `~/Betting Skill/HANDOFF.md` (newest section to be prepended after this file is validated)
- Universal rules: `~/.claude/CLAUDE.md`
- DK Edge Finder domain skill: `~/.claude/skills/dk-edge-finder/`
- DK Edge Finder model lessons: `~/Betting Skill/dk-edge-finder/tasks/lessons.md`
- Memory file with paths: `~/.claude/projects/-Users-maxsheahan-DK3/memory/reference_dk_edge_paths.md`

---

**Security Reminder**: Before finalizing, run `validate_handoff.py` to check for accidental secret exposure.
