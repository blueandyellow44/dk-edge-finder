#!/usr/bin/env python3
"""Proxy backtest: normal-CDF vs Poisson prop model on resolved history.

WHY THIS IS A PROXY, NOT A REAL BACKTEST: there are zero resolved MLB or soccer
prop records in pick_history (the target sports). All resolved props are NBA and
NHL, and the structured `line` field is null on every one — projection and line
survive only inside the free-text `notes` string. So this harness:

  1. Parses projection / line / sigma-separation out of `notes` (old normal-path
     format: "averages X <stat> (last Ng), line is L: D over with Sσ separation").
  2. Recovers the SD the old model used: sd = |proj - line| / sigma.
  3. Reconstructs whether the over actually occurred from (pick_side, outcome).
  4. Recomputes P(over) under BOTH normal and Poisson and scores Brier vs reality.

Caveat reported inline: NBA prop lines are high-count (points 24.5, etc.) where
Poisson ~ normal, so the NBA rows show little separation. NHL props are the
low-count 0.5/1.5 lines where the distribution actually matters — but only ~27
resolved exist, so the signal is real but underpowered. This is evidence, not
proof. The go-live gate for MLB/soccer is the analytic tests plus a forward
paper window, per the Phase 1 scope.

Run:

    python3 scripts/backtest_prop_model.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import props_kernel as K

REPO_ROOT = Path(__file__).resolve().parent.parent
PICK_HISTORY = REPO_ROOT / "pick_history.json"

# "averages 1.4 Points (last 10g), line is 0.5: 0.9 over with 1.0σ separation."
NOTE_RE = re.compile(
    r"averages\s+([\d.]+)\s+.*?line is\s+([\d.]+).*?([\d.]+)σ separation",
    re.IGNORECASE | re.DOTALL,
)


def resolved(outcome) -> bool:
    return str(outcome).lower() in ("win", "won", "loss", "lost")


def is_win(outcome) -> bool:
    return str(outcome).lower() in ("win", "won")


def parse_note(note: str):
    """Return (projection, line, sd) or None if unparseable."""
    if not note:
        return None
    m = NOTE_RE.search(note)
    if not m:
        return None
    proj, line, sigma = float(m.group(1)), float(m.group(2)), float(m.group(3))
    if sigma <= 0 or line <= 0:
        return None
    sd = abs(proj - line) / sigma
    if sd <= 0:
        return None
    return proj, line, sd


def over_occurred(pick: str, outcome) -> int | None:
    """Reconstruct the binary 'the over hit' from the picked side + result."""
    p = pick.lower()
    side = "over" if "over" in p else ("under" if "under" in p else None)
    if side is None:
        return None
    win = is_win(outcome)
    if side == "over":
        return 1 if win else 0
    return 0 if win else 1  # under win => over did NOT occur


def main() -> None:
    history = json.loads(PICK_HISTORY.read_text())
    by_sport = defaultdict(lambda: {"n": 0, "bn": 0.0, "bp": 0.0,
                                    "rows": [], "unparsed": 0})

    for p in history:
        if p.get("market", "").lower() != "player prop":
            continue
        if not resolved(p.get("outcome")):
            continue
        sport = p.get("sport", "").lower()
        parsed = parse_note(p.get("notes", ""))
        occ = over_occurred(p.get("pick", ""), p.get("outcome"))
        bucket = by_sport[sport]
        if parsed is None or occ is None:
            bucket["unparsed"] += 1
            continue
        proj, line, sd = parsed
        p_norm = 1.0 - K.normal_cdf((line - proj) / sd)
        p_pois = K.poisson_over_under(proj, line)[0]
        bucket["n"] += 1
        bucket["bn"] += (p_norm - occ) ** 2
        bucket["bp"] += (p_pois - occ) ** 2
        bucket["rows"].append((p_norm, p_pois, occ))

    print("Proxy backtest — normal vs Poisson P(over), Brier (lower=better)\n")
    print(f"{'sport':6} {'n':>4} {'unparsed':>9} {'Brier_normal':>13} "
          f"{'Brier_poisson':>14} {'winner':>8}")
    tot_n = 0
    tot_bn = 0.0
    tot_bp = 0.0
    for sport in sorted(by_sport, key=lambda s: -by_sport[s]["n"]):
        b = by_sport[sport]
        if b["n"] == 0:
            print(f"{sport:6} {0:>4} {b['unparsed']:>9} {'—':>13} {'—':>14} {'—':>8}")
            continue
        bn, bp = b["bn"] / b["n"], b["bp"] / b["n"]
        winner = "poisson" if bp < bn else ("normal" if bn < bp else "tie")
        print(f"{sport:6} {b['n']:>4} {b['unparsed']:>9} {bn:>13.4f} "
              f"{bp:>14.4f} {winner:>8}")
        tot_n += b["n"]
        tot_bn += b["bn"]
        tot_bp += b["bp"]

    print("-" * 56)
    if tot_n:
        print(f"{'ALL':6} {tot_n:>4} {'':>9} {tot_bn/tot_n:>13.4f} "
              f"{tot_bp/tot_n:>14.4f} "
              f"{'poisson' if tot_bp < tot_bn else 'normal':>8}")

    # Reliability table on the low-count sport (NHL) where it matters.
    nhl = by_sport.get("nhl", {}).get("rows", [])
    if nhl:
        print("\nNHL reliability (the low-line sport that drove the rebuild):")
        print(f"  mean predicted over — normal {sum(r[0] for r in nhl)/len(nhl):.3f}, "
              f"poisson {sum(r[1] for r in nhl)/len(nhl):.3f}, "
              f"actual over-rate {sum(r[2] for r in nhl)/len(nhl):.3f}")
        print("  (closer mean-predicted to actual = better-calibrated central tendency)")

    print("\nNOTE: NBA lines are high-count (Poisson≈normal by design); NHL is the "
          "\nlow-count signal but underpowered (n≈27). MLB/soccer have ZERO resolved "
          "\nprops — this is proxy evidence, not a go-live proof. Gate on the analytic "
          "\ntests + forward paper window.")


if __name__ == "__main__":
    main()
