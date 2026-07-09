#!/usr/bin/env python3
from __future__ import annotations
"""MLB moneyline (2-way, home/away) edge scanner.

CORE-market addition (2026-06-09). MLB was run-line + totals only; this adds
the straight moneyline. Unlike the run line (which hard-skips -1.5 favorites),
the moneyline is a clean win/lose bet, so it covers favorites the run line
deliberately drops.

Model: each team's runs ~ independent Poisson on the predicted scores already
fetched for the run-line/totals paths; skellam.two_way_win_probs derives
P(home) / P(away) by collapsing the Skellam tie mass (regulation ties go to
extra innings, split 50/50). Baseball has no draws.

Prices: DK 2-way h2h from The Odds API (reuses soccer_moneyline.fetch_h2h_odds,
which is sport-key generic). Resolution reuses resolve_bets.resolve_moneyline
(team ML, no draw). New calibration bucket (mlb, moneyline) auto-fits later.

Verification: scripts/test_mlb_moneyline.py. No MLB ML bet history to backtest;
forward-validated via pnl_if_bet + manual placement (DK Edge is real money).
"""

import props_kernel  # american_to_implied
import soccer_moneyline as _sml  # fetch_h2h_odds, american_to_decimal, _names_match
from skellam import two_way_win_probs
from market_blend import blend_multiway

ODDS_API_SPORT_KEY = "baseball_mlb"

MLB_ML_MIN_EDGE = 0.04        # moneyline is liquid/efficient; modest floor for a
#                               new unvalidated market. Tune via pnl_if_bet.
SUSPICIOUS_EDGE = 0.10
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02


def calculate_mlb_ml_edge(game, pred, h2h, assess_out=None, scan_date=""):
    """Best +EV 2-way moneyline pick for one MLB game, or None.

    When assess_out is a list, appends one game_log-schema assessment row for
    the model's best-edge side regardless of the pick floor — the unbiased
    record the calibration fitter / blend-weight fit needs (2026-07-09; the
    spread/total paths have logged this since 2026-06-09, moneyline never did).
    """
    home_x, away_x = pred.get("home_score"), pred.get("away_score")
    if home_x is None or away_x is None or home_x <= 0 or away_x <= 0:
        return None
    try:
        p_home, p_away = two_way_win_probs(home_x, away_x)
    except ValueError:
        return None
    p_home_raw, p_away_raw = p_home, p_away  # pre-blend, for game_log model_raw

    # Market-anchored blend: pull the model toward the no-vig market (2026-06-09
    # audit — the model barely beats a sharp line; filters adverse selection).
    p_home, p_away = blend_multiway([p_home, p_away],
                                    [h2h.get("home_ml"), h2h.get("away_ml")])

    home, away = game["home"], game["away"]
    home_name = home.get("name", "?")
    away_name = away.get("name", "?")

    candidates = [
        ("home", p_home, p_home_raw, h2h.get("home_ml"), h2h.get("home_link"), home_name),
        ("away", p_away, p_away_raw, h2h.get("away_ml"), h2h.get("away_link"), away_name),
    ]
    best = None          # highest-edge side that clears the pick floor
    best_assess = None   # highest-edge side regardless of floor (for game_log)
    for outcome, model_p, model_p_raw, ml, link, team in candidates:
        if ml is None:
            continue
        edge = model_p - props_kernel.american_to_implied(ml)
        if best_assess is None or edge > best_assess[1]:
            best_assess = (outcome, edge, model_p, model_p_raw, ml, team)
        if edge < MLB_ML_MIN_EDGE:
            continue
        if best is None or edge > best[1]:
            best = (outcome, edge, model_p, ml, link, team)

    if assess_out is not None and best_assess is not None:
        a_out, a_edge, a_cal, a_raw, a_ml, a_team = best_assess
        a_implied = props_kernel.american_to_implied(a_ml)
        assess_out.append({
            "scan_date": scan_date,
            "sport": "MLB",
            "event": f"{away_name} @ {home_name}",
            "event_short": f"{away.get('abbr','?')} @ {home.get('abbr','?')}",
            "market": "moneyline",
            "side": a_out,
            "pick": f"{a_team} ML",
            "line": f"{a_ml:+d}",
            "implied": round(a_implied, 4),
            "model_raw": round(a_raw, 4),
            "model_cal": round(a_cal, 4),
            "edge": round(a_edge, 4),
            "raw_edge": round(a_raw - a_implied, 4),
            "became_pick": best is not None and best[0] == a_out,
            "outcome": "pending",
            "final_score": "",
        })

    if best is None:
        return None
    outcome, edge, model_p, ml, link, team = best

    implied = props_kernel.american_to_implied(ml)
    decimal = _sml.american_to_decimal(ml)
    kelly = min((edge / (decimal - 1)) * KELLY_FRACTION, KELLY_CAP)
    src = pred.get("source_label", "DRatings")

    notes = (
        f"Model ({src}): runs {home.get('abbr','')} {home_x:.2f}, "
        f"{away.get('abbr','')} {away_x:.2f} -> "
        f"P(home {p_home*100:.0f}%, away {p_away*100:.0f}%). "
        f"Pick {team} at {ml:+d} (implied {implied*100:.0f}%)."
    )
    if pred.get("contested"):
        notes += f" CONTESTED: sources disagree by {pred.get('disagreement', 0):.1f}."
    if edge > SUSPICIOUS_EDGE:
        notes += f" SUSPICIOUS EDGE ({edge*100:.1f}%): verify line before placing."

    return {
        "sport": "MLB",
        "event": f"{away_name} @ {home_name}",
        "event_short": f"{away.get('abbr','?')} @ {home.get('abbr','?')}",
        "market": "Moneyline",
        "pick": f"{team} ML",
        "pick_abbr": "",
        "odds": f"{ml:+d}",
        "dk_odds_int": ml,
        "decimal_odds": decimal,
        "implied_prob": implied,
        "model_prob": model_p,
        "edge": round(edge * 100, 1),
        "edge_raw": edge,
        "tier": "High",
        "confidence": "MEDIUM",
        "kelly_pct": kelly,
        "notes": notes,
        "sources": f"{src}, The Odds API (DK)",
        "dk_link": link or game.get("dk_game_link", ""),
        "start_time": game.get("start_time", ""),
        # Logging: persist model inputs/outputs so ML picks are backtestable.
        "home_xg": round(home_x, 3),
        "away_xg": round(away_x, 3),
        "p_home": round(p_home, 4),
        "p_away": round(p_away, 4),
    }


def scan_mlb_moneyline(predictions, games, bankroll=500.0,
                       game_log_records=None, scan_date=""):
    """Scan MLB games for 2-way moneyline edges. Returns a list of pick dicts.

    game_log_records: optional list to append per-game assessment rows to
    (game_log.json schema); scan_date stamps those rows."""
    if not games:
        return []
    h2h_events = _sml.fetch_h2h_odds(ODDS_API_SPORT_KEY)
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
            if _sml._names_match(home_name, ev["home_team"]) and \
               _sml._names_match(away_name, ev["away_team"]):
                h2h = ev
                break
        if h2h is None:
            unmatched += 1
            continue

        pick = calculate_mlb_ml_edge(game, pred, h2h,
                                     assess_out=game_log_records,
                                     scan_date=scan_date)
        if pick:
            picks.append(pick)

    if unmatched:
        print(f"  MLB moneyline: {unmatched} game(s) had no matching h2h odds (skipped)")
    return picks
