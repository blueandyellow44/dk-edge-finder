#!/usr/bin/env python3
"""
DK Edge Finder — Bet Resolution Script
Runs via GitHub Actions. Checks final scores, resolves pending bets,
updates bankroll and data.json.
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "data.json"
BANKROLL_JSON = REPO_ROOT / "bankroll.json"

# ── ESPN Scoreboard API (free, no key needed) ──────────────────────────
def fetch_nba_scores(date_str: str) -> list[dict]:
    """Fetch NBA scores from ESPN API for a given date (YYYYMMDD)."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        games = []
        for event in data.get("events", []):
            competition = event["competitions"][0]
            status = competition["status"]["type"]["name"]  # STATUS_FINAL, STATUS_IN_PROGRESS, etc.
            teams = {}
            for competitor in competition["competitors"]:
                hoa = competitor["homeAway"]
                teams[hoa] = {
                    "name": competitor["team"]["displayName"],
                    "abbr": competitor["team"]["abbreviation"],
                    "score": int(competitor.get("score", 0)),
                }
            games.append({
                "home": teams.get("home", {}),
                "away": teams.get("away", {}),
                "status": status,
                "is_final": status == "STATUS_FINAL",
            })
        return games
    except Exception as e:
        print(f"ESPN API error: {e}", file=sys.stderr)
        return []


def find_game_score(games: list[dict], event_str: str) -> Optional[dict]:
    """Match a bet's event string (e.g. 'Pistons @ Wizards') to an ESPN game."""
    # Parse "Away @ Home" format
    parts = event_str.split(" @ ")
    if len(parts) != 2:
        return None
    away_name, home_name = parts[0].strip(), parts[1].strip()

    for game in games:
        home_match = (
            home_name.lower() in game["home"].get("name", "").lower()
            or home_name.lower() in game["home"].get("abbr", "").lower()
        )
        away_match = (
            away_name.lower() in game["away"].get("name", "").lower()
            or away_name.lower() in game["away"].get("abbr", "").lower()
        )
        if home_match and away_match:
            return game
    return None


def resolve_spread(pick_str: str, home_score: int, away_score: int, event_str: str) -> str:
    """Determine WIN/LOSS/PUSH for a spread bet.
    pick_str like 'Wizards +18' or 'Pacers +15.5'
    """
    parts = pick_str.rsplit(" ", 1)
    if len(parts) != 2:
        return "unknown"
    team_name = parts[0].strip()
    spread = float(parts[1])

    # Figure out which team was picked
    event_parts = event_str.split(" @ ")
    if len(event_parts) != 2:
        return "unknown"

    # Determine if picked team is home or away
    if team_name.lower() in event_parts[1].lower():
        picked_score = home_score
        opponent_score = away_score
    elif team_name.lower() in event_parts[0].lower():
        picked_score = away_score
        opponent_score = home_score
    else:
        return "unknown"

    adjusted = picked_score + spread
    if adjusted > opponent_score:
        return "win"
    elif adjusted < opponent_score:
        return "loss"
    else:
        return "push"


def resolve_moneyline(pick_str: str, home_score: int, away_score: int, event_str: str) -> str:
    """Determine WIN/LOSS for a moneyline bet."""
    team_name = pick_str.replace(" ML", "").strip()
    event_parts = event_str.split(" @ ")
    if len(event_parts) != 2:
        return "unknown"

    if team_name.lower() in event_parts[1].lower():
        return "win" if home_score > away_score else "loss"
    elif team_name.lower() in event_parts[0].lower():
        return "win" if away_score > home_score else "loss"
    return "unknown"


