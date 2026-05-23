#!/usr/bin/env python3
"""Fit per-(sport, market) Platt calibrators against DK Edge pick_history.json.

Run:

    python3 scripts/fit_calibration.py

Prints fitted coefficients for every (sport, market) bucket that meets the
min-sample threshold, in a form ready to paste into scan_edges.py's
PROB_CALIBRATION dict.

**The cover-level Platt fit Max ran out of `predictions-bot-v2` on 2026-05-09
ate post-OLD-LINEAR data and treated it as raw, learning a downward
correction that effectively undid the OLD positive bias plus a tail
squash. When the resulting coefficients were then applied to actually-raw
model output at scan time, MLB/NBA spread probabilities dropped ~10pp and
game picks evaporated from the slate. This fitter exists to refit
correctly, against true raw probabilities recovered by inverting the OLD
linear cal where it was active.**

History semantics (matters for which records have raw vs calibrated model):
- Before 2026-05-04: OLD_LINEAR was not yet deployed; `pick.model` is raw.
- 2026-05-04 .. 2026-05-10: OLD_LINEAR active for (mlb, spread) and
  (nba, spread) only. `pick.model` for those buckets is calibrated and
  must be inverted. Everything else (NHL, totals, soccer) was identity
  even then.
- 2026-05-11 onward: NEW_PLATT (the buggy fit being replaced) was active
  for 5 keys. This fitter SKIPS those records; we refit on the pre-bug
  sample only. Once the corrected coefficients ship and a week of fresh
  history accumulates, future refits can include the post-fix data.

Pure Python, no numpy / scipy. ~120 LOC. Newton-Raphson on the Bernoulli
log-posterior under an isotropic Gaussian prior centered at identity
(a=1, b=0) with precision 10. Identical math to the
predictions-bot-v2 fitter; difference is the inversion step on input.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PICK_HISTORY = REPO_ROOT / "pick_history.json"

# OLD per-sport linear cal that was active 2026-05-04 through 2026-05-10
# for spreads only. Inversion: r = (c - b) / a.
OLD_LINEAR = {
    "mlb": {"a": 0.396, "b": 0.347},
    "nba": {"a": 0.258, "b": 0.300},
}
OLD_LINEAR_DEPLOY_DATE = "2026-05-04"   # first scan_date with OLD_LINEAR active
NEW_PLATT_DEPLOY_DATE = "2026-05-11"    # first scan_date with the buggy fit; we skip these

PRIOR_STRENGTH = 10.0          # L2 prior precision, centered at (a=1, b=0)
MIN_SAMPLES = 30
MAX_NEWTON_ITERS = 200
NEWTON_TOL = 1e-9
LOGIT_CLAMP_LOW = 1e-6
LOGIT_CLAMP_HIGH = 1 - 1e-6


def parse_pct(s):
    """Parse '69.2%' or 0.692 -> 0.692. Returns None on garbage."""
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str):
        s = s.strip().rstrip("%")
        try:
            v = float(s)
            return v / 100.0 if v > 1 else v
        except ValueError:
            return None
    return None


def recover_raw_prob(pick):
    """Return the raw model probability for a pick, or None if unrecoverable."""
    model = parse_pct(pick.get("model"))
    if model is None or not (0 < model < 1):
        return None
    sport = pick.get("sport", "").lower()
    market = pick.get("market", "").lower()
    scan_date = pick.get("scan_date", "")

    if scan_date >= NEW_PLATT_DEPLOY_DATE:
        return None  # buggy regime, skipped

    needs_inversion = (
        scan_date >= OLD_LINEAR_DEPLOY_DATE
        and market == "spread"
        and sport in OLD_LINEAR
    )
    if not needs_inversion:
        return model  # `model` is already raw

    coeffs = OLD_LINEAR[sport]
    raw = (model - coeffs["b"]) / coeffs["a"]
    if not (0.0 < raw < 1.0):
        return None  # outside the OLD_LINEAR image — likely a stale or off-regime row
    return raw


def fit_platt(samples):
    """Newton-Raphson MAP fit. samples is a list of (raw_prob, outcome)
    pairs. Returns (a, b, brier_identity, brier_fitted, n)."""
    a, b = 1.0, 0.0
    z = [math.log(max(min(r, LOGIT_CLAMP_HIGH), LOGIT_CLAMP_LOW)
                  / (1.0 - max(min(r, LOGIT_CLAMP_HIGH), LOGIT_CLAMP_LOW)))
         for r, _ in samples]
    y = [float(outcome) for _, outcome in samples]
    raws = [r for r, _ in samples]
    n = len(samples)

    for _ in range(MAX_NEWTON_ITERS):
        ga = -PRIOR_STRENGTH * (a - 1.0)
        gb = -PRIOR_STRENGTH * b
        haa = -PRIOR_STRENGTH
        hab = 0.0
        hbb = -PRIOR_STRENGTH
        for i in range(n):
            s = a * z[i] + b
            # numerically stable sigmoid
            if s >= 0:
                p = 1.0 / (1.0 + math.exp(-s))
            else:
                e = math.exp(s)
                p = e / (1.0 + e)
            w = p * (1.0 - p)
            ga += z[i] * (y[i] - p)
            gb += (y[i] - p)
            haa -= z[i] * z[i] * w
            hab -= z[i] * w
            hbb -= w
        det = haa * hbb - hab * hab
        if abs(det) < 1e-18:
            break
        # Newton step: [a, b] -= H^{-1} g, with H = [[haa, hab], [hab, hbb]]
        inv_haa = hbb / det
        inv_hab = -hab / det
        inv_hbb = haa / det
        step_a = inv_haa * ga + inv_hab * gb
        step_b = inv_hab * ga + inv_hbb * gb
        a -= step_a
        b -= step_b
        if abs(step_a) < NEWTON_TOL and abs(step_b) < NEWTON_TOL:
            break

    def cal(r):
        zr = math.log(max(min(r, LOGIT_CLAMP_HIGH), LOGIT_CLAMP_LOW)
                      / (1.0 - max(min(r, LOGIT_CLAMP_HIGH), LOGIT_CLAMP_LOW)))
        s = a * zr + b
        if s >= 0:
            return 1.0 / (1.0 + math.exp(-s))
        e = math.exp(s)
        return e / (1.0 + e)

    brier_id = sum((raws[i] - y[i]) ** 2 for i in range(n)) / n
    brier_fit = sum((cal(raws[i]) - y[i]) ** 2 for i in range(n)) / n
    return a, b, brier_id, brier_fit, n


def main():
    history = json.loads(PICK_HISTORY.read_text())
    buckets = defaultdict(list)
    skipped_unresolved = 0
    skipped_no_raw = 0
    skipped_new_regime = 0
    for pick in history:
        outcome = pick.get("outcome", "").lower()
        if outcome in ("win", "won"):
            y = 1
        elif outcome in ("loss", "lost"):
            y = 0
        else:
            skipped_unresolved += 1
            continue
        if pick.get("scan_date", "") >= NEW_PLATT_DEPLOY_DATE:
            skipped_new_regime += 1
            continue
        raw = recover_raw_prob(pick)
        if raw is None:
            skipped_no_raw += 1
            continue
        key = (pick.get("sport", "").lower(), pick.get("market", "").lower())
        buckets[key].append((raw, y))

    print(f"history rows: {len(history)}")
    print(f"  skipped unresolved: {skipped_unresolved}")
    print(f"  skipped post-{NEW_PLATT_DEPLOY_DATE} (buggy regime): {skipped_new_regime}")
    print(f"  skipped no recoverable raw prob: {skipped_no_raw}")
    print(f"  retained: {sum(len(v) for v in buckets.values())}")
    print()

    fits = {}
    for key in sorted(buckets, key=lambda k: -len(buckets[k])):
        n = len(buckets[key])
        if n < MIN_SAMPLES:
            print(f"  skip {key}: n={n} < {MIN_SAMPLES}")
            continue
        a, b, brier_id, brier_fit, _ = fit_platt(buckets[key])
        fits[key] = (a, b)
        print(f"  {key}: n={n}  a={a:+.4f}  b={b:+.4f}  "
              f"Brier {brier_id:.4f} -> {brier_fit:.4f}")

    print()
    print("Paste into scan_edges.py PROB_CALIBRATION:")
    print("PROB_CALIBRATION = {")
    for key in sorted(fits):
        a, b = fits[key]
        sport, market = key
        # right-align (sport, market) tuple text for readability
        tup = f'("{sport}", "{market}")'
        print(f"    {tup:24s}: {{\"a\": {a:.6f}, \"b\": {b:+.6f}}},")
    print("}")


if __name__ == "__main__":
    main()
