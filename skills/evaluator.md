# Evaluator / Decision Framework Skills

## Overview
The evaluator makes the final buy/hold/sell decision based on the aggregated score from the orchestrator. It also tracks decision quality over time and updates confidence based on outcomes.

## Decision Framework

### Score-to-Action Mapping

**0.75+ (Strong Buy)**
- **Action**: Initiate or increase position to target size (5-10% of portfolio)
- **Entry**: Market order (urgency justified by high conviction)
- **Stop Loss**: 8-12% below entry (tight stop for high P/E or momentum play)
- **Take Profit**: 20-30% gain or at resistance level
- **Rebalance Trigger**: If position grows > 15% due to gains, trim excess

**0.65-0.74 (Buy)**
- **Action**: Initiate or add to position (3-5% of portfolio)
- **Entry**: Limit order on dip (patience justified by moderate conviction)
- **Stop Loss**: 12-15% below entry (wider stop for lower conviction)
- **Take Profit**: 15-20% gain or at sector resistance
- **Rebalance Trigger**: If position grows > 12% due to gains, consider trimming half

**0.45-0.64 (Hold)**
- **Action**: Hold existing positions; don't add or trim
- **Entry**: N/A (only for new ideas with higher conviction)
- **Thesis**: Wait for clarity (score rise or fall to trigger action)
- **Timing**: Revisit in 1-4 weeks; new information likely to clarify thesis
- **Risk**: Opportunity cost (capital doing nothing); consider selling if better ideas emerge

**0.35-0.44 (Sell / Caution)**
- **Action**: Reduce position to 50-75% of current size
- **Exit**: Scale out gradually (over 1-2 weeks) or on rallies
- **Rebalance**: Redeploy proceeds to higher-conviction ideas
- **Stop Loss**: N/A (actively exiting, not holding)
- **Watch**: If score drops < 0.35, exit remaining position

