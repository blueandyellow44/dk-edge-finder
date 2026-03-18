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
