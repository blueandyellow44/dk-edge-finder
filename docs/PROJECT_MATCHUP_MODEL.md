# Project: Matchup-Aware Model

Multi-session roadmap for evolving DK Edge Finder's model from rolling-mean-
plus-Skellam (current state) into a matchup-aware system that surfaces a
balanced slate across favorites/underdogs and across all bet types.

Established 2026-05-12 after a deep audit of `pick_history.json` (1034
graded picks, 54.4% hit, +$383.94 P/L). The audit revealed structural
imbalances that single-constant calibration cannot fully correct: NBA
Spread underdog and NBA O/U bleed despite the same-shape MLB and NHL
buckets winning. Phase G ("per-side per-sport calibration") will not
land cleanly until A-F are in place to supply the per-bet covariates
that make the calibration actually predictive.

## Why this matters

Current model produces single-shape output:

- 92% of historical prop picks are favorites (audit 2026-05-11)
- Game lines almost never clear thresholds (today: 5 picks shipped, 33
  games rejected) because game markets are sharp and the model can't
  reliably out-predict them by 5-8%
- Prop lines are softer (less efficient) so they always sneak through
  the 15% MAX_EDGE cap on the favored side

A matchup-aware model would (a) lift the edge on game lines into the
required threshold range, surfacing more spreads / totals / MLs, and
(b) shrink the over-confident prop edge to filter out marginal favored-
side picks. Combined effect: a more balanced daily slate where the math
isn't structurally brutal.

## Phasing

Phases A-F each ship independently and don't depend on each other for
their primary lift. G is the cleanup phase that benefits from A-F's
covariates being in place. Phases are not strictly serial — D is the
biggest expected lift and could run in parallel with B or C.

### Phase A — Opponent strength adjustment

**What:** Adjust the player projection (or game total) by the opponent's
strength on the relevant axis. For NBA props: opponent defensive rating
(pace-adjusted). For NHL: opposing goalie save% and team Corsi against.
For MLB pitcher props: opposing batting OPS vs the pitcher's handedness.

**Where:** `scripts/props_kernel.py:compute_projection_adjustment` (per
plugin) and `scripts/scan_edges.py:calculate_total_edge` /
`calculate_edge`.

**Effort:** 1 session.

**Expected lift:** +3-7% accuracy on volume-based props; +1-2% on game
totals; modest spread lift.

**Dependencies:** None. ESPN exposes team rating tables; data is free.

**Calibration loop:** Re-run audit after a 2-3 week sample; tune
adjustment magnitude per sport.

### Phase B — Pace / volume adjustment

**What:** Adjust volume-based projections by expected possessions /
shots. NBA pace × player usage = expected touches. Soccer xG/match
× minutes-played = expected shooting volume. MLB pitcher: expected
batters faced derived from opposing lineup.

**Where:** Per-plugin projection step. Most impactful for points,
rebounds, assists, shots-on-goal, 3-pt-made props.

**Effort:** 1 session.

**Expected lift:** +2-4% on volume props.

**Dependencies:** None functionally, but more powerful with Phase A
installed (opponent pace varies by matchup).

### Phase C — Rest, b2b, schedule context

**What:** Flag back-to-back nights, 3-in-4 stretches, long road trips,
day-after-time-zone-change games. Apply known performance penalties.

**Where:** New helper in `scripts/scan_edges.py` that walks ESPN's
schedule for each team-game; per-plugin adjustment hook reads the flag.

**Effort:** 1 session.

**Expected lift:** +1-3% on game spreads (NBA b2b is well-known) and
+1-2% on related props.

**Dependencies:** None.

### Phase D — Injury context

**What:** Pull ESPN injury feed (Out, Questionable, Doubtful) for every
key player. Adjust teammate usage projections when the named-out player
is a starter. Drop a prop entirely if its subject is Out.

**Where:** New `scripts/fetch_injuries.py`; injects context into the
projection step. Hooks into `calculate_prop_edge` and `calculate_edge`.

**Effort:** 2 sessions (data quality, edge cases like Q-then-active).

**Expected lift:** Highest single-phase lift on props. A Wembanyama
assist line shifts dramatically if the Spurs' point guard is Out — the
current model doesn't see this.

