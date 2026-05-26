# Sentiment Analysis Skills

## Overview
Sentiment analysis measures market psychology and collective trader opinions. Uses **LLM-based analysis** of prediction market data and retail sentiment forums. Focus: short to medium-term (days to weeks). Sentiment is momentum fuel but not a standalone thesis.

## Sentiment Sources

### Polymarket (Prediction Markets)
- **What**: Real-money prediction markets on various outcomes (e.g., "Will AAPL hit $150 by EOY?")
- **API**: `/events` endpoint with tag filtering, sortable by volume/date
- **Signal**: Market odds reflect collective trader conviction
- **Reliability**: High (real money at stake), leading indicator
- **Latency**: Real-time, updates as new bets placed

### StockTwits (Retail Sentiment)
- **What**: Community sentiment, message board activity, tagged sentiment (Bullish/Bearish)
- **API**: Streams API for symbol, message sentiment tagging
- **Signal**: High message volume = attention, bullish % = retail bias
- **Reliability**: Medium (retail traders, meme stocks), momentum indicator
- **Latency**: Real-time or minutes behind

### LLM Analysis
- **Process**: Feed Polymarket markets + StockTwits messages to Claude
- **Advantage**: Understands context, nuance, implications (vs. keyword matching)
- **Output**: Score 1-5, decision (BUY/HOLD/SELL), confidence, reasoning

## Sentiment Scoring

### LLM Scoring Guidelines

**Strong Bullish (4.5-5.0)**
- Polymarket: Multiple bullish markets with high volume, long odds on bearish outcomes
- StockTwits: 70%+ bullish sentiment, positive message tone, high engagement
- Combined: Markets pricing in strong upside, retail enthusiasm confirmed

**Bullish (3.5-4.5)**
- Polymarket: More bullish than bearish markets, moderate volume
- StockTwits: 55-70% bullish, constructive tone
- Combined: Positive bias but not euphoric

**Neutral (2.5-3.5)**
- Polymarket: Mixed or balanced markets, low volume
- StockTwits: 45-55% bullish, neutral tone
- Combined: No clear conviction

**Bearish (1.5-2.5)**
- Polymarket: More bearish markets, moderate volume
- StockTwits: 30-45% bullish, critical tone
- Combined: Negative bias but not panic

**Strong Bearish (1.0-1.5)**
- Polymarket: Multiple bearish markets with high volume, long odds on bullish outcomes
- StockTwits: <30% bullish, alarm/capitulation tone
- Combined: Strong bearish consensus

## Signal Interpretation

### High Conviction Signals
- **Polymarket + StockTwits aligned**: Both bullish or both bearish = high confidence
- **Market volume > $100K in 24h**: Strong conviction (real money)
- **Message sentiment extreme**: 70%+ or <30% = either euphoria or panic

### Contrarian Signals
- **Overbullish** (Markets/StockTwits >75% bullish): Risk of pullback
- **Oversold** (Markets/StockTwits <25% bullish): Risk of bounce
- **Divergence** (Markets bullish, StockTwits bearish): Mixed signals, investigate

## Timing Sentiment

### Event-Driven Sentiment
- **Pre-earnings**: Polymarket odds expand, StockTwits volume spikes
- **Post-earnings**: Markets adjust quickly; StockTwits sentiment lags 1-2 hours
- **Catalyst news**: Watch for Polymarket market creation (leading indicator)

### Sentiment Lag
- Polymarket = most responsive (real-time bets)
- StockTwits = lags by hours/days (users commenting)
- LLM analysis = blends both for current consensus

## Combining Sentiment with Other Signals

### High Confidence Setup
- Positive fundamentals + positive sentiment (markets + retail) + technical breakout = strong buy
- Negative fundamentals + negative sentiment (markets + retail) + technical breakdown = strong sell

### Mixed Signals
- Positive sentiment + negative technicals = momentum exhaustion risk
- Negative sentiment + positive technicals = contrarian accumulation
- Research the disconnect

## Data Quality Notes

- **No Polymarket data**: Lower conviction (no prediction market price)
- **No StockTwits data**: Missing retail sentiment (but smart money may still buy quietly)
- **Low volume**: Both markets light; high uncertainty
- **New markets**: Early adoption; signal strength builds over days

## Sentiment Extremes

### Overbullish (Contrarian Caution)
- "Can't-miss opportunity", guarantee language
- Polymarket odds extreme (>80% for bullish)
- All StockTwits positive, no skepticism
- **Risk**: FOMO peak, pullback often follows

### Oversold (Contrarian Opportunity)
- "Stock is finished", bankruptcy language
- Polymarket odds extreme (<20% for bullish)
- Capitulation tone on StockTwits
- **Risk**: Panic selling, bounce often follows

