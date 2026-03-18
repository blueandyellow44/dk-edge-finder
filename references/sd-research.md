# Standard Deviation Research — Sports Betting Outcomes

## Measured Values (High Confidence)

### NBA Spreads (Boyd's Bets, multi-season)
- Average ATS margin SD: **11.26 points**
- Range: 9.20 (at -13.5) to 12.03 (at -15)
- Correlation with spread size: **0.60** (larger spreads slightly MORE predictable)
- Key insight: oddsmakers are better at predicting blowouts than close games

### NBA Totals (Boyd's Bets, multi-season)
- Average O/U margin SD: **17.19 points**
- Range: 15.08 (low totals) to 21.25 (high totals)
- Correlation with total size: **0.33** (higher totals slightly less predictable)
- Totals >200 have ~1 extra point of variance vs <200

### NFL Spreads (Boyd's Bets + Stern 1991)
- Boyd's average: **13.28 points**
- Stern (1991): **13.86 points** (1981, 1983, 1984 seasons)
- Modern replication (1978-2012): **13.45 points**
- Recent 3 seasons: **13.87 points**
- Correlation with spread size: **-0.06** (essentially zero — no relationship)
- Distribution: confirmed normal by Stern

### NFL Totals (Boyd's Bets)
- Average O/U margin SD: **13.28 points**
- Correlation with total size: **-0.02** (no relationship)

## Derived Values (Medium Confidence)

### Soccer/EPL (Dixon-Coles 1997 model)
- Home team λ: 1.48-1.56 goals/match
- Away team λ: 1.42 goals/match
- Total goals/match: ~2.9-3.0
- Goal margin SD (Skellam): **~1.71 goals** (sqrt(λ_h + λ_a))
- Total goals SD: **~1.71 goals**
- Correlation parameter ρ: **-0.1285** (2017/18 EPL optimal)
- Home advantage γ: **0.27** (log scale, ~30% boost)
- Over 2.5 goals: **53-54%** of EPL matches
- Overdispersion factor: 1.05-1.15x (near-Poisson)

## No Data Available

### NHL
- No published ATS margin SD
- No published O/U margin SD
- Puck line fixed at ±1.5 — not comparable to variable spreads

### MLB
- Run margin SD: **2.54 runs** (2013 season, single source)
- Run total SD: **~4.1 runs** (estimated, negative binomial distribution)
- NOT validated across multiple seasons or sources

### MMA/UFC
- No spread/total market (moneyline only)
- Favorite win rate: 68-72%
- Heavy favorites (-400 to -900): 88-93% accurate
- Even matchups: ~51% (coin flip)
- Model accuracy ceiling: ~70%

## Key Academic Sources
- Stern, H.S. (1991). "On the Probability of Winning a Football Game." The American Statistician, 45(3), 179-183.
- Dixon, M.J. & Coles, S.G. (1997). "Modelling Association Football Scores and Inefficiencies in the Football Betting Market." JRSS-C, 46(2), 265-280.
- Boyd's Bets: boydsbets.com/ats-margin-standard-deviations-by-point-spread/
- Boyd's Bets: boydsbets.com/standard-deviations-of-overunder-margins-by-total/

## Critical Note on Model Error
The GAME SD values above measure how much actual outcomes deviate from the CLOSING LINE (market consensus). When we use DRatings predictions instead of closing lines, there's additional uncertainty because DRatings isn't as accurate as the market. However, we intentionally do NOT add a "model error SD" because:

1. We don't have a measured value for DRatings' prediction error
2. Adding an unmeasured estimate would inflate uncertainty and suppress real edges
3. The normal CDF conversion implicitly handles this — if DRatings disagrees with the market by a large amount but the game SD is small, the probability will be high regardless, which is correct if DRatings is right and dangerous if DRatings is wrong

The calibration loop (tracking actual hit rate vs predicted probability) is the proper way to validate whether the game-SD-only approach produces accurate probabilities.
