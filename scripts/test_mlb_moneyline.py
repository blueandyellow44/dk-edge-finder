#!/usr/bin/env python3
"""Tests for MLB 2-way moneyline (2026-06-09). Pure asserts, no network.

Run:  python3 scripts/test_mlb_moneyline.py
"""

from __future__ import annotations

import sys

import skellam as S
import mlb_moneyline as M

checks = 0
failures: list[str] = []


def truthy(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}: expected True")


def approx(label, got, want, tol=1e-9):
    global checks
    checks += 1
    if abs(got - want) > tol:
        failures.append(f"{label}: got {got!r}, want {want!r} (±{tol})")


# ── two_way_win_probs: sums to 1, no draw ─────────────────
for hx in [3.0, 4.0, 4.6, 5.5]:
    for ax in [3.0, 4.0, 4.6, 5.5]:
        ph, pa = S.two_way_win_probs(hx, ax)
        approx(f"sum=1 @ ({hx},{ax})", ph + pa, 1.0, tol=1e-9)
        truthy(f"both in (0,1) @ ({hx},{ax})", 0 < ph < 1 and 0 < pa < 1)

# Higher predicted runs => higher win prob
ph, pa = S.two_way_win_probs(5.2, 3.8)
truthy("home fav (more runs) wins more", ph > pa)
ph, pa = S.two_way_win_probs(3.8, 5.2)
truthy("away fav wins more", pa > ph)

# Equal runs + neutral tie split => 50/50
ph, pa = S.two_way_win_probs(4.3, 4.3)
approx("equal runs => 50/50", ph, 0.5, tol=1e-9)

# Tie split is the three-way draw mass redistributed
p3h, p3d, p3a = S.three_way_probs(4.6, 4.0)
ph, pa = S.two_way_win_probs(4.6, 4.0)
approx("home ml = P(win) + 0.5*P(tie)", ph, p3h + 0.5 * p3d, tol=1e-12)
approx("away ml = P(loss) + 0.5*P(tie)", pa, p3a + 0.5 * p3d, tol=1e-12)

# Sanity: a modest home favorite lands in a plausible MLB range
ph, _ = S.two_way_win_probs(4.7, 4.1)
truthy(f"modest home fav P(win)={ph:.3f} in [0.52,0.60]", 0.52 <= ph <= 0.60)

# home_tie_edge parameter shifts the split
ph0, _ = S.two_way_win_probs(4.3, 4.3, home_tie_edge=0.5)
ph1, _ = S.two_way_win_probs(4.3, 4.3, home_tie_edge=0.55)
truthy("higher home_tie_edge raises home prob", ph1 > ph0)


# ── end-to-end edge calc (with the market-anchored blend) ──
from market_blend import blend_multiway
game = {"home": {"abbr": "NYY", "name": "New York Yankees"},
        "away": {"abbr": "BOS", "name": "Boston Red Sox"},
        "dk_game_link": "", "start_time": ""}
# Strong model home favorite (5.5 vs 3.5 runs) priced as a pick'em — a big
# model-vs-market disagreement that survives the blend's shrinkage.
pred = {"home_score": 5.5, "away_score": 3.5, "source_label": "DRatings", "sources": 2}
ph, pa = S.two_way_win_probs(5.5, 3.5)
bh, ba = blend_multiway([ph, pa], [+100, -120])  # what the edge calc uses
res = M.calculate_mlb_ml_edge(game, pred, {"home_ml": +100, "away_ml": -120,
                                           "home_link": "x", "away_link": ""})
truthy("e2e produces a pick", isinstance(res, dict))
if isinstance(res, dict):
    truthy("e2e picks the home favorite", res["pick"] == "New York Yankees ML")
    truthy("e2e market is Moneyline", res["market"] == "Moneyline")
    truthy("e2e logs xg + probs", res["home_xg"] == 5.5 and "p_home" in res)
    # model_prob is the BLENDED home prob, not the raw skellam one
    approx("e2e model_prob == blended home", res["model_prob"], bh, tol=1e-9)
    truthy("blend shrinks model toward market (blended < raw)", bh < ph)

# No-edge: home over-priced (-300) so even the strong model has no edge => None
none_res = M.calculate_mlb_ml_edge(game, pred, {"home_ml": -300, "away_ml": +240,
                                                "home_link": "", "away_link": ""})
truthy("over-priced favorite => no pick", none_res is None)


print(f"ran {checks} checks")
if failures:
    print(f"\nFAILED ({len(failures)}):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
