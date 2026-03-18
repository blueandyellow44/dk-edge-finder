#!/usr/bin/env python3
"""
DK Edge Finder — Mark bets as placed.
Updates data.json: sets pick status to PLACED, deducts bankroll, adds to bets array.
Called by GitHub Actions workflow with pick indices or "all".
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "data.json"
BANKROLL_JSON = REPO_ROOT / "bankroll.json"


def main():
    if len(sys.argv) < 2:
        print("Usage: place_bets.py <indices|all>")
        sys.exit(1)

    picks_arg = sys.argv[1].strip()

    # Load data
    data = json.loads(DATA_JSON.read_text())
    bankroll = json.loads(BANKROLL_JSON.read_text()) if BANKROLL_JSON.exists() else None

    picks = data.get("picks", [])
    if not picks:
        print("No picks to place.")
        sys.exit(0)

    # Determine which picks to place
    if picks_arg.lower() == "all":
        indices = list(range(len(picks)))
    else:
        indices = [int(x.strip()) for x in picks_arg.split(",") if x.strip().isdigit()]

    # Filter to only unplaced picks
    to_place = []
    for i in indices:
        if i < len(picks) and picks[i].get("status") not in ("PLACED", "WIN", "LOSS", "PUSH", "PENDING"):
            to_place.append(i)

    if not to_place:
        print("No new bets to place (already placed or invalid indices).")
        sys.exit(0)

    # Calculate total wager
    total_wager = 0
    for i in to_place:
        wager = float(picks[i]["bet"].replace("$", "").replace(",", ""))
        total_wager += wager

    # Get current available bankroll
    amt = data["bankroll"].get("available", data["bankroll"].get("current", 500))

    # Deduct from bankroll
    new_amt = round(amt - total_wager, 2)

    print(f"Placing {len(to_place)} bet(s), total wager: ${total_wager:.2f}")
    print(f"Bankroll: ${amt:.2f} → ${new_amt:.2f}")

    # Update each pick
    for i in to_place:
        p = picks[i]
        p["status"] = "PLACED"
        wager = float(p["bet"].replace("$", "").replace(",", ""))

        # Add to bets array if not already there
        already_in_bets = any(
            b["pick"] == p["pick"] and b["date"] == data["scan_date"]
            for b in data.get("bets", [])
        )
        if not already_in_bets:
            data.setdefault("bets", []).insert(0, {
                "date": data["scan_date"],
                "sport": p.get("sport", "NBA"),
                "event": p["event"],
                "pick": p["pick"],
                "odds": p["odds"],
                "decimal_odds": _american_to_decimal(p["odds"]),
                "edge": p.get("edge", ""),
                "wager": wager,
                "outcome": "pending"
            })

        print(f"  [{i}] {p['pick']} — ${wager:.2f} PLACED")

    # Update bankroll in data.json
    data["bankroll"]["available"] = new_amt
    pending_count = sum(1 for b in data.get("bets", []) if b.get("outcome") == "pending")
    pending_total = sum(b.get("wager", 0) for b in data.get("bets", []) if b.get("outcome") == "pending")
    data["bankroll"]["pending_count"] = pending_count
    data["bankroll"]["pending_total"] = round(pending_total, 2)
    data["bankroll"]["pending_label"] = f"{pending_count} bet(s) pending (${pending_total:.2f})"

    # Write data.json
    DATA_JSON.write_text(json.dumps(data, indent=2) + "\n")

    # Update bankroll.json
    if bankroll:
        bankroll["current_bankroll"] = new_amt
        bankroll["last_updated"] = data["scan_date"] + "T12:00:00-07:00"

        # Add to pending_bets in bankroll.json
        for i in to_place:
            p = picks[i]
            wager = float(p["bet"].replace("$", "").replace(",", ""))
            already = any(
                pb["pick"] == p["pick"] and pb["date"] == data["scan_date"]
                for pb in bankroll.get("pending_bets", [])
            )
            if not already:
                bankroll.setdefault("pending_bets", []).append({
                    "id": _make_id(p, data["scan_date"]),
                    "date": data["scan_date"],
                    "sport": p.get("sport", "nba").lower(),
                    "event": p["event"],
                    "market": p.get("market", "spread").lower(),
                    "pick": p["pick"],
                    "odds": int(p["odds"]) if p["odds"].lstrip("-").isdigit() else p["odds"],
                    "decimal_odds": _american_to_decimal(p["odds"]),
                    "model_prob": float(p.get("model", "0").replace("%", "")) / 100 if p.get("model") else 0,
                    "edge_pct": float(p.get("edge", 0)) if isinstance(p.get("edge"), (int, float)) else float(str(p.get("edge", "0")).replace("%", "")),
                    "tier": p.get("tier", "High"),
                    "bet_size": wager
                })

        bankroll["lifetime_bets"] = len(bankroll.get("resolved_bets", [])) + len(bankroll.get("pending_bets", []))
        BANKROLL_JSON.write_text(json.dumps(bankroll, indent=2) + "\n")

    print(f"\nDone. {len(to_place)} bet(s) placed. Bankroll: ${new_amt:.2f}")


def _american_to_decimal(odds_str: str) -> float:
    try:
        odds = int(odds_str)
        if odds < 0:
            return round(1 + 100 / abs(odds), 3)
        else:
            return round(1 + odds / 100, 3)
    except ValueError:
        return 1.909  # fallback


def _make_id(pick: dict, date: str) -> str:
    team = pick["pick"].split("+")[0].split("-")[0].strip().lower()[:3]
    market = pick.get("market", "spread").lower()[:6]
    return f"{team}-{market}-{date.replace('-', '')}"


if __name__ == "__main__":
    main()
