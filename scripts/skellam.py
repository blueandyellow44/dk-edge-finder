"""
Skellam Distribution for Sports Betting Line Probabilities
===========================================================

This module implements the Skellam distribution from first principles using
only Python standard library. The Skellam distribution models the difference
of two independent Poisson random variables, making it ideal for modeling
goal/run/point differentials in sports betting.

Mathematical Foundation
-----------------------
If X₁ ~ Poisson(μ₁) and X₂ ~ Poisson(μ₂) are independent, then
D = X₁ - X₂ follows a Skellam distribution with parameters μ₁ and μ₂.

PMF: P(D=k) = exp(-(μ₁+μ₂)) * (μ₁/μ₂)^(k/2) * I_|k|(2√(μ₁μ₂))
where I_n is the modified Bessel function of the first kind.

Sports Applications
-------------------
- NHL puck line: ±1.5 spread on goal differential
- MLB run line: ±1.5 spread on run differential
- Soccer: ±0.5, ±1.0, ±1.5 goal spreads (draw-no-bet available at ±0.5)

For the run line in baseball, use with caution: runs follow negative binomial
(overdispersed), not Poisson. Skellam will slightly underestimate underdog
probability and overestimate favorite probability.
"""

import math


def bessel_i_zero(x):
    """Modified Bessel function I₀(x) using series expansion.

    Series: I₀(x) = Σ_{k=0}^∞ (x/2)^(2k) / (k!)²

    Args:
        x: Argument (non-negative)

    Returns:
        I₀(x)
    """
    result = 1.0
    term = 1.0
    for k in range(1, 150):
        term *= (x * x) / (4.0 * k * k)
        if term < 1e-15 * result:
            break
        result += term
    return result


def bessel_i_one(x):
    """Modified Bessel function I₁(x) using series expansion.

    Series: I₁(x) = (x/2) * Σ_{k=0}^∞ (x/2)^(2k) / (k! * (k+1)!)

    Args:
        x: Argument (non-negative)

    Returns:
        I₁(x)
    """
    result = 0.0
    term = x / 2.0
    result = term
    for k in range(1, 150):
        term *= (x * x) / (4.0 * k * (k + 1))
        if term < 1e-15 * result:
            break
        result += term
    return result


def bessel_i_n(n, x):
    """Modified Bessel function I_n(x) for non-negative integer n.

    Uses upward recurrence relation:
    I_{k+1}(x) = I_{k-1}(x) - (2k/x) * I_k(x)

    This is numerically stable for non-negative n and positive x.

    Args:
        n: Order (non-negative integer)
        x: Argument (positive)

    Returns:
        I_n(x)
    """
    if n == 0:
        return bessel_i_zero(x)
    if n == 1:
        return bessel_i_one(x)

    # Forward recurrence for n >= 2
    i_km1 = bessel_i_zero(x)
    i_k = bessel_i_one(x)

    for k in range(1, n):
        i_kp1 = i_km1 - (2.0 * k / x) * i_k
        i_km1 = i_k
        i_k = i_kp1

    return i_k


def skellam_pmf(k, mu1, mu2):
    """Probability mass function of Skellam distribution.

    Args:
        k: Value (integer, can be negative)
        mu1: Mean of first Poisson component (e.g., away team scoring rate)
        mu2: Mean of second Poisson component (e.g., home team scoring rate)

    Returns:
        P(D = k) where D ~ Skellam(mu1, mu2)

    Raises:
        ValueError: If mu1 or mu2 is not positive
    """
    if mu1 <= 0 or mu2 <= 0:
        raise ValueError("Means must be positive")

    # Compute in log space for numerical stability
    log_prob = -(mu1 + mu2)
    log_prob += (k / 2.0) * math.log(mu1 / mu2)

    # Bessel function argument
    bessel_arg = 2.0 * math.sqrt(mu1 * mu2)
    bessel_val = bessel_i_n(abs(k), bessel_arg)

    if bessel_val <= 0:
        return 0.0

    log_prob += math.log(bessel_val)
    return math.exp(log_prob)


