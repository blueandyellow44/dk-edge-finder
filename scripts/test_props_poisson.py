#!/usr/bin/env python3
"""Analytic unit tests for the Poisson prop model (Phase 1, 2026-06-09).

These are the correctness gate for the count-distribution rebuild. They are
deterministic and need no data or network — they assert the kernel's Poisson
math against hand-computed values and prove the fix direction vs the old
normal-CDF path.

Run:

    python3 scripts/test_props_poisson.py

Exits non-zero on any failure. Pure asserts, no pytest dependency (matches the
fit_calibration.py house style).
"""

from __future__ import annotations

import math
import sys
from types import SimpleNamespace

import props_kernel as K

TOL = 1e-6
checks = 0
failures: list[str] = []


def approx(label, got, want, tol=TOL):
    global checks
    checks += 1
    if abs(got - want) > tol:
        failures.append(f"{label}: got {got!r}, want {want!r} (±{tol})")


def truthy(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}: expected True")


# ── poisson_cdf_le: exact small-m values ──────────────────
# P(X<=0; λ) = e^-λ
approx("cdf_le(0, 1.4)", K.poisson_cdf_le(0, 1.4), math.exp(-1.4))
# P(X<=1; λ) = e^-λ (1 + λ)
approx("cdf_le(1, 2.5)", K.poisson_cdf_le(1, 2.5), math.exp(-2.5) * (1 + 2.5))
# P(X<=2; λ) = e^-λ (1 + λ + λ²/2)
approx("cdf_le(2, 3.0)", K.poisson_cdf_le(2, 3.0),
       math.exp(-3.0) * (1 + 3.0 + 3.0**2 / 2))
# Degenerate / edge inputs
approx("cdf_le(0, 0)  -> 1.0 (lam<=0)", K.poisson_cdf_le(0, 0.0), 1.0)
approx("cdf_le(-1, 2) -> 0.0 (m<0)", K.poisson_cdf_le(-1, 2.0), 0.0)
# Large m converges to 1
truthy("cdf_le(50, 5) ~ 1.0", abs(K.poisson_cdf_le(50, 5.0) - 1.0) < 1e-9)


# ── poisson_over_under: the headline fix case ─────────────
# A 1.4/game player, OVER 0.5: true base rate = 1 - e^-1.4 = 0.7534.
over, under = K.poisson_over_under(1.4, 0.5)
approx("over_under(1.4,0.5) over", over, 1 - math.exp(-1.4))
approx("over_under(1.4,0.5) under", under, math.exp(-1.4))
truthy("tails sum to 1 @ (1.4,0.5)", abs(over + under - 1.0) < 1e-12)

# OVER 1.5 with λ=2.5: over = 1 - e^-2.5(1+2.5)
over15, under15 = K.poisson_over_under(2.5, 1.5)
approx("over_under(2.5,1.5) over", over15, 1 - math.exp(-2.5) * (1 + 2.5))
truthy("tails sum to 1 @ (2.5,1.5)", abs(over15 + under15 - 1.0) < 1e-12)

# Low projection under the line: under favored. λ=0.3, OVER 0.5.
over_lo, under_lo = K.poisson_over_under(0.3, 0.5)
approx("over_under(0.3,0.5) under", under_lo, math.exp(-0.3))
truthy("under favored when λ<line", under_lo > over_lo)


