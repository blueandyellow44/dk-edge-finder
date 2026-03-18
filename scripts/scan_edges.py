#!/usr/bin/env python3
"""
DK Edge Finder — Autonomous Edge Scanner
Runs via GitHub Actions at 6 AM PT daily. No Claude, no Mac needed.

Pipeline:
1. Resolve any pending bets from last night
2. Fetch today's NBA schedule + DK odds via ESPN API
3. Fetch model probabilities from DRatings
4. Apply situational adjustments (tanking, B2B, motivation)
5. Calculate edges and Kelly sizing
6. Update data.json + bankroll.json
"""

import json
import sys
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "data.json"
BANKROLL_JSON = REPO_ROOT / "bankroll.json"

# ── Config ──────────────────────────────────────────
MIN_EDGE_HIGH = 0.03      # 3% for spreads/ML/totals
MIN_EDGE_MEDIUM = 0.05    # 5% for props
KELLY_FRACTION_HIGH = 0.5
MAX_SINGLE_BET_PCT = 0.05 # 5% max single bet
MAX_DAILY_EXPOSURE = 0.15 # 15% max daily

# Teams confirmed tanking (update periodically)
# Record threshold: bottom-8 teams (win% < .300 after All-Star break)
TANK_TEAMS_2026 = {
    "WAS": {"confirmed": True, "reason": "12-56, eliminated, starting rookies"},
    "BKN": {"confirmed": True, "reason": "17-51, eliminated, traded stars"},
    "IND": {"confirmed": True, "reason": "15-53, eliminated, traded Siakam"},
    "SAC": {"confirmed": True, "reason": "18-51, eliminated, Fox shut down"},
    "UTA": {"confirmed": True, "reason": "20-48, eliminated, development mode"},
    "CHA": {"confirmed": False, "reason": "34-34, play-in contention"},
    "DAL": {"confirmed": False, "reason": "26-42, mathematically alive"},
    "TOR": {"confirmed": False, "reason": "36-32, playoff push"},
}

TANK_PENALTY_CONFIRMED = 0.03   # -3% for confirmed tankers
TANK_PENALTY_SUSPECTED = 0.015  # -1.5% for suspected

B2B_PENALTY = 0.015        # -1.5% for back-to-back
B2B_ROAD_PENALTY = 0.025   # -2.5% for road back-to-back
REST_ADVANTAGE = 0.015     # +1.5% for 2+ days rest vs B2B opponent


# ── ESPN API helpers ────────────────────────────────
def espn_fetch(url: str) -> dict:
    """Fetch JSON from ESPN API."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ESPN API error: {e}", file=sys.stderr)
        return {}


def get_today_str() -> str:
    """Get today's date in YYYYMMDD format (Pacific time)."""
    pt = timezone(timedelta(hours=-7))
    return datetime.now(pt).strftime("%Y%m%d")


def get_today_iso() -> str:
    """Get today's date in YYYY-MM-DD format (Pacific time)."""
    pt = timezone(timedelta(hours=-7))
    return datetime.now(pt).strftime("%Y-%m-%d")


