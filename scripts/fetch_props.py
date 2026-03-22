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
# Player team cache (ESPN ID → team abbreviation)
_player_team_cache: dict[str, str] = {}


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


def fetch_player_team(athlete_id: str) -> str | None:
    """Fetch a player's current team abbreviation from ESPN.

    Uses the common athlete endpoint. Cached per session.
    Returns team abbreviation (e.g. 'OKC', 'LAL') or None.
    """
    if athlete_id in _player_team_cache:
        return _player_team_cache[athlete_id]

    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        team_abbr = data.get("athlete", {}).get("team", {}).get("abbreviation")
        if team_abbr:
            _player_team_cache[athlete_id] = team_abbr
            return team_abbr
    except Exception:
        pass

    _player_team_cache[athlete_id] = ""
    return None


def _parse_stat_val(raw) -> float | None:
    """Parse a single ESPN stat value. '3-7' → 3 (made), '28' → 28.0."""
    try:
        if isinstance(raw, str) and "-" in raw:
            return float(raw.split("-")[0])
        return float(raw)
    except (ValueError, TypeError):
        return None


def fetch_player_recent_stats(athlete_id: str, sport: str = "nba", n_games: int = 10) -> dict | None:
    """Fetch player's recent game log from ESPN and compute weighted averages.

    Weighting: last 3 games get 50% weight, previous 7 get 50%.
    Also computes per-stat standard deviations from actual player data.
    """
    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/gamelog"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    # Parse game log — structure: seasonTypes[].categories[].events[]
    rows = []
    for st in data.get("seasonTypes", []):
        if "preseason" in st.get("displayName", "").lower():
            continue
        for cat in st.get("categories", []):
            for event_row in cat.get("events", []):
                stats_list = event_row.get("stats", [])
                if stats_list and len(stats_list) >= 14:
                    rows.append(stats_list)

    if not rows:
        return None

    recent = rows[:n_games]

    # Compute weighted averages and actual standard deviations
    # Weighting: last 3 games = 50%, previous games = 50%
    averages = {}
    actual_sds = {}

    for idx in list(PP_TO_ESPN.values()):
        vals = []
        for row in recent:
            raw = row[idx] if idx < len(row) else "0"
            v = _parse_stat_val(raw)
            if v is not None:
                vals.append(v)

        if not vals:
            continue

        # Weighted average: recent 3 games get 50% weight, older games get 50%
        if len(vals) >= 5:
            recent_3 = vals[:3]
            older = vals[3:]
            recent_avg = sum(recent_3) / len(recent_3)
            older_avg = sum(older) / len(older)
            weighted_avg = recent_avg * 0.5 + older_avg * 0.5
        else:
            # Not enough games for split — use flat average
            weighted_avg = sum(vals) / len(vals)

        averages[idx] = round(weighted_avg, 2)

        # Compute actual SD from player's game-to-game variance
        if len(vals) >= 3:
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            actual_sds[idx] = round(variance ** 0.5, 2)

    # Also store flat averages for notes (show both weighted and flat)
    flat_averages = {}
    for idx in list(PP_TO_ESPN.values()):
        vals = []
        for row in recent:
            raw = row[idx] if idx < len(row) else "0"
            v = _parse_stat_val(raw)
            if v is not None:
                vals.append(v)
        if vals:
            flat_averages[idx] = round(sum(vals) / len(vals), 2)

    return {
        "averages": averages,
        "flat_averages": flat_averages,
        "actual_sds": actual_sds,
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
MAX_PROP_EDGE = 0.15  # Cap at 15% — anything higher is model overconfidence
BLOWOUT_MARGIN = 12   # Games predicted to have >12pt margin get a prop discount
BLOWOUT_DISCOUNT = 0.85  # Reduce model_prob by 15% in blowouts (starters sit)


# ── Opponent Defensive Rating ─────────────────────────────
# Adjusts player projections based on how many points the opponent allows.
# League average PPG allowed ≈ 112 (2025-26 season).
# Good defenses (< 108) make it harder for players → discount projection.
# Bad defenses (> 116) make it easier → boost projection.
# The adjustment is capped at ±8% to avoid overreacting.

LEAGUE_AVG_PPG_ALLOWED = 112.0
MAX_DEF_ADJUSTMENT = 0.08  # Cap at ±8% multiplier

# Session-level cache: team_abbr → avgPointsAgainst
_defense_cache: dict[str, float | None] = {}

# ESPN team abbreviation normalization (Odds API names → ESPN abbr)
_TEAM_NAME_TO_ABBR = {
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN",
    "charlotte hornets": "CHA", "chicago bulls": "CHI", "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL", "denver nuggets": "DEN", "detroit pistons": "DET",
    "golden state warriors": "GS", "houston rockets": "HOU", "indiana pacers": "IND",
    "los angeles clippers": "LAC", "los angeles lakers": "LAL", "memphis grizzlies": "MEM",
    "miami heat": "MIA", "milwaukee bucks": "MIL", "minnesota timberwolves": "MIN",
    "new orleans pelicans": "NO", "new york knicks": "NY", "oklahoma city thunder": "OKC",
    "orlando magic": "ORL", "philadelphia 76ers": "PHI", "phoenix suns": "PHX",
    "portland trail blazers": "POR", "sacramento kings": "SAC", "san antonio spurs": "SA",
    "toronto raptors": "TOR", "utah jazz": "UTAH", "washington wizards": "WSH",
}


def _team_name_to_abbr(name: str) -> str | None:
    """Convert full team name to ESPN abbreviation."""
    return _TEAM_NAME_TO_ABBR.get(name.lower().strip())


def fetch_team_defensive_rating(team_abbr: str) -> float | None:
    """Fetch a team's average points allowed per game from ESPN.

    Returns avgPointsAgainst or None if unavailable. Cached per session.
    """
    if team_abbr in _defense_cache:
        return _defense_cache[team_abbr]

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_abbr}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        team = data.get("team", {})
        record = team.get("record", {})
        for item in record.get("items", []):
            if item.get("type") == "total":
                for stat in item.get("stats", []):
                    if stat.get("name") == "avgPointsAgainst":
                        ppg = float(stat["value"])
                        _defense_cache[team_abbr] = ppg
                        return ppg
    except Exception:
        pass

    _defense_cache[team_abbr] = None
    return None


