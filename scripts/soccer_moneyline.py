#!/usr/bin/env python3
from __future__ import annotations
"""Soccer 3-way moneyline (home / draw / away) edge scanner.

CORE-market addition (2026-06-09). The game scanner historically produced only
Spread and Over/Under; soccer was totals-only. This module adds the 3-way
moneyline, soccer's primary market.

Model: each team's goals ~ independent Poisson on the predicted scores already
fetched for the totals path (pred["home_score"], pred["away_score"]); 3-way
probabilities come from skellam.three_way_probs (direct Poisson convolution).

Prices: DK 3-way h2h from The Odds API's bulk /odds endpoint (1 credit/league,
home/draw/away in one call). Chosen over the free ESPN parse, which does not
carry reliable soccer 3-way / draw prices. (Max's call, 2026-06-09.)

Verification: scripts/test_soccer_moneyline.py is the analytic correctness gate.
No clean historical backtest exists (predicted goals were never persisted), so
the model logs home_xg/away_xg + the three probs on every pick going forward,
and real-money sizing waits on the pnl_if_bet record. DK Edge is real money with
manual placement; shipping this only changes what the scanner surfaces.
"""

import json
import math
import re
import urllib.error
import urllib.request

import props_kernel  # ODDS_API_KEY, american_to_implied
import props_soccer  # per-league PLUGINS carry ODDS_API_SPORT_KEY
from skellam import three_way_probs

# Min-edge floors. Draws are higher-variance / lower base rate, so they need a
# bigger edge to clear. Tune as the pnl_if_bet record accumulates.
SOCCER_ML_MIN_EDGE = 0.05
SOCCER_ML_DRAW_MIN_EDGE = 0.08
SUSPICIOUS_EDGE = 0.15        # flag in notes, do not cap/drop
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02

# Generic soccer-name tokens to drop before matching ESPN names to Odds API names.
_DROP_TOKENS = {"fc", "cf", "sc", "afc", "ac", "as", "ss", "us", "rc", "cd",
                "ud", "club", "calcio", "if", "bk", "sv", "vfl", "vfb", "tsg",
                "fk", "sd", "ca"}


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation/diacritics-ish, drop generic soccer tokens."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t and t not in _DROP_TOKENS]
    return " ".join(toks)


def _names_match(espn_name: str, odds_name: str) -> bool:
    """Conservative team-name match. False negatives (missed picks) are safe;
    false positives (wrong odds on a game) are not, so require a strong signal."""
    a, b = _normalize(espn_name), _normalize(odds_name)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    # Share a distinctive token (len >= 5) — e.g. "arsenal", "atletico".
    ta, tb = set(a.split()), set(b.split())
    return any(len(t) >= 5 for t in (ta & tb))


def american_to_decimal(odds: int) -> float:
    return 1 + (100 / abs(odds) if odds < 0 else odds / 100)


def fetch_h2h_odds(sport_key: str) -> list[dict]:
    """Fetch DK 3-way h2h for a soccer league via The Odds API bulk /odds.

    Returns one dict per event:
        {home_team, away_team, home_ml, draw_ml, away_ml,
         home_link, draw_link, away_link, start_time}
    Missing prices come back as None. One API request per league.
    """
    key = props_kernel.ODDS_API_KEY
    if not key:
        print("  WARNING: No ODDS_API_KEY; skipping soccer moneyline.")
        return []

    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        f"?apiKey={key}&regions=us&bookmakers=draftkings"
        f"&markets=h2h&oddsFormat=american&includeLinks=true"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DKEdgeFinder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            events = json.loads(resp.read())
            remaining = resp.headers.get("x-requests-remaining", "?")
            print(f"  Odds API h2h ({sport_key}): {len(events)} events (credits remaining: {remaining})")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as e:
        print(f"  Odds API h2h fetch failed for {sport_key}: {e}")
        return []

    out: list[dict] = []
    for ev in events:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        rec = {
            "home_team": home, "away_team": away,
            "home_ml": None, "draw_ml": None, "away_ml": None,
            "home_link": "", "draw_link": "", "away_link": "",
            "start_time": ev.get("commence_time", ""),
        }
        for bm in ev.get("bookmakers", []):
            if bm.get("key") != "draftkings":
                continue
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for o in market.get("outcomes", []):
                    name = o.get("name", "")
                    price = o.get("price")
                    link = o.get("link", "") or ""
                    if price is None:
                        continue
                    if name == home:
                        rec["home_ml"], rec["home_link"] = int(price), link
                    elif name == away:
                        rec["away_ml"], rec["away_link"] = int(price), link
                    elif name.lower() == "draw":
                        rec["draw_ml"], rec["draw_link"] = int(price), link
        out.append(rec)
    return out


