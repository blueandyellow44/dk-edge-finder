# Session State — March 18, 2026 (End of Session)

## Bankroll
- Available: $499.51 (after $82 deducted for 4 pending bets)
- Starting: $500
- Resolved P/L: +$81.51
- Record: 3W-2L-0P (60% win rate)
- Pending: Nets +19.5 ($29), Jazz +13.5 ($25), Grizzlies +13.5 ($16), Mavericks +8.5 ($12)

## What Works
- **GitHub Actions**: resolve_bets.py (10 PM) and scan_edges.py (6 AM) run autonomously
- **ESPN API**: free, no key, returns scores + odds for NBA/NFL/MLB/NHL/MLS/EPL/MMA
- **DRatings scraper**: works for NBA, returns predicted scores
- **Bet resolution**: resolves WIN/LOSS/PUSH, updates bankroll with deduction-on-placement math
- **Kelly criterion**: half-Kelly, 5% max single bet, 15% max daily exposure
- **Tanking detection**: -3% penalty for confirmed tanking teams
- **B2B detection**: -1.5% penalty (road B2B: -2.5%)
- **SSH key**: set up on Mac for git push
- **Netlify**: auto-deploys from GitHub
- **Place buttons**: GitHub Actions workflow_dispatch, token in localStorage
- **Place persistence**: localStorage cache survives refresh (just added)

## What's Broken / Needs Work
1. **Design is generic ESPN knockoff** — user wants DraftKings-inspired dark theme. Study actual DK app.
2. **Totals edges too high** — 26.3% on TOR/CHI under. Using game SD of 17.19 (NBA totals, Boyd's Bets). Math is correct but DRatings prediction may be wrong. Need multi-source ensemble to validate.
3. **NHL/MLB/Soccer DRatings parser** — returns 0 predictions. HTML format differs. Games are fetched but no edges calculated.
4. **NHL/MLB SD values** — derived from Poisson, not measured ATS data. Marked as partially validated.
5. **Multi-source ensemble not built** — proposed: average DRatings + Dimers + ESPN BPI, use disagreement as uncertainty. Would fix the 26% edge problem.
6. **No player props** — user wants them but DK format is tricky. Deferred.
7. **Place button triggers GitHub Action** — takes ~60s to commit. localStorage cache added to survive refresh.
8. **scan_edges.py keeps overwriting picks[]** — fixed: bets[] is now sacred, never wiped. But picks[] still gets replaced each scan.

## Researched SD Values (Production-Ready)
| Sport | Spread SD | Totals SD | Source | Confidence |
|-------|-----------|-----------|--------|------------|
| NBA | 11.26 | 17.19 | Boyd's Bets (measured, multi-season) | HIGH |
| NFL | 13.28 | 13.28 | Boyd's Bets + Stern 1991 | HIGH |
| Soccer | 1.71 | 1.71 | Dixon-Coles Poisson model | MEDIUM |
| NHL | — | — | No measured ATS data | BLOCKED |
| MLB | — | — | No measured ATS data | BLOCKED |

## Key Rules Added This Session
- Bankroll deducts on placement (bets[] is sacred)
- Never assume SD values — research or skip
- Never cap edges — investigate the model inputs
- Suspicious edge flag at >10% (investigate, don't cap)
- Mom Test mindset in CLAUDE.md
- "Anticipate the Next Problem" in CLAUDE.md
- "Don't Make the User Be the Architect" in CLAUDE.md

## Priority for Next Session
1. **Fix the design** — study DraftKings app, build DK-inspired theme
2. **Build multi-source ensemble** — DRatings + Dimers + ESPN BPI averaged
3. **Fix NHL/MLB DRatings parser** for non-NBA sports
4. **Research NHL/MLB SD values** — need measured ATS data, not Poisson estimates
5. **Verify tonight's bet outcomes** — resolve Nets/Jazz/Grizzlies/Mavericks
6. **CLV tracking** — record closing lines, track model accuracy over time

## Files to Push
All changes are in the local folder. Push with:
```
git add -A && git commit -m "Bug fixes: localStorage placement, history pending bets, session state" && git push origin main
```
