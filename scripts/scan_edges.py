#!/usr/bin/env python3
from __future__ import annotations
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
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from skellam import poisson_spread_probability
from fetch_props import scan_props as scan_player_props
from fetch_sources import fetch_all_sources

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "data.json"
BANKROLL_JSON = REPO_ROOT / "bankroll.json"

# ── Config ──────────────────────────────────────────
MIN_EDGE_HIGH = 0.03      # 3% for spreads/ML/totals
MIN_EDGE_MEDIUM = 0.05    # 5% for props
SUSPICIOUS_EDGE = 0.10    # 10% — flag for investigation, don't cap
KELLY_FRACTION_HIGH = 0.5
MAX_SINGLE_BET_PCT = 0.02  # 2% max single bet — smaller bets = more diversification
MAX_DAILY_EXPOSURE = 0.25  # 25% total daily cap
MAX_GAME_EXPOSURE = 0.15   # 15% budget for game edges (spreads/ML/totals)
MAX_PROP_EXPOSURE = 0.10   # 10% budget for prop edges

# ── CALIBRATION OVERRIDES (April 2026) ────────────────
# NBA spreads: 5-7 (41.7%) — model's weakest market.
NBA_SPREAD_MIN_EDGE = 0.05           # 5% base for NBA spreads
NBA_LARGE_SPREAD_MIN_EDGE = 0.08     # 8% for spreads >12 pts
NBA_LARGE_SPREAD_THRESHOLD = 12.0

# Graduated edge discount for bet sizing.
# 10%+ edges hit only 58.8% vs 75% for 5-8% edges.
EDGE_DISCOUNT_TIERS = [
    (0.15, 0.10),   # 15%+ → size as 10%
    (0.12, 0.10),   # 12-15% ��� size as 10%
    (0.10, 0.08),   # 10-12% → size as 8%
]

# MLB run line calibration: model overestimates due to right-skewed margins.
# Even with widened SD, require higher min edge for MLB.
MLB_SPREAD_MIN_EDGE = 0.05              # 5% min for MLB run lines

# Single-source Kelly penalty (25% reduction for DRatings-only picks)
SINGLE_SOURCE_KELLY_DISCOUNT = 0.75

# ── GAME OUTCOME STANDARD DEVIATIONS ───────────────
# These are the SDs of (actual outcome - market prediction).
# For NBA/NFL: measured from closing line ATS data (Boyd's Bets).
# For NHL/MLB: measured margins, then adjusted for model-vs-market gap.
# For Soccer: derived from Poisson scoring model (Dixon-Coles).
#
# MODEL ERROR BUFFER:
# NHL and MLB measured SDs come from comparing actual outcomes to closing lines.
# But we use DRatings/Dimers predictions (which can deviate from markets).
# Puck line underdogs historically cover 70-75%, not 87.6% (as 1.274 would imply).
# Solution: apply model error buffer to widen SD and account for our model's
# additional uncertainty vs. the market's prediction.
# - NHL: 1.274 * 1.4 = 1.78 (40% wider, more realistic to historical data)
# - MLB: 2.538 * 1.3 = 3.30 (30% wider)
#
# ┌─────────────┬──────────┬──────────┬──────────────────────────────────────────────────┐
# │ Sport       │ Spread   │ Totals   │ Source & Notes                                   │
# ├─────────────┼──────────┼──────────┼──────────────────────────────────────────────────┤
# │ NBA         │ 11.26    │ 17.19    │ Boyd's Bets (measured, multi-season, validated)  │
# │ NFL         │ 13.28    │ 13.28    │ Boyd's Bets + Stern 1991 (validated multi-year)  │
# │ NHL         │ 1.78     │ —        │ Measured 1.274 * 1.4 (model error buffer)        │
# │ MLB         │ 3.30     │ —        │ Measured 2.538 * 1.3 (model error buffer)        │
# │ Soccer      │ 1.71     │ 1.71     │ Dixon-Coles (1997), Poisson-derived              │
# │ MMA         │ —        │ —        │ No spread/total market                           │
# └─────────────┴──────────┴──────────┴──────────────────────────────────────────────────┘
#
# Sources:
# - Boyd's Bets: https://www.boydsbets.com/ats-margin-standard-deviations-by-point-spread/
# - Boyd's Bets: https://www.boydsbets.com/standard-deviations-of-overunder-margins-by-total/
# - Stern (1991): "On the Probability of Winning a Football Game", American Statistician 45(3):179-183
# - Dixon & Coles (1997): "Modelling Association Football Scores", JRSS-C 46(2):265-280

GAME_SD = {
    # NBA — MEASURED (Boyd's Bets, multi-season)
    # Spread: avg 11.26, range 9.20-12.03, correlation 0.60 (larger spreads slightly more predictable)
    # Totals: avg 17.19, range 15.08-21.25, correlation 0.33 (higher totals slightly less predictable)
    "nba_spread": 11.26,
    "nba_total": 17.19,

    # NFL — MEASURED (Boyd's Bets + Stern 1991)
    # Spread: avg 13.28, Stern measured 13.86 (1981-84), modern ~13.7, correlation -0.06 (no relationship)
    # Totals: avg 13.28, correlation -0.02 (no relationship)
    "nfl_spread": 13.28,
    "nfl_total": 13.28,

    # Soccer — DERIVED from Dixon-Coles Poisson model
    # All major leagues: λ_home ≈ 1.5, λ_away ≈ 1.42, total SD ≈ sqrt(λ_h + λ_a) ≈ 1.71
    # Goal margin SD from Skellam distribution ≈ sqrt(λ_h + λ_a) ≈ 1.71
    # ρ (correlation) = -0.13, γ (home advantage) = 0.27 log scale
    # Over 2.5 goals ≈ 53-54% historically
    "epl_spread": 1.71,   # DERIVED — Skellam distribution, NOT measured ATS data
    "epl_total": 1.71,    # DERIVED — sum of Poisson SDs
    "mls_spread": 1.71,   # DERIVED — similar scoring rates to EPL
    "mls_total": 1.71,
    "la_liga_spread": 1.71,   # DERIVED — Spain, similar to EPL
    "la_liga_total": 1.71,
    "bundesliga_spread": 1.71,   # DERIVED — Germany, similar to EPL
    "bundesliga_total": 1.71,
    "serie_a_spread": 1.71,   # DERIVED — Italy, similar to EPL
    "serie_a_total": 1.71,
    "ligue_1_spread": 1.71,   # DERIVED — France, similar to EPL
    "ligue_1_total": 1.71,
    "ucl_spread": 1.71,   # DERIVED — Champions League, similar to EPL
    "ucl_total": 1.71,

    # NHL — MEASURED then ADJUSTED (Mysterious Lights: 1.274 * 1.4 model error buffer)
    # Raw margin of victory SD: 1.274 goals (single season, 1230 games — MEDIUM confidence)
    # Puck line underdogs historically cover 70-75%, not 87.6% (as raw 1.274 would imply)
    # Applying 40% model error buffer: 1.274 * 1.4 = 1.78 (accounts for DRatings vs market gap)
    # Totals SD: NOT measured — no published O/U margin SD for NHL
    "nhl_spread": 1.78,
    # "nhl_total": None,  # BLOCKED — no measured value

    # MLB — MEASURED then ADJUSTED (April 2026 re-calibration)
    # Raw run margin SD: 2.538 runs (single season, ~2430 games — MEDIUM confidence)
    # Previous: 2.538 * 1.3 = 3.30 (30% buffer). Produced 20-25% edges — far too aggressive.
    # MLB run margins are right-skewed (blowouts), so normal CDF overestimates +1.5 cover rates.
    # Historical +1.5 underdogs cover ~57-59%, but SD=3.30 produces 62-65% model probs.
    # Fix: widen to 2.538 * 1.8 = 4.57 (80% buffer accounts for skewness + model error).
    # At SD=4.57: +1.5 cover with 1-run cushion ≈ 58.7% — matches historical data.
    # Totals SD: NOT measured — no published O/U margin SD for MLB
    "mlb_spread": 4.57,
    # "mlb_total": None,  # BLOCKED — no measured value
}

# Sports with partially validated SD — edges will be labeled MEDIUM confidence
PARTIALLY_VALIDATED_SPORTS = {"nhl", "mlb"}
# MMA has no spread/total market at all — moneyline only
UNVALIDATED_SPORTS = {"mma"}
# Note: NHL and MLB games are still fetched for display purposes,
# but no edges will be calculated without measured SDs.

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