**Dependencies:** Useful with A in place (defensive context + injury
overlap). Standalone is still high-value.

**Risk:** ESPN's Q designations are noisy. Need a confidence
threshold so we don't drop picks on a player who plays anyway.

### Phase E — Vegas line movement signal

**What:** Record DK's line at scan time. Re-fetch later in the day.
Compute the delta. Reverse line movement (line moves against the
public) is a documented sharp-money signal — when DK moves the line
contrary to where amateur money is flowing, follow the move.

**Where:** Persist scan snapshots into a small log file
(`scripts/line_movement_log.jsonl`). Cron a poll workflow. Adjust
model probability based on direction and magnitude of the move.

**Effort:** 1 session.

**Expected lift:** +2-3% on game lines (totals + spreads). Primarily
calibrates the model toward the market when the market is moving.

**Dependencies:** None.

### Phase F — Smarter recent-form weighting

**What:** Currently the kernel uses a flat last-10-games mean for player
stats. Replace with: (a) exponentially-weighted recent form (last 5 ×
0.6 + games 6-10 × 0.4), (b) automatic exclusion of obvious bad-matchup
outlier games (player got 2 assists vs the #1 defense doesn't tell us
much about tonight's matchup vs #28).

**Where:** Per-plugin `parse_gamelog_row` + the kernel's mean / SD
computation.

**Effort:** 1 session.

**Expected lift:** +2-3% prop accuracy, especially for high-variance
players in streak-heavy stretches.

**Dependencies:** Best paired with Phase A (the outlier exclusion uses
opponent strength to decide what's an outlier).

### Phase G — Per-side, per-sport calibration

**What:** Today's `PROB_CALIBRATION` is keyed by `(sport, market)`.
Split it to `(sport, market, side)` where side is `favorite | underdog`.
The MLB-favorite hard-skip is what this phase obsoletes: instead of
binary hard-skip, the favorite-side calibration shrinks the bleeder
buckets to non-betting and keeps the genuine signals.

**Where:** `scripts/analyze_history.py` (audit) and the
`PROB_CALIBRATION` dict in `scripts/scan_edges.py`.

**Effort:** 1 session, but requires enough graded picks per
(sport, market, side) cell — minimum n=50 to fit a stable Platt scaler.
NBA spread underdog has 89 picks (enough); MLB favorite has 133 picks
(enough); NHL spread favorite has 75 (marginal). Other cells need more
samples to graduate.

**Expected lift:** Cleans up structural bleed without sport-by-sport
hard-skip rules. The MLB favorite hard-skip survives until G fits a
genuine favorite calibration that's better than skipping entirely.

**Dependencies:** Best after A-F because the per-side fit benefits from
the additional covariates these phases inject.

## Sequencing recommendation

1. **A** — foundational covariate; benefits everything downstream
2. **D** — highest single-phase lift; can run parallel to A
3. **C** — small lift but cheap and risk-free
4. **B** — modest lift; benefits from A
5. **F** — modest lift; benefits from A
6. **E** — separate axis (market signal not player signal); independent
7. **G** — calibration cleanup; benefits from A-F's covariates

Realistic cadence: 1-2 phases per week of focused work, 6-8 weeks total.

## Out of scope for now

- Full ML model retraining (e.g., gradient-boosted trees over all
  features). Worth considering at Phase H, but only after the
  hand-crafted phases hit diminishing returns.
- Live-betting / in-game prop signal. Different market structure;
  different infrastructure.
- Parlay / SGP construction. The current single-bet model is the
  foundation; parlays are a UX layer on top.
- Reinforcement / bankroll optimization beyond Kelly. Fractional Kelly
  with current MAX_DAILY_EXPOSURE is fine until lift compounds.

## Calibration loop

After each phase ships:

1. Wait 2-3 weeks for enough new graded picks
2. Re-run the audit script (the one used 2026-05-12) split by
   (sport, market, side, odds_bucket)
3. Compare W/L and P/L vs the pre-phase baseline
4. Decide: keep, refine, or revert

Audit script lives ad-hoc for now (see `Daily/2026-05-12.md` for the
template). Phase G is the natural place to formalize it into
`scripts/audit_history.py`.
