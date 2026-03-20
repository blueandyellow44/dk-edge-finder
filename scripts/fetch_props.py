#!/usr/bin/env python3
"""
Player Prop Edge Scanner
Fetches projections from PrizePicks API, builds player-specific projections
using ESPN game logs, and flags edges where our projection disagrees with
the market line.

Props are Medium confidence tier: 5% min edge, 1/4 Kelly.
"""

import json
import math
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone


# ── PrizePicks API ────────────────────────────────────────

NBA_TEAMS = {
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NO", "NY",
    "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SA", "TOR", "UTAH", "WSH",
}


def fetch_prizepicks_projections(sport: str = "nba") -> list[dict]:
    """Fetch today's player prop projections from PrizePicks.

    Retries once after 10s on rate limit (429).
    Filters to NBA teams only to exclude college/G-League.
    """
    url = f"https://api.prizepicks.com/projections?sport={sport}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })

    data = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                print(f"  PrizePicks rate limited, retrying in 10s...")
                time.sleep(10)
                continue
            print(f"  PrizePicks fetch error: {e}")
            return []
        except Exception as e:
            print(f"  PrizePicks fetch error: {e}")
            return []

    if not data:
        return []

    projections = data.get("data", [])
    included = {}
    for item in data.get("included", []):
        key = f"{item['type']}_{item['id']}"
        included[key] = item.get("attributes", {})

    props = []
    for proj in projections:
        attrs = proj.get("attributes", {})
        if not attrs.get("today"):
            continue

        stat_type = attrs.get("stat_type", "")
        line = attrs.get("line_score")
        if line is None or stat_type not in SUPPORTED_PROPS:
            continue

        rels = proj.get("relationships", {})
        player_id = rels.get("new_player", {}).get("data", {}).get("id", "")
        player_info = included.get(f"new_player_{player_id}", {})

        player_name = player_info.get("display_name") or player_info.get("name", "Unknown")
        team = player_info.get("team", "")
        position = player_info.get("position", "")

        # Filter to NBA teams only (skip college, G-League, etc.)
        if sport == "nba" and team and team.upper() not in NBA_TEAMS:
            continue

        odds_type = attrs.get("odds_type", "standard")
        if odds_type == "demon":
            over_odds, under_odds = -105, -115
        elif odds_type == "goblin":
            over_odds, under_odds = -120, 100
        else:
            over_odds, under_odds = -110, -110

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


# ── ESPN Player Stats ─────────────────────────────────────

# Map PrizePicks stat names to ESPN gamelog column indices
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

    # ESPN search endpoint
    query = urllib.parse.quote(player_name)
    url = f"https://site.api.espn.com/apis/common/v3/search?query={query}&limit=5&type=player"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = data.get("results", []) or data.get("items", [])
        if not results:
            # Try alternate structure
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


import urllib.parse


