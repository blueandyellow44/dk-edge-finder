# DK Edge Finder — Current TODO

## Plan: Stabilize and Ship (March 19, 2026)

### Goal
Get the uncommitted soccer + Skellam changes verified and pushed, then address NHL calibration, before adding new features.

### Priority Order (one concern at a time)
1. **Verify + commit soccer parser fix** — single-word team names, corrected DRatings URLs, odds null guard
2. **Test soccer parser end-to-end** — fetch EPL predictions for a weekend date, confirm parsing works
3. **Calibrate NHL Skellam** — 58% is too conservative vs 73% historical. Research OT/EN adjustment.
4. **Polish checklist** — favicon, page title, meta tags, 375px mobile test
5. **Push everything** — one push after all verified
6. **Player props research** — separate session, needs data source discovery
7. **B2B detection for NHL/MLB** — generalize fetch_yesterday_games()

### Files Affected
- scripts/scan_edges.py (soccer parser, Skellam calibration)
- scripts/skellam.py (OT adjustment if needed)
- index.html (polish checklist items)
- data.json (updated by scan)

### Failure Modes
- Soccer parser matches false positives (column headers like "Time", "Goals" as team names)
- DRatings HTML format changes break parsers
- Skellam OT adjustment overcorrects and creates new fake edges

### Verification
- For each change: Python syntax check, test with real data, verify edge outputs are reasonable
- Before push: run full scan, check data.json output, node --check on index.html
- Staff engineer test: "Would I bet real money based on these edges?"

---

## Completed This Session
- [x] NHL/MLB DRatings parser
- [x] Multi-source ensemble (DRatings + Dimers)
- [x] DK dark theme
- [x] Real DK odds from ESPN
- [x] Skellam distribution for discrete scoring sports
- [x] Risk/Win dollar display (replaced breakeven %)
- [x] DK deep links to bet slip
- [x] Confidence badge fix
- [x] P/L chart chronological fix
- [x] Bankroll update on placement
- [x] Pending bets in Results/History
- [x] Resolved 3 NHL bets (all won, 9W-6L, +$85.67)