def fetch_schedule_and_odds(date_str: str, sport: str = "nba") -> list[dict]:
    """Fetch games with odds from ESPN for a given date and sport."""
    sport_endpoints = {
        "nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}",
        "nhl": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date_str}",
        "mlb": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date_str}",
        "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}",
        "mls": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates={date_str}",
        "epl": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={date_str}",
        "la_liga": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates={date_str}",
        "bundesliga": "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard?dates={date_str}",
        "serie_a": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard?dates={date_str}",
        "ligue_1": "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard?dates={date_str}",
        "ucl": "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates={date_str}",
        "mma": "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates={date_str}",
    }
    url = sport_endpoints.get(sport.lower(), sport_endpoints["nba"]).format(date_str=date_str)
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
        odds_list = comp.get("odds") or [{}]
        odds_data = odds_list[0] if odds_list and odds_list[0] else {}
        spread = odds_data.get("spread", 0)
        over_under = odds_data.get("overUnder", 0)
        spread_odds = odds_data.get("spreadOdds", {})
        details = odds_data.get("details", "")

        # Parse spread from details (e.g., "OKC -19.5")
        home = teams.get("home", {})
        away = teams.get("away", {})

        # Determine which team is favored and assign spread
        home_spread = None
        away_spread = None
        if spread and spread != 0:
            # ESPN returns 'spread' as the absolute value of the point spread
            # 'details' tells us who is favored: "OKC -19.5" or "COL -142"
            # CRITICAL: For NHL/MLB, details contains MONEYLINE (e.g. "COL -142"),
            # not the actual spread. Use the 'spread' API field for the value,
            # and 'details' only to determine favorite direction.
            spread_val = abs(float(spread))
            if details:
                parts = details.split(" ")
                fav_abbr = parts[0] if parts else ""
                # For NBA/NFL, details value matches the spread. For NHL/MLB it's moneyline.
                # Always trust the 'spread' API field for the actual spread value.
                if fav_abbr == home.get("abbr"):
                    home_spread = -spread_val  # Home is favored (negative spread)
                    away_spread = spread_val
                else:
                    away_spread = -spread_val
                    home_spread = spread_val
            else:
                # No details — use spread sign directly
                # ESPN spread field: negative means home favored
                home_spread = float(spread)
                away_spread = -float(spread)

        # Extract ACTUAL DK spread/total/ML odds from ESPN's detailed odds object
        # ESPN provides: pointSpread.home/away.close.odds, total.over/under.close.odds, moneyline
        home_spread_odds = None  # Actual DK juice on the spread (e.g., -285)
        away_spread_odds = None
        over_odds = None
        under_odds = None
        ps_data = odds_data.get("pointSpread", {})
        if ps_data:
            try:
                home_ps = ps_data.get("home", {}).get("close", {})
                away_ps = ps_data.get("away", {}).get("close", {})
                if home_ps.get("odds"):
                    home_spread_odds = int(home_ps["odds"])
                if away_ps.get("odds"):
                    away_spread_odds = int(away_ps["odds"])
            except (ValueError, TypeError):
                pass
        total_data = odds_data.get("total", {})
        if total_data:
            try:
                over_close = total_data.get("over", {}).get("close", {})
                under_close = total_data.get("under", {}).get("close", {})
                if over_close.get("odds"):
                    over_odds = int(over_close["odds"])
                if under_close.get("odds"):
                    under_odds = int(under_close["odds"])
            except (ValueError, TypeError):
                pass

        # Extract DK deep links for bet slip (from ESPN's link.href with preurl param)
        dk_spread_links = {"home": "", "away": ""}
        dk_total_links = {"over": "", "under": ""}
        dk_game_link = ""
        if ps_data:
            for side in ("home", "away"):
                raw = ps_data.get(side, {}).get("close", {}).get("link", {}).get("href", "")
                if "preurl=" in raw:
                    dk_spread_links[side] = urllib.parse.unquote(raw.split("preurl=")[-1])
                elif raw:
                    dk_spread_links[side] = raw
        if total_data:
            for side in ("over", "under"):
                raw = total_data.get(side, {}).get("close", {}).get("link", {}).get("href", "")
                if "preurl=" in raw:
                    dk_total_links[side] = urllib.parse.unquote(raw.split("preurl=")[-1])
                elif raw:
                    dk_total_links[side] = raw
        game_link_raw = odds_data.get("link", {}).get("href", "")
        if "preurl=" in game_link_raw:
            dk_game_link = urllib.parse.unquote(game_link_raw.split("preurl=")[-1])
        elif game_link_raw:
            dk_game_link = game_link_raw

        game = {
            "home": home,
            "away": away,
            "status": status,
            "is_final": status == "STATUS_FINAL",
            "home_spread": home_spread,
            "away_spread": away_spread,
            "home_spread_odds": home_spread_odds,  # Actual DK juice
            "away_spread_odds": away_spread_odds,
            "over_under": over_under,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "event_str": f"{away.get('name', '?')} @ {home.get('name', '?')}",
            "event_short": f"{away.get('abbr', '?')} @ {home.get('abbr', '?')}",
            "start_time": event.get("date", ""),
            "odds_details": details,
            "dk_spread_links": dk_spread_links,
            "dk_total_links": dk_total_links,
            "dk_game_link": dk_game_link,
        }
        games.append(game)

    return games


def fetch_nba_schedule_and_odds(date_str: str) -> list[dict]:
    """Backward-compatible wrapper for NBA schedule fetching."""
    return fetch_schedule_and_odds(date_str, "nba")