def fetch_player_recent_stats(athlete_id: str, sport: str = "nba", n_games: int = 10) -> dict | None:
    """Fetch player's recent game log from ESPN and compute averages.

    Returns dict with average stats over last n_games, or None if unavailable.
    """
    sport_path = {"nba": "basketball/nba", "nhl": "hockey/nhl", "mlb": "baseball/mlb"}.get(sport)
    if not sport_path:
        return None

    url = f"https://site.api.espn.com/apis/common/v3/sports/{sport_path}/athletes/{athlete_id}/gamelog"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    # Collect all regular season game stats
    all_stats = []
    for season_type in data.get("seasonTypes", []):
        if "Regular" not in season_type.get("displayName", ""):
            continue
        for cat in season_type.get("categories", []):
            for event in cat.get("events", []):
                stats = event.get("stats", [])
                if stats and len(stats) >= 14:  # Full stat line
                    all_stats.append(stats)

    if not all_stats:
        return None

    # Take last n_games
    recent = all_stats[:n_games]

    # Compute averages for each stat
    def parse_stat(val, idx):
        """Parse a stat value — handle 'made-attempted' format for FG/3PT/FT."""
        if idx in (1, 3, 5):  # FG, 3PT, FT (made-attempted)
            parts = str(val).split("-")
            return float(parts[0]) if parts else 0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0

    averages = {}
    for idx in range(14):
        vals = [parse_stat(g[idx], idx) for g in recent if len(g) > idx]
        if vals:
            averages[idx] = sum(vals) / len(vals)

    return {
        "games_sampled": len(recent),
        "averages": averages,
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
    "Shots On Goal": 1.5,
    "Goalie Saves": 8.0,
    "Goals": 0.8,
    "Power Play Points": 0.7,
    "Pitcher Strikeouts": 2.0,
    "Hits": 1.0,
    "Total Bases": 1.5,
    "Home Runs": 0.5,
    "RBIs": 1.0,
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
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def calculate_prop_edge(prop: dict, player_stats: dict | None) -> dict | None:
    """Calculate edge for a single player prop using our projection vs the line.

    Model: player's recent average (last 10 games) vs PrizePicks line.
    If our average differs from the line by enough (relative to SD), flag the edge.
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

    if abs(diff) < 0.5:
        return None  # Too close to call

    # Convert to probability using normal distribution
    # P(actual > line) = P(Z > (line - projection) / SD) = 1 - Phi((line - proj) / SD)
    z = (line - our_projection) / sd
    over_prob = 1.0 - normal_cdf(z)
    under_prob = normal_cdf(z)

    # Determine which side to bet
    if diff > 0:
        # We think OVER
        pick_side = "over"
        model_prob = over_prob
        dk_odds = prop["over_odds"]
    else:
        # We think UNDER
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
    kelly = min(kelly, 0.03)  # 3% max per prop

    return {
        "sport": "NBA",
        "player": prop["player"],
        "team": prop["team"],
        "stat_type": stat_type,
        "pick": f"{prop['player']} {'OVER' if pick_side == 'over' else 'UNDER'} {line} {stat_type}",
        "line": line,
        "our_projection": round(our_projection, 1),
        "pick_side": pick_side,
        "odds": str(dk_odds),
        "implied": f"{implied*100:.1f}%",
        "model": f"{model_prob*100:.1f}%",
        "edge": round(edge * 100, 1),
        "tier": "Medium",
        "confidence": "MEDIUM",
        "kelly_pct": kelly,
        "notes": f"Last {player_stats['games_sampled']}g avg: {our_projection:.1f} {stat_type}. Line: {line}. Diff: {diff:+.1f}. Model says {pick_side} at {model_prob*100:.1f}%.",
        "sources": "PrizePicks, ESPN",
        "market": "Player Prop",
        "event": prop.get("description", ""),
    }


# ── Main Scanner ──────────────────────────────────────────

def scan_props(sport: str = "nba", bankroll: float = 500.0, max_lookups: int = 30) -> list[dict]:
    """Scan player props and return edges.

    Limits ESPN lookups to max_lookups to avoid rate limiting.
    Prioritizes highest-volume stat types (points, rebounds, assists).
    """
    print(f"  Fetching PrizePicks {sport.upper()} props...")
    props = fetch_prizepicks_projections(sport)
    print(f"  Found {len(props)} props ({sum(1 for p in props if p['stat_type'] in SUPPORTED_PROPS)} supported)")

    if not props:
        return []

    # Group by player, prioritize main stats
    by_player = {}
    priority_stats = ["Points", "Rebounds", "Assists", "3-PT Made", "Pts+Rebs+Asts"]
    for p in props:
        if p["stat_type"] in priority_stats:
            name = p["player"]
            if name not in by_player:
                by_player[name] = []
            by_player[name].append(p)

    # Fetch stats for top players (limit lookups)
    # Sort by highest points line — stars first, better chance of finding edges
    def player_max_line(item):
        _, props_list = item
        return max((p["line"] for p in props_list if p["stat_type"] == "Points"), default=0)

    edges = []
    lookups = 0
    player_stats_cache = {}

    for player_name, player_props in sorted(by_player.items(), key=player_max_line, reverse=True):
        if lookups >= max_lookups:
            break

        # Find ESPN ID (1 API call)
        espn_id = find_espn_athlete_id(player_name)
        if not espn_id:
            continue
        lookups += 1

        # Fetch game log (1 API call)
        stats = fetch_player_recent_stats(espn_id, sport)
        if not stats:
            continue
        lookups += 1
        player_stats_cache[player_name] = stats

        # For each stat type, find the main line (closest to player's average)
        # then calculate edge only on that line. Alt lines are noise.
        by_stat = {}
        for prop in player_props:
            st = prop["stat_type"]
            if st not in by_stat:
                by_stat[st] = []
            by_stat[st].append(prop)

        for st, stat_props in by_stat.items():
            # Get our projection for this stat
            proj = None
            if st in PP_TO_ESPN:
                proj = stats["averages"].get(PP_TO_ESPN[st])
            elif st in PP_COMBOS:
                vals = [stats["averages"].get(idx) for idx in PP_COMBOS[st]]
                if all(v is not None for v in vals):
                    proj = sum(vals)
            if proj is None:
                continue

            # Pick the line closest to our projection (the "main" DK-style line)
            main_prop = min(stat_props, key=lambda p: abs(p["line"] - proj))

            edge = calculate_prop_edge(main_prop, stats)
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
    print("=== Player Prop Edge Scanner ===\n")
    edges = scan_props("nba", bankroll=585.67, max_lookups=20)
    print(f"\nFound {len(edges)} edges:")
    for e in edges[:10]:
        print(f"  {e['pick']} ({e['odds']}) — {e['edge']}% edge | Proj: {e['our_projection']}, Line: {e['line']}")
