# DK Edge Finder — Lessons Learned

## 2026-05-02: NBA regular-season Spread picks at raw edge >= 8% are anti-signal [AUTOMATE - DONE]
**Observation:** Microscopic audit of pick_history.json (759 resolved picks, 2026-03-24 to 2026-05-01) shows NBA Spread picks split sharply by raw edge. Edges below 8% are roughly break-even (15W-14L over the 3-5% and 5-8% buckets combined). Edges at or above 8% hit 21W-39L (35.0%) at -$198.40 over 60 picks. The 8-12% bucket alone is 7W-18L (28.0%) at -$115. The 2026-04-30 NBA playoff discount block already protects in-window picks; the bleed is regular-season-only.
**Impact:** Replay against historical picks: if the new guard had been live since 2026-03-24, it would have dropped 57 NBA Spread picks (18W-39L at -$225) and kept 32 (18W-14L at +$25). Net +$250 swing on NBA alone. Patch is mostly forward-looking because the NBA regular season has already ended; takes effect for the 2026-27 season opener.
**Rule:** When a model's edge estimate is ANTI-correlated with realized outcome over a meaningful sample (here n=60, p < 0.05 against fair coin), the model is fighting market closing line value, not finding alpha. Hard-skip the bucket. Mirror the existing playoff hard-skip pattern; do not try to fix the underlying SD or DRatings prediction in the same patch (one change per audit window).
**Code fix:** scripts/scan_edges.py added NBA_REGULAR_SEASON_SPREAD_HARD_SKIP_AT = 0.08 constant and a guard block in calculate_edge() that skips NBA Spread candidates with raw edge >= 8% when not in the playoff window. Mirrors the lines 1373-1377 playoff pattern. Commit forthcoming.
**Backlog (deferred per panel):**
- Instrument CLV in resolve_bets.py: log closing line and bet line per pick, so a future audit can confirm whether the NBA bleed is sharp-money exploitation vs model error.
- Press MLB Spread 12%+ bucket (74.4% / +$714 over 90 picks): consider raising Kelly fraction. Defer until next audit so this NBA change has clean attribution.
- Consolidate the NBA override layer (NBA_SPREAD_MIN_EDGE, NBA_LARGE_*, NBA_PLAYOFF_*, regular-season hard-skip) into a single per-sport-per-market filter table. Tech debt, not a bleed.
- Confidence labeler is broken: HIGH only fires on NBA, hits 50.8%, no signal. Fix or retire the field. Not bleed-stopping.

## 2026-04-30: Resolver scoreboard cache must key on (sport, date), not sport alone [AUTOMATE - DONE]
**Mistake:** scripts/resolve_bets.py cached fetched ESPN scoreboards under all_games[sport]. The first pending pick of each sport triggered a fetch for that pick's scan_date. Every subsequent pending pick of the same sport silently reused the same scoreboard regardless of its own date. find_game_score then could not locate games on other dates and the picks stayed pending forever.
**Impact:** 110 NBA paper picks across April 5-29 were stuck pending for weeks. After fix, all resolved. Record went from 363W-257L to 415W-315L.
**Rule:** Whenever caching API results in a loop that processes items spanning multiple parameter axes (sport, date, league), the cache key must include every axis the API call depends on. A cache key that loses information is a silent bug. Always test by running the resolver against a multi-date dataset.
**Code fix:** scripts/resolve_bets.py both main() and resolve_pick_history() now key all_games by (sport, date_str). Lookup paths updated to compute date from each pending entry. Commits 8fd86b7 (code) + a3efced (data).
**Pattern reinforcement of 2026-03-21 META:** Lessons must become code. This bug existed because the original cache key was a manual choice; a guard clause or unit test on the cache lookup would have caught it.

## 2026-04-30 backlog: NBA model is unprofitable, needs a separate calibration pass [BACKLOG]
**Observation:** With the resolver fix in place, NBA paper trading sits at 80W-98L (44.9%) with paper P/L -$252.63 over 178 picks. The buggy resolver was masking nearly 100 NBA losses. MLB and NHL are profitable (61.2% and 59.5% respectively). The NBA model is genuinely worse than the others, not just under-resolved.
**Rule:** Until a targeted NBA calibration ships, treat NBA picks as paper-only. Do not increase NBA Kelly fraction. Consider raising NBA min-edge threshold from current 5% to 8%+ until per-bin hit rates clear break-even.
**Added to:** lessons.md as [BACKLOG] for follow-up calibration work.