def fetch_dratings_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch model predictions from DRatings.
    Returns dict keyed by "AWAY_NAME@HOME_NAME" with predicted scores and win probs.

    DRatings HTML row format (pipe-separated after stripping tags):
    date | time | away_team | (away_record) | home_team | (home_record) |
    away_prob% | home_prob% | ...odds... | away_score | home_score | total | ...

    sport: "nba", "nhl", or "ncaam"
    """
    sport_urls = {
        "nba": "https://www.dratings.com/predictor/nba-basketball-predictions/",
        "nhl": "https://www.dratings.com/predictor/nhl-hockey-predictions/",
        "mlb": "https://www.dratings.com/predictor/mlb-baseball-predictions/",
        "nfl": "https://www.dratings.com/predictor/nfl-football-predictions/",
        "mls": "https://www.dratings.com/predictor/mls-soccer-predictions/",
        "epl": "https://www.dratings.com/predictor/english-premier-league-predictions/",
        "la_liga": "https://www.dratings.com/predictor/spain-la-liga-predictions/",
        "bundesliga": "https://www.dratings.com/predictor/german-bundesliga-predictions/",
        "serie_a": "https://www.dratings.com/predictor/italy-serie-a-predictions/",
        "ligue_1": "https://www.dratings.com/predictor/france-ligue-1-predictions/",
        "ucl": "https://www.dratings.com/predictor/champions-league-predictions/",
        # MMA: DRatings doesn't have UFC predictions — will return empty, that's fine
    }
    url = sport_urls.get(sport.lower(), sport_urls["nba"])
    predictions = {}

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Sport-specific score detection config
        # NBA/NFL: 2-3 digits before decimal, 1 after, range 70-160
        # NHL: 1-2 digits before decimal, 1-2 after, range 0.5-8
        # MLB: 1-2 digits before decimal, 1-2 after, range 0.5-15
        # Soccer: 1 digit before decimal, 1-2 after, range 0.3-5
        score_config = {
            "nba":  {"regex": r'^(\d{2,3}\.\d{1,2})$', "min": 70, "max": 160},
            "nfl":  {"regex": r'^(\d{2,3}\.\d{1,2})$', "min": 10, "max": 60},
            "nhl":  {"regex": r'^(\d{1,2}\.\d{1,2})$', "min": 0.5, "max": 8},
            "mlb":  {"regex": r'^(\d{1,2}\.\d{1,2})$', "min": 0.5, "max": 15},
            "mls":  {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "epl":  {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "la_liga":    {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "bundesliga": {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "serie_a":    {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "ligue_1":    {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
            "ucl":        {"regex": r'^(\d{1}\.\d{1,2})$',   "min": 0.3, "max": 5},
        }
        cfg = score_config.get(sport.lower(), score_config["nba"])
        score_re = re.compile(cfg["regex"])
        score_min, score_max = cfg["min"], cfg["max"]

        # Minimum cells: NHL/MLB/soccer tables may have fewer columns than NBA
        min_cells = 6 if sport.lower() in ("nhl", "mlb", "mls", "epl", "la_liga", "bundesliga", "serie_a", "ligue_1", "ucl") else 10

        # Non-team strings to filter out (varies by sport)
        non_team_strings = {
            "Eastern Conference", "Western Conference", "Atlantic Division",
            "Pacific Division", "Central Division", "Metropolitan Division",
            "American League", "National League", "Upcoming Games",
        }

        # Extract table rows
        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

        for tr in trs:
            # Strip HTML tags, split by cell boundaries
            text = re.sub(r'<[^>]+>', '|', tr)
            cells = [x.strip() for x in text.split('|') if x.strip()]

            if len(cells) < min_cells:
                continue

            scores = []
            team_names = []
            records = []

            for cell in cells:
                # Match predicted score (sport-specific format and range)
                m = score_re.match(cell)
                if m:
                    val = float(m.group(1))
                    if score_min <= val <= score_max:
                        scores.append(val)

                # Match team name — capitalized word(s)
                # Multi-word: "Manchester United", "St. Louis Blues"
                # Single-word (soccer): "Bournemouth", "Liverpool", "Wolverhampton"
                is_soccer = sport.lower() in ("mls", "epl", "la_liga", "bundesliga", "serie_a", "ligue_1", "ucl")
                if is_soccer:
                    # Allow single-word names (min 4 chars to avoid matching "Win", "Draw", etc.)
                    if re.match(r'^[A-Z][a-z]{3,}(?: [A-Z][a-z]+)*$', cell):
                        if cell not in non_team_strings and cell not in ("Time", "Teams", "Draw", "Best", "Goals", "Total", "Value", "Loss", "Final", "More", "Details", "Sportsbook", "DRatings"):
                            team_names.append(cell)
                else:
                    if re.match(r'^[A-Z][a-z]+\.?(?: [A-Z][a-z]+)+$', cell):
                        if cell not in non_team_strings:
                            team_names.append(cell)

                # Match record: (W-L), (W-L-OTL), or (W-L-T)
                rm = re.match(r'^\((\d+-\d+(?:-\d+)?)\)$', cell)
                if rm:
                    records.append(rm.group(1))

            # We need exactly 2 team names and 2+ scores (away_score, home_score, [total])
            if len(team_names) >= 2 and len(scores) >= 2:
                away_name = team_names[0]
                home_name = team_names[1]
                away_score = scores[0]
                home_score = scores[1]

                # Map full names to abbreviations based on sport
                if sport.lower() == "nhl":
                    team_map = NHL_TEAM_NAME_TO_ABBR
                elif sport.lower() == "mlb":
                    team_map = MLB_TEAM_NAME_TO_ABBR
                elif sport.lower() == "ncaam":
                    team_map = NCAAM_TEAM_NAME_TO_ABBR
                else:
                    team_map = TEAM_NAME_TO_ABBR

                away_abbr = team_map.get(away_name, away_name[:3].upper())
                home_abbr = team_map.get(home_name, home_name[:3].upper())

                key = f"{away_abbr}@{home_abbr}"
                predictions[key] = {
                    "away_name": away_name,
                    "home_name": home_name,
                    "away_abbr": away_abbr,
                    "home_abbr": home_abbr,
                    "away_score": away_score,
                    "home_score": home_score,
                    "margin": round(home_score - away_score, 1),
                }

                print(f"    {away_abbr} {away_score} @ {home_abbr} {home_score} (margin: {home_score - away_score:+.1f})")

        print(f"  DRatings: found {len(predictions)} game predictions")

    except Exception as e:
        print(f"  DRatings fetch error: {e}", file=sys.stderr)

    return predictions


def fetch_dimers_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch predictions from Levy Edge (Dimers backend) API.
    Returns dict keyed by "AWAY_ABBR@HOME_ABBR" with predicted scores.

    The API uses Season/Round numbers. We search for the round matching today's date.
    """
    sport_map = {"nba": "NBA", "nhl": "NHL", "mlb": "MLB", "nfl": "NFL"}
    api_sport = sport_map.get(sport.lower())
    if not api_sport:
        return {}

    predictions = {}
    today_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    try:
        # Determine season year
        year = int(date_str[:4])
        month = int(date_str[4:6])
        # MLB season starts in March and uses the current year (2026 season = Season=2026)
        # NBA/NHL seasons span two years and use the starting year (2025-26 = Season=2025)
        if api_sport == "MLB":
            season = year  # MLB 2026 season = Season=2026
        else:
            season = year - 1 if month < 7 else year  # Before July = previous year's season

        # Search for today's round by scanning recent rounds
        # MLB rounds start at 1 for Opening Day (~late March), incrementing ~1/day
        # NBA/NHL rounds are higher numbers late in the season
        # Base rounds updated April 2026 — NBA ~167, NHL ~181 by season end
        base_round = {"NBA": 165, "NHL": 178, "MLB": 10, "NFL": 15}.get(api_sport, 100)

        # Find the round matching today's date.
        # Challenge: Levy Edge uses UTC dates, so March 18 evening ET = March 19 UTC.
        # Strategy: find ALL rounds within ±24h, then pick the one closest to
        # target_date at 7PM ET (midnight UTC = typical game time).
        found_round = None
        target_dt = datetime.strptime(date_str, "%Y%m%d")
        # Target: 7 PM ET = midnight UTC of the next day
        target_ts = (target_dt.replace(tzinfo=timezone.utc) + timedelta(hours=24)).timestamp()
        best_round = None
        best_diff = float("inf")

        for offset in range(-10, 15):
            r = base_round + offset
            if r < 1:
                continue
            url = f"https://levy-edge.statsinsider.com.au/round/matches?Sport={api_sport}&Round={r}&Season={season}&strip=true"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    rdata = json.loads(resp.read())
                if not isinstance(rdata, list) or not rdata:
                    continue

                ds = rdata[0].get("MatchData", {}).get("DateStamp", 0)
                if ds:
                    diff = abs(ds - target_ts)
                    if diff < 24 * 3600 and diff < best_diff:
                        best_diff = diff
                        best_round = r
                else:
                    match_date = str(rdata[0].get("MatchData", {}).get("Date", ""))
                    if today_iso in match_date:
                        best_round = r
                        break
            except:
                continue

        found_round = best_round

        if found_round is None:
            print(f"  Dimers: could not find round for {today_iso}")
            return {}

        # Fetch the found round
        url = f"https://levy-edge.statsinsider.com.au/round/matches?Sport={api_sport}&Round={found_round}&Season={season}&strip=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        for game in data:
            pre = game.get("PreData", {})
            match_data = game.get("MatchData", {})
            sid = match_data.get("SIMatchID", "") or game.get("LiveData", {}).get("SIMatchID", "")

            pred_away = pre.get("PredAwayScore")
            pred_home = pre.get("PredHomeScore")

            # Extract team abbreviations from SIMatchID (format: SPORT_SEASON_ROUND_AWAY_HOME)
            parts = sid.split("_")
            if len(parts) >= 5:
                away_abbr = parts[3]
                home_abbr = parts[4]
            else:
                continue

            # If predicted scores are missing (common for MLB early season),
            # derive implied scores from Pythagorean win probabilities.
            # margin = norm.ppf(home_win_prob) * sport_SD
            # Then split into scores using a sport-typical total.
            if pred_away is None or pred_home is None:
                pythag_home = pre.get("PythagHome")
                pythag_away = pre.get("PythagAway")
                if pythag_home is None or pythag_away is None:
                    continue
                # Derive margin from win probability using inverse normal CDF
                # For MLB: typical total ~8.5 runs, SD ~4.5
                # For others: skip (they should have PredScores)
                if api_sport == "MLB":
                    from math import erfc, sqrt, log
                    # Rational approximation of inverse normal CDF (Beasley-Springer-Moro)
                    def _norm_ppf(p: float) -> float:
                        """Inverse normal CDF approximation (good to ~1e-6)."""
                        if p <= 0 or p >= 1:
                            return 0.0
                        # Use symmetry for p < 0.5
                        if p < 0.5:
                            return -_norm_ppf(1 - p)
                        t = sqrt(-2 * log(1 - p))
                        # Abramowitz & Stegun 26.2.23 rational approx
                        c0, c1, c2 = 2.515517, 0.802853, 0.010328
                        d1, d2, d3 = 1.432788, 0.189269, 0.001308
                        return t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)

                    implied_margin = _norm_ppf(pythag_home) * GAME_SD.get("mlb_spread", 4.57)
                    typical_total = 8.5  # MLB average game total
                    pred_home = round((typical_total + implied_margin) / 2, 1)
                    pred_away = round((typical_total - implied_margin) / 2, 1)
                else:
                    continue

            key = f"{away_abbr}@{home_abbr}"
            predictions[key] = {
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                "away_score": round(pred_away, 1),
                "home_score": round(pred_home, 1),
                "margin": round(pred_home - pred_away, 1),
                "pythag_away": pre.get("PythagAway", 0),
                "pythag_home": pre.get("PythagHome", 0),
            }

            print(f"    {away_abbr} {pred_away:.1f} @ {home_abbr} {pred_home:.1f} (margin: {pred_home - pred_away:+.1f})")

        print(f"  Dimers: found {len(predictions)} game predictions (round {found_round})")

    except Exception as e:
        print(f"  Dimers fetch error: {e}", file=sys.stderr)

    return predictions


