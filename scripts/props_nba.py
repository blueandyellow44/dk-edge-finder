#!/usr/bin/env python3
from __future__ import annotations
"""NBA player-prop plugin for the props_kernel.

Owns:
  - NBA-specific Odds API market keys, ESPN URL templates, gamelog column map
  - Standard deviations and combo definitions
  - The opponent-defense projection adjustment (PPG-allowed deviation from
    league average, capped at ±8%)
  - The blowout prob adjustment (predicted margin > 12pt → 15% discount on
    OVER picks; UNDER picks unaffected, since blowouts help unders)

See props_kernel.py for the plugin contract.
"""

import json
import urllib.error
import urllib.request

from props_kernel import standard_gamelog_rows


# ── Plugin contract: constants ────────────────────────────

SPORT = "nba"
SPORT_DISPLAY = "NBA"
ODDS_API_SPORT_KEY = "basketball_nba"

PROP_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
]

# Markets we could add if credit budget allows. Not currently requested.
EXTRA_MARKETS = [
    "player_points_rebounds_assists",
    "player_steals",
    "player_blocks",
]

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

COMBOS = {
    "Pts+Rebs": ["Points", "Rebounds"],
    "Pts+Asts": ["Points", "Assists"],
    "Rebs+Asts": ["Rebounds", "Assists"],
    "Pts+Rebs+Asts": ["Points", "Rebounds", "Assists"],
}

# Distribution per stat (2026-07-09). NBA was left on the legacy normal-CDF
# path when the Poisson kernel shipped for MLB/soccer (2026-06-09), and the
# June Finals window showed exactly the predicted failure: 8 straight losses
# on low-count props (Rebounds 3.5, Assists 3.5, 3-PT Made 1.5) carrying
# 75-83% claimed probabilities at the 15% edge cap. Low-count NBA stats are
# Poisson territory; a Gaussian at lambda ~2-4 leaks mass below 0 and
# overstates the favorite side. Points and the combo stats stay normal: at
# lambda ~15-35 the normal approximation is fine and Poisson's variance=mean
# is far too tight for scoring (PROP_SD has Points at 8.0, Poisson would
# imply ~4.5), and combos are sums of correlated stats, not one count.
DEFAULT_DIST = "poisson"
STAT_DIST = {
    "Points": "normal",
    "Pts+Rebs": "normal",
    "Pts+Asts": "normal",
    "Rebs+Asts": "normal",
    "Pts+Rebs+Asts": "normal",
}

MIN_EDGE = 0.05         # Medium tier: 5% min
MAX_EDGE = 0.15         # Cap at 15%. Anything higher is model overconfidence.
KELLY_FRACTION = 0.25   # 1/4 Kelly for Medium tier
KELLY_CAP = 0.02        # 2% max per prop (matches game max)

TIER = "Medium"
CONFIDENCE = "MEDIUM"

NEEDS_PLAYER_TEAM = True  # opponent defense lookup needs the player's team


# ── ESPN URL builders ─────────────────────────────────────

