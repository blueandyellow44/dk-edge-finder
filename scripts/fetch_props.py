#!/usr/bin/env python3
"""
Player Prop Edge Scanner
Fetches projections from PrizePicks API, compares to our model, flags edges.

PrizePicks lines correlate closely with DraftKings. We use them as a proxy
since DK has no public prop API.

Props are Medium confidence tier: 5% min edge, 1/4 Kelly.
"""

import json
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone


def fetch_prizepicks_projections(sport: str = "nba") -> list[dict]:
    """Fetch today's player prop projections from PrizePicks.

    Returns flat list of props with player name, stat type, line, and game info.
    """
    sport_map = {"nba": "nba", "nhl": "nhl", "mlb": "mlb", "nfl": "nfl"}
    pp_sport = sport_map.get(sport.lower())
    if not pp_sport:
        return []

    url = f"https://api.prizepicks.com/projections?sport={pp_sport}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  PrizePicks fetch error: {e}")
        return []

    # Parse the JSONAPI structure
    projections = data.get("data", [])

    # Build lookup for included resources (players, games, etc.)
    included = {}
    for item in data.get("included", []):
        key = f"{item['type']}_{item['id']}"
        included[key] = item.get("attributes", {})

    props = []
    for proj in projections:
        attrs = proj.get("attributes", {})
        if not attrs.get("today"):
            continue  # Skip non-today props

        stat_type = attrs.get("stat_type", "")
        line = attrs.get("line_score")
        odds_type = attrs.get("odds_type", "standard")

        if line is None:
            continue

        # Get player info from relationships
        rels = proj.get("relationships", {})
        player_id = rels.get("new_player", {}).get("data", {}).get("id", "")
        player_info = included.get(f"new_player_{player_id}", {})

        player_name = player_info.get("display_name") or player_info.get("name", "Unknown")
        team = player_info.get("team", "")
        position = player_info.get("position", "")

        # Infer odds from odds_type
        # standard ≈ -110 both sides, demon ≈ -105/-115, goblin ≈ -120/-100
        if odds_type == "demon":
            over_odds = -105
            under_odds = -115
        elif odds_type == "goblin":
            over_odds = -120
            under_odds = 100
        else:  # standard
            over_odds = -110
            under_odds = -110

        props.append({
            "player": player_name,
            "team": team,
            "position": position,
            "stat_type": stat_type,
            "line": float(line),
            "over_odds": over_odds,
            "under_odds": under_odds,
            "odds_type": odds_type,
            "start_time": attrs.get("start_time", ""),
            "description": attrs.get("description", ""),
        })

    return props


# Standard deviations for player prop outcomes
# These are approximate and based on NBA/NHL historical variance
PROP_SD = {
    # NBA — roughly 20-25% of the line value
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
    # NHL
    "Shots On Goal": 1.5,
    "Goalie Saves": 8.0,
    "Goals": 0.8,
    "Power Play Points": 0.7,
    # MLB
    "Pitcher Strikeouts": 2.0,
    "Hits": 1.0,
    "Total Bases": 1.5,
    "Home Runs": 0.5,
    "RBIs": 1.0,
}

# Stat types we can model (have SD values for)
SUPPORTED_PROPS = set(PROP_SD.keys())

# Minimum edge to flag (Medium tier = 5%)
MIN_PROP_EDGE = 0.05


def calculate_prop_edge(prop: dict) -> dict | None:
    """Calculate edge for a single player prop.

    Simple model: PrizePicks line IS the market consensus projection.
    We look for mispricing in the odds, not the line.

    For now, we flag props where:
    1. The stat type has a known SD
    2. The odds imply a probability significantly different from 50%
       (e.g., demon lines where one side is -105)
    3. We can identify obvious over/under bias

    Future: add player-specific projections using season averages + opponent adjustment.
    """
    stat_type = prop.get("stat_type", "")
    if stat_type not in SUPPORTED_PROPS:
        return None

    line = prop.get("line", 0)
    if line <= 0:
        return None

    sd = PROP_SD.get(stat_type, 0)
    if sd <= 0:
        return None

    # For now, simple approach: if the line seems off from typical,
    # or if odds type gives us a small edge, flag it.
    # This is a placeholder until we build player-specific projections.

    # With odds_type "demon" (-105/-115), over has slight edge:
    # implied_over = 105/205 = 51.2%, implied_under = 115/215 = 53.5%
    # Market believes under is slightly more likely.
    # If we think it's 50/50, over has +1.2% edge (below threshold)

    # Without player-specific projections, we can't flag real edges yet.
    # Return the prop data formatted for future use.
    return None  # TODO: implement when we have player projections


def fetch_and_summarize(sport: str = "nba") -> dict:
    """Fetch props and return a summary for the dashboard."""
    props = fetch_prizepicks_projections(sport)

    # Filter to supported stat types
    supported = [p for p in props if p["stat_type"] in SUPPORTED_PROPS]

    # Group by stat type
    by_type = {}
    for p in supported:
        st = p["stat_type"]
        if st not in by_type:
            by_type[st] = []
        by_type[st].append(p)

    return {
        "sport": sport,
        "total_props": len(props),
        "supported_props": len(supported),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "props": supported,
    }


if __name__ == "__main__":
    print("=== PrizePicks Player Props ===")
    for sport in ["nba", "nhl"]:
        print(f"\n{sport.upper()}:")
        summary = fetch_and_summarize(sport)
        print(f"  Total: {summary['total_props']}, Supported: {summary['supported_props']}")
        print(f"  By type: {summary['by_type']}")
        # Show first 3 props
        for p in summary["props"][:3]:
            print(f"  {p['player']} ({p['team']}): {p['stat_type']} {p['line']} [{p['odds_type']}]")
