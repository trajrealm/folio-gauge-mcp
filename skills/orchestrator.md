# Orchestrator / Aggregation Skills

## Overview
The orchestrator aggregates scores from all 10 specialist analysts into a single consensus score. The goal is to balance diverse viewpoints, prevent groupthink, and identify high-conviction setups where most analysts agree.

## Score Aggregation Methods

### Weighted Average
- **Formula**: Portfolio Score = Σ (Analyst Score × Analyst Weight)
- **Weights** (defined in config.py):
  - Technical: 12%
  - Fundamentals: 18%
  - Sentiment: 8%
  - Macro: 15%
  - Peers: 10%
  - Sector: 10%
  - Trends: 7%
  - Industry: 7%
  - Discovery: 8%
  - Portfolio: 8%
- **Total**: Must sum to 100% (validate in tests)
- **Flexibility**: Adjust weights based on macro regime (e.g., increase Macro weight during late-cycle)

### Example Calculation
```
Technical: 0.75 × 12% = 0.090
Fundamentals: 0.60 × 18% = 0.108
Sentiment: 0.55 × 8% = 0.044
Macro: 0.70 × 15% = 0.105
Peers: 0.65 × 10% = 0.065
Sector: 0.80 × 10% = 0.080
Trends: 0.50 × 7% = 0.035
Industry: 0.65 × 7% = 0.046
Discovery: 0.60 × 8% = 0.048
Portfolio: 0.70 × 8% = 0.056

Final Score = 0.677 (68% confidence)
```

## Consensus Analysis

### High Consensus (Good Signal)
- **Setup**: 7+ analysts score 0.65+
- **Interpretation**: Broad agreement across diverse perspectives
- **Confidence**: High. Multiple independent checks all aligned.
- **Example**: Breakout + technical strength + fundamental upgrade + sector rotation + analyst consensus
- **Action**: Strong buy; high position weight justified

### Divided Opinion (Caution)
- **Setup**: 5 analysts 0.70+, but 5 analysts 0.40-
- **Interpretation**: Conflicting signals (e.g., good fundamentals but bad technicals)
- **Confidence**: Lower. Watch which signal proves correct (thesis validation needed).
- **Example**: Undervalued (fundamentals) but in downtrend (technicals)
- **Action**: Reduce position size; build thesis over time, not all-in bet

### Negative Consensus (Avoid)
- **Setup**: 7+ analysts score 0.35-
- **Interpretation**: Broad disagreement with bullish thesis
- **Confidence**: Avoid unless high conviction on specific overlooked angle
- **Example**: Cheap valuation but deteriorating fundamentals, weak technicals, bearish sentiment
- **Action**: Avoid or very small speculative position only

## Identifying Divergence

### Bullish Divergence (Opportunity)
- **Pattern**: Sentiment negative but technicals bullish (breaking out)
  - Interpretation: Underappreciated or under-researched opportunity
  - Setup: Often leads to catch-up rally as sentiment catches technicals
- **Pattern**: Fundamentals improving but valuation cheap
  - Interpretation: Market hasn't priced in improvement
  - Setup: Earnings beat likely; short-term rally
- **Pattern**: Sector momentum positive but individual stock overlooked
  - Interpretation: Stock likely to follow sector rotation (coattail trade)

### Bearish Divergence (Risk)
- **Pattern**: Fundamentals deteriorating but sentiment remains bullish
  - Interpretation: Market ignoring warning signs (FOMO)
  - Risk: Sharp sell-off when reality hits (earnings miss)
- **Pattern**: Technicals breaking down but sector strength persists
  - Interpretation: Stock weakness could spread to sector
  - Risk: Failed relative strength; sector leadership shift
- **Pattern**: Valuation expanding but growth slowing
  - Interpretation: Multiple expansion likely to reverse (P/E contraction)
  - Risk: Valuation reset; drawdown likely

## Macro Regime Adjustments

### Weights by Macro Regime

