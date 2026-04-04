# DK Edge Finder — TODO

## Status as of March 28, 2026

**Bankroll:** $608.33 (confirmed from DK app + live site March 28)
**Record:** 18-12-0 (60% win rate)
**Lifetime profit:** +$108.33 (21.7% ROI)
**Phase:** Green (bankroll well below $2,500, no limiting signs)
**8 edges on today's scan**

---

## Immediate — Housekeeping

- [x] Sync bankroll.json to live site: $608.33, 18-12-0, +$108.33
- [ ] Verify GitHub Actions workflows ran since March 21 push

---

## Phase 1: Outcome Feedback Loop

**Goal:** Every settled bet feeds back into model evaluation. The system knows whether it is getting smarter or drifting.

- [ ] Verify pick logging captures all required fields (odds at flag, model prob, edge %, timestamp)
- [ ] Build or verify auto-settlement — match logged picks to game results on session start
- [ ] Capture closing odds where available (The Odds API historical endpoint)
- [ ] Build calibration analyzer — bin by sport × edge range, predicted vs actual, min 30/bin
- [ ] Build CLV tracker — compare flagged odds vs closing line, surface CLV rate
- [ ] Build model health dashboard — ROI by sport, calibration curve, CLV rate, drawdown, market-level value
- [ ] Verify: if the model is consistently wrong about a sport, that shows up clearly

## Phase 2: Recalibration Engine

**Goal:** The model proposes its own improvements. Max approves. Improvements are verified before going live.

- [ ] Build recalibration engine — detect overconfident/underconfident bins, propose weight changes
- [ ] Enforce 30-bet minimum per bin
- [ ] Log every proposal: date, bin, old weight, new weight, sample size, reasoning
- [ ] Build backtest runner — verify proposed weights improve historical performance
- [ ] Approval flow: propose → evidence → Max approves/rejects → weights update only on approval
- [ ] Track recalibration history — did past adjustments actually work?

## Phase 3: Formatting Options

**Goal:** The right view for the right question, automatically.

- [ ] Quick Scan — 3-5 lines, instant read
- [ ] Deep Dive — single game, all markets, model breakdown, correlations, SGP suggestions
- [ ] Performance Report — calibration chart, CLV, ROI trends, model health
- [ ] Bankroll Report — balance, exposure, drawdown, active/pending
- [ ] Export — CSV/JSON
- [ ] Auto-format inference from question patterns

## Phase 4: Account Longevity (Three-Phase Trigger System)

**Goal:** Extend DK account life through automated phase transitions. Green → Yellow → Red.

- [ ] Implement phase state tracking — store current phase, transition date, trigger that fired
- [ ] Build session-start phase check: bankroll vs $2,500, CLV rate over last 100, lifetime profit, user-reported limiting signs
- [ ] Green phase: no restrictions. Log all data for future phase evaluation.
- [ ] Yellow phase: enforce round bet sizes, 40% prop cap, 15-30 min line delay, raised min edge (4%/6%), skip-day logic
- [ ] Red phase: mainlines only, 1% max bet, 10% daily cap, 2-3 days/week, auto-surface migration checklist
- [ ] Limiting detection — session-start check for shrinking max bets, vanishing markets, missing promos
- [ ] Phase transition logging in tasks/lessons.md with date and trigger
- [ ] Migration readiness score — portability to prediction market feeds

## Phase 5: Site Polish

**Goal:** dk-edge.netlify.app is clean under daily use.

- [ ] Mobile test at 375px. Touch targets 44px. No horizontal scroll.
- [ ] Error states: every API failure shows human-readable message
- [ ] Loading states: every async op shows spinner/skeleton
- [ ] Console clean in production
- [ ] Off-season handling

## Phase 6: Prediction Market Migration (When Needed)

**Goal:** When DK limits come, the model migrates to exchanges that welcome sharps.

- [ ] Research Kalshi sports contract API and data format
- [ ] Research Polymarket sports market structure
- [ ] Map DK odds to prediction market contract prices (both are implied probabilities)
- [ ] Build adapter layer: same model, different odds source
- [ ] Parallel test: run model against DK and prediction market prices for one week
- [ ] Decision point: migrate fully or run dual-source

---

## Backlog (Carried Forward)

- [ ] Odds API credit budgeting (~349 remaining as of March 21)
- [ ] Alt line scanning (Skellam model on DK alt spreads)
- [ ] B2B detection for NHL/MLB (currently NBA-only)
- [ ] NHL Skellam calibration (58% too conservative vs 73% historical)
- [ ] Email/push notifications for qualifying picks

---

## Completed History

### March 21, 2026 — Session 2
- [x] Split GitHub Actions workflows (game-only every 3hrs + full 2x/day)
- [x] Opponent defensive rating adjustment for prop projections
- [x] Verified morning scan status

### March 21, 2026 — Session 1
- [x] Bankroll corrections, replaced PrizePicks with real DK odds
- [x] Fixed ESPN gamelog parser, GitHub Actions workflows
- [x] Diversified bet sizing (2% max, category budgets)
- [x] Both-sides spread evaluation, improved prop model
- [x] UI improvements (to-win amounts, pending count fix, bankroll sizing in all sections)
