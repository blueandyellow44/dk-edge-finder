#!/usr/bin/env python3
"""
Player Prop Edge Scanner — Real DK Odds Edition
Fetches actual DraftKings player prop odds from The Odds API,
builds player-specific projections using ESPN game logs,
and flags edges where our projection disagrees with the DK line.

Props are Medium confidence tier: 5% min edge, 1/4 Kelly.
"""

import json
import math
import os
import urllib.request
import urllib.error
import urllib.parse
import time
from datetime import datetime, timezone
from pathlib import Path


# ── The Odds API ─────────────────────────────────────────

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# Load from .env if not in environment
if not ODDS_API_KEY:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ODDS_API_KEY="):
                ODDS_API_KEY = line.split("=", 1)[1].strip()
                break

# Odds API sport keys
SPORT_KEYS = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
}

# Odds API market keys → our stat type names
MARKET_TO_STAT = {
    "player_points": "Points",
    "player_rebounds": "Rebounds",
    "player_assists": "Assists",
    "player_threes": "3-PT Made",
    "player_blocks": "Blocked Shots",
    "player_steals": "Steals",
    "player_turnovers": "Turnovers",
    "player_points_rebounds_assists": "Pts+Rebs+Asts",
    "player_points_rebounds": "Pts+Rebs",
    "player_points_assists": "Pts+Asts",
    "player_rebounds_assists": "Rebs+Asts",
}

# Which markets to request (costs credits per market group)
PROP_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
]

# Additional markets to add if credits allow
EXTRA_MARKETS = [
    "player_points_rebounds_assists",
    "player_steals",
    "player_blocks",
]


