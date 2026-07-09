#!/usr/bin/env python3
from __future__ import annotations
"""
Player Prop Edge Scanner: shared kernel.

Sport plugins (props_nba, props_nhl, ...) supply the small per-sport tables
and helpers; this module owns the Odds API fetch, ESPN athlete search, the
normal-CDF / Kelly math, the edge calculator, and the scan orchestrator.

Plugin contract: a Python module that exposes the following module-level
attributes.

Constants:
    SPORT                  lowercase short name (e.g. "nba", "nhl", "mlb")
    SPORT_DISPLAY          uppercase display name used in pick output
    ODDS_API_SPORT_KEY     The Odds API sport key (e.g. "basketball_nba")
    PROP_MARKETS           list of Odds API market keys to request
    MARKET_TO_STAT         dict[market_key, stat_label]
    PROP_SD                dict[stat_label, fallback_sd]
    COMBOS                 dict[combo_stat_label, list[component_stat_labels]]
                           (e.g. {"Pts+Rebs+Asts": ["Points", "Rebounds", "Assists"]})
    MIN_EDGE               min edge floor (e.g. 0.05 for 5%)
    MAX_EDGE               edge cap (e.g. 0.15 for 15%)
    KELLY_FRACTION         e.g. 0.25 for quarter-Kelly
    KELLY_CAP              max Kelly fraction (e.g. 0.02 for 2%)
    TIER                   pick tier label ("Medium")
    CONFIDENCE             confidence label ("MEDIUM")
    NEEDS_PLAYER_TEAM      bool; True if compute_projection_adjustment or
                           compute_prob_adjustment depends on opponent abbr

Functions:
    gamelog_url(athlete_id) -> str
        ESPN gamelog URL for the athlete in this sport.
    athlete_url(athlete_id) -> str
        ESPN athlete URL used to fetch the player's current team. Only called
        when NEEDS_PLAYER_TEAM is True.
    extract_gamelog_rows(response_data) -> list[list]
        Walk the parsed JSON response from gamelog_url and return a flat list
        of stats rows. NBA, NHL, and MLB use the standard
        seasonTypes[].categories[].events[].stats path (use the
        standard_gamelog_rows helper exported below). Soccer overrides this:
        per-game stats live at gameLog.statistics[0].events[].stats.
    parse_gamelog_row(stats_list) -> dict[stat_label, float]
        Parse one stats row into a dict keyed by stat_label. Sport-specific
        because ESPN column ordering differs across sports.
    event_to_team_abbrs(event_str) -> tuple[str | None, str | None]
        Parse "Home @ Away" (full names from Odds API) into ESPN abbrs.
        Used to determine opponent_abbr from player_team_abbr.
    compute_projection_adjustment(prop, projection, context) -> tuple[float, list[str]]
        Pre-z multiplier on the projection (e.g. NBA opponent defense).
        Return (1.0, []) for sports without projection-side adjustments.
    compute_prob_adjustment(prop, pick_side, context) -> tuple[float, list[str]]
        Post-pick-side multiplier on model_prob (e.g. NBA blowout discount).
        Return (1.0, []) for sports without prob-side adjustments.

Context passed to compute_*_adjustment is a dict with:
    athlete_id            ESPN athlete id (str)
    player_team_abbr      ESPN team abbr or None
    opponent_abbr         ESPN team abbr of the opposing team or None
    game_margins          dict[event_str, predicted_abs_margin]
    event_str             prop["event"]
"""

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ── The Odds API ─────────────────────────────────────────

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()

# Load from .env if not in environment
if not ODDS_API_KEY:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ODDS_API_KEY="):
                ODDS_API_KEY = line.split("=", 1)[1].strip()
                break


