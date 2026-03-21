# DK Edge Finder — Current TODO

## Status as of March 21, 2026

**Bankroll:** $570.57 (11W-8L, +$70.57 profit)
**Last scan:** March 21, 2026 — 15 edges found (7 game, 8 props)
**Bets placed today:** 14 pending ($152.86 at risk)

---

## Completed (March 21)

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

## In Progress

- [ ] **Push index.html UI fixes** — "to win" amounts + pending count fix (Max needs to commit + push)

## Backlog — Short Term

- [ ] **Lower daily exposure cap** — 35% → 25% total (too aggressive today at $164)
- [ ] **Cap prop edges at 15%** — model overconfident (31% edge on Luka 3s is unrealistic)
- [ ] **Better prop model** — weighted recency, opponent defensive rating, confidence discount
- [ ] **Verify GitHub Actions auto-scan** — trigger manual workflow run, check Actions tab

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
- [ ] Odds API credit budgeting (349 remaining, ~24/scan, ~14 days of headroom)

---

## Next Session Should Start With

1. Push index.html (pending count fix + "to win" amounts)
2. Lower daily exposure to 25% and cap prop edges at 15%
3. Check if morning scan auto-ran (GitHub Actions)
4. Verify bankroll matches DK app after today's bets resolve
5. Begin multi-user planning: audit React app, map Firestore schema changes
