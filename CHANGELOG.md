# Changelog

All notable changes to the DK Edge Finder rebuild are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Conventional Commits are used in git history.

## [Unreleased]

### Fixed
- **scripts/resolve_bets.py:** Scoreboard cache now keyed by `(sport, date)` instead of `sport` alone. Previously the first pending pick of each sport triggered a fetch for that pick's date, and every later pending pick of the same sport silently reused the same scoreboard regardless of its own date. 110 NBA paper picks across April 5-29 had been stuck pending for weeks; all resolved after the fix. Commits `8fd86b7` (code) + `a3efced` (data).
- **scripts/scan_edges.py:** Added NBA playoff discount window (Apr 15 to Jun 30). During the window NBA edges are reduced 40%, NBA OVER totals get an additional 10% penalty, NBA min-edge is raised to 8%, and any pick whose post-discount edge is still above 10% is hard-skipped (treated as model hallucination). Tactical patch until a real NBA playoff calibration ships. Commits `fe63294` (code) + `c08a0e3` (today's re-scan).

### Added
- `lessons.md`, `HANDOFF.md`, `CHANGELOG.md` at repo root for the v2 frontend rebuild. Model-side lessons remain at `dk-edge-finder/tasks/lessons.md`.
- Branch `rebuild/v2-frontend` created off `a3efced` for the frontend + auth + KV state work.
- Approved rebuild plan at `/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`.

### Notes
- The resolver fix surfaced two model-level findings now in `dk-edge-finder/tasks/lessons.md` as `[BACKLOG]`:
  - NBA paper trading is unprofitable at 44.9% over 178 picks (paper P/L `-$252.63`)
  - 5-8% edge bucket sits at 52.8% over 271 picks, below the 52.4% break-even at -110 odds
- Calibration outputs captured at `/tmp/dk-edge-calibration-BASELINE.txt` and `/tmp/dk-edge-calibration-AFTER-FIX.txt`.