def fetch_dk_prop_odds(plugin, max_events: int = 6) -> list[dict]:
    """Fetch DraftKings player prop odds for `plugin`'s sport from The Odds API.

    Returns a list of normalized prop dicts:
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

    sport_key = plugin.ODDS_API_SPORT_KEY

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
    events.sort(key=lambda e: e.get("commence_time", ""))
    events = events[:max_events]

    markets_str = ",".join(plugin.PROP_MARKETS)
    all_props: list[dict] = []

    for event in events:
        event_id = event["id"]
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        event_label = f"{away} @ {home}"

        # includeLinks=true asks the Odds API to attach DK deep-link URLs to
        # each outcome. Without it, prop picks ship with dk_link="" and the
        # SPA renders a disabled "Place on DraftKings" button. The cost is
        # informational metadata on the response — does not change credit
        # counting per the API docs.
        props_url = (
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
            f"?apiKey={ODDS_API_KEY}&regions=us&bookmakers=draftkings"
            f"&oddsFormat=american&markets={markets_str}&includeLinks=true"
        )

        try:
            req = urllib.request.Request(props_url, headers={"User-Agent": "DKEdgeFinder/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                remaining = resp.headers.get("x-requests-remaining", "?")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"    {event_label}: fetch failed ({e})")
            continue

        for bm in data.get("bookmakers", []):
            if bm["key"] != "draftkings":
                continue

            for market in bm.get("markets", []):
                market_key = market["key"]
                stat_type = plugin.MARKET_TO_STAT.get(market_key)
                if not stat_type:
                    continue

                # Group outcomes by player + point (line). Each player has Over and Under
                # at the same point. Capture per-side DK deep links so the pick
                # output can use the side that actually got picked.
                player_lines: dict[tuple[str, float], dict] = {}
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
                    link = outcome.get("link", "") or ""

                    key = (name, point)
                    if key not in player_lines:
                        player_lines[key] = {
                            "over": None,
                            "under": None,
                            "over_link": "",
                            "under_link": "",
                        }

                    if side == "over":
                        player_lines[key]["over"] = int(price)
                        player_lines[key]["over_link"] = link
                    elif side == "under":
                        player_lines[key]["under"] = int(price)
                        player_lines[key]["under_link"] = link

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
                        "dk_over_link": sides.get("over_link", "") or "",
                        "dk_under_link": sides.get("under_link", "") or "",
                    })

        time.sleep(0.3)

    print(f"  Fetched {len(all_props)} DK prop lines across {min(len(events), max_events)} games")
    print(f"  Odds API credits remaining: {remaining}")
    return all_props


# ── ESPN athlete lookups ──────────────────────────────────

# ESPN athlete-id cache (player name → ESPN id). Sport-agnostic; ESPN's search
# endpoint indexes all sports.
_espn_id_cache: dict[str, str] = {}
# Player team cache (ESPN id → team abbreviation)
_player_team_cache: dict[str, str] = {}


def find_espn_athlete_id(player_name: str, team: str = "") -> str | None:
    """Search ESPN for a player's athlete id. Cached per session."""
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


def fetch_player_team(plugin, athlete_id: str) -> str | None:
    """Fetch a player's current team abbreviation from ESPN. Cached per session.

    Returns team abbreviation (e.g. 'OKC', 'LAL') or None.
    """
    if athlete_id in _player_team_cache:
        return _player_team_cache[athlete_id] or None

    url = plugin.athlete_url(athlete_id)
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


