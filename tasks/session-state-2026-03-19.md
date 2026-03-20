# Session State — March 19, 2026 (End of Session)

## Bankroll
- Available: $548.64 (after placing 3 NHL bets — $466.35 if they don't hit)
- Starting: $500
- Resolved P/L: +$48.64
- Record: 6W-6L-0P (50% win rate)
- Pending: DET +1.5 ($27.43), NYI +1.5 ($27.43), FLA +1.5 ($27.43)

## What Was Shipped This Session
1. NHL/MLB DRatings parser (score regex, W-L-OTL, MLB team map)
2. ESPN spread parsing fix (moneyline-as-spread bug)
3. NHL/MLB SD values (1.274 goals, 2.538 runs)
4. Multi-source ensemble model (DRatings + Dimers/Levy Edge)
5. H/A reversal handling in ensemble
6. DK dark theme (full CSS rewrite)
7. Bankroll update on bet placement
8. Pending bets in Results/History
9. DK deep links to bet slip (from ESPN pointSpread.link.href)
10. Model logic visible in pick cards
11. Confidence badge (not market tier)
12. P/L chart fixed (chronological accumulation)
13. Real DK odds from ESPN (not flat -190 default)
14. "No games scheduled" → "All games in progress" subtitle fix
15. Pick preservation when no upcoming games

## CRITICAL: Audit Findings — Priority Fixes for Next Session

### P0: NHL Model Is Overconfident (BANKROLL RISK)
- Model says 87.6% for puck line underdogs, historical base rate is ~70-75%
- Normal distribution is WRONG for discrete goal scoring (Poisson)
- Need to switch to Skellam distribution for NHL/soccer
- Need to switch to negative binomial for MLB
- Keep normal CDF for NBA only (large numbers, CLT applies)
- ALSO: need breakeven rate shown on every pick ("you need 74% to profit")

### P1: Soccer Coverage Incomplete
- Currently only MLS and EPL
- User wants ALL leagues: La Liga, Bundesliga, Serie A, Ligue 1, UCL
- ESPN endpoints exist for all of them
- DRatings has separate pages for each
- Need to add to all_sports list and test parsers

### P2: Player Props Not Implemented
- User wants EVERYTHING DK offers (points, assists, rebounds, 3s, etc.)
- Audit wrongly recommended deprioritizing — props are where DK misprices most
- Needs: data source research, SD values for player stats, separate scan pipeline
- DRatings doesn't have props; need FantasyLabs, PrizePicks, or similar
- This is a separate feature build, not a patch

### P3: B2B Detection Only Works for NBA
- NHL and MLB teams play back-to-backs too
- fetch_yesterday_games() is hardcoded for NBA basketball endpoint
- Need to generalize to accept sport parameter

### P4: CLV Tracking Not Implemented
- Rules file says to track it, code doesn't
- resolve_bets.py should record closing line when games finalize
- Best predictor of long-term profitability

### P5: Tanking Detection Only Works for NBA
- NHL teams tank too (sell at deadline, play rookies)
- Should be data-driven (compute win% from record) not hardcoded

### P6: Pipeline Resilience
- DRatings timeout kills entire sport (no retry, no cache)
- Dimers round detection is fragile (hardcoded base_round)
- No atomic writes for data.json/bankroll.json

## Mom Test Insights from Max
1. He chases highest edge % — model accuracy is CRITICAL
2. He'll bet any sport — "whatever has edges"
3. He would NOT have placed NHL bets if he saw "need 2/3 to break even"
4. He wants ALL player props, not just spreads/totals
5. "What can help you be more intuitive?" — screenshots of DK, his betting workflow, WHY something feels off not just that it does

## What Max Can Help With
- Screenshots of specific DK pages (bet slip, prop builder, game page)
- When bugs feel wrong, explain WHY (like "need 2/3 to break even")
- A 10-min walkthrough of his actual DK betting flow

## Files Changed (All Committed, Need Push)
- scripts/scan_edges.py (ensemble, parser, real odds, DK links)
- index.html (DK dark theme, bankroll fix, deep links, logic display)
- data.json (real odds, 3 under bets, NHL picks for Mar 19)
- tasks/lessons.md (7 new lessons)

## Git Status
- Remote: git@github.com:blueandyellow44/dk-edge-finder.git (SSH)
- All changes committed locally
- Push from Mac: `cd ~/Betting\ Skill && git push origin main`
