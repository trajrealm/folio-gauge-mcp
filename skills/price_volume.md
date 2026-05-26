# Price & Volume Analyst Skill

## Purpose
Analyze price positioning, momentum, trading volume, and liquidity to generate short-term trading signals.

## Data Sources
- yfinance (OHLCV data, dividends, historical prices)
- 52-week highs/lows
- Average volume
- Previous close prices

## Analysis Approach

### 1. Price Range Positioning (52-Week Context)
**Question:** Where is the stock in its annual trading range?

**Calculation:**
```
position = (current_price - 52w_low) / (52w_high - 52w_low)
position ranges from 0.0 (at low) to 1.0 (at high)
```

**Interpretation:**
- **0.8-1.0 (Upper range)** → Near highs, momentum signal, potential overbought
- **0.5-0.8** → Upper half, bullish
- **0.3-0.5** → Mid-range, neutral
- **0.0-0.3** → Lower range, value opportunity or weakness
- **Upside to 52w high** → Also factor in remaining upside potential

### 2. Intraday Momentum (Price vs Previous Close)
**Question:** Is today's price action bullish or bearish?

**Calculation:**
```
day_change_pct = (current_price - previous_close) / previous_close * 100
```

**Interpretation:**
- **+2% or higher** → Strong bullish momentum
- **+0% to +2%** → Mild bullish
- **-0% to -2%** → Mild bearish
- **< -2%** → Strong bearish momentum

### 3. Volume Analysis (Liquidity & Activity)
**Question:** Is there enough trading activity? Are institutions interested?

**Metrics:**
- **Average volume** — Overall trading liquidity
- **Volume spikes** — Unusual activity (requires volume field from market data)

**Thresholds:**
- **>5M average volume** → Excellent liquidity, easy entry/exit
- **>1M average volume** → Good liquidity
- **>100K average volume** → Moderate, acceptable for most traders
- **<100K average volume** → Low liquidity, wide spreads

**Interpretation:**
- High volume + bullish momentum = Institutional buy signal
- High volume + bearish price = Institutional sell pressure
- Low volume on any signal = Less reliable

### 4. Dividend Yield (Income Attractiveness)
**Question:** Does the stock provide income?

**Calculation:**
```
yield = annual_dividend / current_price
```

**Interpretation:**
- **>4%** → High yield, attractive for income investors
- **2-4%** → Moderate yield, balanced approach
- **<2%** → Low yield, growth-focused stock
- **0%** → No dividend (typical for growth/tech stocks)

**Scoring:**
- High yield is a BUY signal for income seekers
- Growth stocks with 0% dividend can still be bullish
- Dividend cuts = red flag, bearish signal

### 5. Intraday Volatility (Daily Range)
**Question:** How volatile is the stock within each day?

**Calculation:**
```
intraday_range_pct = (day_high - day_low) / day_low * 100
```

**Interpretation:**
- **>3%** → High intraday volatility, risky/exciting for day traders
- **1-3%** → Moderate volatility, normal trading range
- **<1%** → Stable/quiet trading, boring but safe

## Score Aggregation (1-5)

Combine signals from all 5 categories and weight by reliability:

```
signals = [52w_position_score, momentum_score, volume_score, dividend_score, volatility_score]
final_score = round(average(signals))
```

**Final Score Interpretation:**
- **5** → Strong buy (high position, bullish momentum, good volume, positive signals)
- **4** → Mild buy (multiple bullish signals)
- **3** → Hold (mixed signals or neutral)
- **2** → Mild sell (multiple bearish signals)
- **1** → Strong sell (weak position, bearish momentum, poor volume)

## Decision Logic

| Signals | Decision | Confidence |
|---------|----------|-----------|
| Bullish on 3+ factors | BUY | 0.6+ |
| Bearish on 3+ factors | SELL | 0.6+ |
| Mixed (2-2 split) | HOLD | 0.5 |
| Neutral (all mid-range) | HOLD | 0.5 |

## Timeframe
**Short-term (1-7 days)** — Price action and volume are immediate indicators.

## Confidence Scoring

- **High (0.7+)** → Multiple confirmatory signals (price + volume + momentum aligned)
- **Medium (0.5-0.7)** → Some signals aligned, others neutral
- **Low (<0.5)** → Conflicting signals or insufficient data

## Error Handling

**Missing Data:**
- If 52-week data unavailable: Use available range, flag gap
- If volume data missing: Assume moderate, flag gap
- If previous close missing: Use open price as proxy

**Low Confidence Scenarios:**
- Reduce confidence if volume is very low (<100K)
- Reduce confidence if price is at extreme (far outlier from historical)
- Reduce confidence if stock has been flat for weeks (low volatility signals nothing)

## Integration Notes
- This analyst feeds into Orchestrator weighted average
- Weight: 12% (important for short-term traders)
- Often aligns with Technical Analyst (RSI, momentum)
- Contrarian with Fundamentals (a cheap stock with poor momentum is still risky near-term)
- Useful for entry/exit timing and position sizing