def fetch_nba_schedule_and_odds(date_str: str) -> list[dict]:
    """Fetch NBA games with odds from ESPN for a given date."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    data = espn_fetch(url)
    games = []

    for event in data.get("events", []):
        comp = event["competitions"][0]
        status = comp["status"]["type"]["name"]

        teams = {}
        for c in comp["competitors"]:
            hoa = c["homeAway"]
            record = c.get("records", [{}])[0].get("summary", "0-0")
            teams[hoa] = {
                "name": c["team"]["displayName"],
                "abbr": c["team"]["abbreviation"],
                "score": int(c.get("score", 0)),
                "record": record,
            }

        # Extract odds if available
        odds_data = comp.get("odds", [{}])[0] if comp.get("odds") else {}
        spread = odds_data.get("spread", 0)
        over_under = odds_data.get("overUnder", 0)
        spread_odds = odds_data.get("spreadOdds", {})
        details = odds_data.get("details", "")

        # Parse spread from details (e.g., "OKC -19.5")
        home = teams.get("home", {})
        away = teams.get("away", {})

        # Determine which team is favored
        home_spread = None
        away_spread = None
        if spread and spread != 0:
            # ESPN spread is from perspective of the favorite
            # details string tells us who: "OKC -19.5"
            if details:
                parts = details.split(" ")
                if len(parts) >= 2:
                    fav_abbr = parts[0]
                    try:
                        spread_val = float(parts[1])
                    except ValueError:
                        spread_val = 0
                    if fav_abbr == home.get("abbr"):
                        home_spread = spread_val
                        away_spread = -spread_val
                    else:
                        away_spread = spread_val
                        home_spread = -spread_val

        game = {
            "home": home,
            "away": away,
            "status": status,
            "is_final": status == "STATUS_FINAL",
            "home_spread": home_spread,
            "away_spread": away_spread,
            "over_under": over_under,
            "event_str": f"{away.get('name', '?')} @ {home.get('name', '?')}",
            "event_short": f"{away.get('abbr', '?')} @ {home.get('abbr', '?')}",
            "odds_details": details,
        }
        games.append(game)

    return games


def fetch_dratings_predictions(date_str: str) -> dict:
    """
    Fetch model predictions from DRatings.
    Returns dict keyed by "AWAY@HOME" abbreviation with predicted scores.
    """
    # DRatings URL format
    url = f"https://www.dratings.com/predictor/nba-basketball-predictions/"
    predictions = {}

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Parse predicted scores from DRatings HTML
        # Look for patterns like team names and predicted scores
        # DRatings format varies but typically has predicted scores in table rows
        # This is a simplified parser — may need adjustment if DRatings changes format

        # Look for game rows with predicted scores
        # Pattern: team abbreviation followed by predicted score
        rows = re.findall(
            r'(?i)(\w{2,3})\s+(\d{2,3}(?:\.\d)?)\s*[,-]\s*(\w{2,3})\s+(\d{2,3}(?:\.\d)?)',
            html
        )

        for match in rows:
            team1, score1, team2, score2 = match
            try:
                s1, s2 = float(score1), float(score2)
                key = f"{team1.upper()}@{team2.upper()}"
                predictions[key] = {"away_score": s1, "home_score": s2}
                # Also store reverse key
                predictions[f"{team2.upper()}@{team1.upper()}"] = {"away_score": s2, "home_score": s1}
            except ValueError:
                continue

        print(f"  DRatings: found {len(predictions)//2} game predictions")

    except Exception as e:
        print(f"  DRatings fetch error: {e}", file=sys.stderr)

    return predictions


# ── Schedule / B2B detection ────────────────────────
def fetch_yesterday_games(date_str: str) -> set[str]:
    """Return set of team abbreviations that played yesterday."""
    # Calculate yesterday
    dt = datetime.strptime(date_str, "%Y%m%d")
    yesterday = (dt - timedelta(days=1)).strftime("%Y%m%d")

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={yesterday}"
    data = espn_fetch(url)
    teams_played = set()

    for event in data.get("events", []):
        comp = event["competitions"][0]
        for c in comp["competitors"]:
            teams_played.add(c["team"]["abbreviation"])

    return teams_played


# ── Edge calculation ────────────────────────────────
def american_to_decimal(odds: int) -> float:
    if odds < 0:
        return round(1 + 100 / abs(odds), 3)
    else:
        return round(1 + odds / 100, 3)


def american_to_implied(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def calc_kelly(edge: float, decimal_odds: float, fraction: float) -> float:
    """Calculate fractional Kelly bet size as percentage of bankroll."""
    if decimal_odds <= 1 or edge <= 0:
        return 0
    kelly = edge / (decimal_odds - 1)
    return kelly * fraction


def calculate_edge(game: dict, predictions: dict, b2b_teams: set) -> dict | None:
    """
    Calculate edge for a single game's spread.
    Returns pick dict or None if no edge.
    """
    home = game["home"]
    away = game["away"]
    home_abbr = home.get("abbr", "")
    away_abbr = away.get("abbr", "")

    # Need a spread to work with
    if game["home_spread"] is None or game["away_spread"] is None:
        return None

    # Try to find DRatings prediction
    key = f"{away_abbr}@{home_abbr}"
    pred = predictions.get(key)

    if not pred:
        # Try alternate key formats
        key2 = f"{away_abbr.upper()}@{home_abbr.upper()}"
        pred = predictions.get(key2)

    if not pred:
        return None

    # Model predicted margin (positive = home favored)
    model_home_margin = pred["home_score"] - pred["away_score"]

    # Determine which side to bet (the underdog if model margin < spread)
    # ESPN spread: negative = favored. e.g., home_spread = -19.5 means home favored by 19.5
    espn_spread = game["home_spread"]  # from home perspective

    # The bet is on the underdog (positive spread side)
    # If home is underdog (positive spread), bet home
    # If away is underdog, bet away
    if espn_spread > 0:
        # Home is underdog
        pick_team = home
        pick_spread = espn_spread
        pick_side = "home"
        # Model probability: does model think home covers?
        # Home covers if: actual_margin > -spread (home perspective)
        # Approximate: model_margin vs spread
        model_margin_for_pick = -model_home_margin  # from underdog perspective
        spread_cushion = pick_spread - abs(model_home_margin)
    else:
        # Away is underdog
        pick_team = away
        pick_spread = game["away_spread"]  # positive number
        pick_side = "away"
        model_margin_for_pick = model_home_margin  # home winning margin
        spread_cushion = pick_spread - abs(model_home_margin)

    if pick_spread <= 0:
        return None  # No underdog spread to bet

    # Estimate cover probability from model margin vs spread
    # Rough heuristic: each point of cushion ≈ 2-3% cover probability
    # Base: if model exactly matches spread, ~50% cover
    base_cover_prob = 0.50
    cushion_boost = spread_cushion * 0.025  # 2.5% per point of cushion
    model_prob = min(0.80, max(0.30, base_cover_prob + cushion_boost))

    # Standard DK juice for big spreads: -110 to -115
    # Use -110 as default if we don't have exact juice
    dk_odds = -110
    if pick_spread >= 15:
        dk_odds = -112  # Larger spreads often have slightly more juice
    if pick_spread >= 18:
        dk_odds = -115

    implied_prob = american_to_implied(dk_odds)

    # ── Apply situational adjustments ──

    # Tanking penalty
    tank_info = TANK_TEAMS_2026.get(pick_team.get("abbr", ""), None)
    tank_note = ""
    if tank_info:
        if tank_info["confirmed"]:
            model_prob -= TANK_PENALTY_CONFIRMED
            tank_note = f"TANK RISK: {tank_info['reason']} (-3% adj)"
        else:
            model_prob -= TANK_PENALTY_SUSPECTED
            tank_note = f"TANK WATCH: {tank_info['reason']} (-1.5% adj)"

    # B2B penalty
    b2b_note = ""
    if pick_team.get("abbr", "") in b2b_teams:
        if pick_side == "away":
            model_prob -= B2B_ROAD_PENALTY
            b2b_note = f"{pick_team['abbr']} on road B2B (-2.5% adj)"
        else:
            model_prob -= B2B_PENALTY
            b2b_note = f"{pick_team['abbr']} on B2B (-1.5% adj)"

    # Opponent B2B bonus
    opponent = away if pick_side == "home" else home
    if opponent.get("abbr", "") in b2b_teams:
        model_prob += REST_ADVANTAGE
        b2b_note += f" | {opponent['abbr']} on B2B (+1.5% boost)"

    # Calculate edge
    edge = model_prob - implied_prob

    if edge < MIN_EDGE_HIGH:
        return None  # Below threshold

    # Kelly sizing
    decimal_odds = american_to_decimal(dk_odds)
    kelly_pct = calc_kelly(edge, decimal_odds, KELLY_FRACTION_HIGH)

    # Build notes
    notes_parts = [
        f"DRatings: {away_abbr} {pred['away_score']:.1f}, {home_abbr} {pred['home_score']:.1f} (projected margin: {abs(model_home_margin):.1f}).",
        f"Spread cushion: {spread_cushion:.1f} pts.",
    ]
    if tank_note:
        notes_parts.append(tank_note)
    if b2b_note:
        notes_parts.append(b2b_note.strip())

    return {
        "sport": "NBA",
        "event": game["event_str"],
        "event_short": game["event_short"],
        "market": "Spread",
        "pick": f"{pick_team['name']} +{pick_spread}",
        "pick_abbr": pick_team.get("abbr", ""),
        "odds": str(dk_odds),
        "dk_odds_int": dk_odds,
        "decimal_odds": decimal_odds,
        "implied_prob": implied_prob,
        "model_prob": model_prob,
        "edge": round(edge * 100, 1),
        "edge_raw": edge,
        "tier": "High",
        "kelly_pct": kelly_pct,
        "notes": " ".join(notes_parts),
        "sources": "DRatings, ESPN",
        "tank_risk": bool(tank_info and tank_info["confirmed"]),
        "spread_cushion": spread_cushion,
    }


# ── Main ────────────────────────────────────────────
def main():
    today = get_today_str()
    today_iso = get_today_iso()
    print(f"DK Edge Finder — Scanning for {today_iso}")

    # Step 1: Resolve pending bets first
    print("\n[1] Resolving pending bets...")
    import importlib.util
    resolve_path = REPO_ROOT / "scripts" / "resolve_bets.py"
    if resolve_path.exists():
        spec = importlib.util.spec_from_file_location("resolve_bets", resolve_path)
        resolve_mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(resolve_mod)
            resolve_mod.main()
        except SystemExit:
            pass  # resolve_bets calls sys.exit(0) when no pending bets

    # Reload data after resolution
    data = json.loads(DATA_JSON.read_text()) if DATA_JSON.exists() else {}
    bankroll = json.loads(BANKROLL_JSON.read_text()) if BANKROLL_JSON.exists() else {
        "current_bankroll": 500.0, "starting_bankroll": 500.0
    }

    available = bankroll.get("current_bankroll", 500.0)

    # Step 2: Fetch today's games
    print(f"\n[2] Fetching NBA schedule for {today}...")
    games = fetch_nba_schedule_and_odds(today)
    # Filter to only games that haven't started
    upcoming = [g for g in games if g["status"] in ("STATUS_SCHEDULED", "STATUS_PREGAME")]
    print(f"  Found {len(games)} total games, {len(upcoming)} upcoming")

    if not upcoming:
        print("No upcoming games. Saving empty scan.")
        data["scan_date"] = today_iso
        data["scan_subtitle"] = f"{today_iso} — No NBA games scheduled"
        data["picks"] = []
        data["no_edge_games"] = []
        DATA_JSON.write_text(json.dumps(data, indent=2) + "\n")
        return

    # Step 3: Fetch model predictions
    print("\n[3] Fetching DRatings predictions...")
    predictions = fetch_dratings_predictions(today)

    # Step 4: Check B2B teams
    print("\n[4] Checking back-to-back schedule...")
    b2b_teams = fetch_yesterday_games(today)
    print(f"  Teams on B2B: {', '.join(sorted(b2b_teams)) if b2b_teams else 'none'}")

    # Step 5: Calculate edges
    print("\n[5] Calculating edges...")
    picks = []
    no_edge = []

    for game in upcoming:
        result = calculate_edge(game, predictions, b2b_teams)
        if result:
            picks.append(result)
            print(f"  EDGE: {result['pick']} ({result['odds']}) — {result['edge']}% edge")
        else:
            home_spread = game.get("home_spread")
            away_spread = game.get("away_spread")
            spread_str = game.get("odds_details", "N/A")
            reason = "No model data" if not predictions.get(f"{game['away']['abbr']}@{game['home']['abbr']}") else "Edge below 3% threshold"

            # Check if it was filtered by tanking
            pick_abbr = game["home"]["abbr"] if (home_spread or 0) > 0 else game["away"]["abbr"]
            tank_info = TANK_TEAMS_2026.get(pick_abbr)
            if tank_info and tank_info["confirmed"]:
                reason = f"Tank penalty applied — {tank_info['reason']}"

            no_edge.append({
                "sport": "NBA",
                "event": game["event_short"],
                "line": spread_str if spread_str else "N/A",
                "reason": reason,
            })

    # Sort picks by edge descending
    picks.sort(key=lambda x: x["edge"], reverse=True)

    # Step 6: Size bets with Kelly
    print(f"\n[6] Sizing {len(picks)} picks (bankroll: ${available:.2f})...")
    total_exposure = 0
    formatted_picks = []

    for i, pick in enumerate(picks):
        bet_pct = min(pick["kelly_pct"], MAX_SINGLE_BET_PCT)
        bet_amount = round(available * bet_pct, 2)

        # Check daily exposure limit
        if total_exposure + bet_amount > available * MAX_DAILY_EXPOSURE:
            remaining = (available * MAX_DAILY_EXPOSURE) - total_exposure
            if remaining > 5:  # Min bet $5
                bet_amount = round(remaining, 2)
            else:
                print(f"  Skipping {pick['pick']} — daily exposure limit reached")
                no_edge.append({
                    "sport": pick["sport"],
                    "event": pick["event_short"],
                    "line": f"{pick['pick']} ({pick['odds']})",
                    "reason": f"Edge exists ({pick['edge']}%) but daily exposure limit reached",
                })
                continue

        total_exposure += bet_amount

        formatted_picks.append({
            "rank": i + 1,
            "sport": pick["sport"],
            "event": pick["event"],
            "market": pick["market"],
            "pick": pick["pick"],
            "odds": pick["odds"],
            "implied": f"{pick['implied_prob']*100:.1f}%",
            "model": f"{pick['model_prob']*100:.1f}%",
            "edge": pick["edge"],
            "tier": pick["tier"],
            "bet": f"${bet_amount:.2f}",
            "status": "",
            "result": "",
            "notes": pick["notes"],
            "sources": pick["sources"],
        })

        print(f"  #{i+1}: {pick['pick']} ({pick['odds']}) — {pick['edge']}% edge — ${bet_amount:.2f}")

    # Step 7: Build data.json
    print(f"\n[7] Updating data.json...")

    # Determine best bet
    best_bet = None
    if formatted_picks:
        bp = formatted_picks[0]
        best_bet = {
            "title": f"{bp['pick']} ({bp['odds']}) — {bp['edge']}% Edge ({bp['tier']} Tier)",
            "desc": bp["notes"][:200],
        }

    # Preserve existing bet history
    existing_bets = data.get("bets", [])
    # Remove any existing bets for today (will be replaced by new picks if placed)
    existing_bets = [b for b in existing_bets if b.get("date") != today_iso]

    # Build subtitle
    subtitle = f"{datetime.strptime(today, '%Y%m%d').strftime('%A, %B %d, %Y')} — NBA ({len(games)} games)"

    # Get current record from bankroll
    rec = data.get("bankroll", {}).get("record", {"wins": 0, "losses": 0, "pushes": 0})

    new_data = {
        "scan_date": today_iso,
        "scan_subtitle": subtitle,
        "bankroll": {
            "available": available,
            "starting": bankroll.get("starting_bankroll", 500.0),
            "profit": round(available - bankroll.get("starting_bankroll", 500.0), 2),
            "record": rec,
            "pending_count": 0,
            "pending_total": 0,
            "pending_label": "No unsettled bets",
        },
        "games_analyzed": len(games),
        "best_bet": best_bet,
        "picks": formatted_picks,
        "no_edge_games": no_edge,
        "bets": existing_bets,
    }

    DATA_JSON.write_text(json.dumps(new_data, indent=2) + "\n")
    print(f"\nDone. {len(formatted_picks)} edges found, {len(no_edge)} games no edge.")
    print(f"Total suggested exposure: ${total_exposure:.2f} ({(total_exposure/available*100):.1f}% of bankroll)")


if __name__ == "__main__":
    main()
