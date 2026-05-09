#!/usr/bin/env python3
from __future__ import annotations
"""NHL player-prop plugin for the props_kernel.

Phase A scope: skater-only, no goalie saves, no opponent-defense angle.
Markets covered (4):
  - Points (Goals + Assists; ESPN gamelog idx 2 already pre-summed)
  - Goals (idx 0)
  - Assists (idx 1)
  - Shots on Goal (idx 5; ESPN's "shotsTotal")

Excluded from Phase A:
  - Goalie saves (different SD baselines, opponent-shot-volume adjustment,
    starter-vs-backup logic; defer per scope decision 2026-05-09).
  - Hits and blocks (ESPN basic gamelog doesn't expose them per-game; the box
    score does, so we COULD resolve them but can't project. Defer until we
    swap to a richer gamelog endpoint or scrape skater-summary tables).
  - Power Play Points (ESPN gamelog has PPG and PPA, but the box-score endpoint
    doesn't break out per-strength scoring, so we can project but not resolve.
    Defer until a resolution path exists; resolver-branch-in-same-commit rule
    blocks shipping projection-only).

See props_kernel.py for the plugin contract.
"""

from props_kernel import no_projection_adjustment, no_prob_adjustment


# ── Plugin contract: constants ────────────────────────────

SPORT = "nhl"
SPORT_DISPLAY = "NHL"
ODDS_API_SPORT_KEY = "icehockey_nhl"

PROP_MARKETS = [
    "player_points",
    "player_goals",
    "player_assists",
    "player_shots_on_goal",
]

MARKET_TO_STAT = {
    "player_points": "Points",
    "player_goals": "Goals",
    "player_assists": "Assists",
    "player_shots_on_goal": "Shots on Goal",
}

# Fallback SDs for the normal-CDF projection. Calibrated from public NHL
# skater-game data: top scorers cluster around 0.7-1.5 PPG with SD ~0.9-1.0;
# shots on goal sit around 2-4 with SD ~1.5-2.0. The kernel prefers the
# player's actual SD when 3+ games are sampled, so these are rarely used in
# practice once a season is under way.
PROP_SD = {
    "Points": 1.0,
    "Goals": 0.6,
    "Assists": 0.7,
    "Shots on Goal": 1.6,
}

COMBOS: dict[str, list[str]] = {}

MIN_EDGE = 0.05         # Medium tier: 5% min
MAX_EDGE = 0.15
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02

TIER = "Medium"
CONFIDENCE = "MEDIUM"

NEEDS_PLAYER_TEAM = False  # no defense angle in Phase A first cut


# ── ESPN URL builders ─────────────────────────────────────

def gamelog_url(athlete_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{athlete_id}/gamelog"


def athlete_url(athlete_id: str) -> str:
    # Defined for contract completeness; unused while NEEDS_PLAYER_TEAM is False.
    return f"https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{athlete_id}"


# ── Gamelog row parser ────────────────────────────────────

# ESPN top-level "names" array confirms column ordering for hockey/nhl gamelog:
# 0 goals, 1 assists, 2 points, 3 plusMinus, 4 PIM, 5 shotsTotal,
# 6 shootingPct, 7 powerPlayGoals, 8 powerPlayAssists, 9 SHG, 10 SHA,
# 11 GWG, 12 TOI/G, 13 production
_NHL_STAT_INDEX = {
    "Goals": 0,
    "Assists": 1,
    "Points": 2,
    "Shots on Goal": 5,
}


def _parse_stat_val(raw) -> float | None:
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def parse_gamelog_row(stats_list: list) -> dict[str, float]:
    """Translate one ESPN NHL gamelog row into {stat_label: value}.

    Rejects rows shorter than 14 columns (scratched / partial entries).
    """
    if not stats_list or len(stats_list) < 14:
        return {}

    out: dict[str, float] = {}
    for label, idx in _NHL_STAT_INDEX.items():
        if idx < len(stats_list):
            v = _parse_stat_val(stats_list[idx])
            if v is not None:
                out[label] = v
    return out


# ── Event string parser (no-op) ───────────────────────────

def event_to_team_abbrs(event_str: str) -> tuple[str | None, str | None]:
    """Stub: NHL Phase A has no defense angle so opponent abbr is unused.
    Defined for contract completeness.
    """
    return (None, None)


# ── Adjustment hooks: identity ────────────────────────────

# NHL Phase A first cut has no opponent-defense angle and no blowout discount.
# Wire the kernel's no-op identity functions in directly.
compute_projection_adjustment = no_projection_adjustment
compute_prob_adjustment = no_prob_adjustment
