#!/usr/bin/env python3
from __future__ import annotations
"""Market-anchored probability blend (2026-06-09 projection-quality audit).

On the unbiased game_log the raw model barely beats a sharp DK line and the
no-vig market is the best-calibrated single predictor; the pick sample's
overconfidence is adverse selection (betting the biggest model-vs-market
disagreements). Anchoring the model toward the de-vigged market shrinks those
disagreements so the most adverse-selected picks fall below the edge floor.

Shared by scan_edges (spread/total) and the moneyline modules so the weight is
defined once. Set to 1.0 to disable (pure model).

Per-market weights (2026-07-09, fit on the first post-blend month of game_log:
536 resolved rows, 2026-06-10..2026-07-09): on spreads the model has no alpha —
log-loss is minimized at w=0 (pure market) — while on totals the pure calibrated
model BEATS the no-vig market (log-loss 0.6798 vs 0.6902, n=150, paired
bootstrap P(model better)=0.948). Weights are pulled in from the fitted
extremes (0/1) to 0.3/0.85 to hedge one-month overfit. Markets without an
entry (moneyline — not yet in game_log) keep the 0.6 default until a month of
logged assessments exists to fit them.
"""

from props_kernel import american_to_implied

MARKET_BLEND_WEIGHT = 0.6

MARKET_BLEND_WEIGHTS = {
    "spread": 0.3,
    "total": 0.85,
}


def weight_for(market: str) -> float:
    """Blend weight for a game_log market key ('spread', 'total', 'moneyline')."""
    return MARKET_BLEND_WEIGHTS.get(market, MARKET_BLEND_WEIGHT)


def blend_two_way(model_prob: float, pick_odds, other_odds,
                  weight: float = MARKET_BLEND_WEIGHT) -> float:
    """Blend one picked side's model_prob toward its no-vig market prob.

    Returns model_prob unchanged if weight >= 1.0 or either side's odds are
    missing (cannot de-vig). Downstream edge math still uses the raw vigged
    implied as the price, so the blend moves only the model estimate.
    """
    if weight >= 1.0 or not pick_odds or not other_odds:
        return model_prob
    imp_pick = american_to_implied(pick_odds)
    imp_other = american_to_implied(other_odds)
    s = imp_pick + imp_other
    if s <= 0:
        return model_prob
    return weight * model_prob + (1.0 - weight) * (imp_pick / s)


def blend_multiway(model_probs, odds_list,
                   weight: float = MARKET_BLEND_WEIGHT):
    """Blend every outcome of a 2- or 3-way market toward its no-vig prob.

    model_probs and odds_list are parallel lists (e.g. [home, draw, away] for
    soccer, [home, away] for baseball). An entry with odds None keeps its model
    prob unchanged. The market is de-vigged across all outcomes that have odds.
    Returns a new list of blended probs (NOT renormalized — the caller selects a
    single side, so the blended probs need not sum to 1).
    """
    if weight >= 1.0:
        return list(model_probs)
    imps = [american_to_implied(o) if o is not None else None for o in odds_list]
    s = sum(i for i in imps if i is not None)
    if s <= 0:
        return list(model_probs)
    out = []
    for mp, imp in zip(model_probs, imps):
        if imp is None:
            out.append(mp)
        else:
            out.append(weight * mp + (1.0 - weight) * (imp / s))
    return out