def main():
    # Load current state
    if not DATA_JSON.exists():
        print("data.json not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_JSON.read_text())
    bankroll = json.loads(BANKROLL_JSON.read_text()) if BANKROLL_JSON.exists() else None

    bets = data.get("bets", [])
    pending = [b for b in bets if b.get("outcome") == "pending"]

    if not pending:
        print("No pending bets to resolve.")
        sys.exit(0)

    print(f"Found {len(pending)} pending bet(s). Fetching scores...")

    # Get unique dates from pending bets
    dates = set()
    for bet in pending:
        d = bet.get("date", "")
        if d:
            dates.add(d.replace("-", ""))

    # Fetch scores for each date
    all_games = []
    for date_str in dates:
        games = fetch_nba_scores(date_str)
        all_games.extend(games)
        print(f"  Fetched {len(games)} games for {date_str}")

    # Resolve each pending bet
    resolved_count = 0
    for bet in bets:
        if bet.get("outcome") != "pending":
            continue

        game = find_game_score(all_games, bet["event"])
        if not game:
            print(f"  Could not find game: {bet['event']}")
            continue
        if not game["is_final"]:
            print(f"  Game not final: {bet['event']}")
            continue

        home_score = game["home"]["score"]
        away_score = game["away"]["score"]
        score_str = f"{game['away']['abbr']} {away_score}, {game['home']['abbr']} {home_score}"

        # Determine outcome
        pick = bet["pick"]
        if "ML" in pick:
            outcome = resolve_moneyline(pick, home_score, away_score, bet["event"])
        elif "+" in pick or "-" in pick.split(" ")[-1]:
            outcome = resolve_spread(pick, home_score, away_score, bet["event"])
        else:
            outcome = "unknown"

        if outcome == "unknown":
            print(f"  Could not determine outcome for: {pick}")
            continue

        # Calculate P/L
        wager = bet["wager"]
        decimal_odds = bet.get("decimal_odds", 1.909)
        if outcome == "win":
            pnl = round(wager * (decimal_odds - 1), 2)
        elif outcome == "loss":
            pnl = round(-wager, 2)
        else:  # push
            pnl = 0.0

        bet["outcome"] = outcome
        bet["pnl"] = pnl
        bet["final_score"] = score_str
        resolved_count += 1
        print(f"  {bet['event']}: {pick} → {outcome.upper()} ({score_str}) P/L: ${pnl:+.2f}")

    if resolved_count == 0:
        print("No bets resolved (games may still be in progress).")
        sys.exit(0)

    # Update bankroll
    current = data["bankroll"].get("available", data["bankroll"].get("current", 500))
    wins = data["bankroll"]["record"]["wins"]
    losses = data["bankroll"]["record"]["losses"]
    pushes = data["bankroll"]["record"]["pushes"]

    for bet in bets:
        if bet.get("outcome") in ("win", "loss", "push") and "pnl" in bet:
            # Only count newly resolved bets
            pass

    # Recalculate from resolved bets
    for bet in bets:
        if bet.get("outcome") == "pending":
            continue

    # Simpler approach: recalculate bankroll from all resolved bets
    total_pnl = sum(b.get("pnl", 0) for b in bets if b.get("outcome") in ("win", "loss", "push"))
    pending_locked = sum(b.get("wager", 0) for b in bets if b.get("outcome") == "pending")
    win_count = sum(1 for b in bets if b.get("outcome") == "win")
    loss_count = sum(1 for b in bets if b.get("outcome") == "loss")
    push_count = sum(1 for b in bets if b.get("outcome") == "push")
    pending_count = sum(1 for b in bets if b.get("outcome") == "pending")

    # Available = starting + total_pnl - pending_locked
    starting = data["bankroll"]["starting"]
    available = round(starting + total_pnl - pending_locked, 2)

    data["bankroll"]["available"] = available
    data["bankroll"]["profit"] = round(total_pnl, 2)
    data["bankroll"]["record"] = {"wins": win_count, "losses": loss_count, "pushes": push_count}
    data["bankroll"]["pending_count"] = pending_count
    data["bankroll"]["pending_total"] = round(pending_locked, 2)
    if pending_count > 0:
        data["bankroll"]["pending_label"] = f"{pending_count} bet(s) pending (${pending_locked:.2f})"
    else:
        data["bankroll"]["pending_label"] = "No unsettled bets"

    # Update picks statuses
    for pick in data.get("picks", []):
        matching_bet = next((b for b in bets if b["pick"] == pick["pick"] and b["date"] == data["scan_date"]), None)
        if matching_bet and matching_bet.get("outcome") != "pending":
            pick["status"] = matching_bet["outcome"].upper()
            if "final_score" in matching_bet:
                pick["result"] = matching_bet["final_score"]

    # Write updated data.json
    DATA_JSON.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nUpdated data.json — Available: ${available:.2f}, Record: {win_count}W-{loss_count}L-{push_count}P")

    # Update bankroll.json if it exists
    if bankroll:
        bankroll["current_bankroll"] = available
        bankroll["lifetime_wins"] = win_count
        bankroll["lifetime_losses"] = loss_count
        bankroll["lifetime_pushes"] = push_count
        bankroll["lifetime_profit"] = round(total_pnl, 2)
        total_wagered = sum(b.get("wager", 0) for b in bets if b.get("outcome") in ("win", "loss", "push"))
        bankroll["roi_pct"] = round((total_pnl / total_wagered * 100) if total_wagered > 0 else 0, 1)
        bankroll["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Move resolved from pending to resolved in bankroll.json
        still_pending = []
        newly_resolved = []
        for pb in bankroll.get("pending_bets", []):
            matching = next((b for b in bets if b["pick"] == pb["pick"] and b.get("outcome") != "pending"), None)
            if matching:
                pb["outcome"] = matching["outcome"]
                pb["pnl"] = matching.get("pnl", 0)
                newly_resolved.append(pb)
            else:
                still_pending.append(pb)
        bankroll["pending_bets"] = still_pending
        bankroll["resolved_bets"] = bankroll.get("resolved_bets", []) + newly_resolved
        bankroll["lifetime_bets"] = len(bankroll.get("resolved_bets", [])) + len(still_pending)

        BANKROLL_JSON.write_text(json.dumps(bankroll, indent=2) + "\n")
        print(f"Updated bankroll.json")

    print(f"\nResolved {resolved_count} bet(s). Done.")


if __name__ == "__main__":
    main()
