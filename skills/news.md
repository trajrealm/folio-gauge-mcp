# News Analyst Skill

## Purpose
Analyze sentiment and tone from recent news articles about a stock ticker to determine bullish, bearish, or neutral outlook.

## Data Sources
- RSS feeds (Yahoo, Reuters)
- NewsAPI (latest articles)
- Article headlines and summaries

## Analysis Approach

### 1. Sentiment Classification
For each article headline + summary, classify as:
- **Bullish** — positive developments (earnings beat, new products, partnerships, upgrades, record profits)
- **Bearish** — negative developments (earnings miss, layoffs, fraud, downgrades, recalls, competition)
- **Neutral** — factual reporting without clear sentiment direction

### 2. Signal Weighting
- **Recent articles (< 7 days)** → Higher weight
- **Older articles (7-30 days)** → Lower weight
- **Very old articles (> 30 days)** → Ignore

### 3. Consensus Calculation
```
bullish_ratio = bullish_count / total_articles
bearish_ratio = bearish_count / total_articles
neutral_ratio = neutral_count / total_articles
```

### 4. Decision Logic

**BUY Signal Criteria:**
- Bullish ratio > 60%
- More than 5 recent bullish articles
- Positive trend (bullish articles increasing over time)

**SELL Signal Criteria:**
- Bearish ratio > 60%
- More than 5 recent bearish articles
- Negative trend (bearish articles increasing over time)

**HOLD Signal Criteria:**
- Bullish and bearish roughly balanced (45-55%)
- Mixed or inconsistent sentiment
- Insufficient article volume

### 5. Score Calculation (1-5)

- **5** → Strong bullish (70%+ bullish, >10 articles)
- **4** → Mild bullish (60-70% bullish)
- **3** → Neutral (45-55% balanced)
- **2** → Mild bearish (30-40% bullish)
- **1** → Strong bearish (< 30% bullish)

### 6. Timeframe
**Short-term (7 days)** — News impact is most immediate for trading decisions.

## Confidence Scoring

- **High confidence (0.8+)** → Clear sentiment (>60% one direction) with >10 articles
- **Medium confidence (0.6-0.8)** → Moderate consensus with 5-10 articles
- **Low confidence (<0.6)** → Mixed signals or <5 articles

## Error Handling

If no articles found:
- Return HOLD score=2 with confidence=0.2
- Flag data gap: "No recent articles found"

If news sentiment conflicts with other signals:
- Document as data gap: "News diverges from [other analyst]"
- Confidence reduced by 0.1-0.2

## Key Limitations
- Headlines can be misleading or sensationalized
- Sentiment keywords may not capture nuance
- Earnings date news creates temporary spikes
- Need to account for known announcements (earnings, conference calls)

## Integration Notes
- This analyst feeds into Orchestrator weighted average
- Weight: 10% (moderate importance)
- Often confirms or contradicts Sentiment Analyst findings
- Useful for short-term swing trading signals