def build_ensemble(dratings: dict, dimers: dict, sport: str, extra_sources: dict = None) -> dict:
    """
    Average predictions from all available sources into an ensemble.

    Primary sources: DRatings (always has correct H/A from ESPN) and Dimers.
    Extra sources: dict of {"source_name": predictions_dict} from fetch_sources.py.

    Key matching: Sources may use different home/away ordering
    for the same game (e.g., "MTL@DET" vs "DET@MTL"). We match by canonical
    key (sorted team pair) and normalize to DRatings' perspective if available.

    Returns dict keyed by "AWAY@HOME" (DRatings perspective) with ensemble predictions.
    """
    extra_sources = extra_sources or {}
    # Disagreement thresholds by sport
    disagree_thresh = {"nba": 3.0, "nfl": 3.0, "nhl": 0.5, "mlb": 0.5,
                       "epl": 0.3, "mls": 0.3}
    thresh = disagree_thresh.get(sport.lower(), 3.0)

    # Common abbreviation aliases between ESPN/DRatings and Dimers
    abbr_aliases = {
        "GSW": "GS", "GS": "GSW", "NOP": "NO", "NO": "NOP",
        "NYK": "NY", "NY": "NYK", "SAS": "SA", "SA": "SAS",
        "WAS": "WSH", "WSH": "WAS", "VGK": "VEG", "VEG": "VGK",
        "NJD": "NJ", "NJ": "NJD", "SJS": "SJ", "SJ": "SJS",
        "TBL": "TB", "TB": "TBL", "LAK": "LA", "LA": "LAK",
        "CHW": "CWS", "CWS": "CHW", "SDP": "SD", "SD": "SDP",
        "SFG": "SF", "SF": "SFG", "TBR": "TB", "WSN": "WSH",
        "KCR": "KC", "KC": "KCR", "AZ": "ARI", "ARI": "AZ",
        "VOL": "UTA", "UTA": "VOL",  # Utah Jazz / Hockey rebrands
    }

    def canonical_key(key):
        """Create a sorted team-pair key for matching, with alias resolution."""
        parts = key.split("@")
        if len(parts) != 2:
            return key
        t1, t2 = parts[0].upper(), parts[1].upper()
        # Normalize both through aliases
        t1n = abbr_aliases.get(t1, t1)
        t2n = abbr_aliases.get(t2, t2)
        return tuple(sorted([t1, t1n, t2, t2n]))  # Broad match set

    def teams_match(key1, key2):
        """Check if two AWAY@HOME keys represent the same game.
        Returns (matched: bool, reversed: bool).
        Reversed means teams are the same but home/away flipped — one source
        got it wrong. This IS the same game (teams don't play twice in a night)."""
        p1 = key1.split("@")
        p2 = key2.split("@")
        if len(p1) != 2 or len(p2) != 2:
            return False, False
        t1a, t1h = p1[0].upper(), p1[1].upper()
        t2a, t2h = p2[0].upper(), p2[1].upper()
        aliases_1a = {t1a, abbr_aliases.get(t1a, t1a)}
        aliases_1h = {t1h, abbr_aliases.get(t1h, t1h)}
        aliases_2a = {t2a, abbr_aliases.get(t2a, t2a)}
        aliases_2h = {t2h, abbr_aliases.get(t2h, t2h)}
        fwd = bool(aliases_1a & aliases_2a) and bool(aliases_1h & aliases_2h)
        rev = bool(aliases_1a & aliases_2h) and bool(aliases_1h & aliases_2a)
        if fwd:
            return True, False
        if rev:
            return True, True
        return False, False

    ensemble = {}
    dimers_matched = set()

    # Process DRatings predictions first (they have full team names)
    for dr_key, dr in dratings.items():
        # Try to find matching Dimers prediction
        dm = None
        dm_key = None
        dm_reversed = False
        for dk, dv in dimers.items():
            if dk in dimers_matched:
                continue
            matched, reversed_ = teams_match(dr_key, dk)
            if matched:
                dm = dv
                dm_key = dk
                dm_reversed = reversed_
                break

        if dm:
            dimers_matched.add(dm_key)
            # When reversed, one source has home/away flipped for the SAME game.
            # Both models predict "away team scores X, home team scores Y" — but they
            # disagree on who's away/home. To compare apples-to-apples, we match by
            # TEAM IDENTITY: find each team's predicted score across both sources.
            #
            # Example: DRatings DET@WSH: DET(away)=121.5, WSH(home)=108.1
            #          Dimers  WAS@DET: WAS(away)=121.5, DET(home)=108.4
            # DET's score: DR=121.5 (as away), DM=108.4 (as home)
            # WSH's score: DR=108.1 (as home), DM=121.5 (as away)
            # The ~13pt difference per team is from home advantage being applied
            # to different teams. Average removes the bias:
            # DET avg: (121.5+108.4)/2 = 115.0, WSH avg: (108.1+121.5)/2 = 114.8
            if dm_reversed:
                # H/A flipped — same game, one source has home/away wrong.
                # DRatings matches ESPN schedule, so USE DRATINGS SCORES as primary.
                # Dimers confirms team strength agreement (low magnitude diff = high confidence).
                dm_margin_magnitude = abs(dm["margin"])
                dr_margin_magnitude = abs(dr["margin"])
                margin_diff = abs(dr_margin_magnitude - dm_margin_magnitude)
                contested = margin_diff > thresh

                ensemble[dr_key] = {
                    "away_abbr": dr.get("away_abbr", ""),
                    "home_abbr": dr.get("home_abbr", ""),
                    "away_name": dr.get("away_name", ""),
                    "home_name": dr.get("home_name", ""),
                    "away_score": dr["away_score"],  # Use DRatings (correct H/A)
                    "home_score": dr["home_score"],
                    "margin": dr["margin"],           # Use DRatings margin
                    "sources": 2,
                    "source_label": "DRatings + Dimers",
                    "contested": contested,
                    "disagreement": round(margin_diff, 1),
                    "dr_margin": dr["margin"],
                    "dm_margin": dm["margin"],
                }
            else:
                # Same H/A direction — safe to average
                dm_away_score = dm["away_score"]
                dm_home_score = dm["home_score"]
                dm_margin = dm["margin"]

                avg_away = round((dr["away_score"] + dm_away_score) / 2, 1)
                avg_home = round((dr["home_score"] + dm_home_score) / 2, 1)
                margin_diff = abs(dr["margin"] - dm_margin)
                contested = margin_diff > thresh

                ensemble[dr_key] = {
                    "away_abbr": dr.get("away_abbr", ""),
                    "home_abbr": dr.get("home_abbr", ""),
                    "away_name": dr.get("away_name", ""),
                    "home_name": dr.get("home_name", ""),
                    "away_score": avg_away,
                    "home_score": avg_home,
                    "margin": round(avg_home - avg_away, 1),
                    "sources": 2,
                    "source_label": "DRatings + Dimers",
                    "contested": contested,
                    "disagreement": round(margin_diff, 1),
                    "dr_margin": dr["margin"],
                    "dm_margin": dm_margin,
                }
        else:
            ensemble[dr_key] = {**dr, "sources": 1, "source_label": "DRatings only",
                                "contested": False, "disagreement": 0}

    # Add unmatched Dimers predictions
    for dm_key, dm in dimers.items():
        if dm_key not in dimers_matched:
            ensemble[dm_key] = {**dm, "sources": 1, "source_label": "Dimers only",
                                "contested": False, "disagreement": 0}

    # ── Integrate extra sources (Massey, OddsShark, Sagarin, Club Elo, etc.) ──
    if extra_sources:
        for game_key, ens_val in ensemble.items():
            extra_margins = []
            extra_names = []

            for src_name, src_preds in extra_sources.items():
                # Try to match this game across the source
                matched_pred = None
                for sk, sv in src_preds.items():
                    m, rev = teams_match(game_key, sk)
                    if m:
                        matched_pred = sv
                        if rev:
                            # Flip margin if home/away reversed
                            matched_pred = {**sv, "margin": -sv["margin"]}
                        break

                if matched_pred is not None:
                    extra_margins.append(matched_pred["margin"])
                    extra_names.append(src_name)

            if extra_margins:
                # Recalculate ensemble with all sources
                # Primary margin (from DRatings/Dimers ensemble)
                primary_margin = ens_val["margin"]
                all_margins = [primary_margin] + extra_margins
                avg_margin = round(sum(all_margins) / len(all_margins), 1)

                # Update source count and label
                old_sources = ens_val.get("sources", 1)
                old_label = ens_val.get("source_label", "")
                new_count = old_sources + len(extra_margins)
                new_label = old_label + " + " + " + ".join(extra_names)

                # Recalculate scores from averaged margin
                total = ens_val["away_score"] + ens_val["home_score"]
                new_home = round((total + avg_margin) / 2, 1)
                new_away = round((total - avg_margin) / 2, 1)

                # Check for disagreement across ALL sources
                margin_spread = max(all_margins) - min(all_margins)
                contested = margin_spread > thresh * 2  # Higher bar with more sources

                ens_val.update({
                    "away_score": new_away,
                    "home_score": new_home,
                    "margin": avg_margin,
                    "sources": new_count,
                    "source_label": new_label,
                    "contested": contested,
                    "disagreement": round(margin_spread, 1),
                    "all_margins": all_margins,
                })

        # Add games found ONLY in extra sources (not in DRatings or Dimers)
        extra_only_keys = set()
        for src_name, src_preds in extra_sources.items():
            for sk in src_preds:
                # Check if already in ensemble
                already = False
                for ek in ensemble:
                    m, _ = teams_match(ek, sk)
                    if m:
                        already = True
                        break
                if not already:
                    extra_only_keys.add(sk)

        for sk in extra_only_keys:
            margins = []
            names = []
            base_pred = None
            for src_name, src_preds in extra_sources.items():
                for ssk, sv in src_preds.items():
                    m, rev = teams_match(sk, ssk)
                    if m:
                        if base_pred is None:
                            base_pred = sv if not rev else {
                                **sv,
                                "away_abbr": sv["home_abbr"], "home_abbr": sv["away_abbr"],
                                "away_score": sv["home_score"], "home_score": sv["away_score"],
                                "margin": -sv["margin"],
                            }
                        margin = sv["margin"] if not rev else -sv["margin"]
                        margins.append(margin)
                        names.append(src_name)
                        break

            if base_pred and margins:
                avg_margin = round(sum(margins) / len(margins), 1)
                total = base_pred["away_score"] + base_pred["home_score"]
                new_home = round((total + avg_margin) / 2, 1)
                new_away = round((total - avg_margin) / 2, 1)
                ensemble[sk] = {
                    "away_abbr": base_pred["away_abbr"],
                    "home_abbr": base_pred["home_abbr"],
                    "away_name": base_pred.get("away_name", ""),
                    "home_name": base_pred.get("home_name", ""),
                    "away_score": new_away,
                    "home_score": new_home,
                    "margin": avg_margin,
                    "sources": len(margins),
                    "source_label": " + ".join(names),
                    "contested": False,
                    "disagreement": round(max(margins) - min(margins), 1) if len(margins) > 1 else 0,
                }

    return ensemble


# NBA team name to abbreviation mapping
TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NO", "New York Knicks": "NY", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SA",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WSH",
}

# NHL team name to abbreviation mapping
NHL_TEAM_NAME_TO_ABBR = {
    "Anaheim Ducks": "ANA", "Arizona Coyotes": "ARI", "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF", "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL", "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL", "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL", "Nashville Predators": "NSH", "New Jersey Devils": "NJ",
    "New York Islanders": "NYI", "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJ",
    "Seattle Kraken": "SEA", "St. Louis Blues": "STL", "Tampa Bay Lightning": "TB",
    "Toronto Maple Leafs": "TOR", "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH", "Winnipeg Jets": "WPG",
}