def skellam_cdf(k_threshold, mu1, mu2):
    """Cumulative distribution function of Skellam.

    Computes P(D <= k_threshold) by summing the PMF over an appropriate range.
    The range is determined dynamically: ±6σ from the mean covers 99.73% of
    the probability mass (per normal approximation).

    Args:
        k_threshold: Upper limit
        mu1, mu2: Poisson means

    Returns:
        P(D <= k_threshold), clamped to [0, 1]
    """
    mean = mu1 - mu2
    std = math.sqrt(mu1 + mu2)

    # Bounds: ±6σ from mean covers 99.73% of normal distribution
    k_min = math.floor(mean - 6 * std) - 1
    # CRITICAL: use floor, not int. int(-1.5) = -1 (truncates toward zero)
    # but floor(-1.5) = -2. For P(D ≤ -1.5) we need to sum up to k=-2 only.
    k_max = math.floor(k_threshold) + 1

    result = 0.0
    for k in range(k_min, k_max):
        pmf_val = skellam_pmf(k, mu1, mu2)
        result += pmf_val
        if pmf_val < 1e-15:
            break

    return min(1.0, result)


def skellam_sf(k_threshold, mu1, mu2):
    """Survival function of Skellam.

    Computes P(D > k_threshold) = 1 - P(D <= k_threshold).

    Args:
        k_threshold: Lower limit (strictly greater than)
        mu1, mu2: Poisson means

    Returns:
        P(D > k_threshold)
    """
    return 1.0 - skellam_cdf(k_threshold, mu1, mu2)


def three_way_probs(home_xg, away_xg, max_goals=15):
    """(p_home, p_draw, p_away) for a 3-way soccer match.

    Models each team's goals as independent Poisson — home ~ Poisson(home_xg),
    away ~ Poisson(away_xg) — and sums the joint score matrix:

        P(home win) = Σ_{i>j} P(home=i) P(away=j)
        P(draw)     = Σ_{i=j} P(home=i) P(away=j)
        P(away win) = Σ_{i<j} P(home=i) P(away=j)

    This is the same goal-difference (Skellam) model the run/puck lines use, but
    computed by DIRECT CONVOLUTION rather than the Bessel-based skellam_cdf path.
    The Bessel recurrence (bessel_i_n) is numerically unstable when its order
    exceeds its argument, which is exactly the small-mean regime of soccer xG
    (~0.5-3); convolution is exact and stable there. O(max_goals²) ≈ 256 ops.

    max_goals caps each team's goals (P(>15) is ~0 for any real xG); the result
    is renormalized to absorb that negligible truncated tail. Raises ValueError
    on non-positive xg.
    """
    if home_xg <= 0 or away_xg <= 0:
        raise ValueError("expected goals must be positive")

    def _poisson_pmf_vector(lam, n_max):
        """[P(X=0), ..., P(X=n_max)] via iterative term (no factorial overflow)."""
        out = [math.exp(-lam)]
        term = out[0]
        for i in range(1, n_max + 1):
            term *= lam / i
            out.append(term)
        return out

    home_p = _poisson_pmf_vector(home_xg, max_goals)
    away_p = _poisson_pmf_vector(away_xg, max_goals)

    p_home = p_draw = p_away = 0.0
    for i in range(max_goals + 1):
        hi = home_p[i]
        for j in range(max_goals + 1):
            joint = hi * away_p[j]
            if i > j:
                p_home += joint
            elif i == j:
                p_draw += joint
            else:
                p_away += joint

    total = p_home + p_draw + p_away  # ~1 minus the truncated >max_goals tail
    if total <= 0:
        raise ValueError("degenerate probabilities")
    return (p_home / total, p_draw / total, p_away / total)


def poisson_spread_probability(predicted_away, predicted_home, spread):
    """Returns probability that home beats the spread using Skellam distribution.

    This is the main API for sports betting applications. It computes the
    probability that the home team's result beats a given spread.

    Spread Interpretation
    --------------------
    The spread parameter uses the standard betting convention:
    - Negative spread (e.g., -1.5): Home is the underdog, receiving a bonus
    - Positive spread (e.g., +1.5): Home is the favorite, facing a handicap

    For NEGATIVE spreads (home is underdog):
        Example: spread = -1.5 (home gets +1.5 advantage)
        Home wins the bet if: home_score - away_score + (-1.5) > 0
        i.e., home_score - away_score > 1.5
        i.e., home wins by 2 or more goals/runs

    For POSITIVE spreads (home is favorite):
        Example: spread = 1.5 (home must overcome -1.5 disadvantage)
        Home wins the bet if: home_score - away_score - 1.5 > 0
        i.e., home_score - away_score > 1.5
        i.e., home wins by 2 or more goals/runs

    Both simplify to: P(D > -spread) where D = home_score - away_score

    Examples
    --------
    Puck line (NHL):
        >>> poisson_spread_probability(3.0, 3.0, -1.5)  # Even match, away +1.5
        0.2646
        >>> poisson_spread_probability(3.0, 3.0, 1.5)   # Even match, home -1.5
        0.5833

    Soccer draw-no-bet:
        >>> poisson_spread_probability(1.2, 1.5, -0.5)  # Away +0.5
        0.3037  # Away doesn't lose
        >>> poisson_spread_probability(1.2, 1.5, 0.5)   # Home -0.5
        0.3037  # Home wins by 1+ (integer outcome)

    Args:
        predicted_away: Expected scoring rate for away team (e.g., expected goals)
        predicted_home: Expected scoring rate for home team
        spread: Spread value (negative = home underdog, positive = home favorite)

    Returns:
        Probability that home beats the spread, in [0, 1]
    """
    threshold = -spread
    return skellam_sf(threshold, predicted_away, predicted_home)


