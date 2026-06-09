#!/usr/bin/env python3
"""Regression tests for the skellam_cdf low-mean fix (2026-06-09).

The bug: skellam_cdf had an early `break` on the first pmf < 1e-15. The loop
starts in the far-left tail (k_min ≈ mean - 6σ) where the pmf is ~0, so for low
means it broke on iteration 1 and returned 0 — turning skellam_sf into a
spurious 1.0. This hit low-scoring run lines (e.g. 2.7 vs 3.4 runs), not just
the unreached soccer-xG regime. The fix gates the break on having seen real
mass, keeping the break point identical where the old code worked.

These tests verify:
  1. The fixed skellam probabilities match an independent Poisson-convolution
     reference across a grid of means (small AND large).
  2. The specific buggy case is corrected and no longer returns 1.0.
  3. CDF is monotone and bounded.

Pure asserts, no pytest. Run:  python3 scripts/test_skellam.py
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


def approx(label, got, want, tol):
    global checks
    checks += 1
    if abs(got - want) > tol:
        failures.append(f"{label}: got {got!r}, want {want!r} (±{tol})")


# Independent reference: P(D <= k) for D = X1 - X2, X1~Pois(mu1), X2~Pois(mu2),
# by direct convolution. No Bessel, no early exit — the ground truth.
def conv_cdf(k_threshold, mu1, mu2, N=40):
    def plist(lam):
        out = [math.exp(-lam)]
        t = out[0]
        for i in range(1, N + 1):
            t *= lam / i
            out.append(t)
        return out
    p1, p2 = plist(mu1), plist(mu2)
    kt = math.floor(k_threshold)
    total = 0.0
    for x1 in range(N + 1):
        for x2 in range(N + 1):
            if x1 - x2 <= kt:
                total += p1[x1] * p2[x2]
    return total


# ── 1. Agreement with convolution across a grid of means ──
# Includes the low-mean regime where the old code returned 0.
for mu1 in [0.8, 1.5, 2.7, 3.4, 4.0, 4.6, 5.5]:
    for mu2 in [0.8, 1.5, 2.7, 3.4, 4.0, 4.6, 5.5]:
        for k in [-2, -1, 0, 1, 2]:
            got = S.skellam_cdf(k, mu1, mu2)
            want = conv_cdf(k, mu1, mu2)
            approx(f"cdf({k},{mu1},{mu2}) vs conv", got, want, tol=2e-3)


# ── 2. The specific buggy case is corrected ───────────────
# poisson_spread_probability(2.7, 3.4, 1.5) returned 1.0 before the fix.
fixed = S.poisson_spread_probability(2.7, 3.4, 1.5)
truthy(f"buggy case no longer 1.0 (got {fixed:.4f})", fixed < 0.99)
truthy("buggy case in a sane range", 0.4 < fixed < 0.8)

# skellam_cdf(-1, 2.7, 3.4) must be > 0 (was 0 pre-fix)
truthy("low-mean cdf(-1) > 0", S.skellam_cdf(-1, 2.7, 3.4) > 0.01)


# ── 3. CDF monotone and bounded ───────────────────────────
for mu1, mu2 in [(0.8, 2.0), (3.4, 2.7), (4.6, 4.0)]:
    prev = -1.0
    mono = True
    for k in range(-6, 7):
        c = S.skellam_cdf(k, mu1, mu2)
        if not (0.0 <= c <= 1.0):
            failures.append(f"cdf out of [0,1] @ k={k} ({mu1},{mu2}): {c}")
            checks += 1
        if c < prev - 1e-12:
            mono = False
        prev = c
    truthy(f"cdf monotone @ ({mu1},{mu2})", mono)


# ── 4. pmf clamp: no term exceeds 1, none non-finite ──────
clamp_ok = True
for k in range(-50, 51):
    p = S.skellam_pmf(k, 0.5, 0.5)
    if not math.isfinite(p) or p > 1.0 or p < 0.0:
        clamp_ok = False
truthy("pmf clamped to [0,1], finite, even in unstable tail", clamp_ok)


print(f"ran {checks} checks")
if failures:
    print(f"\nFAILED ({len(failures)}):")
    for f in failures[:20]:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