# MLB team name to abbreviation mapping
MLB_TEAM_NAME_TO_ABBR = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}

# NCAAM team name to abbreviation mapping (major schools)
NCAAM_TEAM_NAME_TO_ABBR = {
    "Duke Blue Devils": "DUKE", "North Carolina Tar Heels": "UNC", "Kansas Jayhawks": "KU",
    "Kentucky Wildcats": "UK", "UCLA Bruins": "UCLA", "Michigan Wolverines": "MICH",
    "Indiana Hoosiers": "IU", "Ohio State Buckeyes": "OSU", "Gonzaga Bulldogs": "GONZ",
    "Auburn Tigers": "AU", "Tennessee Volunteers": "TENN", "Purdue Boilermakers": "PURDUE",
    "Alabama Crimson Tide": "BAMA", "Arizona Wildcats": "ARI", "Baylor Bears": "BAYLOR",
    "Houston Cougars": "HOU", "Iowa Hawkeyes": "IOWA", "Marquette Golden Eagles": "MARQ",
    "Providence Friars": "PROV", "Connecticut Huskies": "CONN", "Creighton Bluejays": "CREIGHTON",
    "DePaul Blue Demons": "DEPAUL", "Georgetown Hoyas": "GTOWN", "Villanova Wildcats": "NOVA",
    "Saint John's Red Storm": "SJU", "Butler Bulldogs": "BUTLER", "Dayton Flyers": "DAYTON",
    "VCU Rams": "VCU", "San Diego State Aztecs": "SDSU", "TCU Horned Frogs": "TCU",
}


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
def normal_cdf(x: float) -> float:
    """Approximate the standard normal CDF using Abramowitz & Stegun formula.
    Accurate to ~0.0005. No scipy needed."""
    import math
    if x < 0:
        return 1.0 - normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - d * math.exp(-0.5 * x * x) * poly


def cushion_to_probability(cushion: float, sport: str, market: str) -> float | None:
    """Convert points of cushion to cover probability using normal distribution.

    Uses sport-specific combined SD (game variance + model error).
    Returns None if the sport doesn't have researched SD values.
    """
    key = f"{sport.lower()}_{market.lower()}"
    sd = GAME_SD.get(key)

    if sd is None:
        # No researched SD for this sport/market — can't calculate probability
        return None

    if sd <= 0 or cushion <= 0:
        return 0.50

    z = cushion / sd
    return normal_cdf(z)


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


def discount_edge_for_sizing(raw_edge: float) -> float:
    """Reduce large edges to realistic levels for Kelly calculation.
    Raw edge is used for filtering; discounted edge is used for sizing.
    10%+ edges hit only 58.8% vs 75% for 5-8% edges."""
    for floor, cap in EDGE_DISCOUNT_TIERS:
        if raw_edge >= floor:
            return cap
    return raw_edge


def get_effective_min_edge(sport: str, market: str, spread_points: float, base_min_edge: float) -> float:
    """Apply sport-specific min edge overrides.
    NBA spreads are 5-7 (41.7%) — raise threshold."""
    if sport.lower() == "nba" and market.lower() in ("spread", "spreads"):
        abs_spread = abs(spread_points) if spread_points else 0
        if abs_spread > NBA_LARGE_SPREAD_THRESHOLD:
            return max(base_min_edge, NBA_LARGE_SPREAD_MIN_EDGE)
        return max(base_min_edge, NBA_SPREAD_MIN_EDGE)
    # MLB run line: model overestimates due to right-skewed margins
    if sport.lower() == "mlb" and market.lower() in ("spread", "spreads"):
        return max(base_min_edge, MLB_SPREAD_MIN_EDGE)
    return base_min_edge


def calculate_edge(game: dict, predictions: dict, b2b_teams: set, sport: str = "nba") -> dict | None:
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

    # Try to find DRatings prediction — try multiple key formats
    key = f"{away_abbr}@{home_abbr}"
    pred = predictions.get(key)

    if not pred:
        # ESPN uses slightly different abbreviations than DRatings sometimes
        # Sport-specific alternate mappings
        alt_maps = {
            "nba": {"GSW": "GS", "GS": "GSW", "NOP": "NO", "NO": "NOP",
                    "NYK": "NY", "NY": "NYK", "SAS": "SA", "SA": "SAS",
                    "WAS": "WSH", "WSH": "WAS"},
            "nhl": {"VGK": "VEG", "VEG": "VGK", "NJD": "NJ", "NJ": "NJD",
                    "SJS": "SJ", "SJ": "SJS", "TBL": "TB", "TB": "TBL",
                    "LAK": "LA", "LA": "LAK", "WSH": "WAS", "WAS": "WSH"},
            "mlb": {"AZ": "ARI", "ARI": "AZ", "CHW": "CWS", "CWS": "CHW",
                    "SDP": "SD", "SD": "SDP", "SFG": "SF", "SF": "SFG",
                    "TBR": "TB", "TB": "TBR", "WSN": "WSH", "WSH": "WSN",
                    "KCR": "KC", "KC": "KCR"},
        }
        alt_map = alt_maps.get(sport.lower(), alt_maps.get("nba", {}))
        alt_away = alt_map.get(away_abbr, away_abbr)
        alt_home = alt_map.get(home_abbr, home_abbr)
        for a in [away_abbr, alt_away]:
            for h in [home_abbr, alt_home]:
                pred = predictions.get(f"{a}@{h}")
                if pred:
                    break
            if pred:
                break

    if not pred:
        return None

    # Model predicted margin (positive = home favored)
    model_home_margin = pred["home_score"] - pred["away_score"]

    # Evaluate BOTH sides of the spread and pick whichever has a bigger edge
    # ESPN spread: negative = favored. e.g., home_spread = -19.5 means home favored by 19.5
    espn_spread = game["home_spread"]  # from home perspective

    # Build candidate list: evaluate underdog AND favorite
    candidates = []
    DISCRETE_SPORTS = {"nhl", "mlb", "mls", "epl", "la_liga", "bundesliga", "serie_a", "ligue_1", "ucl"}

    # Identify underdog and favorite
    if espn_spread > 0:
        dog_team, dog_spread, dog_side = home, espn_spread, "home"
        fav_team, fav_spread, fav_side = away, abs(espn_spread), "away"
    elif espn_spread < 0:
        dog_team, dog_spread, dog_side = away, game.get("away_spread", abs(espn_spread)), "away"
        fav_team, fav_spread, fav_side = home, abs(espn_spread), "home"
    else:
        return None  # Pick'em, skip for now

    if dog_spread <= 0:
        return None

    # Calculate underdog cover probability
    if sport.lower() in DISCRETE_SPORTS:
        import math as _math
        from skellam import skellam_cdf
        k = _math.floor(dog_spread)
        if dog_side == "home":
            dog_prob = skellam_cdf(k, pred["away_score"], pred["home_score"])
        else:
            dog_prob = skellam_cdf(k, pred["home_score"], pred["away_score"])
        if dog_prob is None or dog_prob <= 0:
            dog_prob = None
    else:
        spread_cushion_dog = dog_spread - abs(model_home_margin)
        dog_prob = cushion_to_probability(spread_cushion_dog, sport, "spread")

    # Favorite cover probability = 1 - underdog cover probability
    fav_prob = (1 - dog_prob) if dog_prob is not None else None

    # Get DK odds for each side
    def get_dk_odds(side, spread_val):
        if side == "home" and game.get("home_spread_odds"):
            return game["home_spread_odds"]
        elif side == "away" and game.get("away_spread_odds"):
            return game["away_spread_odds"]
        # Fallback defaults
        if sport.lower() == "nhl":
            return -190
        elif sport.lower() == "mlb":
            return -170
        else:
            odds = -110
            if spread_val >= 15:
                odds = -112
            if spread_val >= 18:
                odds = -115
            return odds

    # Evaluate underdog side
    if dog_prob is not None:
        dog_odds = get_dk_odds(dog_side, dog_spread)
        dog_implied = american_to_implied(dog_odds)
        dog_cushion = dog_spread - abs(model_home_margin)
        candidates.append({
            "team": dog_team, "side": dog_side, "spread": dog_spread,
            "pick_label": f"{dog_team['name']} +{dog_spread}",
            "model_prob": dog_prob, "dk_odds": dog_odds, "implied_prob": dog_implied,
            "spread_cushion": dog_cushion, "is_favorite": False,
        })

    # Evaluate favorite side
    if fav_prob is not None:
        fav_odds = get_dk_odds(fav_side, fav_spread)
        fav_implied = american_to_implied(fav_odds)
        fav_cushion = abs(model_home_margin) - fav_spread  # how much the model margin exceeds the spread
        candidates.append({
            "team": fav_team, "side": fav_side, "spread": fav_spread,
            "pick_label": f"{fav_team['name']} -{fav_spread}",
            "model_prob": fav_prob, "dk_odds": fav_odds, "implied_prob": fav_implied,
            "spread_cushion": fav_cushion, "is_favorite": True,
        })

    if not candidates:
        return None

    # Apply situational adjustments to each candidate, then pick the best edge
    source_label = pred.get("source_label", "DRatings")
    best = None
    best_edge = -1

    for cand in candidates:
        pick_team = cand["team"]
        pick_side = cand["side"]
        model_prob = cand["model_prob"]

        # Tanking check
        tank_info = TANK_TEAMS_2026.get(pick_team.get("abbr", ""), None)
        tank_note = ""
        if tank_info and tank_info["confirmed"]:
            continue  # Skip tanking teams
        if tank_info and not tank_info["confirmed"]:
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
        implied_prob = cand["implied_prob"]
        edge = model_prob - implied_prob

        # Heavy juice filter: picks at -200 or worse need 5% edge, not 3%
        # Rationale: at -250, you risk $250 to win $100. A 3% edge isn't worth it.
        dk_odds_val = cand.get("dk_odds", -110)
        min_edge = MIN_EDGE_HIGH  # default 3%
        if dk_odds_val < -200:
            min_edge = 0.05  # 5% for heavy favorites

        # NBA spread calibration override (April 2026): 5% base, 8% for >12pt spreads
        spread_pts = cand.get("spread", 0)
        min_edge = get_effective_min_edge(sport, "spread", spread_pts, min_edge)

        if edge >= min_edge and edge > best_edge:
            best_edge = edge
            best = {
                "cand": cand, "model_prob": model_prob, "edge": edge,
                "implied_prob": implied_prob, "tank_note": tank_note, "b2b_note": b2b_note,
                "tank_info": tank_info,
            }

    if best is None:
        return None

    cand = best["cand"]
    pick_team = cand["team"]
    pick_side = cand["side"]
    model_prob = best["model_prob"]
    edge = best["edge"]
    implied_prob = best["implied_prob"]
    dk_odds = cand["dk_odds"]
    spread_cushion = cand["spread_cushion"]
    tank_note = best["tank_note"]
    b2b_note = best["b2b_note"]
    tank_info = best["tank_info"]

    # Flag suspicious edges — don't cap, but warn
    suspicious = edge > SUSPICIOUS_EDGE

    # Kelly sizing — apply graduated edge discount and single-source penalty
    sizing_edge = discount_edge_for_sizing(edge)
    decimal_odds = american_to_decimal(dk_odds)
    kelly_fraction = KELLY_FRACTION_HIGH
    is_single_source = pred.get("sources", 1) == 1
    if is_single_source:
        kelly_fraction *= SINGLE_SOURCE_KELLY_DISCOUNT
    kelly_pct = calc_kelly(sizing_edge, decimal_odds, kelly_fraction)

    # Build notes — narrative first, then data
    notes_parts = [
        f"Model ({source_label}): {away_abbr} {pred['away_score']:.1f}, {home_abbr} {pred['home_score']:.1f} (margin: {abs(model_home_margin):.1f}). {spread_cushion:.1f} pts of cushion beyond the spread.",
    ]
    # Ensemble disagreement warning
    if pred.get("contested"):
        notes_parts.append(f"⚠ CONTESTED: Sources disagree by {pred['disagreement']:.1f} pts (DRatings: {pred.get('dr_margin', '?'):+.1f}, Dimers: {pred.get('dm_margin', '?'):+.1f}). Lower confidence.")
    elif is_single_source:
        notes_parts.append(f"Single source — {source_label}. Lower confidence without cross-validation. Kelly reduced 25%.")
    if suspicious:
        notes_parts.append(f"⚠ SUSPICIOUS EDGE ({round(edge*100,1)}%): Model disagrees with market by {spread_cushion:.1f} pts. Investigate before betting.")
    if tank_note:
        notes_parts.append(tank_note)
    if b2b_note:
        notes_parts.append(b2b_note.strip())

    # Label partially validated sports
    confidence = "MEDIUM" if sport.lower() in PARTIALLY_VALIDATED_SPORTS else "HIGH"
    if pred.get("contested"):
        confidence = "LOW"
    elif pred.get("sources", 1) == 1:
        confidence = "MEDIUM" if confidence == "HIGH" else confidence
    if confidence != "HIGH":
        notes_parts.append(f"⚠ Confidence: {confidence}")

    return {
        "sport": sport.upper(),
        "event": game["event_str"],
        "event_short": game["event_short"],
        "market": "Spread",
        "pick": cand["pick_label"],
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
        "sources": f"{source_label}, ESPN",
        "tank_risk": bool(tank_info and tank_info["confirmed"]),
        "spread_cushion": spread_cushion,
        "confidence": confidence,
        "dk_link": game.get("dk_spread_links", {}).get(pick_side, "") or game.get("dk_game_link", ""),
        "start_time": game.get("start_time", ""),
    }