# ============================================================================
# COMPARISON TO NORMAL APPROXIMATION
# ============================================================================

def normal_spread_probability(predicted_away, predicted_home, spread):
    """Compute spread probability using normal approximation for comparison.

    Under the normal approximation, D = X₁ - X₂ is approximately
    N(μ₁ - μ₂, μ₁ + μ₂).

    This is faster but less accurate, especially for small means.

    Args:
        predicted_away, predicted_home, spread: Same as poisson_spread_probability

    Returns:
        Probability using normal CDF approximation
    """
    mean = predicted_away - predicted_home
    var = predicted_away + predicted_home
    std = math.sqrt(var)

    if std == 0:
        return 0.5

    # P(D > -spread) using normal CDF
    z = (-spread - mean) / std
    # CDF of standard normal: Φ(z) = 0.5 * (1 + erf(z / √2))
    phi_z = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return 1.0 - phi_z


if __name__ == "__main__":
    # Validation tests
    print("=" * 80)
    print("SKELLAM DISTRIBUTION - VALIDATION EXAMPLES")
    print("=" * 80)

    print("\n1. EVEN GAME (NHL Puck Line)")
    print("-" * 80)
    mu_away, mu_home = 3.0, 3.0
    spread_values = [-1.5, 1.5]

    print(f"λ_away={mu_away}, λ_home={mu_home}\n")
    print("Spread | Skellam | Normal  | Difference")
    print("-------|---------|---------|------------")
    for spread in spread_values:
        skel = poisson_spread_probability(mu_away, mu_home, spread)
        norm = normal_spread_probability(mu_away, mu_home, spread)
        diff = abs(skel - norm)
        print(f"{spread:6.1f} | {skel:7.4f} | {norm:7.4f} | {diff:+7.4f}")

    print("\n2. MODERATE FAVORITE")
    print("-" * 80)
    mu_away, mu_home = 2.7, 3.3
    print(f"λ_away={mu_away}, λ_home={mu_home}\n")
    print("Spread | Skellam | Normal  | Difference")
    print("-------|---------|---------|------------")
    for spread in spread_values:
        skel = poisson_spread_probability(mu_away, mu_home, spread)
        norm = normal_spread_probability(mu_away, mu_home, spread)
        diff = abs(skel - norm)
        print(f"{spread:6.1f} | {skel:7.4f} | {norm:7.4f} | {diff:+7.4f}")

    print("\n3. SOCCER (Draw-No-Bet)")
    print("-" * 80)
    mu_away, mu_home = 1.2, 1.5
    spread_values_soccer = [-0.5, 0.5]
    print(f"λ_away={mu_away}, λ_home={mu_home}\n")
    print("Spread | Skellam | Normal  | Difference")
    print("-------|---------|---------|------------")
    for spread in spread_values_soccer:
        skel = poisson_spread_probability(mu_away, mu_home, spread)
        norm = normal_spread_probability(mu_away, mu_home, spread)
        diff = abs(skel - norm)
        print(f"{spread:6.1f} | {skel:7.4f} | {norm:7.4f} | {diff:+7.4f}")

    print("\n4. BASEBALL/RUN LINE")
    print("-" * 80)
    mu_away, mu_home = 4.2, 4.5
    print(f"λ_away={mu_away}, λ_home={mu_home}")
    print("(Note: Runs follow negative binomial; use Skellam with caution)\n")
    print("Spread | Skellam | Normal  | Difference")
    print("-------|---------|---------|------------")
    for spread in [-1.5, 1.5]:
        skel = poisson_spread_probability(mu_away, mu_home, spread)
        norm = normal_spread_probability(mu_away, mu_home, spread)
        diff = abs(skel - norm)
        print(f"{spread:6.1f} | {skel:7.4f} | {norm:7.4f} | {diff:+7.4f}")