def fetch_player_recent_stats(plugin, athlete_id: str, n_games: int = 10) -> dict | None:
    """Fetch player's recent game log from ESPN and compute weighted averages.

    Weighting: last 3 games get 50% weight, previous 7 get 50%.
    Also computes per-stat standard deviations from actual player data.
    Returns dict with keys "averages", "flat_averages", "actual_sds",
    "games_sampled". All are keyed by stat_label (not raw column index).
    """
    url = plugin.gamelog_url(athlete_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    rows = plugin.extract_gamelog_rows(data)
    if not rows:
        return None

    recent = rows[:n_games]

    # Parse each row into a {stat_label: value} dict using the plugin parser.
    parsed_rows: list[dict[str, float]] = []
    for row in recent:
        parsed = plugin.parse_gamelog_row(row)
        if parsed:
            parsed_rows.append(parsed)

    if not parsed_rows:
        return None

    # Compute weighted averages and actual SDs per stat label.
    averages: dict[str, float] = {}
    flat_averages: dict[str, float] = {}
    actual_sds: dict[str, float] = {}

    stat_labels: set[str] = set()
    for parsed in parsed_rows:
        stat_labels.update(parsed.keys())

    for label in stat_labels:
        vals = [p[label] for p in parsed_rows if label in p]
        if not vals:
            continue

        # Weighted avg: last 3 games = 50%, older games = 50%
        if len(vals) >= 5:
            recent_3 = vals[:3]
            older = vals[3:]
            recent_avg = sum(recent_3) / len(recent_3)
            older_avg = sum(older) / len(older)
            weighted_avg = recent_avg * 0.5 + older_avg * 0.5
        else:
            weighted_avg = sum(vals) / len(vals)

        averages[label] = round(weighted_avg, 2)
        flat_averages[label] = round(sum(vals) / len(vals), 2)

        if len(vals) >= 3:
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            actual_sds[label] = round(variance ** 0.5, 2)

    return {
        "averages": averages,
        "flat_averages": flat_averages,
        "actual_sds": actual_sds,
        "games_sampled": len(parsed_rows),
    }


# ── Math utilities ────────────────────────────────────────

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


def poisson_cdf_le(m: int, lam: float) -> float:
    """P(X <= m) for X ~ Poisson(lam). `m` is a non-negative integer.

    Iterative term (term_{i} = term_{i-1} * lam / i) so there is no factorial
    overflow and no numpy dependency. Returns 1.0 for lam <= 0 (degenerate) and
    0.0 for m < 0.
    """
    if lam <= 0:
        return 1.0
    if m < 0:
        return 0.0
    term = math.exp(-lam)   # P(X = 0)
    cdf = term
    for i in range(1, m + 1):
        term *= lam / i
        cdf += term
    return min(1.0, cdf)


def poisson_over_under(lam: float, line: float) -> tuple[float, float]:
    """(over_prob, under_prob) for a DK count line under Poisson(lam).

    DK count props use half-integer lines (0.5, 1.5, ...), so there is no push:
    over  = P(X >= floor(line) + 1) = 1 - P(X <= floor(line))
    under = P(X <= floor(line)).
    This is the correct model for low-count discrete stats (hits, shots, goals,
    SOG) where the old normal-CDF path overstated the favorite side — a Gaussian
    tail off a last-N-game mean is wrong when the line sits in the discrete gap
    between 0 and 1. Validated in scripts/test_props_poisson.py (analytic) and
    scripts/backtest_prop_model.py (NBA/NHL proxy). Rebuilt 2026-06-09.
    """
    m = math.floor(line)
    under = poisson_cdf_le(m, lam)
    over = 1.0 - under
    return over, under


# Poisson path coin-flip guard: replaces the normal model's |z| >= 0.5 gate.
# Skip a prop whose favored side is within this band of 50% — no real edge,
# just noise around the line.
POISSON_COINFLIP_BAND = 0.06


def resolve_distribution(plugin, stat_type: str) -> str:
    """Distribution for a (plugin, stat): per-stat STAT_DIST override, then the
    plugin's DEFAULT_DIST, then "normal". A plugin that declares neither keeps
    the legacy normal-CDF path (as of 2026-07-09 only NHL, which is hard-skipped
    anyway; NBA moved its low-count stats to Poisson after the June Finals 0-8).
    """
    per_stat = getattr(plugin, "STAT_DIST", {}) or {}
    if stat_type in per_stat:
        return per_stat[stat_type]
    return getattr(plugin, "DEFAULT_DIST", "normal")


# ── Edge calculation ──────────────────────────────────────

def calculate_prop_edge(plugin, prop: dict, player_stats: dict | None,
                        context: dict | None = None) -> dict | None:
    """Calculate edge for a single player prop.

    Pipeline:
      1. Look up the projection (sport-specific via stat_label dict from
         parse_gamelog_row; combos summed via plugin.COMBOS).
      2. Apply plugin.compute_projection_adjustment (e.g. NBA opponent defense).
      3. Compute z-score against the line; gate on |z| >= 0.5.
      4. Pick the side; apply plugin.compute_prob_adjustment (e.g. NBA blowout).
      5. Compare model_prob vs implied_prob; cap raw edge at plugin.MAX_EDGE.
      6. Floor at plugin.MIN_EDGE; size with plugin.KELLY_FRACTION (capped at
         plugin.KELLY_CAP).

    Returns the pick dict or None if the prop doesn't clear the gate.
    """
    if context is None:
        context = {}

    stat_type = prop["stat_type"]
    line = prop["line"]
    fallback_sd = plugin.PROP_SD.get(stat_type, 0)

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

    # Project: single stat from averages, or sum of components for a combo.
    our_projection: float | None = None
    flat_projection: float | None = None
    player_sd: float | None = None

    if stat_type in plugin.COMBOS:
        components = plugin.COMBOS[stat_type]
        comp_vals = [avgs.get(c) for c in components]
        flat_comp_vals = [flat_avgs.get(c) for c in components]
        if all(v is not None for v in comp_vals):
            our_projection = sum(comp_vals)
        if all(v is not None for v in flat_comp_vals):
            flat_projection = sum(flat_comp_vals)
        sd_vals = [actual_sds.get(c) for c in components]
        if all(v is not None for v in sd_vals):
            # Sum of SDs (conservative: assume correlation across components).
            player_sd = sum(sd_vals)
    else:
        our_projection = avgs.get(stat_type)
        flat_projection = flat_avgs.get(stat_type)
        player_sd = actual_sds.get(stat_type)

    if our_projection is None:
        return None

    # ── Pre-z projection adjustment (sport-specific) ──
    proj_mult, pre_notes = plugin.compute_projection_adjustment(prop, our_projection, context)
    if proj_mult != 1.0:
        our_projection = round(our_projection * proj_mult, 2)

    # Use player's actual SD if available; widen by 25% when <7 games sampled.
    sd = player_sd if player_sd and player_sd > 0 else fallback_sd
    if games_sampled < 7:
        sd *= 1.25

    diff = our_projection - line  # positive = projected over
    dist = resolve_distribution(plugin, stat_type)

    if dist == "poisson":
        # Discrete count model: lambda = projection, SD ignored. Correct for
        # low-line count props (hits, shots, goals, SOG) where the normal path
        # overstated the favorite side.
        if our_projection <= 0:
            return None  # degenerate lambda; a player projected to never record
                         # the stat would otherwise flag UNDER at ~100%.
        over_prob, under_prob = poisson_over_under(our_projection, line)
        sd_p = math.sqrt(our_projection)  # Poisson SD, for the narrative only
        sep_label = (
            f"{abs(diff):.1f} {'over' if diff > 0 else 'under'} "
            f"(λ={our_projection:.2f}, {abs(diff) / sd_p:.1f}σ_P separation)"
        )
    else:
        if abs(diff) < 0.3:
            return None  # too close to call
        z = (line - our_projection) / sd
        if abs(z) < 0.5:
            return None  # not enough separation: noise, not signal
        over_prob = 1.0 - normal_cdf(z)
        under_prob = normal_cdf(z)
        sep_label = (
            f"{abs(diff):.1f} {'over' if diff > 0 else 'under'} "
            f"with {abs(diff) / sd if sd > 0 else 0:.1f}σ separation"
        )

    # Pick the higher-probability side (model_prob >= 0.5 by construction).
    if over_prob >= under_prob:
        pick_side, model_prob, dk_odds = "over", over_prob, prop["over_odds"]
    else:
        pick_side, model_prob, dk_odds = "under", under_prob, prop["under_odds"]

    # Poisson coin-flip guard (the normal path already gated on |z| above).
    if dist == "poisson" and abs(model_prob - 0.5) < POISSON_COINFLIP_BAND:
        return None

    adjustments: list[str] = list(pre_notes)

    # ── Post-pick-side prob adjustment (sport-specific) ──
    prob_mult, post_notes = plugin.compute_prob_adjustment(prop, pick_side, context)
    if prob_mult != 1.0:
        model_prob *= prob_mult
    adjustments.extend(post_notes)

    implied = american_to_implied(dk_odds)
    raw_edge = model_prob - implied

    if raw_edge > plugin.MAX_EDGE:
        capped_edge = plugin.MAX_EDGE
        adjustments.append(f"Edge capped: {raw_edge*100:.1f}% → {capped_edge*100:.1f}%")
        edge = capped_edge
    else:
        edge = raw_edge

    if edge < plugin.MIN_EDGE:
        return None

    # Heavy-favorite hard cap. Reject picks priced worse than -220
    # regardless of edge. At -245 (today's Suzuki UNDER 1.5 Points) you
    # risk $11 to win $4.49 — one loss eats ~2.5 wins, and the model's
    # edge has to be very accurate to overcome the juice cost. Threshold
    # picked from 2026-05-12 audit + Max's call: in 32 graded historical
    # props only 3 were priced ≤-180 (all wins, n=3 = noise); no
    # historical picks priced ≤-200. This cap mostly prevents future
    # outliers like Suzuki rather than reshaping today's mix. Re-audit
    # quarterly and tune as the prop history grows.
    if dk_odds <= -220:
        return None

    decimal_odds = 1 + 100 / abs(dk_odds) if dk_odds < 0 else 1 + dk_odds / 100
    kelly = (edge / (decimal_odds - 1)) * plugin.KELLY_FRACTION
    kelly = min(kelly, plugin.KELLY_CAP)

    adj_note = " | ".join(adjustments) if adjustments else ""

    narrative = (
        f"{prop['player']} averages {our_projection:.1f} {stat_type} "
        f"(last {games_sampled}g), line is {line}: {sep_label}."
    )

    if flat_projection and abs(flat_projection - our_projection) > 0.5:
        trend_dir = "trending up" if our_projection > flat_projection else "trending down"
        narrative += f" {trend_dir.capitalize()} (season avg: {flat_projection:.1f})."

    if raw_edge > plugin.MAX_EDGE:
        narrative += f" Raw edge: {raw_edge*100:.1f}% (capped at {plugin.MAX_EDGE*100:.0f}%)."

    if adj_note:
        narrative += f" {adj_note}."

    # Tag the pick with a {side}_{odds-tier} bucket so future audits can
    # group prop performance cleanly without re-deriving from odds string.
    # Aligned with the 2026-05-11 prop audit buckets: underdog (positive
    # odds) or one of four favorite tiers.
    if dk_odds > 0:
        odds_tier = "underdog"
    elif dk_odds >= -120:
        odds_tier = "near_even_fav"
    elif dk_odds >= -150:
        odds_tier = "moderate_fav"
    elif dk_odds >= -200:
        odds_tier = "heavy_fav"
    else:
        odds_tier = "very_heavy_fav"
    prop_bucket = f"{pick_side}_{odds_tier}"

    return {
        "sport": plugin.SPORT_DISPLAY,
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
        "tier": plugin.TIER,
        "confidence": plugin.CONFIDENCE,
        "kelly_pct": kelly,
        "notes": narrative,
        "sources": "The Odds API (DK), ESPN",
        "market": "Player Prop",
        "event": prop.get("event", ""),
        "prop_bucket": prop_bucket,
        "dk_link": (
            prop.get("dk_over_link", "")
            if pick_side == "over"
            else prop.get("dk_under_link", "")
        ),
    }


# ── Default no-op adjustment hooks ────────────────────────
# Plugins that don't need projection or prob adjustments can wire these in
# directly: `compute_projection_adjustment = props_kernel.no_projection_adjustment`.

def no_projection_adjustment(prop, projection, context) -> tuple[float, list[str]]:
    return 1.0, []


def no_prob_adjustment(prop, pick_side, context) -> tuple[float, list[str]]:
    return 1.0, []


# ── Standard gamelog row extractor ────────────────────────
# Used by NBA, NHL, MLB. Soccer overrides because its data lives at
# gameLog.statistics[0].events[].stats instead of the standard path.

def standard_gamelog_rows(data: dict) -> list[list]:
    """Walk seasonTypes[].categories[].events[].stats and return a flat
    list of stats rows. Skips preseason types.
    """
    rows: list[list] = []
    for st in data.get("seasonTypes", []):
        if "preseason" in st.get("displayName", "").lower():
            continue
        for cat in st.get("categories", []):
            for event_row in cat.get("events", []):
                stats_list = event_row.get("stats", [])
                if stats_list:
                    rows.append(stats_list)
    return rows


# ── Scan orchestrator ─────────────────────────────────────

def scan_props(plugin, bankroll: float = 500.0, max_lookups: int = 30,
               game_margins: dict | None = None) -> list[dict]:
    """Scan player props for `plugin`'s sport using real DK odds.

    Flow:
      1. Fetch DK prop odds from The Odds API.
      2. For each player with supported props, fetch ESPN game log.
      3. (Optional) Look up player's team for sport-specific adjustments.
      4. Compute edge per prop; gate, cap, and size with Kelly.
      5. Return edges sorted by edge descending.

    Args:
        game_margins: dict mapping event strings to predicted absolute margin
                      (used by NBA's blowout discount; ignored by other sports).
    """
    if game_margins is None:
        game_margins = {}

    # Per-plugin hard-skip: suppress an entire sport's props before any Odds API
    # call. Used to wind a sport down (e.g. NHL props 2026-06-09) when the kernel
    # model is wrong for it. Reversible by flipping the plugin's HARD_SKIP flag.
    if getattr(plugin, "HARD_SKIP", False):
        print(f"  {plugin.SPORT_DISPLAY} props hard-skipped (plugin.HARD_SKIP=True)")
        return []

    print(f"  Fetching DK {plugin.SPORT_DISPLAY} prop odds from The Odds API...")
    props = fetch_dk_prop_odds(plugin, max_events=6)

    if not props:
        print("  No prop odds available")
        return []

    supported = set(plugin.PROP_SD.keys())

    by_player: dict[str, list[dict]] = {}
    for p in props:
        if p["stat_type"] in supported:
            by_player.setdefault(p["player"], []).append(p)

    print(f"  {len(by_player)} players with supported prop lines")

    # Stars first: order players by their highest line on the primary stat (Points
    # for NBA; sport plugins can rely on the highest-line heuristic for any stat,
    # so we use the max line across all stat types as a generic proxy).
    def player_max_line(item):
        _, props_list = item
        return max((p["line"] for p in props_list), default=0)

    edges: list[dict] = []
    lookups = 0

    for player_name, player_props in sorted(by_player.items(), key=player_max_line, reverse=True):
        if lookups >= max_lookups:
            break

        espn_id = find_espn_athlete_id(player_name)
        if not espn_id:
            continue
        lookups += 1

        stats = fetch_player_recent_stats(plugin, espn_id)
        if not stats:
            continue
        lookups += 1

        player_team_abbr = fetch_player_team(plugin, espn_id) if plugin.NEEDS_PLAYER_TEAM else None

        for prop in player_props:
            event_str = prop.get("event", "")
            opponent_abbr: str | None = None
            if player_team_abbr and event_str:
                away_abbr, home_abbr = plugin.event_to_team_abbrs(event_str)
                if player_team_abbr == away_abbr and home_abbr:
                    opponent_abbr = home_abbr
                elif player_team_abbr == home_abbr and away_abbr:
                    opponent_abbr = away_abbr

            context = {
                "athlete_id": espn_id,
                "player_team_abbr": player_team_abbr,
                "opponent_abbr": opponent_abbr,
                "event_str": event_str,
                "game_margins": game_margins,
            }

            edge = calculate_prop_edge(plugin, prop, stats, context)
            if edge:
                edges.append(edge)

        # Rate-limit protection
        if lookups % 10 == 0:
            time.sleep(1)

    edges.sort(key=lambda x: x["edge"], reverse=True)

    print(f"  Checked {lookups} ESPN lookups, found {len(edges)} prop edges")
    return edges