# ── Monotonicity: P(over) strictly increases in λ ─────────
prev = -1.0
mono = True
for lam in [0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
    o, _ = K.poisson_over_under(lam, 0.5)
    if o <= prev:
        mono = False
    prev = o
truthy("P(over 0.5) monotincreasing in λ", mono)


# ── The fix direction: Poisson < normal on a low line ─────
# Old normal path: over = 1 - normal_cdf((line - proj)/sd).
# The real NHL blowup case (Dorofeyev): proj=1.4, line=0.5, sd=0.9
# ("1.0σ separation" in the logged notes). Normal said ~84%; Poisson says 75.3%.
proj, line, sd = 1.4, 0.5, 0.9
normal_over = 1.0 - K.normal_cdf((line - proj) / sd)
poisson_over = K.poisson_over_under(proj, line)[0]
truthy(f"poisson {poisson_over:.3f} < normal {normal_over:.3f} (the bug)",
       poisson_over < normal_over)
truthy("normal overstated by ~9pp here",
       (normal_over - poisson_over) > 0.08)


# ── resolve_distribution dispatch ─────────────────────────
mlb_like = SimpleNamespace(DEFAULT_DIST="poisson", STAT_DIST={"Pitcher Outs": "normal"})
soccer_like = SimpleNamespace(DEFAULT_DIST="poisson")
nba_like = SimpleNamespace()  # declares neither -> legacy normal

truthy("MLB Hits -> poisson", K.resolve_distribution(mlb_like, "Hits") == "poisson")
truthy("MLB Pitcher Outs -> normal (override)",
       K.resolve_distribution(mlb_like, "Pitcher Outs") == "normal")
truthy("Soccer Shots -> poisson", K.resolve_distribution(soccer_like, "Shots") == "poisson")
truthy("NBA (no decl) -> normal", K.resolve_distribution(nba_like, "Points") == "normal")


# ── End-to-end: calculate_prop_edge on a Poisson plugin ───
# Build a minimal poisson plugin and a prop where the model should flag OVER.
plug = SimpleNamespace(
    SPORT_DISPLAY="MLB", SPORT="mlb",
    PROP_SD={"Hits": 0.9}, COMBOS={},
    DEFAULT_DIST="poisson", STAT_DIST={},
    MIN_EDGE=0.05, MAX_EDGE=0.15, KELLY_FRACTION=0.25, KELLY_CAP=0.02,
    TIER="Medium", CONFIDENCE="MEDIUM",
    compute_projection_adjustment=K.no_projection_adjustment,
    compute_prob_adjustment=K.no_prob_adjustment,
)
# Player averages 1.4 hits, line 0.5, DK prices OVER at -150 (implied 60%).
prop = {
    "stat_type": "Hits", "line": 0.5, "player": "Test Batter",
    "over_odds": -150, "under_odds": +130, "event": "AAA @ BBB",
}
stats = {"averages": {"Hits": 1.4}, "actual_sds": {"Hits": 1.0},
         "flat_averages": {"Hits": 1.3}, "games_sampled": 10}
res = K.calculate_prop_edge(plug, prop, stats)
truthy("e2e poisson pick returns a dict", isinstance(res, dict))
if isinstance(res, dict):
    truthy("e2e picks OVER", res["pick_side"] == "over")
    # model prob should be the Poisson 75.3%, not the normal ~81.6%
    approx("e2e model_prob ~ 75.3%", float(res["model"].rstrip("%")) / 100,
           1 - math.exp(-1.4), tol=0.005)
    # edge = 75.3% - 60% = 15.3% -> capped at MAX_EDGE 15%
    truthy("e2e edge capped at 15%", abs(res["edge"] - 15.0) < 0.01)

# Degenerate guard: projection 0 -> no pick (would be UNDER @ ~100% otherwise).
zero_stats = {"averages": {"Hits": 0.0}, "actual_sds": {"Hits": 0.0},
              "flat_averages": {"Hits": 0.0}, "games_sampled": 10}
truthy("e2e λ=0 returns None",
       K.calculate_prop_edge(plug, prop, zero_stats) is None)

# Coin-flip guard: λ just above the OVER-0.5 break-even (ln2≈0.693) should be
# suppressed when within the band. λ=0.72 -> over≈0.513, |0.513-0.5|<0.06.
cf_stats = {"averages": {"Hits": 0.72}, "actual_sds": {"Hits": 0.9},
            "flat_averages": {"Hits": 0.72}, "games_sampled": 10}
truthy("e2e coin-flip λ=0.72 returns None",
       K.calculate_prop_edge(plug, prop, cf_stats) is None)


# ── Report ────────────────────────────────────────────────
print(f"ran {checks} checks")
if failures:
    print(f"\nFAILED ({len(failures)}):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