**Expansion (Growth > 3%, Inflation Contained)**
- Emphasize: Technical (momentum), Growth fundamentals, Sentiment, Trends
- De-emphasize: Macro headwinds, defensive plays

**Late Cycle (Growth 1-2%, Inflation Rising)**
- Emphasize: Quality fundamentals, Macro outlook, Sector rotation
- De-emphasize: Momentum, Sentiment (peak euphoria likely)

**Slowdown (Growth < 1%, Recession Risk)**
- Emphasize: Macro warning, Defensive positioning, Divergence
- De-emphasize: Growth expectations, Momentum (likely to fade)

**Recession (Negative Growth)**
- Emphasize: Portfolio risk management, Sector rotation to defensive
- De-emphasize: Technical momentum (loses relevance), Growth stories (earnings cuts)

## Handling Outlier Analysts

### Outlier Definition
- **If One Analyst** significantly different from consensus (e.g., 0.90 while others 0.55)
- **Reasons**:
  - Analyst focused on one dimension (e.g., Technical Analyst seeing breakout others missed)
  - Analyst has different risk tolerance (Portfolio Analyst more conservative)
  - Analyst has error or unique insight

### Deciding on Outlier

**Weight Outlier if:**
- Analyst has clear rationale (documented in score comment)
- Rationale is contradicted by other information (worth investigating)
- Outlier represents new information (e.g., news break on specific analyst's timeline)

**Dismiss Outlier if:**
- No clear rationale provided
- Outlier contradicts majority on well-established fact (e.g., fundamentals)
- Outlier reflects niche perspective not relevant to general thesis

## Score Thresholds

### Scoring Scale
- **0.75+**: Strong Buy
- **0.65-0.74**: Buy
- **0.45-0.64**: Hold / Neutral
- **0.35-0.44**: Sell / Caution
- **Below 0.35**: Strong Sell / Avoid

### Final Recommendation Logic
```
If score >= 0.75 AND consensus broad:
  → Strong Buy, increase position if not fully invested
If score 0.65-0.74 AND consensus broad:
  → Buy, add to position or initiate if new
If score 0.45-0.64:
  → Hold, rebalance only if drifted
If score 0.35-0.44 AND consensus clear:
  → Reduce position, trim to smaller core
If score < 0.35 OR divergence extreme:
  → Exit or avoid, capital better deployed elsewhere
```

## Position Rebalancing Triggers

### Based on Score Change
- **Score drops > 0.15 points**: Reassess thesis. Reduce position or close.
- **Score improves > 0.15 points**: Add to position if margin of safety exists.
- **Score stable**: Hold, don't overtrade.

### Based on Portfolio Impact
- **Position drifted to > 15% of portfolio**: Trim to target (sell outperformers, buy underperformers)
- **Correlation with portfolio increased**: Reduce to lower portfolio concentration risk
- **New macro regime detected**: Rebalance weights across holdings (e.g., shift from growth to defensive)

## Red Flags for Orchestrator

### Warning Signs
- **No Score < 0.45**: Suggests Portfolio analyst missing risks (too bullish)
- **No Score > 0.65**: Suggests no high-conviction ideas (too bearish or indecisive)
- **Weights Drifted**: If any holding > 20% or sector > 30%, rebalance
- **Portfolio Beta > 1.5**: Portfolio too aggressive for stated risk tolerance
- **Concentration Risk**: If top 5 holdings > 70%, reduce

## Scoring Guidelines

- **Perfect Orchestration**: Balanced analyst perspectives, broad consensus on high-confidence plays, clear divergence identified, macro-aware weighting, portfolio optimized for risk/reward
- **Good Orchestration**: Most analysts aligned, high conviction on majority of picks, reasonable portfolio allocation
- **Poor Orchestration**: Divergent analyst signals, high portfolio concentration, insufficient macro weighting, overtraded positions
- **Dangerous**: No consensus, overconfidence in narrow thesis, concentrated bets, macro headwinds ignored