def _build_pick(game, sport, pred, h2h, outcome, model_p, ml_odds, link):
    """Assemble a pick dict for one chosen 3-way outcome. Outcome is
    'home' | 'draw' | 'away'."""
    home, away = game["home"], game["away"]
    home_name, away_name = home.get("name", "?"), away.get("name", "?")
    home_xg, away_xg = pred["home_score"], pred["away_score"]
    p_home, p_draw, p_away = three_way_probs(home_xg, away_xg)

    implied = props_kernel.american_to_implied(ml_odds)
    raw_edge = model_p - implied
    decimal = american_to_decimal(ml_odds)
    kelly = min((raw_edge / (decimal - 1)) * KELLY_FRACTION, KELLY_CAP)

    if outcome == "home":
        pick_str, sel_label = f"{home_name} ML", home_name
    elif outcome == "away":
        pick_str, sel_label = f"{away_name} ML", away_name
    else:
        pick_str, sel_label = "Draw ML", "Draw"

    src = pred.get("source_label", "DRatings")
    notes = (
        f"Model ({src}): xG {home.get('abbr','')} {home_xg:.2f}, "
        f"{away.get('abbr','')} {away_xg:.2f} -> "
        f"P(home {p_home*100:.0f}%, draw {p_draw*100:.0f}%, away {p_away*100:.0f}%). "
        f"Pick {sel_label} at {ml_odds:+d} (implied {implied*100:.0f}%)."
    )
    if pred.get("contested"):
        notes += f" CONTESTED: sources disagree by {pred.get('disagreement', 0):.1f}."
    if raw_edge > SUSPICIOUS_EDGE:
        notes += f" SUSPICIOUS EDGE ({raw_edge*100:.1f}%): verify line before placing."

    return {
        "sport": sport.upper(),
        "event": f"{away_name} @ {home_name}",
        "event_short": f"{away.get('abbr','?')} @ {home.get('abbr','?')}",
        "market": "Moneyline",
        "pick": pick_str,
        "pick_abbr": "",
        "odds": f"{ml_odds:+d}",
        "dk_odds_int": ml_odds,
        "decimal_odds": decimal,
        "implied_prob": implied,
        "model_prob": model_p,
        "edge": round(raw_edge * 100, 1),
        "edge_raw": raw_edge,
        "tier": "High",
        "confidence": "MEDIUM",
        "kelly_pct": kelly,
        "notes": notes,
        "sources": f"{src}, The Odds API (DK)",
        "dk_link": link or game.get("dk_game_link", ""),
        "start_time": game.get("start_time", ""),
        # Logging fix: persist the model inputs/outputs so 3-way picks are
        # backtestable going forward (predicted goals were never stored before).
        "home_xg": round(home_xg, 3),
        "away_xg": round(away_xg, 3),
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
    }


def calculate_moneyline_edge(game, pred, h2h):
    """Return the single best +EV 3-way pick for a game, or None.

    Picks the outcome with the highest positive edge that clears its floor
    (draws use a higher floor). Betting one side of a mutually-exclusive 3-way
    avoids stacking exposure on a single match.
    """
    home_xg, away_xg = pred.get("home_score"), pred.get("away_score")
    if home_xg is None or away_xg is None or home_xg <= 0 or away_xg <= 0:
        return None
    try:
        p_home, p_draw, p_away = three_way_probs(home_xg, away_xg)
    except ValueError:
        return None

    candidates = [
        ("home", p_home, h2h.get("home_ml"), h2h.get("home_link"), SOCCER_ML_MIN_EDGE),
        ("draw", p_draw, h2h.get("draw_ml"), h2h.get("draw_link"), SOCCER_ML_DRAW_MIN_EDGE),
        ("away", p_away, h2h.get("away_ml"), h2h.get("away_link"), SOCCER_ML_MIN_EDGE),
    ]
    best = None
    for outcome, model_p, ml, link, floor in candidates:
        if ml is None:
            continue
        edge = model_p - props_kernel.american_to_implied(ml)
        if edge < floor:
            continue
        if best is None or edge > best[1]:
            best = (outcome, edge, model_p, ml, link)

    if best is None:
        return None
    outcome, _edge, model_p, ml, link = best
    return _build_pick(game, game.get("sport", "soccer"), pred, h2h, outcome, model_p, ml, link)


def scan_soccer_moneyline(sport, predictions, games, bankroll=500.0):
    """Scan one soccer league's games for 3-way moneyline edges.

    Args:
        sport: league key (e.g. "mls", "epl").
        predictions: ensemble dict keyed "AWAY@HOME" (abbrs), each carrying
                     home_score / away_score (predicted goals).
        games: upcoming game dicts for this league (from fetch_schedule_and_odds).
    Returns a list of pick dicts.
    """
    plugin = props_soccer.PLUGINS.get(sport.lower())
    if plugin is None or not games:
        return []

    h2h_events = fetch_h2h_odds(plugin.ODDS_API_SPORT_KEY)
    if not h2h_events:
        return []

    picks = []
    unmatched = 0
    for game in games:
        home_name = game["home"].get("name", "")
        away_name = game["away"].get("name", "")
        away_abbr = game["away"].get("abbr", "")
        home_abbr = game["home"].get("abbr", "")

        pred = predictions.get(f"{away_abbr}@{home_abbr}")
        if not pred:
            continue

        h2h = None
        for ev in h2h_events:
            if _names_match(home_name, ev["home_team"]) and _names_match(away_name, ev["away_team"]):
                h2h = ev
                break
        if h2h is None:
            unmatched += 1
            continue

        pick = calculate_moneyline_edge(game, pred, h2h)
        if pick:
            picks.append(pick)

    if unmatched:
        print(f"  {sport.upper()} moneyline: {unmatched} game(s) had no matching h2h odds (skipped)")
    return picks
