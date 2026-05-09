#!/usr/bin/env python3
from __future__ import annotations
"""Soccer player-prop plugin factory.

Builds six per-league plugin instances (MLS, EPL, La Liga, Bundesliga,
Serie A, UCL) sharing the same prop markets, SD baselines, and gamelog
parser. Each league differs only in its Odds API sport key and its ESPN
URL slug.

Phase A scope: Shots and Shots on Target. ESPN's per-game player stats
for soccer live in /athletes/{id}/overview at gameLog.statistics[0]
.events[].stats[] (a different shape from US sports), so this plugin
overrides extract_gamelog_rows. The endpoint returns the most recent
~5 events per player; the kernel handles short windows but projections
are noisier than for US sports until a season is far enough along.

Excluded from Phase A:
  - Anytime goalscorer / score 2+: binary markets, kernel only handles
    over/under.
  - Goals and Assists over/under: lines are typically 0.5 and outcomes
    are sparse (most players get 0); essentially binary in practice.
  - Cards / fouls / passes: niche markets, less consistent DK pricing.
  - Per-league defense angles (xGA, opponent strength): per scope
    decision 2026-05-09, ship without on first cut.

Ligue 1 is omitted: the game-line scanner covers it but Max's
2026-05-09 scope answer specified six leagues that match the ones
listed in the question (MLS, EPL, Bundesliga, La Liga, Serie A, UCL).

See props_kernel.py for the plugin contract.
"""

from types import SimpleNamespace

from props_kernel import no_projection_adjustment, no_prob_adjustment


# ── Shared per-league constants ───────────────────────────

PROP_MARKETS = [
    "player_shots",
    "player_shots_on_target",
]

MARKET_TO_STAT = {
    "player_shots": "Shots",
    "player_shots_on_target": "Shots on Target",
}

# Fallback SDs from public per-game data. Shots-per-game cluster around
# 0-3 for most starters with SD ~1; shots on target are roughly half of
# total shots.
PROP_SD = {
    "Shots": 1.2,
    "Shots on Target": 0.8,
}

COMBOS: dict[str, list[str]] = {}

MIN_EDGE = 0.05
MAX_EDGE = 0.15
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02

TIER = "Medium"
CONFIDENCE = "MEDIUM"

NEEDS_PLAYER_TEAM = False


# ── Gamelog row parser (shared across leagues) ────────────

# Confirmed via ESPN /overview endpoint:
# overview.gameLog.statistics[0] columns:
# 0 appearances ("Started"/"Sub"/etc., NOT a numeric value)
# 1 totalGoals
# 2 goalAssists
# 3 totalShots
# 4 shotsOnTarget
# 5 foulsCommitted
# 6 foulsSuffered
# 7 offsides
# 8 yellowCards
# 9 redCards
_SOCCER_INDEX = {
    "Shots": 3,
    "Shots on Target": 4,
}


def _parse_int(raw) -> int | None:
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def parse_gamelog_row(stats_list: list) -> dict[str, float]:
    """Translate one ESPN soccer gamelog row into {stat_label: value}.

    Rejects rows shorter than 10 columns. The first column is a string
    ("Started"/"Sub"/"Did Not Play") so it's not parsed numerically.
    """
    if not stats_list or len(stats_list) < 10:
        return {}

    out: dict[str, float] = {}
    for label, idx in _SOCCER_INDEX.items():
        v = _parse_int(stats_list[idx])
        if v is not None:
            out[label] = float(v)
    return out


def extract_gamelog_rows(data: dict) -> list[list]:
    """Walk gameLog.statistics[].events[].stats and return a flat list
    of stats rows. ESPN soccer's per-game player data lives here rather
    than under seasonTypes[].categories[].events[]."""
    rows: list[list] = []
    gl = data.get("gameLog", {})
    for stat_group in gl.get("statistics", []):
        for event in stat_group.get("events", []):
            stats_list = event.get("stats", [])
            if stats_list:
                rows.append(stats_list)
    return rows


def event_to_team_abbrs(event_str: str) -> tuple[str | None, str | None]:
    """Stub: soccer Phase A has no defense angle so opponent abbr is unused."""
    return (None, None)


# ── Per-league plugin factory ─────────────────────────────

def make_league_plugin(sport_key: str, sport_display: str,
                       odds_api_key: str, espn_slug: str) -> SimpleNamespace:
    """Build a soccer plugin instance for one league.

    Closures bake the league's ESPN slug into the URL builders so the
    same plugin contract works across MLS, EPL, La Liga, Bundesliga,
    Serie A, and UCL.
    """
    def _gamelog_url(athlete_id: str) -> str:
        return f"https://site.web.api.espn.com/apis/common/v3/sports/soccer/{espn_slug}/athletes/{athlete_id}/overview"

    def _athlete_url(athlete_id: str) -> str:
        return f"https://site.web.api.espn.com/apis/common/v3/sports/soccer/{espn_slug}/athletes/{athlete_id}"

    return SimpleNamespace(
        SPORT=sport_key,
        SPORT_DISPLAY=sport_display,
        ODDS_API_SPORT_KEY=odds_api_key,
        PROP_MARKETS=PROP_MARKETS,
        MARKET_TO_STAT=MARKET_TO_STAT,
        PROP_SD=PROP_SD,
        COMBOS=COMBOS,
        MIN_EDGE=MIN_EDGE,
        MAX_EDGE=MAX_EDGE,
        KELLY_FRACTION=KELLY_FRACTION,
        KELLY_CAP=KELLY_CAP,
        TIER=TIER,
        CONFIDENCE=CONFIDENCE,
        NEEDS_PLAYER_TEAM=NEEDS_PLAYER_TEAM,
        gamelog_url=_gamelog_url,
        athlete_url=_athlete_url,
        extract_gamelog_rows=extract_gamelog_rows,
        parse_gamelog_row=parse_gamelog_row,
        event_to_team_abbrs=event_to_team_abbrs,
        compute_projection_adjustment=no_projection_adjustment,
        compute_prob_adjustment=no_prob_adjustment,
    )


# ── League registry ───────────────────────────────────────

# (sport_key, sport_display, odds_api_key, espn_slug)
LEAGUES = [
    ("mls", "MLS", "soccer_usa_mls", "usa.1"),
    ("epl", "EPL", "soccer_epl", "eng.1"),
    ("la_liga", "La Liga", "soccer_spain_la_liga", "esp.1"),
    ("bundesliga", "Bundesliga", "soccer_germany_bundesliga", "ger.1"),
    ("serie_a", "Serie A", "soccer_italy_serie_a", "ita.1"),
    ("ucl", "UCL", "soccer_uefa_champs_league", "uefa.champions"),
]

# sport_key -> plugin instance, ready to register into fetch_props.PLUGINS.
PLUGINS = {
    sport_key: make_league_plugin(sport_key, sport_display, odds_key, slug)
    for sport_key, sport_display, odds_key, slug in LEAGUES
}

# League ESPN slugs exposed for the resolver's per-league box fetcher.
LEAGUE_SLUGS = {sport_key: slug for sport_key, _, _, slug in LEAGUES}
