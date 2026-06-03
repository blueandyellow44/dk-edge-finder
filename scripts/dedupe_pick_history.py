#!/usr/bin/env python3
"""One-off: collapse duplicate rows in pick_history.json.

Background: until the upsert fix in scan_edges.py (Step 8), every scan
blind-appended to pick_history.json. The game-scan cron runs 4x/day, so a pick
that persisted across the day's scans was logged up to 6x. ~55% of rows were
same-day duplicates, which silently over-weighted those games in the calibration
fit and inflated the paper-trading win/loss counts shown on the dashboard.

This script keeps ONE row per (scan_date, event, pick, market):
  - prefer a resolved row (win/loss/push) over a pending one,
  - among resolved rows prefer the one carrying a final_score,
  - otherwise keep the last occurrence (latest scan = most-informed odds).

It snapshots the file first and prints before/after counts plus the recomputed
W/L so the dashboard-number change is explicit. Run once:

    python3 scripts/dedupe_pick_history.py            # writes the deduped file
    python3 scripts/dedupe_pick_history.py --dry-run   # report only, no write
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_JSON = REPO_ROOT / "pick_history.json"
BACKUP_JSON = REPO_ROOT / "pick_history.json.prededuped.bak"


def _key(r: dict) -> tuple:
    return (
        str(r.get("scan_date", ""))[:10],
        r.get("event", ""),
        r.get("pick", ""),
        r.get("market", ""),
    )


def _better(candidate: dict, incumbent: dict) -> bool:
    """Is `candidate` a better representative of the group than `incumbent`?"""
    resolved = {"win", "loss", "push"}
    c_res = candidate.get("outcome") in resolved
    i_res = incumbent.get("outcome") in resolved
    if c_res != i_res:
        return c_res  # resolved beats pending
    if c_res and i_res:
        # both resolved: prefer one with a final_score recorded
        c_fs = bool(candidate.get("final_score"))
        i_fs = bool(incumbent.get("final_score"))
        if c_fs != i_fs:
            return c_fs
    return True  # same tier: later occurrence wins (most-informed scan)


def _wl(rows: list) -> str:
    c = collections.Counter(r.get("outcome") for r in rows)
    return f"{c.get('win', 0)}W-{c.get('loss', 0)}L, {c.get('push', 0)}P, {c.get('pending', 0)} pending"


def main(dry_run: bool = False) -> None:
    history = json.loads(HISTORY_JSON.read_text())
    before = len(history)
    print(f"pick_history.json: {before} rows  ({_wl(history)})")

    # Walk in order; keep the best representative per key, preserving first-seen order.
    best: dict[tuple, dict] = {}
    order: list[tuple] = []
    for r in history:
        k = _key(r)
        if k not in best:
            best[k] = r
            order.append(k)
        elif _better(r, best[k]):
            best[k] = r

    deduped = [best[k] for k in order]
    after = len(deduped)
    removed = before - after
    print(f"deduped:           {after} rows  ({_wl(deduped)})")
    print(f"removed {removed} duplicate row(s) ({removed / before * 100:.1f}% of file)")

    if dry_run:
        print("\n--dry-run: no files written.")
        return

    BACKUP_JSON.write_text(json.dumps(history, indent=2) + "\n")
    HISTORY_JSON.write_text(json.dumps(deduped, indent=2) + "\n")
    print(f"\nSnapshot written: {BACKUP_JSON.name}")
    print(f"Deduped file written: {HISTORY_JSON.name}")
    print("Rollback: cp pick_history.json.prededuped.bak pick_history.json")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