## 2026-04-30 backlog: 5-8% edge bucket is below break-even [BACKLOG]
**Observation:** With the resolver fix in place, the 5-8% edge bucket sits at 52.8% hit rate over 271 picks, paper P/L -$156.32. Implied break-even at -110 odds is 52.4%. The model has effectively zero edge in this bucket once vig is included.
**Rule:** Consider raising base min-edge threshold from 5% to 8% globally. Or apply a graduated discount that pushes 5-8% edges below the bet-flagging threshold.

## 2026-04-30: Stale stash from prior local sessions can pollute the working tree [MANUAL]
**Mistake:** Today's `git stash && git pull --rebase && git stash pop` ritual popped a stash from a prior session even though the user had no local changes today. The stash contained 43 stale duplicate April 6 picks that landed in pick_history.json's working tree. Initially looked like real in-progress work but turned out to be debris.
**Rule:** Before applying lesson 2026-03-22's `git stash pop`, run `git stash list` first. If there is already a stash entry, decide whether to drop it before adding a new one. The pop will replay an OLD stash, not necessarily today's work. Saved the stale data to /tmp/dk-edge-stashed-april-6-props.json for reference.

## 2026-03-22: Always git pull --rebase before pushing when automated scans are running
**Mistake:** Every push from local fails with "non-fast-forward" because GitHub Actions game-scan and morning-scan workflows commit to main between local work sessions. This has now happened 3+ times.
**Rule:** ALWAYS run `git stash && git pull --rebase && git stash pop` before pushing. Automated scans commit data.json changes to remote main every few hours. Local will always be behind. If data.json conflicts during rebase, take `--theirs` (remote) since the next scan regenerates it anyway. Tell Max this upfront every time, not after the push fails.

## 2026-03-17: Deduct bankroll on bet placement
**Mistake:** Kept bankroll at $586.60 after user placed $48.50 in bets. Dashboard showed pre-bet balance as "current."
**Rule:** When bets are placed, immediately deduct wager total from current bankroll. Available = current - pending wagers. Kelly sizing uses available balance only. On resolution: WIN adds wager + profit, LOSS stays deducted, PUSH returns wager.
**Added to:** dk-edge-finder-rules.md (Bankroll file section)

## 2026-03-17: Odds accuracy — always verify on DK directly
**Mistake:** Used ESPN odds that showed Wizards +18.5 (-105) when DK actually had +17.5 (-105), later +18 (-110). Lines differ by book and move fast.
**Rule:** Always cross-reference Action Network or DK directly. ESPN "provided by DraftKings" odds can lag. Note time of observation.

## 2026-03-17: DK prop format
**Mistake:** Listed "Mitchell o3.5 3PM" — user said DK uses whole numbers or halves for 3PM props, not always matching other books.
**Rule:** Verify prop availability on DK Oregon specifically. Dimers props may reference lines from other books.

## 2026-03-17: No player props unless confirmed available
**Mistake:** Included player props that user couldn't find on DK.
**Rule:** User said no player props. Stick to spreads/ML/totals unless user explicitly requests props and confirms availability.

## 2026-03-18: Tanking teams blow spreads — apply tank penalty
**Mistake:** Flagged Pacers +15.5 (15-53 team) and Kings +13.5 (18-51 team) as edges. Both lost by huge margins (Knicks by 26, Spurs by 28). Models don't account for teams actively trying to lose.
**Rule:** Bottom-8 teams after All-Star break get a -3% tank penalty to model cover probability. If edge disappears after penalty, skip the bet. Tanking teams lose by MORE than expected — starters sit in Q4, developmental lineups run, no competitive effort in close games. Added full tanking detection framework to dk-edge-finder-rules.md.

