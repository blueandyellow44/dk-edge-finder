# DK Edge Finder — Current TODO

## Status as of March 21, 2026 (Session 2)

**Bankroll:** $570.57 (11W-8L, +$70.57 profit)
**Last scan:** March 21, 2026 — 15 edges found (7 game, 8 props)
**Bets placed today:** 14 pending ($152.86 at risk)

---

## Completed (March 21 — Session 2)

- [x] **Split GitHub Actions workflows** — game-only scans every 3hrs (free, no API credits) + full scans 2x/day (6 AM + 3 PM PT)
  - Created `.github/workflows/game-scan.yml` (cron: 9 AM, 12 PM, 6 PM, 9 PM PT)
  - Updated `.github/workflows/morning-scan.yml` to run at 6 AM + 3 PM PT
  - Added `--games-only` flag to `scan_edges.py` that skips prop scanning
  - Games-only mode preserves existing prop picks from last full scan (doesn't wipe them)
- [x] **Opponent defensive rating adjustment** — prop projections now adjusted by opponent PPG allowed
  - ESPN API provides team defensive stats (avgPointsAgainst)
  - Good defenses (BOS 107 PPG) → discount projection by ~4.5%
  - Bad defenses (WSH 123.8 PPG) → boost projection by up to 8% (capped)
  - League avg ~112 PPG, adjustment capped at ±8%
  - Player team fetched via ESPN athlete API, opponent determined from event string
  - All data cached per session (no repeated API calls)
- [x] **Daily exposure already at 25%** — was already set (15% games + 10% props)
- [x] **Verified morning scan status** — no automated scans have run yet (all commits are manual pushes). Workflow schedule will activate after next push.

## Completed (March 21 — Session 1)

- [x] Corrected bankroll to $570.57 (DK app balance override)
- [x] Removed 3 unplaced bets from March 20 history
- [x] Replaced PrizePicks with real DK odds from The Odds API
- [x] Fixed ESPN gamelog parser (categories by month, not "regular")
- [x] Fixed GitHub Actions workflows (working-directory + ODDS_API_KEY)
- [x] Automated git lock cleanup (index.lock, HEAD.lock, maintenance.lock)
- [x] Diversified bet sizing: category budgets (20% games, 15% props) instead of single 20% pool
- [x] Lowered per-bet max from 3.5% to 2% for more diversification
- [x] Added "to win" amounts on pick cards, pending bets, and pending stats card
- [x] Fixed pending count to use actual bets[] count instead of stale bankroll.pending_count
- [x] Both-sides spread evaluation (underdogs + favorites)
- [x] Improved prop model (weighted recency, player SD, blowout discount, 15% edge cap)
- [x] Bankroll sizing logic in all 4 expandable UI sections

## In Progress

- [ ] **Push all changes** — Max needs to commit + push from Mac (`cd ~/Betting\ Skill && git add -A && git push`)

## Backlog — Short Term

- [ ] **Verify GitHub Actions auto-scan after push** — trigger manual workflow run, confirm cron schedules work
- [ ] **Odds API credit budgeting** — ~349 remaining, full scan costs ~24 credits, game-only scan costs 0. At 2 full scans/day = ~48 credits/day ≈ 7 days of headroom
- [ ] **Prop history tracking** — log all prop picks/results to measure true model calibration over time

## Backlog — Multi-User (Next Major Feature)

**Goal:** Make the app usable by multiple users with fully personalized settings.
**Approach:** Build on existing Firebase/React app (already has auth + Firestore).

- [ ] **Per-user settings in Firestore** — kelly fractions, min edge thresholds, max bet %, daily exposure %, preferred sports, excluded events
- [ ] **Settings UI** — expand Settings page with risk controls, sport filters, Kelly tuning
- [ ] **Personalized Kelly sizing** — PicksTable + kellyBetSize() read user settings instead of hardcoded values
- [ ] **Per-user bankroll tracking** — already exists in Firestore, needs override support like bankroll.json
- [ ] **Connect scan pipeline to Firestore** — scan_edges.py writes to daily_scans collection (currently only writes data.json)
- [ ] **Deploy React app on Netlify** — replace static index.html with built React app
- [ ] **Test with 1 user first** — Max uses the React app, verifies feature parity with static site
- [ ] **Invite user #2** — onboard second user with their own bankroll + settings

## Backlog — Long Term

- [ ] Alt line scanning (Skellam model on DK alt spreads)
- [ ] B2B detection for NHL/MLB (currently NBA-only)
- [ ] NHL Skellam calibration (58% too conservative vs 73% historical)
- [ ] Bet tracking ROI by sport/tier/type (reporting dashboard)
- [ ] CSV export for bet history
- [ ] Email/push notifications for qualifying picks

---

## Next Session Should Start With

1. Verify GitHub Actions workflows ran (check Actions tab for game-scan and full-scan runs)
2. Verify bankroll matches DK app after today's bets resolve
3. Review prop model accuracy — are defensive adjustments improving or hurting picks?
4. Begin multi-user planning: audit React app, map Firestore schema changes