def gamelog_url(athlete_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/gamelog"


def athlete_url(athlete_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}"


# ── Gamelog row parser ────────────────────────────────────

# ESPN order: MIN, FG, FG%, 3PT, 3P%, FT, FT%, REB, AST, BLK, STL, PF, TO, PTS
_PP_TO_ESPN_IDX = {
    "Points": 13,         # PTS
    "Rebounds": 7,        # REB
    "Assists": 8,         # AST
    "3-PT Made": 3,       # 3PT (made-attempted, e.g. "3-7")
    "Steals": 10,         # STL
    "Blocked Shots": 9,   # BLK
    "Turnovers": 12,      # TO
}


def _parse_stat_val(raw) -> float | None:
    """Parse one ESPN stat value. '3-7' → 3 (made), '28' → 28.0."""
    try:
        if isinstance(raw, str) and "-" in raw:
            return float(raw.split("-")[0])
        return float(raw)
    except (ValueError, TypeError):
        return None


def parse_gamelog_row(stats_list: list) -> dict[str, float]:
    """Translate a single ESPN gamelog row into {stat_label: value}.

    Returns {} if the row is shorter than the highest column we need (14
    columns). That filters preseason / split rows that lack full columns.
    """
    if not stats_list or len(stats_list) < 14:
        return {}

    out: dict[str, float] = {}
    for label, idx in _PP_TO_ESPN_IDX.items():
        if idx < len(stats_list):
            v = _parse_stat_val(stats_list[idx])
            if v is not None:
                out[label] = v
    return out


extract_gamelog_rows = standard_gamelog_rows


# ── Event string parsing ──────────────────────────────────

# ESPN team-abbreviation lookup (Odds API full names → ESPN abbr).
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
    return _TEAM_NAME_TO_ABBR.get(name.lower().strip())


def event_to_team_abbrs(event_str: str) -> tuple[str | None, str | None]:
    """Parse 'Away @ Home' (Odds API full names) into (away_abbr, home_abbr)."""
    parts = event_str.split(" @ ")
    if len(parts) != 2:
        return (None, None)
    away_name, home_name = parts[0].strip(), parts[1].strip()
    return (_team_name_to_abbr(away_name), _team_name_to_abbr(home_name))


# ── Opponent defensive rating (projection adjustment) ─────
# Adjusts projection by opponent PPG allowed vs league average, capped at ±8%.

LEAGUE_AVG_PPG_ALLOWED = 112.0
MAX_DEF_ADJUSTMENT = 0.08

# Session-level cache: team_abbr → avgPointsAgainst
_defense_cache: dict[str, float | None] = {}


def fetch_team_defensive_rating(team_abbr: str) -> float | None:
    """Fetch a team's average points allowed per game from ESPN. Cached."""
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


def _get_defense_multiplier(opponent_abbr: str) -> tuple[float, str]:
    """Return (projection_multiplier, note_string) for opponent defense.

    multiplier > 1.0 = bad defense → boost projection
    multiplier < 1.0 = good defense → discount projection
    multiplier == 1.0 = average defense or unknown
    """
    ppg_allowed = fetch_team_defensive_rating(opponent_abbr)
    if ppg_allowed is None:
        return 1.0, ""

    diff_pct = (ppg_allowed - LEAGUE_AVG_PPG_ALLOWED) / LEAGUE_AVG_PPG_ALLOWED
    adj = max(-MAX_DEF_ADJUSTMENT, min(MAX_DEF_ADJUSTMENT, diff_pct))

    if abs(adj) < 0.01:
        return 1.0, ""

    multiplier = 1.0 + adj
    direction = "boost" if adj > 0 else "discount"
    note = f"vs {opponent_abbr} ({ppg_allowed:.1f} PPG allowed, {direction} {abs(adj)*100:.1f}%)"
    return multiplier, note


# ── Blowout discount (prob adjustment) ────────────────────
# When the predicted absolute margin exceeds BLOWOUT_MARGIN, starters sit and
# OVER picks suffer. UNDER picks actually benefit from blowouts, so we only
# discount the over side.

BLOWOUT_MARGIN = 12
BLOWOUT_DISCOUNT = 0.85


# ── Plugin hooks: projection and prob adjustments ────────

def compute_projection_adjustment(prop, projection, context) -> tuple[float, list[str]]:
    """NBA: opponent-defense projection multiplier."""
    opponent_abbr = context.get("opponent_abbr")
    if not opponent_abbr:
        return 1.0, []

    mult, note = _get_defense_multiplier(opponent_abbr)
    notes = [f"Def adj: {note}"] if note else []
    return mult, notes


def compute_prob_adjustment(prop, pick_side, context) -> tuple[float, list[str]]:
    """NBA: blowout discount on OVER picks when predicted margin > 12pt."""
    if pick_side != "over":
        return 1.0, []

    game_margins = context.get("game_margins") or {}
    event_str = context.get("event_str", "")

    margin = 0.0
    for key, val in game_margins.items():
        if key and event_str and (key in event_str or event_str in key):
            margin = val
            break

    if margin <= BLOWOUT_MARGIN:
        return 1.0, []

    note = f"Blowout risk ({margin:.0f}pt margin): -15% adj"
    return BLOWOUT_DISCOUNT, [note]