## 2026-03-18: Scan keeps wiping placed bets — NEVER touch bets[]
**Mistake:** scan_edges.py overwrote data.json and wiped the user's 4 placed bets THREE TIMES in one session. Bets were in picks[] (status "PLACED") but not in bets[]. Scan replaces picks[] every run.
**Rule:** The bets[] array is SACRED. The scan must NEVER remove entries from it. Bets only enter bets[] when the user places them (via Place button or manual confirmation). The scan writes picks[] (today's suggestions) but preserves bets[] untouched. This is the #1 data integrity rule.

## 2026-03-18: Don't change git remote URL from this VM
**Mistake:** Changed remote from SSH (`git@github.com:...`) to HTTPS (`https://github.com/...`) when trying to push from the Cowork VM. This broke Max's push from his Mac — it asked for a password instead of using his SSH key.
**Rule:** Never run `git remote set-url` in this VM. The SSH remote is configured on Max's Mac with his SSH key. If we can't push from the VM, just tell Max to push from his Mac. Don't try to "fix" the remote.

## 2026-03-18: Ensemble — reversed home/away is the same game, not different games
**Mistake:** Initially rejected reversed matches (DET@WSH vs WSH@DET) thinking they were different games on back-to-back nights. They're the same game — one source just has home/away flipped. Also initially computed disagreement as `|DR_margin - DM_margin|` which showed 26.5pts when the real team-strength disagreement was only 0.3pts.
**Rule:** Teams don't play each other twice in one night. If the same two teams appear in both sources with reversed H/A, it's the same game. Match by team identity, swap scores to align perspectives, compute true disagreement as `||DR_margin| - |DM_margin||` (magnitude difference, ignoring sign).

## 2026-03-18: ESPN 'details' field contains moneyline for NHL/MLB, not spread
**Mistake:** Parser treated ESPN's `details` field (e.g., "COL -142") as the point spread for all sports. For NBA it IS the spread ("OKC -19.5"), but for NHL/MLB it's the moneyline. Created 142-point fake spreads and 45% fake edges.
**Rule:** Use ESPN's `spread` API field for the actual spread value. Only use `details` to determine which team is favored (the team abbreviation). Never parse the number from `details` for NHL/MLB.

## 2026-03-18: Don't show internal implementation details to users
**Mistake:** Added "(H/A reversed)" label to user-facing source notes on picks. Users don't care about data source disagreements — they just want the pick and confidence level.
**Rule:** Keep internal data quality notes (H/A reversed, single source, parser issues) out of user-facing labels. Use confidence levels (HIGH/MEDIUM/LOW) and contested flags instead.

## 2026-03-18: Verify before push — NEVER ship broken code
**Mistake:** Pushed index.html with broken JS template literals (missing `}` in ternary expressions inside style strings). Site showed "Loading..." forever because render() crashed. User had to push twice.
**Rule:** Before ANY commit that touches index.html:
1. Run `node -c index.html` or extract the JS and run `node --check` on it to catch syntax errors
2. If the file has template literals with ternaries inside style attributes, manually verify every `${condition?'a':'b'}` has its closing brace BEFORE the semicolon
3. Open the file locally in a browser and confirm it renders with data.json before telling user to push
4. Never let a subagent write JS without verifying the output compiles
**General rule from user:** "Have high confidence in everything before a push." No more ship-and-pray. Verify locally first.

## 2026-03-17: Don't rename data.json fields without updating index.html
**Mistake:** Renamed `bankroll.current` to `bankroll.available` in data.json without updating index.html. Netlify site broke — "Error loading data" because `b.current.toFixed(2)` threw on undefined.
**Rule:** Any data.json schema change MUST have a corresponding index.html update in the same commit. Use fallback patterns like `b.available || b.current || 0` for backward compatibility.

## 2026-03-20: PrizePicks returns non-NBA players for sport=nba
**Mistake:** First prop scan found 0 edges because PrizePicks includes college/G-League players whose ESPN game logs don't exist. All 10 ESPN lookups were wasted on minor players.
**Rule:** Always filter PrizePicks props to known NBA team abbreviations before looking up stats. Also sort by highest line (stars) so limited lookups focus on the players most likely to have edges.

## 2026-03-20: PrizePicks rate limits aggressively
**Mistake:** Multiple rapid calls to PrizePicks API triggered 429 (Too Many Requests) that persists for ~30 seconds.
**Rule:** Never call PrizePicks more than once per scan session. Add retry-after-10s for 429 errors. Cache the result for the full scan.

## 2026-03-20: Embedded git repos break Netlify deploys
**Mistake:** Running `git add -A` committed `.claude/worktrees/` directories which contain embedded git repos. Netlify treats these as submodules and fails when there's no `.gitmodules` entry.
**Rule:** ALWAYS have a .gitignore with `.claude/worktrees/` and `__pycache__/` BEFORE the first `git add`. Never use `git add -A` without verifying .gitignore covers agent artifacts. Prefer `git add <specific files>` over `git add -A`.

## 2026-03-21: Git index.lock keeps blocking pushes
**Mistake:** Stale `.git/index.lock` files left by crashed git processes (from Cowork VM or interrupted terminal commands) block all subsequent git operations. This has happened 3+ times.
**Rule:** scan_edges.py now auto-removes stale index.lock on startup. For manual fix: `rm -f .git/index.lock`. Root cause: two environments (Cowork VM + Mac terminal) share the same .git directory. Long-term: only one environment should write to git at a time.
**Code fix:** Added Step 0 to scan_edges.py that unlinks stale index.lock before any git operations.

## 2026-03-21: Bankroll must come from DK app, not calculated PnL
**Mistake:** Scan calculated bankroll from bet history PnL ($568.61) but actual DK balance was $570.57. The $2 gap comes from rounding on odds/payouts in manually entered historical bets. Every scan overwrote the real balance with the wrong number.
**Rule:** DK app balance is always the source of truth. Set `balance_override` in bankroll.json to the real number. The scan uses it when present, falls back to calculated PnL when not set. After every session where bets are placed or resolved, update bankroll.json with the actual DK balance.
**Code fix:** Added `balance_override` field to bankroll.json and corresponding logic in scan_edges.py.

## 2026-03-21: Max doesn't place every suggested bet — don't assume he does
**Mistake:** Scan suggested 7 bets for March 20. Data showed all 7 in bet history as if placed. Max only placed 4. Record showed 12W-10L instead of correct 11W-8L.
**Rule:** NEVER auto-add picks to the bets[] array. Bets only enter history when Max explicitly confirms placement via the site's "Mark Placed" button or tells us directly. If Max says "bankroll should be X", that's the number — don't argue with calculated PnL.

## 2026-03-21: META — Lessons must become code, not just docs
**Pattern:** We keep writing rules in lessons.md but the same bugs recur because the rules require manual compliance. A lesson that says "always do X" will eventually be forgotten. A guard clause that enforces X cannot be.
**Rule:** Every lesson that CAN be automated MUST be automated:
- "Never overwrite bets[]" → code preserves bets[] (done)
- "Use DK balance not calculated" → balance_override in bankroll.json (done)
- "Clean stale git locks" → Step 0 in scan_edges.py (done)
- "Verify JS syntax before push" → TODO: add pre-commit hook
- "Don't change git remote" → TODO: add check that warns if remote URL changes
If a lesson can only be a doc (like "verify odds on DK"), tag it `[MANUAL]`. If it should be code, tag it `[AUTOMATE]` until the code exists.

## 2026-03-21: PrizePicks lines are NOT DK odds — never use them for edge calculation
**Mistake:** Used PrizePicks projections (e.g. SGA OVER 0.5 3-PT Made at -120) as if they were DraftKings betting lines. PrizePicks is a DFS contest platform — their "lines" are projection points, not odds. Real DK odds for SGA OVER 0.5 3PT would be -700+. This produced fake 20%+ edges on bets that either don't exist on DK or are priced completely differently.
**Rule:** Only use actual sportsbook odds for edge calculation. The Odds API (`api.the-odds-api.com`) provides real DK prop lines with American odds. Never treat DFS projections as betting odds.
**Code fix:** Replaced PrizePicks fetcher with The Odds API fetcher in fetch_props.py. API key stored in .env (local) and GitHub Actions secret (CI).

## 2026-03-21: ESPN gamelog categories are by month, not by "regular"/"preseason"
**Mistake:** `fetch_player_recent_stats()` filtered categories by `cat.get("name") == "regular"`, but ESPN's gamelog API groups categories by month (displayName: "march", "february", etc.) with no "name" field. Every player returned 0 stats.
**Rule:** Don't filter on `cat.get("name")`. Instead skip the preseason seasonType by checking `st.get("displayName")` and take all events from remaining seasonTypes.
**Code fix:** Updated `fetch_player_recent_stats()` in fetch_props.py.

## 2026-03-21: Single exposure pool lets one category crowd out others [AUTOMATE]
**Mistake:** 20% daily cap with all picks sorted by edge descending meant 6 high-edge props ate the entire budget. Zero game edges made it through.
**Rule:** Use per-category budgets (games vs props) so neither can crowd out the other. Sort within each category independently.
**Code fix:** Added MAX_GAME_EXPOSURE (20%) and MAX_PROP_EXPOSURE (15%) with fill_category() function in scan_edges.py.

## 2026-03-21: Never trust bankroll.pending_count — count from actual bets [AUTOMATE]
**Mistake:** bankroll.pending_count accumulated to 29 across multiple workflow runs but actual pending bets in bets[] was 14. Pending stats card showed wrong number.
**Rule:** Always derive pending count and total from `bets.filter(x => x.outcome === 'pending')`. Never trust pre-computed fields that can go stale from workflow race conditions.
**Code fix:** Updated render() in index.html to count from bets[] array instead of bankroll.pending_count.

## 2026-03-21: 10-game average overestimates prop edges — cap or discount [MANUAL]
**Observation:** Prop edges of 31% (Luka 3s), 23% (Wemby 3s) are suspiciously large. Real sharp edges are 3-8%. Our model (simple 10-game ESPN average vs DK line) doesn't account for matchup, minutes variance, pace, or blowout risk.
**Rule:** Treat prop edges over 15% as "directionally correct but magnitude overstated." Future fix: weighted recency, opponent defensive rating, sample size confidence discount.

## 2026-03-21: NEVER say "fixed" without verifying the rendered output [AUTOMATE]
**Pattern:** Multiple times this session, Claude declared a UI change "done" and told Max to push, but the change either didn't work, was reverted by a later edit, or had the wrong behavior. Max had to screenshot the broken state each time. This wastes Max's time and erodes trust.
**Rule:** Before telling Max a UI change is ready to push:
1. Read the actual code that renders the affected section — not from memory, from the file
2. Trace the logic: if condition X is true, what HTML gets rendered? Walk through it line by line
3. Check for accidental reverts: did a later edit undo the fix?
4. Check brace/paren/backtick balance on the whole file
5. If possible, run a lightweight simulation of the rendering logic in Node
6. Only THEN say "push it"
Never say "done" based on writing the edit. Verify the edit survived and works.

## 2026-03-21: Git push — always verify the correct directory first
**Mistake:** Repeatedly tried to `git push` from the wrong directory (e.g., "Political Ap" instead of the dk-edge-finder repo). The Cowork mount name ("Betting Skill") does not match the actual Mac directory name.
**Rule:** Before any git command, run `pwd` and verify you're in a directory with a `.git` folder. The dk-edge-finder repo on Max's Mac is at `~/Betting Skill` (NOT `~/Desktop/Betting Skill`). Command: `cd ~/Betting\ Skill`. Consider adding a shell alias: `alias cdb='cd ~/Betting\ Skill'`.

## 2026-03-21: Player prop model must account for variance, not just averages
**Mistake:** Flat 10-game average with hardcoded standard deviations produced edges of 20-31% — far above realistic sharp edges of 3-8%. Luka OVER 3.5 3PT showed 90.9% model confidence, which is absurd for a prop market.
**Rule:** Prop model improvements applied:
1. Weighted recency: last 3 games = 50% weight, previous 7 = 50% (captures streaks without overweighting)
2. Player-specific SD: compute actual game-to-game variance from ESPN data, fall back to hardcoded only when unavailable
3. Sample size penalty: widen SD by 25% when <7 games sampled
4. Blowout discount: reduce OVER model_prob by 15% when predicted margin >12pts (starters sit)
5. Edge cap at 15%: anything higher is model overconfidence, not a real edge
6. Kelly max per prop reduced from 3.5% to 2%

## 2026-03-21: Spread evaluation must check BOTH sides
**Mistake:** `calculate_spread_edge()` only evaluated the underdog side of every spread. If the model predicted a favorite would cover by more than the spread, that edge was invisible. Result: 100% of game edges were underdogs — a systematic bias, not a market insight.
**Rule:** Always evaluate both the underdog AND favorite side of each spread. Calculate cover probability for each, get DK odds for each, compute edge for each, and return whichever side has the larger edge (if either clears the threshold). Never assume one side of the market is always where the value lives.

## 2026-03-21: Opponent defense matters for props — adjust projections [AUTOMATE - DONE]
**Observation:** A player's 10-game average doesn't account for tonight's matchup. Scoring 30 PPG against bottom defenses doesn't mean 30 against Boston (107 PPG allowed vs league avg 112).
**Rule:** Adjust player projections by opponent defensive rating before computing edge. ESPN's `/teams/{abbr}` endpoint provides `avgPointsAgainst` for free, no auth needed. Multiplier = (opponent PPG allowed / league avg), capped at ±8% to avoid overreaction. Cache per session — never re-fetch the same team twice.
**Code fix:** Added `fetch_team_defensive_rating()`, `get_defense_multiplier()`, and `fetch_player_team()` to fetch_props.py. Integrated into `calculate_prop_edge()` and `scan_props()`.

## 2026-03-21: Game-only scans preserve prop picks from last full scan [AUTOMATE - DONE]
**Observation:** When `--games-only` mode runs, it doesn't scan props, so `formatted_picks` only contains game edges. Writing this to data.json would wipe all prop picks from the last full scan.
**Rule:** In games-only mode, preserve existing prop picks (`type == "prop"`) from the current data.json and append them to the new game-only picks before writing. Props only get refreshed during full scans.
**Code fix:** Added preservation logic in scan_edges.py Step 7 that merges existing prop picks when `games_only=True`.

## 2026-03-22: resolve_bets.py must handle ALL bet types, not just spreads/ML [AUTOMATE - DONE]
**Mistake:** `resolve_bets.py` only handled spread and moneyline bets. Totals (OVER/UNDER) bets fell through to `outcome = "unknown"` and stayed pending forever. Grizzlies UNDER 234.5 was stuck as PENDING even though the game was final (total 225).
**Rule:** Every bet type the scan can produce (spread, moneyline, total, prop) must have a corresponding resolver in `resolve_bets.py`. When adding a new bet type to the scan pipeline, add its resolver in the same commit.
**Code fix:** Added `resolve_total()` function and detection for `OVER`/`UNDER` pick strings in the resolution logic.

## 2026-03-22: Variable scope — all_predictions not predictions
**Mistake:** Step 5b (game margins for blowout discount) used `predictions` which doesn't exist in `main()` scope. The actual variable is `all_predictions` (dict keyed by sport). Caused NameError crash on every full scan.
**Rule:** After any refactor that changes variable names, grep for ALL usages of the old name. `predictions` was the old name from before the ensemble refactor; `all_predictions` is the current one. The game margins builder needs `all_predictions.get("nba", {})` to get the NBA-specific predictions dict.

## 2026-03-26: CALIBRATION — First week results (March 19-25, 18 picks, 12W-6L) [MANUAL]

### Overall: 66.7% win rate, +$59.40, 18.4% ROI
- Sample is small (n=18) — don't over-optimize from this data. Directional signals only.

### By sport:
- **NHL puck lines: 3-0 (100%)** — DRatings consensus is strong for hockey. Continue weighting DRatings highly for NHL.
- **NBA (mixed markets): 9-5 (64.3%)** — Solid. Spreads, totals, and props all contributing.
- **EPL soccer: 0-1** — Man U @ Bournemouth UNDER 3.5 lost (4 goals). Single data point, can't draw conclusions. Need 10+ soccer picks before adjusting the Skellam/Dixon-Coles model.

### By market type:
- **Game bets (spreads/totals/puck lines): 7-2 (78%)** — Model's core strength. Prioritize these.
- **Player props: 4-3 (57%)** — Break-even after vig. Props eat more bankroll than they return at current calibration. Keep sizing at 1/4 Kelly until accuracy improves.
- **Soccer totals: 0-1** — Too few to judge.

### By edge bucket:
- **10%+ edge: 9-4 (69.2%)** — High-edge picks convert, but losers in this bucket averaged HIGHER edges (14.77%) than winners (13.50%). Confirms the lesson: edges over 15% are overestimated. The 15% cap is working as intended.
- **5-8% edge: 1-1 (50%)** — Neutral. Need more data.
- **3-5% edge: 2-1 (66.7%)** — Small edges can work on game bets where the model is well-calibrated.

### Specific calibration adjustments:
1. **Large NBA spread losses trace to tanking/blowout teams** — The two pre-existing losses (Pacers +15.5, Kings +13.5 from March 17) plus GS +10.5 (March 21) are all large spreads on bad teams. Tank penalty helps but large spreads (>10 pts) remain risky. Consider raising the min edge threshold for spreads >10 pts from 3% to 5%.
2. **Prop edge magnitude is unreliable** — Luka OVER 3.5 3PT at 31.2% edge: LOSS. Wemby OVER 2.5 3PT at 23.5% edge: LOSS. But Luka OVER 32.5 pts at 20.8%: WIN. Edge size doesn't predict prop outcomes well. Stick with the 15% cap and treat all prop edges as "medium confidence" regardless of magnitude.
3. **UNDER totals performing well** — Both UNDER picks hit (Celtics/Grizzlies UNDER 229.5, Grizzlies/Hornets UNDER 234.5). Model may have a slight edge on UNDER totals — possibly because public money biases toward OVER, giving the book reason to shade UNDER lines.
4. **resolve_bets.py is silently failing on props and soccer** — 11 bets from March 21 sat "pending" for 5 days because the resolver couldn't match event strings or handle prop/soccer bet types. The totals fix from 3/22 helped but prop and soccer resolution paths are still broken or missing. [AUTOMATE — add prop and soccer resolvers]

### Rule: Run calibration report monthly
Schedule a manual calibration review on the 1st of each month. Compare: win rate by sport, by market, by edge bucket. Look for drift. If any sport drops below 55% win rate over 30+ picks, flag for model adjustment.

## 2026-04-03: CALIBRATION — Full history review (March 15–April 3, 34 bets, 20W-14L) [MANUAL]

### Overall: 58.8% win rate, ~+$100 profit, ~20% ROI on starting bankroll
- Record updated from 18-12 to 20-14 after resolving 4 pending MLB bets from March 29 (2W-2L).
- Win rate dropped from 60% to 58.8% — still profitable but trending toward breakeven.

### NBA Spreads are actively losing money: 5-7 (41.7%) [AUTOMATE]
- This is the model's single biggest weakness. NBA spread bets are below breakeven.
- Large spreads on bad/tanking teams are the worst (15+ pts: 2-3, ≤10 pts: 1-2).
- **Rule:** Raise NBA spread min edge from 3% to 5%. For spreads >12 pts, raise to 8%. This would have avoided 4 of the 7 losses.

### 5-8% edge bucket is the sweet spot: 6-2 (75%) [MANUAL]
- This outperforms both small edges (3-5%: 50%) and large edges (10%+: 58.8%).
- The model is best calibrated in this range. Larger edges are overestimated.
- **Rule:** Apply graduated edge discount for sizing: 10-12% edges → size as 8%, 12-15% → size as 10%. Never size on raw edge above 10%.

### MLB first results: 2-2 (50%) — neutral start [MANUAL]
- Underdog run lines (+1.5) went 2-1. Favorite run lines (-1.5) went 0-1.
- DRatings-only data for MLB (no Dimers cross-validation). Early season = high variance.
- **Rule:** MLB edges require pitching matchup data before trusting team-strength-only models. Add starter ERA/WHIP to MLB edge calculation.

### Single-source picks need reduced sizing [AUTOMATE]
- Most recent picks are DRatings-only (flagged MEDIUM confidence) but sized at full Kelly tier.
- **Rule:** Reduce Kelly fraction by 25% when only one source provides the model probability. Ensemble > single source, always.

### UNDER totals continue strong: 4-1 vs OVER: 0-1 [MANUAL]
- UNDER bias is real and persistent. Public money leans OVER, books shade UNDER.
- **Rule:** Consider UNDER-only strategy for NBA totals until OVER win rate improves above 55%.

### Auto-settlement still broken for MLB bets [AUTOMATE]
- March 29 MLB bets sat "pending" for 5 days until manual resolution today.
- **Rule:** resolve_bets.py needs MLB game resolution logic. Same pattern as the totals fix from 3/22 — add it now, not later.
