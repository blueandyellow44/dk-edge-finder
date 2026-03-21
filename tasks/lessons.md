# DK Edge Finder — Lessons Learned

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

## 2026-03-21: Spread evaluation must check BOTH sides
**Mistake:** `calculate_spread_edge()` only evaluated the underdog side of every spread. If the model predicted a favorite would cover by more than the spread, that edge was invisible. Result: 100% of game edges were underdogs — a systematic bias, not a market insight.
**Rule:** Always evaluate both the underdog AND favorite side of each spread. Calculate cover probability for each, get DK odds for each, compute edge for each, and return whichever side has the larger edge (if either clears the threshold). Never assume one side of the market is always where the value lives.