def calculate_total_edge(game: dict, predictions: dict, sport: str = "nba") -> dict | None:
    """
    Calculate edge for a game's over/under (totals) market.
    Returns pick dict or None if no edge.

    For totals: model predicts away_score + home_score.
    Compare vs ESPN over/under line.
    Standard juice: -110.
    """
    home = game["home"]
    away = game["away"]
    home_abbr = home.get("abbr", "")
    away_abbr = away.get("abbr", "")

    # Need an over/under line
    if game.get("over_under") is None or game["over_under"] == 0:
        return None

    # Try to find DRatings prediction
    key = f"{away_abbr}@{home_abbr}"
    pred = predictions.get(key)

    if not pred:
        # Sport-specific alternate abbreviation mappings
        alt_maps = {
            "nba": {"GSW": "GS", "GS": "GSW", "NOP": "NO", "NO": "NOP",
                    "NYK": "NY", "NY": "NYK", "SAS": "SA", "SA": "SAS",
                    "WAS": "WSH", "WSH": "WAS"},
            "nhl": {"VGK": "VEG", "VEG": "VGK", "NJD": "NJ", "NJ": "NJD",
                    "SJS": "SJ", "SJ": "SJS", "TBL": "TB", "TB": "TBL",
                    "LAK": "LA", "LA": "LAK", "WSH": "WAS", "WAS": "WSH"},
            "mlb": {"AZ": "ARI", "ARI": "AZ", "CHW": "CWS", "CWS": "CHW",
                    "SDP": "SD", "SD": "SDP", "SFG": "SF", "SF": "SFG",
                    "TBR": "TB", "TB": "TBR", "WSN": "WSH", "WSH": "WSN",
                    "KCR": "KC", "KC": "KCR"},
        }
        alt_map = alt_maps.get(sport.lower(), {})
        alt_away = alt_map.get(away_abbr, away_abbr)
        alt_home = alt_map.get(home_abbr, home_abbr)
        for a in [away_abbr, alt_away]:
            for h in [home_abbr, alt_home]:
                pred = predictions.get(f"{a}@{h}")
                if pred:
                    break
            if pred:
                break

    if not pred:
        return None

    # Model predicted total
    model_total = pred["away_score"] + pred["home_score"]

    # ESPN over/under line
    espn_total = game["over_under"]

    # Determine which side to bet (under if model < line, over if model > line)
    if model_total > espn_total:
        pick_side = "over"
        cushion = model_total - espn_total
    elif model_total < espn_total:
        pick_side = "under"
        cushion = espn_total - model_total
    else:
        return None  # Exactly at line, no edge

    if abs(cushion) < 0.5:
        return None  # Less than 0.5 pts of edge, too thin

    # Convert cushion to cover probability using normal distribution
    model_prob = cushion_to_probability(abs(cushion), sport, "total")
    if model_prob is None:
        return None  # No researched SD for this sport — skip

    # Use ACTUAL DK total odds from ESPN when available
    if pick_side == "over" and game.get("over_odds"):
        dk_odds = game["over_odds"]
    elif pick_side == "under" and game.get("under_odds"):
        dk_odds = game["under_odds"]
    else:
        dk_odds = -110  # Standard fallback
    implied_prob = american_to_implied(dk_odds)

    # Calculate edge
    edge = model_prob - implied_prob

    if edge < MIN_EDGE_HIGH:
        return None  # Below 3% threshold

    # Flag suspicious edges — don't cap, but warn
    suspicious = edge > SUSPICIOUS_EDGE

    # Kelly sizing — apply graduated edge discount and single-source penalty
    sizing_edge = discount_edge_for_sizing(edge)
    decimal_odds = american_to_decimal(dk_odds)
    kelly_fraction = KELLY_FRACTION_HIGH
    is_single_source = pred.get("sources", 1) == 1
    if is_single_source:
        kelly_fraction *= SINGLE_SOURCE_KELLY_DISCOUNT
    kelly_pct = calc_kelly(sizing_edge, decimal_odds, kelly_fraction)

    # Build notes with ensemble info
    source_label = pred.get("source_label", "DRatings")
    notes = f"Model ({source_label}): {away_abbr} {pred['away_score']:.1f}, {home_abbr} {pred['home_score']:.1f} (total: {model_total:.1f}). Line: {espn_total}. Cushion: {cushion:.1f} pts."
    if pred.get("contested"):
        notes += f" ⚠ CONTESTED: Sources disagree by {pred['disagreement']:.1f} pts."
    elif is_single_source:
        notes += f" Single source — {source_label}. Kelly reduced 25%."
    if suspicious:
        notes += f" ⚠ SUSPICIOUS EDGE ({round(edge*100,1)}%): Model predicts {model_total:.1f} vs market {espn_total} — {cushion:.1f} pt gap."

    return {
        "sport": sport.upper(),
        "event": game["event_str"],
        "event_short": game["event_short"],
        "market": "Over/Under",
        "pick": f"{pick_side.upper()} {espn_total}",
        "pick_abbr": "",
        "odds": str(dk_odds),
        "dk_odds_int": dk_odds,
        "decimal_odds": decimal_odds,
        "implied_prob": implied_prob,
        "model_prob": model_prob,
        "edge": round(edge * 100, 1),
        "edge_raw": edge,
        "tier": "High",
        "kelly_pct": kelly_pct,
        "notes": notes,
        "sources": f"{source_label}, ESPN",
        "tank_risk": False,
        "spread_cushion": cushion,
        "dk_link": game.get("dk_total_links", {}).get(pick_side, "") or game.get("dk_game_link", ""),
        "start_time": game.get("start_time", ""),
    }


