# DK Edge Finder - March 19-25, 2026 Calibration Analysis

## Overview

This directory contains the complete calibration analysis for the DK Edge Finder model, scoring its picks against actual game results from March 19-25, 2026.

## Files

### `calibration-report-march19-25.md` (16 KB, 427 lines)
**Full detailed calibration report** with all metrics, analysis, and recommendations.

Contents:
- Executive Summary
- Overall Performance Metrics (66.7% win rate, 18 bets, +$59.40 profit)
- Performance Breakdown by Sport (NHL 3-0, NBA 9-5, EPL 0-1)
- Edge Bucket Analysis (10%+ edges: 69.2% win rate)
- Calibration Check: Model Probability vs Actual Outcomes
- Edge Magnitude Comparison: Winners vs Losers
- Detailed Pick-by-Pick Results (all 18 bets listed with P&L)
- Key Findings & Insights
- Recommendations for Model Improvement
- Conclusion & Status Assessment

### `CALIBRATION_SUMMARY.txt` (Quick Reference)
**One-page summary** for quick reference and executive briefing.

Key Sections:
- Key Metrics Summary
- Detailed Findings (3 strengths, 3 weaknesses)
- Calibration Quality Assessment
- Recommendations (Immediate, Short-term, Long-term)
- Status and Next Steps

## Key Findings

### Overall Performance
- **Win Rate:** 66.7% (12-6 record)
- **Total Wagered:** $323.60
- **Total Profit:** $59.40
- **ROI:** 18.4%

### Performance by Sport
- **NHL:** 3-0 (100%) - Perfect record on puck line picks
- **NBA:** 9-5 (64.3%) - Strong across spreads and props
- **EPL:** 0-1 (0%) - Single bet, insufficient sample

### Performance by Edge
- **3-5% edge:** 66.7% win rate (2-1)
- **5-8% edge:** 50.0% win rate (1-1)
- **10%+ edge:** 69.2% win rate (9-4)

## Key Insights

### Strengths
1. **Perfect NHL Performance** - All 3 NHL bets won (13.6%-18.2% edges)
2. **Strong NBA Results** - 9 wins on 14 bets (64.3% win rate)
3. **High-Edge Outperformance** - 10%+ edge picks won at 69.2% rate
4. **Well-Calibrated Probabilities** - Model estimates align with outcomes

### Weaknesses
1. **Small Sample Size** - 18 bets limits statistical confidence
2. **Edge Magnitude Anomaly** - Losing picks averaged higher edges (surprising)
3. **EPL Untested** - Only 1 soccer bet (lost); cannot assess
4. **Large Spread Mixed Results** - Some lopsided matchups underperformed

### Surprise Finding
**Losing picks averaged 14.77% edge vs 13.50% for winning picks.** This counterintuitive result suggests either:
- Small sample variance (most likely with 18 bets)
- Model occasionally overestimates edges on certain lines
- Selection bias in which games were bet

Requires validation with 100+ bet sample.

## Recommendations

### Immediate
1. Reweight DRatings higher for NHL picks
2. Validate moneyline edge formulas (untested)
3. Investigate large spread underperformance

### Short-Term (2-4 weeks)
1. Collect 50-100 additional picks for statistical power
2. Segment analysis by market type
3. Expand EPL validation with 5+ additional picks

### Long-Term (3+ months)
1. Implement monthly recalibration
2. Add drift detection (alert if win rate < 55%)
3. Build confidence intervals around edges
4. Consider ensemble models

## Status

**Model Status:** PRODUCTION-READY (with refinements recommended)

**Confidence Level:** MODERATE (18-bet sample is small but sufficient for proof-of-concept)

**Recommendation:** Continue active use while monitoring monthly performance. Expand validation to 100+ picks before major model changes.

---

## Data Sources

- **Primary:** DRatings, Dimers consensus models
- **Secondary:** ESPN, DraftKings historical data
- **Period:** March 19-25, 2026
- **Bets Analyzed:** 18 settled bets (NBA, NHL, EPL)

## Model Information

- **Model Name:** DK Edge Finder v1.0
- **Core Algorithm:** DRatings + Dimers consensus
- **Data Integration:** Multi-source weighting
- **Edge Calculation:** Implied odds vs Model probability
- **Tier System:** High/Medium/Low confidence classification

---

**Report Generated:** March 26, 2026  
**Analysis Period:** March 19-25, 2026  
**Next Calibration Due:** April 30, 2026 (monthly recalibration schedule)