def get_defense_multiplier(opponent_abbr: str) -> tuple[float, str]:
    """Get a projection multiplier based on opponent defensive strength.

    Returns (multiplier, note_string).
    multiplier > 1.0 = bad defense (boost projection)
    multiplier < 1.0 = good defense (discount projection)
    multiplier == 1.0 = average defense or unknown
    """
    ppg_allowed = fetch_team_defensive_rating(opponent_abbr)
    if ppg_allowed is None:
        return 1.0, ""

    # How far from league average? Positive = bad defense, negative = good defense
    diff_pct = (ppg_allowed - LEAGUE_AVG_PPG_ALLOWED) / LEAGUE_AVG_PPG_ALLOWED

    # Cap the adjustment
    adj = max(-MAX_DEF_ADJUSTMENT, min(MAX_DEF_ADJUSTMENT, diff_pct))

    if abs(adj) < 0.01:
        return 1.0, ""

    multiplier = 1.0 + adj
    direction = "boost" if adj > 0 else "discount"
    note = f"vs {opponent_abbr} ({ppg_allowed:.1f} PPG allowed, {direction} {abs(adj)*100:.1f}%)"
    return multiplier, note


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


def calculate_prop_edge(prop: dict, player_stats: dict | None, game_margin: float = 0.0,
                        defense_multiplier: float = 1.0, defense_note: str = "") -> dict | None:
    """Calculate edge for a single player prop using improved model.

    Improvements over v1:
    1. Weighted recency: last 3 games = 50%, previous 7 = 50%
    2. Uses player's actual SD when available (falls back to hardcoded)
    3. Blowout discount: reduces model_prob when predicted margin >12
    4. Edge cap at 15%: prevents overconfident bets
    5. Sample size penalty: widens SD when <7 games available
    6. Opponent defensive rating: adjusts projection based on opponent PPG allowed

    Args:
        prop: DK prop odds dict
        player_stats: ESPN gamelog stats with weighted averages + actual SDs
        game_margin: predicted absolute margin (from DRatings/Dimers). 0 = unknown.
        defense_multiplier: opponent defense adjustment (>1.0 = bad defense, <1.0 = good)
        defense_note: human-readable note about the defense adjustment
    """
    stat_type = prop["stat_type"]
    line = prop["line"]
    fallback_sd = PROP_SD.get(stat_type, 0)

    if fallback_sd <= 0 or line <= 0:
        return None

    if not player_stats:
        return None

    avgs = player_stats.get("averages", {})
    actual_sds = player_stats.get("actual_sds", {})
    flat_avgs = player_stats.get("flat_averages", {})
    games_sampled = player_stats.get("games_sampled", 0)

    if not avgs:
        return None

    # Compute our projection for this stat type (already weighted by recency)
    our_projection = None
    flat_projection = None

    if stat_type in PP_TO_ESPN:
        idx = PP_TO_ESPN[stat_type]
        our_projection = avgs.get(idx)
        flat_projection = flat_avgs.get(idx)
        player_sd = actual_sds.get(idx)
    elif stat_type in PP_COMBOS:
        indices = PP_COMBOS[stat_type]
        vals = [avgs.get(idx) for idx in indices]
        flat_vals = [flat_avgs.get(idx) for idx in indices]
        if all(v is not None for v in vals):
            our_projection = sum(vals)
        if all(v is not None for v in flat_vals):
            flat_projection = sum(flat_vals)
        # Sum of SDs (conservative: assume correlation)
        sd_vals = [actual_sds.get(idx) for idx in indices]
        if all(v is not None for v in sd_vals):
            player_sd = sum(sd_vals)
        else:
            player_sd = None
    else:
        player_sd = None

    if our_projection is None:
        return None

    # Apply opponent defensive rating adjustment to projection
    # Bad defense (mult > 1.0) = player likely scores more → boost projection
    # Good defense (mult < 1.0) = player likely scores less → discount projection
    if defense_multiplier != 1.0:
        our_projection = round(our_projection * defense_multiplier, 2)

    # Use player's actual SD if available, else fall back to hardcoded
    # Apply sample size penalty: widen SD by 25% when <7 games sampled
    sd = player_sd if player_sd and player_sd > 0 else fallback_sd
    if games_sampled < 7:
        sd *= 1.25  # Less data = wider distribution = less confidence

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

    # ── Apply adjustments ──
    adjustments = []

    # Opponent defensive rating (already applied to projection above)
    if defense_note:
        adjustments.append(f"Def adj: {defense_note}")

    # Blowout discount: starters sit in garbage time of blowouts
    # Only discount OVER bets — UNDER bets actually benefit from blowouts
    if game_margin > BLOWOUT_MARGIN and pick_side == "over":
        model_prob *= BLOWOUT_DISCOUNT
        adjustments.append(f"Blowout risk ({game_margin:.0f}pt margin): -15% adj")

    # Calculate raw edge
    implied = american_to_implied(dk_odds)
    raw_edge = model_prob - implied

    # Cap edge at MAX_PROP_EDGE — anything higher is model overconfidence
    if raw_edge > MAX_PROP_EDGE:
        capped_edge = MAX_PROP_EDGE
        adjustments.append(f"Edge capped: {raw_edge*100:.1f}% → {capped_edge*100:.1f}%")
        edge = capped_edge
    else:
        edge = raw_edge

    if edge < MIN_PROP_EDGE:
        return None

    # Calculate Kelly sizing (1/4 Kelly for Medium tier)
    decimal_odds = 1 + 100 / abs(dk_odds) if dk_odds < 0 else 1 + dk_odds / 100
    kelly = (edge / (decimal_odds - 1)) * 0.25  # Quarter Kelly
    kelly = min(kelly, 0.02)  # 2% max per prop (matches game max)

    # Build notes
    flat_note = f"Flat avg: {flat_projection:.1f}" if flat_projection and abs(flat_projection - our_projection) > 0.2 else ""
    sd_note = f"SD: {sd:.1f}" + (" (player)" if player_sd else " (default)")
    adj_note = " | ".join(adjustments) if adjustments else ""

    notes = f"Weighted {games_sampled}g avg: {our_projection:.1f} {stat_type}. {flat_note+'. ' if flat_note else ''}Line: {line}. Diff: {diff:+.1f}. {sd_note}. DK odds: {dk_odds}. Model says {pick_side} at {model_prob*100:.1f}%.{' | ' + adj_note if adj_note else ''}"

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
        "edge_raw": edge,
        "tier": "Medium",
        "confidence": "MEDIUM",
        "kelly_pct": kelly,
        "notes": notes,
        "sources": "The Odds API (DK), ESPN",
        "market": "Player Prop",
        "event": prop.get("event", ""),
        "dk_link": "",
    }