**Below 0.35 (Strong Sell / Avoid)**
- **Action**: Exit remaining position or avoid if not held
- **Exit**: Market order (don't wait for better price; lost conviction)
- **Reason**: Thesis broken or major new risk identified
- **Rebalance**: Redeploy capital to positive-conviction ideas
- **Follow-Up**: Document what changed (technical break, earnings miss, macro shift)

## Risk Management Rules

### Position Sizing Based on Conviction
- **Score 0.75+**: 8-10% per position (highest conviction)
- **Score 0.65-0.74**: 4-6% per position
- **Score 0.45-0.64**: 2-3% per position (mostly from holdings or speculative)
- **Score < 0.45**: 0-1% or close position (minimal exposure)

### Stop Loss Implementation
- **Technical Stop**: Below recent swing low (tightest stop; trend break = clear signal)
- **Percentage Stop**: Fixed % below entry (e.g., 10% for high-conviction, 15% for medium)
- **Time Stop**: Exit if no progress after 4-6 weeks (thesis too slow to play out)
- **Adaptive Stop**: Tighten as winners run (lock in gains); widen as price near support

### Take Profit Targets
- **Conservative**: 10-15% gain
- **Moderate**: 15-25% gain (realistic for 3-6 month holding period)
- **Aggressive**: 25-50% gain (for high momentum or multiple expansion plays)
- **No Limit**: For multi-year conviction holds (buy-and-hold dividend stocks, growth compounders)

## Decision Confidence Scoring

### Confidence Definition
- **High Confidence (90%+)**: Multiple signals aligned, no red flags, clear catalyst
- **Medium Confidence (70-89%)**: Most signals positive, minor concerns, execution risk
- **Low Confidence (50-69%)**: Mixed signals, meaningful execution risk, thesis unproven
- **Very Low Confidence (< 50%)**: Thesis speculative, many unknowns, avoid unless conviction high

### Example Confidence Factors
- **Increases Confidence**:
  - Broad analyst consensus (7+ of 10 positive)
  - Multiple independent catalysts
  - Clear entry point (technical break, fundamental inflection)
  - Macro tailwind (sector rotation, economic cycle support)
- **Decreases Confidence**:
  - Significant analyst divergence
  - No clear catalyst (hoping for reversion)
  - Entry fuzzy (already run up, mid-range technicals)
  - Macro headwind (recession risk, sector decay)

## Outcome Tracking

### Trade Log Discipline
1. **Entry Date, Price, Shares, Reason**
   - Example: "2024-01-15, AAPL $180, 100 shares, breakout + earnings beat expected"
2. **Exit Date, Price, Reason**
   - Example: "2024-02-20, AAPL $210, +16.7%, thesis played out, trim winners"
3. **Score History** (what was score at entry vs. exit)
   - Help calibrate confidence thresholds
4. **Outcome**: Win, Loss, Scratch
   - Track win rate by entry score level

### Win Rate Analysis
- **Score 0.75+**: Target 65-75% win rate
  - < 60% win rate = confidence threshold too low (lower to 0.70)
  - > 75% win rate = confidence threshold too high (raise to 0.80)
- **Score 0.65-0.74**: Target 55-65% win rate
- **Score 0.45-0.64**: Target 45-55% win rate

### Learning from Losses
- **Stop Loss Hit**: Thesis broken (market disagreed with analysis)
  - Lesson: Entry signal weak OR macro shifted
- **Slow Bleed (10-20% loss)**: Thesis delayed, not broken
  - Lesson: Patience needed; or entry too early
- **Sharp Reversal**: Thesis fundamentally wrong
  - Lesson: Research incomplete; red flag missed
- **Opportunity Cost**: Position unchanged while market rallied elsewhere
  - Lesson: Score too conservative; consider raising thresholds

## Scenario Analysis

### What If Analysis
- **If Score Drops 0.10**: Still hold? Reduce? Exit?
  - Triggers: Earnings miss, technical break, sentiment shift
- **If Score Rises 0.10**: Add position?
  - Triggers: Analyst upgrade, positive news, technical breakout
- **If Macro Regime Shifts**: Rebalance immediately?
  - Example: Recession signal (yield curve inversion) → defensive rotation

### Stress Test Portfolio
- **Market Down 10%**: Which holdings fall > 15% (excess beta)?
- **Market Down 20%**: Do shorts/hedges offset losses? (Portfolio hedging needed?)
- **Sector Rotation**: If tech underperforms 10%, portfolio impact?
  - If > 5% portfolio loss: Too concentrated; reduce tech exposure

## Fraud & Accounting Red Flags

### Preventing Blowups
- **Aggressive Accounting**: Revenue recognition, capitalized expenses (quality red flag)
- **Off-Balance-Sheet Entities**: Debt hidden; Enron-style risk
- **Management Turnover**: Multiple CFO/Auditor changes; warning sign
- **Insider Selling Spike**: Managers exiting; loss of confidence
- **Warrant/Dilution News**: New shares issued; existing holders diluted
- **Accounting Restatements**: Prior earnings "restated"; trust eroded

### Due Diligence Checklist
- [ ] Read recent 10-Q and 10-K (look for red flags in MD&A)
- [ ] Check insider transactions (OpenInsider)
- [ ] Verify no litigation or SEC enforcement
- [ ] Confirm revenue sources (% from top 3 customers)
- [ ] Review debt covenants (any near breach?)
- [ ] Check analyst sentiment (any downgrades recently?)

## Scoring Guidelines

### Evaluator Quality
- **Excellent Evaluator**: 60%+ win rate, captures 80%+ of major moves, limits downside to 8-10%, position sizes reflect conviction
- **Good Evaluator**: 55%+ win rate, reasonable captures, controlled downside
- **Poor Evaluator**: < 50% win rate, misses major moves, frequent 15%+ drawdowns, poor position sizing
- **Dangerous**: Emotional decisions (chase winners, hold losers), no stops, leveraged bets, position sizing unrelated to conviction

### Evaluation Process Quality
- **Rigorous**: Written decision criteria, documented thesis, trade log maintained, outcomes reviewed
- **Disciplined**: Follows score thresholds consistently, doesn't deviate on emotion
- **Adaptive**: Updates confidence levels based on win rate, learns from failures
- **Risk Managed**: Stops in place, position sizes appropriate, portfolio hedged if needed

## Decision Quality Metrics

### Track Over Time
1. **Average Win Size** (% gain on winners)
2. **Average Loss Size** (% loss on losers)
3. **Win:Loss Ratio** (# wins / # losses)
4. **Profit Factor** (Gross Wins / Gross Losses)
   - > 1.5 = good; > 2.0 = excellent
5. **Sharpe Ratio** (Return / Risk) — optimize for risk-adjusted returns
6. **Max Drawdown** (largest peak-to-trough loss)
7. **Recovery Time** (how long to recover from max drawdown)

### Continuous Improvement
- **Monthly Review**: What worked? What didn't?
- **Threshold Calibration**: Adjust score cutoffs based on win rate history
- **Hypothesis Testing**: Try new analyst weights; A/B test decision rules
- **Risk Appetite**: Adjust position sizing based on drawdown tolerance and recent volatility