## Caveats

- Sentiment alone does not drive long-term returns (fundamentals do)
- Sentiment is mean-reverting (extremes reverse quickly)
- Use sentiment to confirm other signals, not as standalone thesis
- Contrarian signals (overbullish/oversold) are highest conviction plays
- Polymarket is US-centric (less coverage for international stocks)
- StockTwits skews retail (less institutional visibility)


## Sentiment Sources

### News Sentiment
- **Positive**: "Stock surges", "beats estimates", "announces deal", "upgrades rating"
- **Negative**: "Plunges", "disappoints", "downgrades", "regulatory probe", "CEO departure"
- **Neutral**: Facts without valuation. E.g., "Company reports Q2 results" (needs context).
- **Source Credibility**: Bloomberg, Reuters, WSJ = reliable. Social media = noise.

### Institutional Sentiment
- **Insider Buying**: CEO/board buying stock = confidence in future. Bullish.
- **Insider Selling**: Executives selling = could be portfolio rebalancing OR lack of confidence. Context matters.
- **Fund Flows**: Large inflows into sector ETFs or stock-specific funds = institutional confidence.
- **Short Interest**: High short % = bear thesis. Potential short squeeze if bullish catalyst.

## Sentiment Scoring

### Keyword-Based Analysis
- **Bullish Keywords**: "buy", "beat", "strong", "rally", "upgrade", "outperform", "surge", "momentum", "opportunity"
- **Bearish Keywords**: "sell", "miss", "weak", "crash", "downgrade", "underperform", "plunge", "risk", "concern", "probe"
- **Neutral Keywords**: "report", "announce", "update", "guidance", "earnings"

### Sentiment Strength
- **Strong Positive**: Bullish words + exclamation, enthusiasm, multiple mentions in short time
- **Moderate Positive**: Bullish words but measured tone
- **Weak Positive**: Single mention or isolated positive comment
- **Weak Negative**: Isolated criticism or concern
- **Moderate Negative**: Bearish tone with specifics (e.g., "earnings miss")
- **Strong Negative**: Multiple bearish words, alarm, or fundamental issue (regulatory, financial distress)

### Sentiment Divergence
- **Positive News + Negative Price Move**: Institutional selling despite retail enthusiasm. Watch for continued selling.
- **Negative News + Positive Price Move**: Short covering or accumulation by smart money. Potential continuation.
- **Both Positive**: Synchronized bullish. Look for breakout continuation.
- **Both Negative**: Synchronized bearish. Look for breakdown continuation.

## Sentiment Extremes

### Overbullish Signs (Contrarian Caution)
- "Can't-miss opportunity", "guaranteed winner"
- All comments positive, no skepticism
- FOMO language ("everyone should own this")
- Euphoria = exhaustion often follows

### Overbearish Signs (Contrarian Opportunity)
- "Stock is finished", "bankruptcy incoming"
- No acknowledgment of positive catalysts
- Panic selling language
- Capitulation = recovery often follows

## Timing Sentiment Signals

### News Reaction Curve
- **Day 0 (News Release)**: Immediate 1-3% move. Sentiment-driven.
- **Day 1-2 (Digestion)**: Secondary reaction as traders reassess. Fake-outs common.
- **Day 3+ (Fundamental Repricing)**: If positive/negative thesis holds, trend continues. If fake-out, reversal.

### Sentiment Lag
- News breaks → social media lags 1-4 hours → traders act 2-6 hours later
- Use this lag to assess if move is exhaustion or continuation

## Combining Sentiment with Other Signals

### High Confidence Setup
- Positive fundamentals + positive sentiment + technical breakout = strong buy
- Negative fundamentals + negative sentiment + technical breakdown = strong sell

### Mixed Signals (Lower Confidence)
- Positive fundamentals + negative sentiment = undervaluation opportunity OR legitimate concern. Research.
- Negative fundamentals + positive sentiment = contrarian play OR FOMO trap.

## Scoring Guidelines

- **Strong Bullish**: Positive news from reliable source, positive sentiment, insider buying, multiple bullish catalysts, no red flags
- **Bullish**: Positive news, fair to positive sentiment
- **Neutral**: No clear catalyst, mixed sentiment, background noise
- **Bearish**: Negative news, concerns mentioned
- **Strong Bearish**: Negative catalyst from reliable source, regulatory/financial concern, multiple negatives

## Caveats

- Sentiment alone does not drive long-term returns (fundamentals do).
- Sentiment is mean-reverting (extremes often reverse).
- Use sentiment to confirm other signals, not as standalone thesis.
- Contrarian signals (overbullish/overbearish) are highest conviction plays.
- **Current limitation**: Sentiment data source not integrated. Defaults to neutral position until alternative source is configured.

