#!/usr/bin/env python3
"""Analytic unit tests for the soccer 3-way moneyline model (Phase 1, 2026-06-09).

The correctness gate for the Skellam-based home/draw/away probabilities. Pure
asserts, no data or network, no pytest dependency (matches the house style).

Run:  python3 scripts/test_soccer_moneyline.py
"""

from __future__ import annotations

import math
import sys

import skellam as S

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


# ── Probabilities sum to 1 across a grid ──────────────────
for hx in [0.5, 1.0, 1.3, 1.8, 2.5, 3.0]:
    for ax in [0.5, 1.0, 1.3, 1.8, 2.5]:
        ph, pd, pa = S.three_way_probs(hx, ax)
        approx(f"sum=1 @ ({hx},{ax})", ph + pd + pa, 1.0, tol=1e-9)
        truthy(f"all in [0,1] @ ({hx},{ax})", 0 <= ph <= 1 and 0 <= pd <= 1 and 0 <= pa <= 1)


# ── Favorite (higher xG) gets the highest win prob ────────
ph, pd, pa = S.three_way_probs(2.0, 0.8)   # home heavily favored
truthy("home fav: p_home highest", ph > pa and ph > pd)
ph, pd, pa = S.three_way_probs(0.7, 2.1)   # away heavily favored
truthy("away fav: p_away highest", pa > ph and pa > pd)


# ── Symmetry: equal xG => equal home/away win probs ───────
ph, pd, pa = S.three_way_probs(1.4, 1.4)
approx("symmetry p_home==p_away @ equal xg", ph, pa, tol=1e-7)  # Bessel approx noise


# ── Draw base rate: equal modest xG lands ~25-28% ─────────
_, pd13, _ = S.three_way_probs(1.3, 1.3)
truthy(f"draw@(1.3,1.3)={pd13:.3f} in [0.24,0.30]", 0.24 <= pd13 <= 0.30)

# Draw probability falls as equal xG rises (more goals => fewer draws)
_, pd_lo, _ = S.three_way_probs(0.8, 0.8)
_, pd_hi, _ = S.three_way_probs(2.6, 2.6)
truthy("draw decreases as equal xg rises", pd_lo > pd13 > pd_hi)


# ── Monotonicity: p_home rises as home_xg rises (away fixed)
prev = -1.0
mono = True
for hx in [0.6, 1.0, 1.5, 2.0, 2.8, 3.5]:
    ph, _, _ = S.three_way_probs(hx, 1.2)
    if ph <= prev:
        mono = False
    prev = ph
truthy("p_home monotincreasing in home_xg", mono)


# ── Cross-method agreement: convolution vs the Bessel-Skellam path ────
# three_way_probs uses direct Poisson convolution; the run-line code uses the
# Bessel-based skellam_cdf. For means in the Bessel-stable regime the two should
# agree to ~1e-6 (the Bessel approximation is the less precise of the two, so we
# don't demand machine precision). This guards the mapping/convention.
hx, ax = 1.7, 1.1
ph, pd, pa = S.three_way_probs(hx, ax)
raw_home = S.skellam_cdf(-1, ax, hx)   # P(D<=-1), D=away-home -> home wins
raw_draw = S.skellam_pmf(0, ax, hx)    # P(D=0)  -> draw
raw_away = S.skellam_sf(0, ax, hx)     # P(D>0)  -> away wins
rtot = raw_home + raw_draw + raw_away
approx("convolution agrees with Bessel p_home", ph, raw_home / rtot, tol=1e-6)
approx("convolution agrees with Bessel p_draw", pd, raw_draw / rtot, tol=1e-6)
approx("convolution agrees with Bessel p_away", pa, raw_away / rtot, tol=1e-6)


# ── Degenerate guard ──────────────────────────────────────
for bad in [(0.0, 1.0), (1.0, 0.0), (-1.0, 1.0)]:
    raised = False
    try:
        S.three_way_probs(*bad)
    except ValueError:
        raised = True
    truthy(f"raises on xg={bad}", raised)


# ── Report ────────────────────────────────────────────────
print(f"ran {checks} checks")
if failures:
    print(f"\nFAILED ({len(failures)}):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