# ── Main ────────────────────────────────────────────
def main(games_only: bool = False):
    today = get_today_str()
    today_iso = get_today_iso()
    print(f"DK Edge Finder — Scanning for {today_iso}")

    # Step 0: Clean ALL stale git locks (prevents "Another git process" errors)
    git_locks = [
        REPO_ROOT / ".git" / "index.lock",
        REPO_ROOT / ".git" / "HEAD.lock",
        REPO_ROOT / ".git" / "objects" / "maintenance.lock",
    ]
    for lock in git_locks:
        if lock.exists():
            try:
                lock.unlink()
                print(f"  Removed stale {lock.relative_to(REPO_ROOT)}")
            except OSError:
                pass  # Permission denied in some envs — user can remove manually

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

    # Calculate bankroll — use manual override if set (from DK app balance), else from bet history
    starting = bankroll.get("starting_bankroll", 500.0)
    existing_bets = data.get("bets", [])
    resolved_pnl = sum(b.get("pnl", 0) for b in existing_bets if b.get("outcome") in ("win", "loss", "push"))
    pending_locked = sum(b.get("wager", 0) for b in existing_bets if b.get("outcome") == "pending")
    calculated = round(starting + resolved_pnl - pending_locked, 2)
    override = bankroll.get("balance_override")
    if override and isinstance(override, (int, float)) and override > 0:
        available = round(float(override), 2)
        print(f"  Bankroll: ${available:.2f} (manual override from DK balance, calculated was ${calculated:.2f})")
    else:
        available = calculated
        print(f"  Bankroll: ${starting:.2f} start + ${resolved_pnl:.2f} P/L - ${pending_locked:.2f} pending = ${available:.2f} available")

    # Step 2: Fetch games for all sports
    print(f"\n[2] Fetching schedule for {today}...")
    # All DraftKings Oregon sports — off-season sports return 0 games, no cost
    all_sports = ["nba", "nhl", "mlb", "nfl", "mls", "epl", "la_liga", "bundesliga", "serie_a", "ligue_1", "ucl", "mma"]
    all_games = []
    all_predictions = {}
    game_count = 0

    for sport in all_sports:
        try:
            games_for_sport = fetch_schedule_and_odds(today, sport)
            print(f"  {sport.upper()}: {len(games_for_sport)} games found")
            game_count += len(games_for_sport)
            # Tag each game with sport
            for g in games_for_sport:
                g["sport"] = sport
            all_games.extend(games_for_sport)
        except Exception as e:
            print(f"  {sport.upper()} fetch error: {e}", file=sys.stderr)

    # Filter to only games that haven't started
    upcoming = [g for g in all_games if g["status"] in ("STATUS_SCHEDULED", "STATUS_PREGAME")]
    print(f"  Found {game_count} total games, {len(upcoming)} upcoming")

    if not upcoming:
        started = sum(1 for g in all_games if g["status"] not in ("STATUS_SCHEDULED", "STATUS_PREGAME"))
        if started > 0:
            msg = f"{today_iso} — All {started} games in progress or final · Next scan 6 AM PT"
        else:
            msg = f"{today_iso} — No games scheduled"
        print(f"No upcoming games ({started} started/final). Preserving existing picks.")
        data["scan_date"] = today_iso
        data["scan_subtitle"] = msg
        # PRESERVE existing picks and no_edge_games — don't wipe them
        # Only clear if there were never any picks for today
        if "picks" not in data:
            data["picks"] = []
        if "no_edge_games" not in data:
            data["no_edge_games"] = []
        DATA_JSON.write_text(json.dumps(data, indent=2) + "\n")
        return

    # Step 3: Fetch model predictions from multiple sources and build ensemble
    print("\n[3] Fetching predictions (multi-source ensemble)...")
    all_dratings = {}
    all_dimers = {}
    all_extra = {}

    # Extract matchups from schedule for rating-based sources
    sport_matchups = {}
    for game in upcoming:
        sport_key = game.get("sport", "nba").lower()
        if sport_key not in sport_matchups:
            sport_matchups[sport_key] = []
        away_abbr = game.get("away", {}).get("abbr", "")
        home_abbr = game.get("home", {}).get("abbr", "")
        if away_abbr and home_abbr:
            sport_matchups[sport_key].append((away_abbr, home_abbr))

    for sport in all_sports:
        matchups = sport_matchups.get(sport.lower(), [])

        # Fetch DRatings
        try:
            dr_preds = fetch_dratings_predictions(today, sport)
            all_dratings[sport] = dr_preds
        except Exception as e:
            print(f"  {sport.upper()} DRatings error: {e}", file=sys.stderr)
            all_dratings[sport] = {}

        # Fetch Dimers/Levy Edge (only for sports with API support)
        if sport.lower() in ("nba", "nhl", "mlb", "nfl"):
            try:
                dm_preds = fetch_dimers_predictions(today, sport)
                all_dimers[sport] = dm_preds
            except Exception as e:
                print(f"  {sport.upper()} Dimers error: {e}", file=sys.stderr)
                all_dimers[sport] = {}
        else:
            all_dimers[sport] = {}

        # Fetch additional sources (Massey, OddsShark, Sagarin, Club Elo, Forebet, FanGraphs, Accuscore)
        try:
            extra = fetch_all_sources(today, sport, matchups)
            all_extra[sport] = extra
        except Exception as e:
            print(f"  {sport.upper()} extra sources error: {e}", file=sys.stderr)
            all_extra[sport] = {}

        # Build ensemble for this sport (DRatings + Dimers + all extra sources)
        ensemble = build_ensemble(
            all_dratings.get(sport, {}),
            all_dimers.get(sport, {}),
            sport,
            extra_sources=all_extra.get(sport, {}),
        )
        all_predictions[sport] = ensemble

        # Log ensemble stats
        n_multi = sum(1 for v in ensemble.values() if v.get("sources", 0) >= 2)
        n_contested = sum(1 for v in ensemble.values() if v.get("contested", False))
        max_src = max((v.get("sources", 0) for v in ensemble.values()), default=0)
        if ensemble:
            print(f"  {sport.upper()} ensemble: {len(ensemble)} games ({n_multi} multi-source, "
                  f"max {max_src} sources, {n_contested} contested)")

    # Step 4: Check B2B teams (NBA only for now; NHL could use same logic)
    print("\n[4] Checking back-to-back schedule...")
    b2b_teams = fetch_yesterday_games(today)
    print(f"  Teams on B2B: {', '.join(sorted(b2b_teams)) if b2b_teams else 'none'}")

    # Step 5: Calculate edges
    print("\n[5] Calculating edges...")
    picks = []
    no_edge = []

    for game in upcoming:
        sport = game.get("sport", "nba")
        sport_preds = all_predictions.get(sport, {})

        # Calculate spread edge for all sports that have spreads
        result = None
        if sport.lower() in ("nba", "nfl", "mlb", "nhl"):
            result = calculate_edge(game, sport_preds, b2b_teams, sport)
            if result:
                picks.append(result)
                print(f"  EDGE: {result['pick']} ({result['odds']}) — {result['edge']}% edge")

        # Calculate totals edge for all sports
        total_result = calculate_total_edge(game, sport_preds, sport)
        if total_result:
            picks.append(total_result)
            print(f"  EDGE: {total_result['pick']} ({total_result['odds']}) — {total_result['edge']}% edge")

        # Track no-edge games — only add if NEITHER spread nor totals edge found
        if not result and not total_result:
            spread_str = game.get("odds_details", "N/A")
            ou_str = f" O/U {game.get('over_under', 'N/A')}" if game.get("over_under") else ""

            # Check if we had model data
            aa, ha = game["away"]["abbr"], game["home"]["abbr"]
            had_model = sport_preds.get(f"{aa}@{ha}") is not None
            reason = "Edge below 3% threshold" if had_model else "No model data"

            # Check if it was filtered by tanking (NBA only)
            if sport.lower() == "nba":
                home_spread = game.get("home_spread", 0) or 0
                pick_abbr = game["home"]["abbr"] if home_spread > 0 else game["away"]["abbr"]
                tank_info = TANK_TEAMS_2026.get(pick_abbr)
                if tank_info and tank_info["confirmed"]:
                    reason = f"Tank penalty applied — {tank_info['reason']}"

            no_edge.append({
                "sport": sport.upper(),
                "event": game["event_short"],
                "line": spread_str if spread_str else "N/A",
                "reason": reason,
            })

    # Step 5b: Scan player props using real DK odds from The Odds API
    # Skipped in --games-only mode (saves API credits)
    if games_only:
        print("\n[5b] Skipping player props (--games-only mode, no API credits used)")
    else:
        # Build game margin map for blowout discount on props
        game_margins = {}
        nba_preds = all_predictions.get("nba", {})
        for game in [g for g in all_games if g.get("sport", "").lower() == "nba"]:
            pred = nba_preds.get(f"{game.get('away_abbr', '')}@{game.get('home_abbr', '')}")
            if pred:
                margin = abs(pred["home_score"] - pred["away_score"])
                event_str = game.get("event_str", "")
                if event_str:
                    game_margins[event_str] = margin
        print(f"\n[5b] Scanning player props (real DK odds, {len(game_margins)} games with margins)...")
        try:
            prop_edges = scan_player_props("nba", bankroll=available, max_lookups=20,
                                           game_margins=game_margins)
            if prop_edges:
                for pe in prop_edges:
                    impl_str = pe.get("implied", "0%").replace("%", "")
                    model_str = pe.get("model", "0%").replace("%", "")
                    pe["implied_prob"] = float(impl_str) / 100 if impl_str else 0
                    pe["model_prob"] = float(model_str) / 100 if model_str else 0
                    pe["event_short"] = pe.get("event", "")
                    pe["tier"] = pe.get("tier", "Medium")
                picks.extend(prop_edges)
                print(f"  Found {len(prop_edges)} prop edges")
            else:
                print("  No prop edges found")
        except Exception as e:
            print(f"  Prop scanning error: {e}", file=sys.stderr)

    # Step 6: Size bets with Kelly — DIVERSIFIED across game + prop categories
    # Split picks into game edges and prop edges, sort each by edge descending
    game_picks = sorted([p for p in picks if p.get("market") != "Player Prop"], key=lambda x: x["edge"], reverse=True)
    all_prop_picks = sorted([p for p in picks if p.get("market") == "Player Prop"], key=lambda x: x["edge"], reverse=True)

    # Cap at 2 props per game — prevents clustering 3+ picks from one matchup
    MAX_PROPS_PER_GAME = 2
    prop_picks = []
    props_per_game: dict[str, int] = {}
    for p in all_prop_picks:
        game_key = p.get("event", "")
        count = props_per_game.get(game_key, 0)
        if count < MAX_PROPS_PER_GAME:
            prop_picks.append(p)
            props_per_game[game_key] = count + 1
        else:
            no_edge.append({
                "sport": p["sport"],
                "event": p.get("event_short", p.get("event", "")),
                "line": f"{p['pick']} ({p['odds']})",
                "reason": f"Max {MAX_PROPS_PER_GAME} props per game (edge: {p['edge']}%)",
            })
    if len(all_prop_picks) > len(prop_picks):
        print(f"    Props filtered: {len(all_prop_picks)} → {len(prop_picks)} (max {MAX_PROPS_PER_GAME}/game)")

    game_budget = available * MAX_GAME_EXPOSURE
    prop_budget = available * MAX_PROP_EXPOSURE
    print(f"\n[6] Sizing picks (bankroll: ${available:.2f})")
    print(f"    Game budget: ${game_budget:.2f} ({len(game_picks)} edges), Prop budget: ${prop_budget:.2f} ({len(prop_picks)} edges)")

    def fill_category(category_picks, budget, category_name):
        """Fill a category up to its budget, return (sized_picks, skipped_picks, total_spent)."""
        sized = []
        skipped = []
        spent = 0
        for pick in category_picks:
            bet_pct = min(pick["kelly_pct"], MAX_SINGLE_BET_PCT)
            bet_amount = round(available * bet_pct, 2)

            if spent + bet_amount > budget:
                remaining = budget - spent
                if remaining > 5:  # Min bet $5
                    bet_amount = round(remaining, 2)
                else:
                    skipped.append(pick)
                    continue

            spent += bet_amount
            sized.append((pick, bet_amount))
        return sized, skipped, spent

    game_sized, game_skipped, game_spent = fill_category(game_picks, game_budget, "game")
    prop_sized, prop_skipped, prop_spent = fill_category(prop_picks, prop_budget, "prop")

    # Add skipped picks to no_edge with reason
    for pick in game_skipped + prop_skipped:
        no_edge.append({
            "sport": pick["sport"],
            "event": pick["event_short"],
            "line": f"{pick['pick']} ({pick['odds']})",
            "reason": f"Edge exists ({pick['edge']}%) but category exposure limit reached",
        })
        print(f"  Skipping {pick['pick']} — category limit reached")

    # Combine and assign ranks (games first, then props — sorted by edge within each)
    total_exposure = game_spent + prop_spent
    formatted_picks = []
    rank = 0

    for pick, bet_amount in game_sized + prop_sized:
        rank += 1
        formatted_picks.append({
            "rank": rank,
            "sport": pick.get("sport", "NBA"),
            "event": pick.get("event", pick.get("event_short", "")),
            "event_short": pick.get("event_short", ""),
            "market": pick.get("market", "Spread"),
            "pick": pick["pick"],
            "odds": pick["odds"],
            "implied": f"{pick['implied_prob']*100:.1f}%",
            "model": f"{pick['model_prob']*100:.1f}%",
            "edge": pick["edge"],
            "tier": pick.get("tier", "High"),
            "bet": f"${bet_amount:.2f}",
            "status": "",
            "result": "",
            "notes": pick.get("notes", ""),
            "sources": pick.get("sources", ""),
            "confidence": pick.get("confidence", "HIGH"),
            "dk_link": pick.get("dk_link", ""),
            "type": "prop" if pick.get("market") == "Player Prop" else "game",
            "start_time": pick.get("start_time", ""),
        })
        print(f"  #{rank}: {pick['pick']} ({pick['odds']}) — {pick['edge']}% edge — ${bet_amount:.2f}")

    print(f"  Games: {len(game_sized)} picks (${game_spent:.2f}), Props: {len(prop_sized)} picks (${prop_spent:.2f})")

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

    # Preserve existing bet history — NEVER delete placed or resolved bets
    existing_bets = data.get("bets", [])
    # Keep ALL bets — placed, pending, resolved, everything. Never wipe the bets array.
    # The scan only adds new picks to the picks[] array, it does NOT touch bets[].
    # Bets only enter the bets[] array when the user clicks "Place" on the site.

    # Build subtitle with sport breakdown
    date_str = datetime.strptime(today, '%Y%m%d').strftime('%A, %B %d, %Y')
    sport_counts = {}
    for g in all_games:
        s = g.get("sport", "nba").upper()
        sport_counts[s] = sport_counts.get(s, 0) + 1
    sports_str = ", ".join([f"{s} ({count})" for s, count in sorted(sport_counts.items())])
    subtitle = f"{date_str} — {sports_str}"

    # Calculate record from ALL bet history
    all_bets = existing_bets  # today's pending removed, will be re-added if placed
    win_count = sum(1 for b in all_bets if b.get("outcome") == "win")
    loss_count = sum(1 for b in all_bets if b.get("outcome") == "loss")
    push_count = sum(1 for b in all_bets if b.get("outcome") == "push")
    pend_count = sum(1 for b in all_bets if b.get("outcome") == "pending")
    pend_total = sum(b.get("wager", 0) for b in all_bets if b.get("outcome") == "pending")
    profit = round(available - starting, 2) if override else round(resolved_pnl, 2)

    # In games-only mode, preserve existing prop picks from last full scan
    final_picks = formatted_picks
    if games_only:
        existing_prop_picks = [p for p in data.get("picks", []) if p.get("type") == "prop"]
        if existing_prop_picks:
            final_picks = formatted_picks + existing_prop_picks
            print(f"  Preserved {len(existing_prop_picks)} prop picks from last full scan")

    new_data = {
        "scan_date": today_iso,
        "scan_subtitle": subtitle,
        "bankroll": {
            "available": available,
            "starting": starting,
            "profit": profit,
            "record": {"wins": win_count, "losses": loss_count, "pushes": push_count},
            "pending_count": pend_count,
            "pending_total": round(pend_total, 2),
            "pending_label": f"{pend_count} bet(s) pending (${pend_total:.2f})" if pend_count > 0 else "No unsettled bets",
        },
        "games_analyzed": len(all_games),
        "best_bet": best_bet,
        "picks": final_picks,
        "no_edge_games": no_edge,
        "bets": existing_bets,
    }

    DATA_JSON.write_text(json.dumps(new_data, indent=2) + "\n")
    print(f"\nDone. {len(formatted_picks)} edges found, {len(no_edge)} games no edge.")
    print(f"Total suggested exposure: ${total_exposure:.2f} ({(total_exposure/available*100):.1f}% of bankroll)")

    # Step 8: Append picks to pick_history.json for paper-trading analysis
    HISTORY_JSON = REPO_ROOT / "pick_history.json"
    try:
        history = json.loads(HISTORY_JSON.read_text()) if HISTORY_JSON.exists() else []
    except (json.JSONDecodeError, Exception):
        history = []

    for pick in final_picks:
        history.append({
            "scan_date": today_iso,
            "sport": pick.get("sport", ""),
            "event": pick.get("event", ""),
            "market": pick.get("market", ""),
            "pick": pick.get("pick", ""),
            "odds": pick.get("odds", ""),
            "implied": pick.get("implied", ""),
            "model": pick.get("model", ""),
            "edge": pick.get("edge", 0),
            "tier": pick.get("tier", ""),
            "confidence": pick.get("confidence", ""),
            "type": pick.get("type", ""),
            "notes": pick.get("notes", ""),
            "outcome": "pending",
            "final_score": "",
            "pnl_if_bet": 0,
        })

    HISTORY_JSON.write_text(json.dumps(history, indent=2) + "\n")
    print(f"[8] Appended {len(final_picks)} picks to pick_history.json (total: {len(history)} tracked)")


if __name__ == "__main__":
    games_only = "--games-only" in sys.argv
    if games_only:
        print("Mode: GAMES ONLY (no prop scan, no API credits used)")
    main(games_only=games_only)
