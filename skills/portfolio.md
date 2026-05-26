# Portfolio Management Skills

## Overview
Portfolio management focuses on risk management, position sizing, allocation strategy, and rebalancing. This analyst ensures the portfolio as a whole is optimized for risk/reward, not just individual stock picks.

## Portfolio Risk Metrics

### Portfolio Beta
- **Definition**: Measure of portfolio volatility vs. market
- **Beta = 1.0**: Portfolio moves in lockstep with market
- **Beta > 1.0**: Portfolio more volatile (aggressive)
- **Beta < 1.0**: Portfolio less volatile (defensive)
- **Target Beta**: 0.8-1.2 for balanced portfolio; adjust by risk tolerance

### Portfolio Concentration Risk
- **Top 1 Holding**: Should be < 15-20% of portfolio
  - > 20% = idiosyncratic risk (one stock drives returns)
- **Top 5 Holdings**: Should be < 60% of portfolio
  - > 60% = concentrated; lack diversification
- **Top 10 Holdings**: Should be 60-75% of portfolio (balanced concentration)

### Sector Allocation
- **Overweight Sector**: > 20% of portfolio (vs. 16% market weight in S&P 500)
  - Bullish bet on sector; acceptance of sector concentration risk
- **Underweight Sector**: < market weight
  - Bearish or defensive stance
- **Neutral Sector**: ~= market weight (passive, no tactical bet)

### Geographic Concentration
- **Domestic**: Typical 60-90% for US-based portfolio (US market bias)
- **International**: 10-40% (diversification benefit, currency exposure)
- **Emerging Markets**: 0-10% (growth potential, but higher volatility)

### Asset Class Allocation
- **Equities**: 60-100% (depending on risk tolerance and time horizon)
- **Fixed Income**: 0-40% (stability, income, capital preservation)
- **Cash**: 0-5% (dry powder for opportunities, cushion)
- **Alternatives**: 0-20% (hedge, uncorrelated, diversification)

## Position Sizing

### Equal Weight vs. Risk Weight
- **Equal Weight**: Each stock 1/N of portfolio (e.g., 10 stocks = 10% each)
  - Simple but ignores risk differences
- **Risk Weight**: Size based on volatility and conviction
  - High conviction + low volatility = larger position
  - Lower conviction + high volatility = smaller position

### Kelly Criterion (Advanced)
- **Optimal Position Size**: f* = (p*b - q) / b
  - p = win probability, b = reward/risk ratio, q = loss probability
  - f* = % of capital to allocate
- **Practical Application**: Kelly often too aggressive (can lead to ruin on bad streak)
  - Use fractional Kelly (f*/2 or f*/4) for safety

### Position Sizing Rules
- **New Idea**: Start 2-3% (small pilot; validate thesis)
- **Confirmed Setup**: Scale to 4-6% (thesis validated)
- **High Conviction + Macro Tailwind**: Can go to 8-10% max per stock
- **Max Position**: Never > 15% (avoid idiosyncratic risk)

## Rebalancing

### Buy Low, Sell High
- **Drift**: Over time, winners grow (higher % of portfolio), losers shrink
  - Winners = now more expensive (relative to entry)
  - Losers = now cheaper (relative to entry)
- **Rebalance**: Sell winners, buy losers
  - Forces disciplined "buy low, sell high"
  - Opposite of emotional buying (chase winners, avoid losers)

### Rebalancing Schedule
- **Calendar Rebalancing**: Every 3-6 months or annually
  - Simple, automatic, prevents drift
- **Threshold Rebalancing**: When position drifts >5% from target
  - More dynamic; responds to market moves
- **Tactical Rebalancing**: When macro environment shifts
  - Less frequent; responds to regime change (bull→bear, etc.)

### Rebalancing Mechanics
- **Example**: Portfolio 30% AAPL (target 10%)
  - Sell 67% of AAPL position (move to 10%)
  - Redeploy proceeds to underweights
- **Tax Consideration**: Selling winners = capital gains tax (not ideal in taxable account)
  - In tax-deferred (401k, IRA), rebalance freely
  - In taxable, minimize selling winners; add new capital to losers instead

## Diversification

### Correlation Matters
- **Low Correlation**: Holdings move independently (true diversification)
  - Example: Tech + Utilities often negatively correlated
- **High Correlation**: Holdings move together (false diversification)
  - Example: Apple + Microsoft both tech; move together in tech rotation
- **Target**: Average portfolio correlation < 0.3 (true diversification benefit)

### Diversification Across Dimensions
- **By Sector**: Exposure across all 11 sectors (or tactical misweights)
- **By Strategy**: Blend of value, growth, dividend (different drivers)
- **By Capitalization**: Large-cap + mid-cap + small-cap (different risk/return profiles)
- **By Geography**: Domestic + international (reduces single-country risk)

## Drawdown Management

### Drawdown Definition
- **Peak-to-Trough Decline**: Largest loss from recent high
- **Typical Bull Market Correction**: 5-20% (healthy)
- **Bear Market**: > 20% (sustained decline)
- **Severe Bear**: > 30% (severe bear or crash)

### Drawdown Tolerance
- **Define Max Acceptable Drawdown**: Based on psychology and goals
  - Aggressive (long time horizon): Can tolerate 30-50% drawdowns
  - Conservative (near retirement): Can tolerate 10-20% only
- **Set Stops or Rebalance Triggers**: If portfolio hits max drawdown, rebalance defensively

### Drawdown Recovery Time
- **5% Drawdown**: ~1 month to recover
- **10% Drawdown**: ~2-3 months to recover
- **20% Drawdown**: ~6+ months to recover
- **40% Drawdown**: ~1-3 years to recover
- **Implication**: Large drawdowns require patience; focus on prevention rather than recovery hope

## Tactical Allocation Shifts

### Market Cycle Positioning
- **Early Cycle** (Recession ending, growth accelerating):
  - Overweight: Growth, Tech, Cyclicals
  - Underweight: Defensive, Utilities, Staples
- **Mid Cycle** (Peak growth, rates rising):
  - Overweight: Financials, Energy, Materials
  - Underweight: Long-duration bonds, Growth
- **Late Cycle** (Growth slowing, rates peaking):
  - Overweight: Defensive, Utilities, Healthcare
  - Underweight: Cyclicals, Industrials
- **Recession** (Negative growth, rates falling):
  - Overweight: Treasuries, Staples, Utilities
  - Underweight: Cyclicals, Discretionary

### Macro Risk Management
- **VIX > 25**: Consider hedges (put spreads, reduce leverage, defensive rotation)
- **Yield Curve Inverted**: Recession risk; reduce leverage, build cash, defensive positioning
- **Breadth Deteriorating**: Fewer stocks participating in rally; quality matters; trim concentrated bets

## Scoring Guidelines

- **Portfolio Optimize**: Balanced allocation across sectors, holdings, and risk; rebalanced regularly; no single point of failure
- **Good Portfolio**: Reasonable diversification, acceptable concentration, known risk limits
- **Overconcentrated**: Top 5 holdings > 70%; single sector > 30%; at risk to idiosyncratic event
- **Too Defensive**: Cash + bonds > 60% in bull market; missing upside; dragging returns
- **Too Aggressive**: Leverage > 1.5x; concentration risk; outsized drawdown potential

## Key Portfolio Management Metrics
1. Portfolio Beta vs. market
2. Concentration ratio (top-10 holdings %)
3. Sector allocation vs. market
4. Maximum drawdown and time to recovery
5. Correlation between holdings
6. Portfolio turnover (how often positions change)