# ── Main Scanner ──────────────────────────────────────────

def scan_props(sport: str = "nba", bankroll: float = 500.0, max_lookups: int = 30,
               game_margins: dict | None = None) -> list[dict]:
    """Scan player props using real DK odds and return edges.

    Flow:
    1. Fetch real DK prop odds from The Odds API
    2. For each player with props, fetch ESPN game log
    3. Calculate edge: weighted projection vs DK line (with adjustments)
    4. Return edges sorted by edge descending

    Args:
        game_margins: dict mapping event strings to predicted absolute margin
                      e.g. {"Los Angeles Lakers @ Orlando Magic": 15.2}
                      Used for blowout discount on props.
    """
    if game_margins is None:
        game_margins = {}

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

        # Fetch player's team to determine opponent for defensive adjustment
        player_team_abbr = fetch_player_team(espn_id)

        # Check each prop for this player
        for prop in player_props:
            # Look up predicted game margin for blowout discount
            event_str = prop.get("event", "")
            margin = 0.0
            for key, val in game_margins.items():
                if key and event_str and (key in event_str or event_str in key):
                    margin = val
                    break

            # Determine opponent team for defensive rating adjustment
            def_mult, def_note = 1.0, ""
            if player_team_abbr and event_str:
                # Event format: "Away Team @ Home Team" (full names from Odds API)
                # Identify opponent: if player is on the away team, opponent is home (and vice versa)
                parts = event_str.split(" @ ")
                if len(parts) == 2:
                    away_name, home_name = parts[0].strip(), parts[1].strip()
                    away_abbr = _team_name_to_abbr(away_name)
                    home_abbr = _team_name_to_abbr(home_name)
                    if player_team_abbr == away_abbr and home_abbr:
                        def_mult, def_note = get_defense_multiplier(home_abbr)
                    elif player_team_abbr == home_abbr and away_abbr:
                        def_mult, def_note = get_defense_multiplier(away_abbr)

            edge = calculate_prop_edge(prop, stats, game_margin=margin,
                                       defense_multiplier=def_mult, defense_note=def_note)
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