def fetch_dk_prop_odds(sport: str = "nba", max_events: int = 6) -> list[dict]:
    """Fetch real DraftKings player prop odds from The Odds API.

    Returns list of props in standardized format:
    {
        "player": "Shai Gilgeous-Alexander",
        "team": "",
        "stat_type": "Points",
        "line": 28.5,
        "over_odds": -110,
        "under_odds": -116,
        "event_id": "abc123",
        "event": "OKC @ WAS",
        "start_time": "2026-03-21T21:10:00Z",
    }
    """
    if not ODDS_API_KEY:
        print("  WARNING: No ODDS_API_KEY found. Set it in .env or environment.")
        return []

    sport_key = SPORT_KEYS.get(sport.lower())
    if not sport_key:
        print(f"  Sport '{sport}' not supported for props yet")
        return []

    # Step 1: Get today's events
    events_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events?apiKey={ODDS_API_KEY}"
    try:
        req = urllib.request.Request(events_url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            events = json.loads(resp.read())
            remaining = resp.headers.get("x-requests-remaining", "?")
            print(f"  Odds API: {len(events)} events found (credits remaining: {remaining})")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  Odds API events fetch failed: {e}")
        return []

    if not events:
        return []

    # Limit events to save credits (each event+market costs ~1-3 credits)
    # Sort by start time, take the soonest games
    events.sort(key=lambda e: e.get("commence_time", ""))
    events = events[:max_events]

    # Step 2: Fetch props for each event
    markets_str = ",".join(PROP_MARKETS)
    all_props = []

    for event in events:
        event_id = event["id"]
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        event_label = f"{away} @ {home}"

        props_url = (
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
            f"?apiKey={ODDS_API_KEY}&regions=us&bookmakers=draftkings"
            f"&oddsFormat=american&markets={markets_str}"
        )

        try:
            req = urllib.request.Request(props_url, headers={"User-Agent": "DKEdgeFinder/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                remaining = resp.headers.get("x-requests-remaining", "?")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"    {event_label}: fetch failed ({e})")
            continue

        # Parse DraftKings bookmaker data
        for bm in data.get("bookmakers", []):
            if bm["key"] != "draftkings":
                continue

            for market in bm.get("markets", []):
                market_key = market["key"]
                stat_type = MARKET_TO_STAT.get(market_key)
                if not stat_type:
                    continue

                # Group outcomes by player + point (line)
                # Each player has Over and Under at the same point
                player_lines = {}
                for outcome in market.get("outcomes", []):
                    name = outcome.get("description", "")
                    if not name:
                        continue
                    point = outcome.get("point")
                    if point is None:
                        continue
                    price = outcome.get("price")
                    if price is None:
                        continue
                    side = outcome.get("name", "").lower()

                    key = (name, point)
                    if key not in player_lines:
                        player_lines[key] = {"over": None, "under": None}

                    if side == "over":
                        player_lines[key]["over"] = int(price)
                    elif side == "under":
                        player_lines[key]["under"] = int(price)

                # Build prop objects
                for (player_name, point), sides in player_lines.items():
                    over_odds = sides.get("over")
                    under_odds = sides.get("under")
                    if over_odds is None or under_odds is None:
                        continue

                    all_props.append({
                        "player": player_name,
                        "team": "",
                        "stat_type": stat_type,
                        "line": float(point),
                        "over_odds": over_odds,
                        "under_odds": under_odds,
                        "event_id": event_id,
                        "event": event_label,
                        "start_time": event.get("commence_time", ""),
                        "description": event_label,
                    })

        # Brief pause between events to be polite
        time.sleep(0.3)

    print(f"  Fetched {len(all_props)} DK prop lines across {min(len(events), max_events)} games")
    print(f"  Odds API credits remaining: {remaining}")
    return all_props


# ── ESPN Player Stats ─────────────────────────────────────

# Map our stat names to ESPN gamelog column indices
# ESPN order: MIN, FG, FG%, 3PT, 3P%, FT, FT%, REB, AST, BLK, STL, PF, TO, PTS
PP_TO_ESPN = {
    "Points": 13,       # PTS
    "Rebounds": 7,       # REB
    "Assists": 8,        # AST
    "3-PT Made": 3,      # 3PT (made-attempted, need to parse)
    "Steals": 10,        # STL
    "Blocked Shots": 9,  # BLK
    "Turnovers": 12,     # TO
}

# Combo stat mappings (sum of individual indices)
PP_COMBOS = {
    "Pts+Rebs": [13, 7],
    "Pts+Asts": [13, 8],
    "Rebs+Asts": [7, 8],
    "Pts+Rebs+Asts": [13, 7, 8],
}

# ESPN athlete ID cache (player name → ESPN ID)
_espn_id_cache = {}


def find_espn_athlete_id(player_name: str, team: str = "") -> str | None:
    """Search ESPN for a player's athlete ID."""
    if player_name in _espn_id_cache:
        return _espn_id_cache[player_name]

    query = urllib.parse.quote(player_name)
    url = f"https://site.api.espn.com/apis/common/v3/search?query={query}&limit=5&type=player"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = data.get("results", []) or data.get("items", [])
        if not results:
            for section in data.get("groups", []):
                results.extend(section.get("items", []))

        for r in results:
            name = r.get("displayName", "") or r.get("name", "")
            if name.lower() == player_name.lower():
                athlete_id = str(r.get("id", ""))
                if athlete_id:
                    _espn_id_cache[player_name] = athlete_id
                    return athlete_id

        # Fallback: take first result if name is close
        if results:
            athlete_id = str(results[0].get("id", ""))
            if athlete_id:
                _espn_id_cache[player_name] = athlete_id
                return athlete_id

    except Exception:
        pass

    return None


def fetch_player_recent_stats(athlete_id: str, sport: str = "nba", n_games: int = 10) -> dict | None:
    """Fetch player's recent game log from ESPN and compute averages."""
    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/gamelog"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    # Parse game log — structure: seasonTypes[].categories[].events[]
    # Categories are grouped by month (displayName: "march", "february", etc.)
    # No "name" field — just grab all events from regular season seasonType
    rows = []
    for st in data.get("seasonTypes", []):
        # Skip preseason
        if "preseason" in st.get("displayName", "").lower():
            continue
        for cat in st.get("categories", []):
            for event_row in cat.get("events", []):
                stats_list = event_row.get("stats", [])
                if stats_list and len(stats_list) >= 14:
                    rows.append(stats_list)

    if not rows:
        return None

    # Take the most recent n_games
    recent = rows[:n_games]

    # Compute averages
    averages = {}
    for idx in list(PP_TO_ESPN.values()):
        vals = []
        for row in recent:
            raw = row[idx] if idx < len(row) else "0"
            try:
                if isinstance(raw, str) and "-" in raw:
                    val = float(raw.split("-")[0])  # "3-7" → 3 (made)
                else:
                    val = float(raw)
                vals.append(val)
            except (ValueError, TypeError):
                continue
        if vals:
            averages[idx] = round(sum(vals) / len(vals), 2)

    return {
        "averages": averages,
        "games_sampled": len(recent),
    }


# ── Edge Calculation ──────────────────────────────────────

# Standard deviations for player prop outcomes
PROP_SD = {
    "Points": 8.0,
    "Rebounds": 3.5,
    "Assists": 2.5,
    "3-PT Made": 1.5,
    "Steals": 1.0,
    "Blocked Shots": 1.0,
    "Turnovers": 1.2,
    "Pts+Rebs": 9.0,
    "Pts+Asts": 9.0,
    "Rebs+Asts": 4.5,
    "Pts+Rebs+Asts": 10.0,
}

SUPPORTED_PROPS = set(PROP_SD.keys())
MIN_PROP_EDGE = 0.05  # 5% minimum for Medium tier


def normal_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    if x < 0:
        return 1.0 - normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    d = 0.3989422804014327
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - d * math.exp(-0.5 * x * x) * poly


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def calculate_prop_edge(prop: dict, player_stats: dict | None) -> dict | None:
    """Calculate edge for a single player prop using our projection vs the DK line.

    Model: player's recent average (last 10 games) vs DK line.
    Uses normal distribution to estimate probability of over/under.
    """
    stat_type = prop["stat_type"]
    line = prop["line"]
    sd = PROP_SD.get(stat_type, 0)

    if sd <= 0 or line <= 0:
        return None

    if not player_stats:
        return None

    avgs = player_stats.get("averages", {})
    if not avgs:
        return None

    # Compute our projection for this stat type
    our_projection = None

    if stat_type in PP_TO_ESPN:
        idx = PP_TO_ESPN[stat_type]
        our_projection = avgs.get(idx)
    elif stat_type in PP_COMBOS:
        indices = PP_COMBOS[stat_type]
        vals = [avgs.get(idx) for idx in indices]
        if all(v is not None for v in vals):
            our_projection = sum(vals)

    if our_projection is None:
        return None

    # Compare our projection to the line
    diff = our_projection - line  # positive = we think OVER

    if abs(diff) < 0.3:
        return None  # Too close to call

    # Convert to probability using normal distribution
    z = (line - our_projection) / sd
    over_prob = 1.0 - normal_cdf(z)
    under_prob = normal_cdf(z)

    # Determine which side to bet
    if diff > 0:
        pick_side = "over"
        model_prob = over_prob
        dk_odds = prop["over_odds"]
    else:
        pick_side = "under"
        model_prob = under_prob
        dk_odds = prop["under_odds"]

    implied = american_to_implied(dk_odds)
    edge = model_prob - implied

    if edge < MIN_PROP_EDGE:
        return None

    # Calculate Kelly sizing (1/4 Kelly for Medium tier)
    decimal_odds = 1 + 100 / abs(dk_odds) if dk_odds < 0 else 1 + dk_odds / 100
    kelly = (edge / (decimal_odds - 1)) * 0.25  # Quarter Kelly
    kelly = min(kelly, 0.035)  # 3.5% max per prop (matches game max)

    return {
        "sport": "NBA",
        "player": prop["player"],
        "team": prop.get("team", ""),
        "stat_type": stat_type,
        "pick": f"{prop['player']} {'OVER' if pick_side == 'over' else 'UNDER'} {line} {stat_type}",
        "line": line,
        "our_projection": round(our_projection, 1),
        "pick_side": pick_side,
        "odds": f"{dk_odds:+d}" if dk_odds > 0 else str(dk_odds),
        "implied": f"{implied*100:.1f}%",
        "model": f"{model_prob*100:.1f}%",
        "edge": round(edge * 100, 1),
        "tier": "Medium",
        "confidence": "MEDIUM",
        "kelly_pct": kelly,
        "notes": f"Last {player_stats['games_sampled']}g avg: {our_projection:.1f} {stat_type}. Line: {line}. Diff: {diff:+.1f}. DK odds: {dk_odds}. Model says {pick_side} at {model_prob*100:.1f}%.",
        "sources": "The Odds API (DK), ESPN",
        "market": "Player Prop",
        "event": prop.get("event", ""),
        "dk_link": "",
    }


# ── Main Scanner ──────────────────────────────────────────

def scan_props(sport: str = "nba", bankroll: float = 500.0, max_lookups: int = 30) -> list[dict]:
    """Scan player props using real DK odds and return edges.

    Flow:
    1. Fetch real DK prop odds from The Odds API
    2. For each player with props, fetch ESPN game log
    3. Calculate edge: our projection (10-game avg) vs DK line
    4. Return edges sorted by edge descending
    """
    print(f"  Fetching DK {sport.upper()} prop odds from The Odds API...")
    props = fetch_dk_prop_odds(sport, max_events=6)

    if not props:
        print("  No prop odds available")
        return []

    # Group by player, prioritize main stats
    by_player = {}
    for p in props:
        if p["stat_type"] in SUPPORTED_PROPS:
            name = p["player"]
            if name not in by_player:
                by_player[name] = []
            by_player[name].append(p)

    print(f"  {len(by_player)} players with supported prop lines")

    # Fetch stats for players (limit lookups to save ESPN rate limits)
    # Sort by highest points line — stars first
    def player_max_line(item):
        _, props_list = item
        return max((p["line"] for p in props_list if p["stat_type"] == "Points"), default=0)

    edges = []
    lookups = 0

    for player_name, player_props in sorted(by_player.items(), key=player_max_line, reverse=True):
        if lookups >= max_lookups:
            break

        # Find ESPN ID
        espn_id = find_espn_athlete_id(player_name)
        if not espn_id:
            continue
        lookups += 1

        # Fetch game log
        stats = fetch_player_recent_stats(espn_id, sport)
        if not stats:
            continue
        lookups += 1

        # Check each prop for this player
        for prop in player_props:
            edge = calculate_prop_edge(prop, stats)
            if edge:
                edges.append(edge)

        # Rate limit protection
        if lookups % 10 == 0:
            time.sleep(1)

    # Sort by edge descending
    edges.sort(key=lambda x: x["edge"], reverse=True)

    print(f"  Checked {lookups} ESPN lookups, found {len(edges)} prop edges")
    return edges


if __name__ == "__main__":
    print("=== Player Prop Edge Scanner (Real DK Odds) ===\n")
    edges = scan_props("nba", bankroll=570.57, max_lookups=20)
    print(f"\nFound {len(edges)} edges:")
    for e in edges[:10]:
        print(f"  {e['pick']} ({e['odds']}) — {e['edge']}% edge | Proj: {e['our_projection']}, Line: {e['line']}")
