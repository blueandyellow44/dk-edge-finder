# DK Edge Finder — Current TODO

## Status as of March 21, 2026

**Bankroll:** $570.57 (11W-8L, +$70.57 profit)
**Last scan:** March 21, 2026 — 7 edges found across NBA, NHL

---

## Completed (March 20-21)

- [x] Player prop pipeline (PrizePicks + ESPN → edge calc → Kelly sizing)
- [x] Fixed Netlify deploy (removed embedded .claude/worktrees repos)
- [x] Added .gitignore to prevent future deploy breaks
- [x] Resolved March 20 bets (4 placed: 2W-2L)
- [x] Corrected bankroll to $570.57 (DK app balance)
- [x] Removed 3 unplaced bets from history (Murray prop, Brunson prop, OVER 213.5)
- [x] Kelly sizing: 3.5% max single bet, 20% daily exposure cap
- [x] Tank team filtering: complete skip instead of -3% penalty
- [x] Added bankroll_override in bankroll.json (scan uses DK app balance)
- [x] Fixed GitHub Actions workflows (working-directory for local imports)
- [x] Fixed profit calculation to use override when set

## In Progress

- [ ] **Push all changes to GitHub** — data.json, scan_edges.py, workflows, bankroll.json
- [ ] **Verify GitHub Actions auto-scan works** — trigger manual workflow run after push

## Backlog

- [ ] Alt line scanning (Skellam model on DK alt spreads)
- [ ] B2B detection for NHL/MLB (currently NBA-only)
- [ ] NHL Skellam calibration (58% too conservative vs 73% historical)
- [ ] SGP correlation analysis
- [ ] Bet tracking ROI by sport/tier/type

---

## Next Session Should Start With

1. Check if morning scan auto-ran (GitHub Actions → Netlify deploy)
2. If not: debug workflow, check Actions tab for errors
3. Verify bankroll matches DK app after any new bets
