#!/usr/bin/env python3
"""
DK Edge Finder — Pick History Analyzer
Reads pick_history.json and produces accuracy breakdowns by:
- Sport, market type, tier, confidence
- Edge buckets (3-5%, 5-8%, 8-12%, 12%+)
- Game edges vs prop edges
- Z-score / signal strength (from notes)
- Day of week
- Paper P/L

Run: python analyze_history.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_JSON = REPO_ROOT / "pick_history.json"


def load_history() -> list[dict]:
    if not HISTORY_JSON.exists():
        print("pick_history.json not found.")
        sys.exit(1)
    try:
        data = json.loads(HISTORY_JSON.read_text())
    except json.JSONDecodeError:
        print("pick_history.json is corrupted.")
        sys.exit(1)
    return data


def bucket_edge(edge: float) -> str:
    if edge < 5:
        return "3-5%"
    elif edge < 8:
        return "5-8%"
    elif edge < 12:
        return "8-12%"
    else:
        return "12%+"


def analyze(history: list[dict]):
    resolved = [h for h in history if h.get("outcome") in ("win", "loss", "push")]
    pending = [h for h in history if h.get("outcome") == "pending"]

    if not resolved:
        print(f"No resolved picks yet. {len(pending)} still pending.")
        return

    print(f"{'='*60}")
    print(f"DK EDGE FINDER — PAPER TRADING ANALYSIS")
    print(f"{'='*60}")
    print(f"Total tracked: {len(history)}  |  Resolved: {len(resolved)}  |  Pending: {len(pending)}")
    print()

    # Overall record
    wins = sum(1 for h in resolved if h["outcome"] == "win")
    losses = sum(1 for h in resolved if h["outcome"] == "loss")
    pushes = sum(1 for h in resolved if h["outcome"] == "push")
    total_pnl = sum(h.get("pnl_if_bet", 0) for h in resolved)
    hit_rate = wins / len(resolved) * 100 if resolved else 0

    print(f"OVERALL: {wins}W-{losses}L-{pushes}P  ({hit_rate:.1f}% hit rate)")
    print(f"Paper P/L: ${total_pnl:+.2f} (on $10/bet standardized)")
    print()

    # Breakdown helper
    def print_breakdown(label: str, groups: dict):
        print(f"--- {label} ---")
        for key in sorted(groups.keys()):
            picks = groups[key]
            w = sum(1 for p in picks if p["outcome"] == "win")
            l = sum(1 for p in picks if p["outcome"] == "loss")
            pu = sum(1 for p in picks if p["outcome"] == "push")
            pnl = sum(p.get("pnl_if_bet", 0) for p in picks)
            n = len(picks)
            hr = w / n * 100 if n > 0 else 0
            print(f"  {key:20s}  {w}W-{l}L-{pu}P  ({hr:5.1f}%)  P/L: ${pnl:+.2f}  (n={n})")
        print()

    # By type (game vs prop)
    by_type = defaultdict(list)
    for h in resolved:
        by_type[h.get("type", "unknown")].append(h)
    print_breakdown("BY TYPE", by_type)

    # By sport
    by_sport = defaultdict(list)
    for h in resolved:
        by_sport[h.get("sport", "?")].append(h)
    print_breakdown("BY SPORT", by_sport)

    # By confidence
    by_conf = defaultdict(list)
    for h in resolved:
        by_conf[h.get("confidence", "?")].append(h)
    print_breakdown("BY CONFIDENCE", by_conf)

    # By edge bucket
    by_edge = defaultdict(list)
    for h in resolved:
        by_edge[bucket_edge(h.get("edge", 0))].append(h)
    print_breakdown("BY EDGE BUCKET", by_edge)

    # By market
    by_market = defaultdict(list)
    for h in resolved:
        by_market[h.get("market", "?")].append(h)
    print_breakdown("BY MARKET", by_market)

    # By date
    by_date = defaultdict(list)
    for h in resolved:
        by_date[h.get("scan_date", "?")].append(h)
    print_breakdown("BY DATE", by_date)

    # Recommendations
    print(f"{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")

    # Find weakest categories
    for label, groups in [("type", by_type), ("sport", by_sport), ("confidence", by_conf), ("edge bucket", by_edge)]:
        for key, picks in groups.items():
            w = sum(1 for p in picks if p["outcome"] == "win")
            n = len(picks)
            hr = w / n * 100 if n > 0 else 0
            if n >= 3 and hr < 40:
                print(f"  ⚠ {label}={key}: {hr:.0f}% hit rate over {n} picks — consider tightening filters")
            elif n >= 3 and hr > 70:
                print(f"  ✓ {label}={key}: {hr:.0f}% hit rate over {n} picks — strong performer")

    print()


if __name__ == "__main__":
    history = load_history()
    analyze(history)
