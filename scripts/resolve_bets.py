#!/usr/bin/env python3
from __future__ import annotations
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
    """Fetch NBA scores from ESPN API for a given date (YYYYMMDD).
    Delegates to fetch_espn_scores so event_id (needed for box-score lookups
    in prop resolution) is included in the returned game dicts."""
    return fetch_espn_scores("basketball/nba", date_str)


def fetch_espn_scores(sport_path: str, date_str: str) -> list[dict]:
    """Generic ESPN scoreboard fetcher. sport_path like 'hockey/nhl', 'baseball/mlb', etc."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date_str}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        games = []
        for event in data.get("events", []):
            competition = event["competitions"][0]
            status = competition["status"]["type"]["name"]
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
                "event_id": event.get("id", ""),
            })
        return games
    except Exception as e:
        print(f"ESPN API error ({sport_path}): {e}", file=sys.stderr)
        return []


def fetch_nhl_scores(date_str: str) -> list[dict]:
    """Fetch NHL scores from ESPN API."""
    return fetch_espn_scores("hockey/nhl", date_str)


def fetch_mlb_scores(date_str: str) -> list[dict]:
    """Fetch MLB scores from ESPN API."""
    return fetch_espn_scores("baseball/mlb", date_str)


# ESPN soccer league paths
SOCCER_LEAGUES = {
    "epl": "soccer/eng.1",
    "la_liga": "soccer/esp.1",
    "bundesliga": "soccer/ger.1",
    "serie_a": "soccer/ita.1",
    "ligue_1": "soccer/fra.1",
    "ucl": "soccer/uefa.champions",
    "mls": "soccer/usa.1",
}


def fetch_soccer_scores(league: str, date_str: str) -> list[dict]:
    """Fetch soccer scores from ESPN API for a specific league."""
    path = SOCCER_LEAGUES.get(league.lower(), f"soccer/{league}")
    return fetch_espn_scores(path, date_str)


# ── Player box scores (for prop resolution) ────────────────────────────
# Mapping from our pick-string stat label to the ESPN box-score key.
# fetch_props.py emits picks like "Player Name OVER 12.5 Rebounds" using
# these stat labels; the ESPN summary endpoint reports them under different
# field names. Add new entries here when adding new prop markets.
NBA_PROP_STAT_TO_ESPN = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "Steals": "steals",
    "Blocked Shots": "blocks",
    "Blocks": "blocks",
    "Turnovers": "turnovers",
    "3-PT Made": "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
    "Threes Made": "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
}


def fetch_nba_player_box(event_id: str) -> dict:
    """Fetch NBA box score and return {player_name: {stat_label: value}}.
    stat_label is one of NBA_PROP_STAT_TO_ESPN keys ("Points", "Rebounds", etc.).
    Returns {} on any error so callers can leave picks pending rather than crash."""
    if not event_id:
        return {}
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            summary = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ESPN box error (event {event_id}): {e}", file=sys.stderr)
        return {}

    out = {}
    for team in summary.get("boxscore", {}).get("players", []):
        for stat_block in team.get("statistics", []):
            keys = stat_block.get("keys", [])
            for athlete in stat_block.get("athletes", []):
                name = athlete.get("athlete", {}).get("displayName", "")
                stats_arr = athlete.get("stats", [])
                if not name or not stats_arr or len(stats_arr) != len(keys):
                    continue
                stats_by_key = dict(zip(keys, stats_arr))
                player_stats = {}
                for label, espn_key in NBA_PROP_STAT_TO_ESPN.items():
                    raw = stats_by_key.get(espn_key)
                    if raw is None or raw == "":
                        continue
                    # 3PM is reported as "made-attempted" e.g. "2-6"; take made.
                    if "-" in str(raw) and "FieldGoals" in espn_key:
                        try:
                            player_stats[label] = int(str(raw).split("-")[0])
                        except (ValueError, IndexError):
                            continue
                    else:
                        try:
                            player_stats[label] = int(raw)
                        except (ValueError, TypeError):
                            continue
                if player_stats:
                    out[name] = player_stats
    return out


# Sport → fetcher mapping
SPORT_FETCHERS = {
    "nba": lambda d: fetch_nba_scores(d),
    "nhl": lambda d: fetch_nhl_scores(d),
    "mlb": lambda d: fetch_mlb_scores(d),
}
# Soccer leagues use sport-specific fetchers
for league_key in SOCCER_LEAGUES:
    SPORT_FETCHERS[league_key] = lambda d, lk=league_key: fetch_soccer_scores(lk, d)


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


def resolve_prop(pick_str: str, player_box: dict) -> tuple[str, str]:
    """Determine WIN/LOSS/PUSH for a player prop.
    pick_str like 'Victor Wembanyama OVER 12.5 Rebounds'.
    player_box is the dict returned by fetch_nba_player_box.
    Returns (outcome, detail_str). Outcome is 'win', 'loss', 'push', or 'unknown'.
    detail_str is a human-readable summary like 'Victor Wembanyama: 18 Rebounds'."""
    import re
    m = re.match(r"^(.+?)\s+(OVER|UNDER)\s+([\d.]+)\s+(.+)$", pick_str.strip())
    if not m:
        return ("unknown", "")
    player, direction, line_str, stat = m.group(1), m.group(2), m.group(3), m.group(4).strip()
    try:
        line = float(line_str)
    except ValueError:
        return ("unknown", "")

    # Player lookup: exact, then case-insensitive, then last-name fallback
    stats = player_box.get(player)
    if stats is None:
        for k, v in player_box.items():
            if k.lower() == player.lower():
                stats = v
                break
    if stats is None:
        # Last-name fallback handles minor name variations (e.g. "DeMar DeRozan" vs "Demar Derozan")
        last = player.rsplit(" ", 1)[-1].lower()
        for k, v in player_box.items():
            if k.lower().rsplit(" ", 1)[-1] == last:
                stats = v
                break
    if stats is None:
        return ("unknown", f"{player} not in box score")

    actual = stats.get(stat)
    if actual is None:
        return ("unknown", f"{stat} not tracked for {player}")

    detail = f"{player}: {actual} {stat}"
    if direction == "OVER":
        if actual > line: return ("win", detail)
        if actual < line: return ("loss", detail)
        return ("push", detail)
    # UNDER
    if actual < line: return ("win", detail)
    if actual > line: return ("loss", detail)
    return ("push", detail)


def resolve_total(pick_str: str, home_score: int, away_score: int) -> str:
    """Determine WIN/LOSS/PUSH for a totals (OVER/UNDER) bet.
    pick_str like 'OVER 220.5' or 'UNDER 234.5'
    """
    parts = pick_str.strip().split()
    if len(parts) != 2:
        return "unknown"

    direction = parts[0].upper()
    try:
        total_line = float(parts[1])
    except (ValueError, IndexError):
        return "unknown"

    actual_total = home_score + away_score

    if direction == "OVER":
        if actual_total > total_line:
            return "win"
        elif actual_total < total_line:
            return "loss"
        else:
            return "push"
    elif direction == "UNDER":
        if actual_total < total_line:
            return "win"
        elif actual_total > total_line:
            return "loss"
        else:
            return "push"
    return "unknown"


def main():
    # Load current state
    if not DATA_JSON.exists():
        print("data.json not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_JSON.read_text())
    bankroll = json.loads(BANKROLL_JSON.read_text()) if BANKROLL_JSON.exists() else None

    bets = data.get("bets", [])

    # Sync any resolved bets from bankroll.json that are missing from data.bets.
    # Manual overrides write directly to bankroll.resolved_bets; without this merge
    # the site Activity view silently drops those bets. Idempotent — keyed on
    # (date, pick). See tasks/lessons.md April 10 entry.
    sync_added = 0
    if bankroll and bankroll.get("resolved_bets"):
        sport_map = {"mlb": "MLB", "nba": "NBA", "nhl": "NHL", "ucl": "UCL",
                     "uel": "UEL", "soccer": "SOCCER"}
        existing_keys = {(b.get("date", ""), b.get("pick", "")) for b in bets}
        for r in bankroll["resolved_bets"]:
            key = (r.get("date", ""), r.get("pick", ""))
            if not key[0] or not key[1] or key in existing_keys:
                continue
            sport_raw = (r.get("sport", "") or "").lower()
            bets.append({
                "date": r["date"],
                "pick": r["pick"],
                "event": r.get("event", ""),
                "sport": sport_map.get(sport_raw, sport_raw.upper()),
                "wager": r.get("bet_size", 0),
                "odds": r.get("odds", 0),
                "outcome": r.get("outcome", ""),
                "pnl": r.get("pnl", 0),
                "final_score": r.get("final_score", ""),
            })
            existing_keys.add(key)
            sync_added += 1
        if sync_added:
            print(f"Synced {sync_added} resolved bet(s) from bankroll.json into data.bets")
            data["bets"] = bets

    pending = [b for b in bets if b.get("outcome") == "pending"]

    all_games = {}  # keyed by sport — shared with pick_history resolver

    if not pending:
        print("No pending placed bets. Will still resolve pick_history.json.")
    else:
        print(f"Found {len(pending)} pending bet(s). Fetching scores...")

        # Get unique (sport, date) pairs from pending bets
        sport_dates = set()
        for bet in pending:
            d = bet.get("date", "")
            sport = bet.get("sport", "nba").lower()
            if d:
                sport_dates.add((sport, d.replace("-", "")))

        # Fetch scores for each sport/date combination.
        # Cache key is (sport, date_str), not just sport, so two different dates
        # of the same sport do not collide.
        for sport, date_str in sport_dates:
            fetcher = SPORT_FETCHERS.get(sport)
            if not fetcher:
                print(f"  No score fetcher for sport: {sport}")
                continue
            games = fetcher(date_str)
            all_games[(sport, date_str)] = games
            print(f"  Fetched {len(games)} {sport.upper()} games for {date_str}")

    # Resolve each pending bet
    resolved_count = 0
    for bet in bets:
        if bet.get("outcome") != "pending":
            continue

        sport = bet.get("sport", "nba").lower()
        bet_date = bet.get("date", "").replace("-", "")
        sport_games = all_games.get((sport, bet_date), [])
        game = find_game_score(sport_games, bet["event"])
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
        pick_upper = pick.strip().upper()
        if "ML" in pick:
            outcome = resolve_moneyline(pick, home_score, away_score, bet["event"])
        elif pick_upper.startswith("OVER ") or pick_upper.startswith("UNDER "):
            outcome = resolve_total(pick, home_score, away_score)
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
        print("No placed bets resolved (games may still be in progress or none pending).")
        # Still write data.json if sync added bankroll-only bets above.
        if sync_added:
            DATA_JSON.write_text(json.dumps(data, indent=2) + "\n")
            print(f"Wrote data.json with {sync_added} synced bet(s).")
        # Still resolve pick_history.json below — do not exit
        resolve_pick_history(all_games)
        return

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

    # ── Resolve pick_history.json (paper-trading tracker) ──────────────
    resolve_pick_history(all_games)


def resolve_pick_history(all_games: dict):
    """Resolve pending picks in pick_history.json for paper-trading analysis.
    Uses the same ESPN scores already fetched. Resolves ALL picks, not just placed bets.
    all_games is a dict keyed by sport.
    """
    HISTORY_JSON = REPO_ROOT / "pick_history.json"
    if not HISTORY_JSON.exists():
        return

    try:
        history = json.loads(HISTORY_JSON.read_text())
    except (json.JSONDecodeError, Exception):
        return

    if not history:
        return

    pending = [h for h in history if h.get("outcome") == "pending"]
    if not pending:
        return

    # Fetch scores for any sport/date combos not already fetched.
    # Cache key is (sport, date) so a second pending pick on a different date
    # of the same sport does not silently reuse the wrong scoreboard.
    for h in pending:
        d = h.get("scan_date", "").replace("-", "")
        sport = h.get("sport", "nba").lower() if h.get("sport") else "nba"
        if not d:
            continue
        fetcher = SPORT_FETCHERS.get(sport)
        if fetcher and (sport, d) not in all_games:
            games = fetcher(d)
            all_games[(sport, d)] = games

    # Player-prop box-score cache: keyed on event_id so multiple props from the
    # same game share one ESPN summary fetch.
    box_cache: dict = {}

    resolved_count = 0
    for h in history:
        if h.get("outcome") != "pending":
            continue

        sport = h.get("sport", "nba").lower() if h.get("sport") else "nba"
        d = h.get("scan_date", "").replace("-", "")
        sport_games = all_games.get((sport, d), [])
        game = find_game_score(sport_games, h.get("event", ""))
        if not game or not game["is_final"]:
            continue

        home_score = game["home"]["score"]
        away_score = game["away"]["score"]
        score_str = f"{game['away']['abbr']} {away_score}, {game['home']['abbr']} {home_score}"

        pick = h.get("pick", "")
        pick_upper = pick.strip().upper()
        is_prop = h.get("type") == "prop" or h.get("market") == "Player Prop"
        prop_detail = ""

        # Determine outcome — same logic as main resolver, with props handled first.
        # Props need a per-game box-score fetch keyed on event_id; cached above so a
        # second prop from the same game costs nothing.
        if is_prop:
            if sport != "nba":
                # Only NBA props are supported today; other sports' fetchers TBD.
                continue
            event_id = game.get("event_id", "")
            if not event_id:
                continue
            if event_id not in box_cache:
                box_cache[event_id] = fetch_nba_player_box(event_id)
            outcome, prop_detail = resolve_prop(pick, box_cache[event_id])
        elif "ML" in pick:
            outcome = resolve_moneyline(pick, home_score, away_score, h.get("event", ""))
        elif pick_upper.startswith("OVER ") or pick_upper.startswith("UNDER "):
            outcome = resolve_total(pick, home_score, away_score)
        elif "+" in pick or "-" in pick.split(" ")[-1]:
            outcome = resolve_spread(pick, home_score, away_score, h.get("event", ""))
        else:
            outcome = "unknown"

        if outcome == "unknown":
            continue

        # For props, surface the actual stat line in final_score so the activity
        # view shows WHY the prop won/lost (game score alone is not enough).
        if is_prop and prop_detail:
            score_str = f"{score_str} | {prop_detail}"

        # Calculate hypothetical P/L (what we WOULD have made)
        odds_str = h.get("odds", "-110")
        try:
            dk_odds = int(odds_str)
        except (ValueError, TypeError):
            dk_odds = -110
        decimal_odds = 1 + 100 / abs(dk_odds) if dk_odds < 0 else 1 + dk_odds / 100
        wager = 10.00  # Standardized $10 paper bet for comparison

        if outcome == "win":
            pnl = round(wager * (decimal_odds - 1), 2)
        elif outcome == "loss":
            pnl = round(-wager, 2)
        else:
            pnl = 0.0

        h["outcome"] = outcome
        h["final_score"] = score_str
        h["pnl_if_bet"] = pnl
        resolved_count += 1

    if resolved_count > 0:
        HISTORY_JSON.write_text(json.dumps(history, indent=2) + "\n")
        total = len(history)
        wins = sum(1 for h in history if h.get("outcome") == "win")
        losses = sum(1 for h in history if h.get("outcome") == "loss")
        still_pending = sum(1 for h in history if h.get("outcome") == "pending")
        print(f"\nPick history: resolved {resolved_count} paper picks. Record: {wins}W-{losses}L, {still_pending} pending (of {total} total)")


if __name__ == "__main__":
    main()
