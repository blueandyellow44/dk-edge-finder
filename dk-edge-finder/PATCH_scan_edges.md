# scan_edges.py — Calibration Patch (April 2026)

Apply these changes to `scan_edges.py` in the GitHub repo. Based on 34-bet calibration: 20-14 (58.8%).

## Change 1: NBA Spread Min Edge Override

Find where spread edges are calculated (likely in `calculate_spread_edge()` or the main edge loop). Add this logic BEFORE the edge threshold check:

```python
# --- NBA SPREAD CALIBRATION (April 2026) ---
# NBA spreads: 5-7 (41.7%) — model's weakest market.
# Raise min edge: 5% base, 8% for large spreads (>12 pts).
NBA_SPREAD_MIN_EDGE = 0.05
NBA_LARGE_SPREAD_MIN_EDGE = 0.08
NBA_LARGE_SPREAD_THRESHOLD = 12.0

def get_effective_min_edge(sport, market, spread_points, base_min_edge):
    """Apply sport-specific min edge overrides."""
    if sport == "nba" and market == "spread":
        abs_spread = abs(spread_points) if spread_points else 0
        if abs_spread > NBA_LARGE_SPREAD_THRESHOLD:
            return max(base_min_edge, NBA_LARGE_SPREAD_MIN_EDGE)
        return max(base_min_edge, NBA_SPREAD_MIN_EDGE)
    return base_min_edge
```

Then in the edge check, replace:
```python
if edge < min_edge_threshold:
```
with:
```python
effective_min = get_effective_min_edge(sport, market, spread_points, min_edge_threshold)
if edge < effective_min:
```

## Change 2: Graduated Edge Discount for Bet Sizing

Add this function and apply it in the Kelly sizing step:

```python
# --- GRADUATED EDGE DISCOUNT (April 2026) ---
# 10%+ edges hit only 58.8% vs 75% for 5-8% edges.
# Discount large edges for sizing, not filtering.
EDGE_DISCOUNT_TIERS = [
    (0.15, 0.10),   # 15%+ → size as 10%
    (0.12, 0.10),   # 12-15% → size as 10%
    (0.10, 0.08),   # 10-12% → size as 8%
]

def discount_edge_for_sizing(raw_edge):
    """Reduce large edges to realistic levels for Kelly calculation."""
    for floor, cap in EDGE_DISCOUNT_TIERS:
        if raw_edge >= floor:
            return cap
    return raw_edge
```

Then in Kelly sizing, replace `edge` with `discount_edge_for_sizing(edge)`:
```python
sizing_edge = discount_edge_for_sizing(edge)
kelly_fraction = (sizing_edge * decimal_odds - (1 - sizing_edge)) / (decimal_odds - 1)
```

## Change 3: Single-Source Kelly Penalty

Where Kelly sizing is applied, add:

```python
SINGLE_SOURCE_KELLY_DISCOUNT = 0.75  # 25% reduction

# In the sizing section:
if len(model_sources) <= 1:  # Only one source (e.g., DRatings-only)
    kelly_multiplier *= SINGLE_SOURCE_KELLY_DISCOUNT
```

## Change 4: MLB Game Resolution in resolve_bets.py

Add MLB game resolution alongside the existing spread/ML/total resolvers:

```python
def resolve_mlb_runline(pick_str, odds_str, final_score):
    """Resolve MLB run line (+1.5 or -1.5) bets."""
    if not final_score:
        return "pending"

    # Parse "+1.5" or "-1.5" from pick string
    parts = pick_str.split()
    spread = None
    team_name = []
    for p in parts:
        try:
            spread = float(p)
        except ValueError:
            team_name.append(p)

    if spread is None:
        return "unknown"

    team = " ".join(team_name)

    # Determine team's score
    team_score = None
    opponent_score = None
    for t, s in final_score.items():
        if team.lower() in t.lower():
            team_score = s
        else:
            opponent_score = s

    if team_score is None or opponent_score is None:
        return "unknown"

    margin = team_score - opponent_score
    adjusted_margin = margin + spread

    if adjusted_margin > 0:
        return "win"
    elif adjusted_margin < 0:
        return "loss"
    return "push"
```

## Verification

After applying, test with:
```bash
python scan_edges.py --dry-run 2>&1 | grep "NBA.*Spread.*edge"
```

Confirm: NBA spreads <5% edge are filtered out, spreads >12 pts <8% are filtered out.
