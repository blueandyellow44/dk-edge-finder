#!/usr/bin/env python3
"""One-shot backfill: KV placements -> data.json.bets[] + bankroll.json.

The SPA's "Mark as placed" button writes to Cloudflare KV
(state:max.sheahan@gmail.com:<scan_date>). resolve_bets.py only sees
data.json.bets[] / bankroll.json.pending_bets[]. So placements have not
flowed back into the canonical bet log since the SPA shipped, leaving the
Activity chart and lifetime stats stuck at April 8.

This script bridges the gap once. It takes the dumped KV state records
(see __main__) and writes new entries into data.json.bets[]. Outcomes
come from pick_history.json. The Bundesliga 5/3 OVER 2.5 is hardcoded
because the cron resolver missed it (resolve_bets.py status check is
STATUS_FINAL only, and ESPN tags soccer with STATUS_FULL_TIME).

Idempotent on (date, pick) so re-running is safe.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data.json"
BANKROLL = REPO / "bankroll.json"
HISTORY = REPO / "pick_history.json"

# Max's stake on the 5/3 + 5/4 batches, per his own statement
# (rounded Kelly equivalent; matches session 13's Math.ceil(pick.wager) rule).
WAGER = 14.0

# Placements pulled from production KV via:
#   npx wrangler kv key get --binding EDGE_STATE --remote \
#     "state:max.sheahan@gmail.com:2026-05-03"
# Each tuple: (scan_date, pick, event, sport).
# Only action='placed' rows are here; skipped rows are dropped at the
# Mark-as-placed UI level and should not appear as bets.
KV_PLACEMENTS = [
    ("2026-05-03", "Colorado Rockies +1.5", "Atlanta Braves @ Colorado Rockies", "MLB"),
    ("2026-05-03", "Los Angeles Angels +1.5", "New York Mets @ Los Angeles Angels", "MLB"),
    ("2026-05-03", "OVER 2.5", "VfL Wolfsburg @ SC Freiburg", "BUNDESLIGA"),
    ("2026-05-03", "Athletics +1.5", "Cleveland Guardians @ Athletics", "MLB"),
    ("2026-05-03", "Pittsburgh Pirates +1.5", "Cincinnati Reds @ Pittsburgh Pirates", "MLB"),
    ("2026-05-03", "Miami Marlins +1.5", "Philadelphia Phillies @ Miami Marlins", "MLB"),
    ("2026-05-04", "Milwaukee Brewers -1.5", "Milwaukee Brewers @ St. Louis Cardinals", "MLB"),
    ("2026-05-04", "Toronto Blue Jays -1.5", "Toronto Blue Jays @ Tampa Bay Rays", "MLB"),
    ("2026-05-04", "Los Angeles Angels -1.5", "Chicago White Sox @ Los Angeles Angels", "MLB"),
    ("2026-05-04", "Cleveland Guardians -1.5", "Cleveland Guardians @ Kansas City Royals", "MLB"),
    ("2026-05-04", "Philadelphia Phillies -1.5", "Philadelphia Phillies @ Miami Marlins", "MLB"),
    ("2026-05-04", "Houston Astros +1.5", "Los Angeles Dodgers @ Houston Astros", "MLB"),
    ("2026-05-04", "Seattle Mariners -1.5", "Atlanta Braves @ Seattle Mariners", "MLB"),
]

# Manually known: cron resolver missed this because of the soccer status bug.
# Wolfsburg 1, Freiburg 1 -> total 2 -> OVER 2.5 = LOSS.
MANUAL_RESOLUTIONS = {
    ("2026-05-03", "OVER 2.5"): {
        "outcome": "loss",
        "final_score": "WOB 1, SCF 1",
    },
}


def odds_to_int(s) -> int:
    if isinstance(s, int):
        return s
    return int(str(s).lstrip("+"))


def decimal_odds(american: int) -> float:
    if american > 0:
        return 1 + american / 100.0
    return 1 + 100.0 / abs(american)


def compute_pnl(outcome: str, wager: float, american_odds: int) -> float:
    if outcome == "win":
        return round(wager * (decimal_odds(american_odds) - 1), 2)
    if outcome == "loss":
        return round(-wager, 2)
    if outcome == "push":
        return 0.0
    return 0.0  # pending


def main():
    data = json.loads(DATA.read_text())
    bankroll = json.loads(BANKROLL.read_text())
    history = json.loads(HISTORY.read_text())

    bets = data.setdefault("bets", [])
    existing = {(b.get("date", ""), b.get("pick", "")) for b in bets}

    added = 0
    bundesliga_resolved_in_history = False

    for scan_date, pick, event, sport in KV_PLACEMENTS:
        if (scan_date, pick) in existing:
            print(f"skip {scan_date} {pick} (already in data.json.bets)")
            continue

        # Find pick_history entry for outcome + odds
        ph_match = next(
            (h for h in history
             if h.get("scan_date") == scan_date
             and h.get("pick", "").strip() == pick.strip()
             and h.get("event", "").strip() == event.strip()),
            None,
        )
        if not ph_match:
            print(f"WARN {scan_date} {pick}: not in pick_history; skipping")
            continue

        american = odds_to_int(ph_match.get("odds", -110))
        ph_outcome = ph_match.get("outcome", "pending")

        manual = MANUAL_RESOLUTIONS.get((scan_date, pick))
        if manual:
            outcome = manual["outcome"]
            final_score = manual["final_score"]
            # Also patch pick_history.json so the next cron tick agrees
            if ph_outcome == "pending":
                ph_match["outcome"] = outcome
                ph_match["final_score"] = final_score
                ph_match["pnl_if_bet"] = compute_pnl(outcome, 10.0, american)
                bundesliga_resolved_in_history = True
        else:
            outcome = ph_outcome
            final_score = ph_match.get("final_score", "")

        pnl = compute_pnl(outcome, WAGER, american)

        bet = {
            "date": scan_date,
            "pick": pick,
            "event": event,
            "sport": sport,
            "wager": WAGER,
            "odds": american,
            "outcome": outcome,
            "pnl": pnl,
            "final_score": final_score,
        }
        bets.append(bet)
        existing.add((scan_date, pick))
        added += 1
        print(f"+ {scan_date} {pick}: {outcome.upper()} pnl=${pnl:+.2f}")

    if added == 0:
        print("\nNo new placements to backfill. Already in sync.")
        return

    # Recompute lifetime stats from data.json.bets[] (single source of truth).
    resolved = [b for b in bets if b.get("outcome") in ("win", "loss", "push")]
    pending = [b for b in bets if b.get("outcome") == "pending"]
    wins = sum(1 for b in resolved if b.get("outcome") == "win")
    losses = sum(1 for b in resolved if b.get("outcome") == "loss")
    pushes = sum(1 for b in resolved if b.get("outcome") == "push")
    total_pnl = round(sum(b.get("pnl", 0) for b in resolved), 2)
    pending_locked = round(sum(b.get("wager", 0) for b in pending), 2)
    total_wagered = round(sum(b.get("wager", 0) for b in resolved), 2)
    starting = data.get("bankroll", {}).get("starting", 500.0)
    available = round(starting + total_pnl - pending_locked, 2)

    data["bankroll"]["available"] = available
    data["bankroll"]["profit"] = total_pnl
    data["bankroll"]["record"] = {"wins": wins, "losses": losses, "pushes": pushes}
    data["bankroll"]["pending_count"] = len(pending)
    data["bankroll"]["pending_total"] = pending_locked
    data["bankroll"]["pending_label"] = (
        f"{len(pending)} bet(s) pending (${pending_locked:.2f})" if pending
        else "No unsettled bets"
    )

    DATA.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nWrote data.json: {wins}W-{losses}L-{pushes}P resolved, "
          f"{len(pending)} pending, profit ${total_pnl:+.2f}, "
          f"available ${available:.2f}")

    # Sync bankroll.json lifetime stats with data.json.bets[].
    bankroll["lifetime_wins"] = wins
    bankroll["lifetime_losses"] = losses
    bankroll["lifetime_pushes"] = pushes
    bankroll["lifetime_bets"] = wins + losses + pushes
    bankroll["lifetime_profit"] = total_pnl
    bankroll["current_bankroll"] = round(starting + total_pnl, 2)
    bankroll["roi_pct"] = round(
        (total_pnl / total_wagered * 100) if total_wagered > 0 else 0, 2
    )
    bankroll["last_updated"] = datetime.now(timezone.utc).isoformat()
    BANKROLL.write_text(json.dumps(bankroll, indent=2) + "\n")
    print(f"Wrote bankroll.json: lifetime {wins}W-{losses}L-{pushes}P, "
          f"profit ${total_pnl:+.2f}, current_bankroll "
          f"${bankroll['current_bankroll']:.2f}")

    if bundesliga_resolved_in_history:
        HISTORY.write_text(json.dumps(history, indent=2) + "\n")
        print("Wrote pick_history.json: Bundesliga 5/3 OVER 2.5 -> loss")


if __name__ == "__main__":
    main()
