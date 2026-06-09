#!/usr/bin/env python3
from __future__ import annotations
"""MLB player-prop plugin for the props_kernel.

Phase A scope: hitter + pitcher props, no opponent angle. Markets:
  Hitter (4): Hits, Home Runs, RBIs, Runs
  Pitcher (5): Strikeouts, Pitcher Outs, Earned Runs, Hits Allowed, Walks Allowed

Excluded from Phase A:
  - Total Bases: ESPN basic gamelog has it derivable (H + 2B + 2*3B + 3*HR)
    but the box-score endpoint exposes neither doubles nor triples per player,
    so we could project it but not resolve it. Lesson 2026-05-03b blocks
    shipping projection-only markets.
  - Hitter walks, stolen bases, singles, doubles, triples: similar issue or
    deferred for first-cut focus.
  - Pitcher wins (player_record_a_win): binary outcome, different sizing
    semantics, defer.
  - Park factors and bullpen adjustments: per scope decision 2026-05-09,
    no defense-rating analog on first cut.

Two-role gamelogs: ESPN serves either a hitter or a pitcher gamelog per
athlete depending on the player's primary role. parse_gamelog_row dispatches
by column count (16 = hitter, 15 = pitcher). Two-way players (Ohtani) get
their hitter side projected from this endpoint; their pitcher props would
need a separate athlete id or a different endpoint, which we'll handle as a
follow-up if it becomes meaningful.

See props_kernel.py for the plugin contract.
"""

from props_kernel import no_projection_adjustment, no_prob_adjustment, standard_gamelog_rows


# ── Plugin contract: constants ────────────────────────────

SPORT = "mlb"
SPORT_DISPLAY = "MLB"
ODDS_API_SPORT_KEY = "baseball_mlb"

PROP_MARKETS = [
    "player_hits",
    "player_home_runs",
    "player_runs_batted_in",
    "player_runs_scored",
    "player_strikeouts",
    "player_pitcher_outs",
    "player_earned_runs",
    "player_hits_allowed",
    "player_walks_allowed",
]

MARKET_TO_STAT = {
    "player_hits": "Hits",
    "player_home_runs": "Home Runs",
    "player_runs_batted_in": "RBIs",
    "player_runs_scored": "Runs",
    "player_strikeouts": "Strikeouts",
    "player_pitcher_outs": "Pitcher Outs",
    "player_earned_runs": "Earned Runs",
    "player_hits_allowed": "Hits Allowed",
    "player_walks_allowed": "Walks Allowed",
}

# Fallback SDs from public per-game data.
# Hitters: a starter sees 3-5 ABs/game; per-game variance on hits, HRs, RBIs,
# and runs is dominated by zero-or-one outcomes. SDs sit close to the means.
# Pitchers: starters typically log 5-6 IP, so SDs scale with workload (~3 outs
# of variance, ~2 hits, ~1 walk, ~2-3 K). Kernel prefers actual SD once 3+
# games sampled.
PROP_SD = {
    "Hits": 0.9,
    "Home Runs": 0.5,
    "RBIs": 1.0,
    "Runs": 0.8,
    "Strikeouts": 2.5,
    "Pitcher Outs": 3.0,
    "Earned Runs": 1.5,
    "Hits Allowed": 2.0,
    "Walks Allowed": 1.0,
}

COMBOS: dict[str, list[str]] = {}

# Distribution model (2026-06-09 Poisson rebuild). Low-line discrete count
# stats are Poisson(lambda=projection); the kernel's old normal-CDF overstated
# the favorite side on these. Pitcher Outs is the exception: at ~15-18 outs it
# is a bounded, managerially-capped, near-bimodal quantity (starters get pulled),
# so the normal approximation is least-bad there and Poisson's variance=mean
# assumption is wrong. RBIs and Earned Runs are overdispersed (Poisson under-
# covers their upper tail); they ship on Poisson now and move to negative
# binomial in Phase 2. See scripts/backtest_prop_model.py (proxy validation).
DEFAULT_DIST = "poisson"
STAT_DIST = {
    "Pitcher Outs": "normal",
}

MIN_EDGE = 0.05
MAX_EDGE = 0.15
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02

TIER = "Medium"
CONFIDENCE = "MEDIUM"

NEEDS_PLAYER_TEAM = False


# ── ESPN URL builders ─────────────────────────────────────

def gamelog_url(athlete_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/{athlete_id}/gamelog"


def athlete_url(athlete_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/{athlete_id}"


# ── Gamelog row parser ────────────────────────────────────

# Confirmed via ESPN baseball/mlb gamelog endpoint:
# Hitter (16 cols): atBats, runs, hits, doubles, triples, homeRuns, RBIs,
#   walks, hitByPitch, strikeouts, stolenBases, caughtStealing, avg, OBP,
#   slug, OPS
# Pitcher (15 cols): innings, hits, runs, earnedRuns, homeRuns, walks,
#   strikeouts, groundBalls, flyBalls, pitches, battersFaced, avgGameScore,
#   wins-losses, saves-blownSaves-holds, ERA
_HITTER_INDEX = {
    "Hits": 2,
    "Home Runs": 5,
    "RBIs": 6,
    "Runs": 1,
}
_PITCHER_INDEX = {
    "Hits Allowed": 1,
    "Earned Runs": 3,
    "Walks Allowed": 5,
    "Strikeouts": 6,
}


def _parse_int(raw) -> int | None:
    try:
        return int(raw)
    except (ValueError, TypeError):
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return None


def _ip_string_to_outs(ip_str) -> int | None:
    """Convert ESPN's 'fullInnings.partInnings' string into total outs.

    '7.0' -> 21 outs (7 full innings).
    '6.1' -> 19 outs (6 full + 1/3).
    '6.2' -> 20 outs (6 full + 2/3).
    """
    if ip_str is None:
        return None
    try:
        s = str(ip_str)
        if "." in s:
            whole, frac = s.split(".", 1)
            return int(whole) * 3 + int(frac)
        return int(s) * 3
    except (ValueError, TypeError):
        return None


def parse_gamelog_row(stats_list: list) -> dict[str, float]:
    """Translate one ESPN MLB gamelog row into {stat_label: value}.

    Dispatches by column count: 16 columns = hitter, 15 columns = pitcher.
    Returns {} for any other length (preseason / partial / unknown rows).
    """
    if not stats_list:
        return {}

    out: dict[str, float] = {}

    if len(stats_list) == 16:
        for label, idx in _HITTER_INDEX.items():
            v = _parse_int(stats_list[idx])
            if v is not None:
                out[label] = float(v)
    elif len(stats_list) == 15:
        for label, idx in _PITCHER_INDEX.items():
            v = _parse_int(stats_list[idx])
            if v is not None:
                out[label] = float(v)
        outs = _ip_string_to_outs(stats_list[0])
        if outs is not None:
            out["Pitcher Outs"] = float(outs)

    return out


# ── Event string parser (no-op) ───────────────────────────

def event_to_team_abbrs(event_str: str) -> tuple[str | None, str | None]:
    """Stub: MLB Phase A has no defense angle so opponent abbr is unused."""
    return (None, None)


extract_gamelog_rows = standard_gamelog_rows


# ── Adjustment hooks: identity ────────────────────────────

compute_projection_adjustment = no_projection_adjustment
compute_prob_adjustment = no_prob_adjustment
