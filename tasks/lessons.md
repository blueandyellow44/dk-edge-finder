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
