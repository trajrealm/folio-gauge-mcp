# Earnings Analyst Skill

## Purpose
Analyze earnings growth, surprises, guidance, and forward outlook using SEC filings (10-K, 10-Q) to determine the company's earnings quality and trajectory.

## Data Sources
- SEC EDGAR filings (10-K, 10-Q, 8-K)
- RAG vector database with filing text chunks
- OpenAI LLM for synthesis of retrieved content
- Earnings surprise history from filings

## Analysis Approach

### 1. Earnings Growth Trajectory
**Question:** Is the company growing earnings, stagnating, or declining?

**Indicators to Extract:**
- **EPS (Earnings Per Share)** year-over-year growth rate
  - Last 3-5 years historical trend
  - Acceleration or deceleration
  
**Interpretation:**
- **>15% annual EPS growth** → Strong growth, BUY signal
- **5-15% growth** → Solid growth, HOLD/BUY
- **0-5% growth** → Flat/slow growth, neutral
- **Negative growth** → Declining, SELL signal

### 2. Earnings Surprises
**Question:** Does the company beat or miss analyst estimates?

**History Analysis:**
- **Consistent beats** (80%+) → Strong execution, high quality
- **Mixed (50-50)** → Unpredictable guidance
- **Consistent misses** → Credibility problem, weak management

**Scoring:**
- Beat history: +1 to score
- Miss history: -1 to score

### 3. Forward Guidance & Tone
**Question:** What is management saying about future earnings?

**Signals from 10-Q/8-K:**
- **Raised full-year guidance** → Bullish (management confident)
- **Maintained guidance** → Neutral
- **Lowered guidance** → Bearish (company struggling)
- **Withdrew guidance** → Bearish (high uncertainty)

**Management Tone:**
- **Optimistic language** ("strong momentum," "well-positioned") → +1
- **Neutral language** (factual reporting) → 0
- **Cautious language** ("headwinds," "uncertainty") → -1

### 4. Earnings Quality
**Question:** Are earnings sustainable or inflated?

**Red Flags (Quality Issues):**
- One-time gains or charges (acquisitions, asset sales, restructuring)
- Large non-GAAP adjustments (removing "bad" items to look better)
- Accounting changes or restatements
- Declining cash flow while earnings stable (earnings quality concern)

**Green Flags (High Quality):**
- Consistent operating performance
- Cash earnings aligned with reported earnings
- Growing dividends (proof of sustainable earnings)
- No major accounting changes

### 5. Forward Estimates vs History
**Question:** Are analyst expectations realistic given company's history?

**Approach:**
- Extract: "What are the key assumptions driving [quarter] guidance?"
- Compare to: "What actually happened in prior quarters?"
- If guidance assumptions are more optimistic than history → Risk flag

## Score Calculation (1-5)

**Raw Score from 5 Factors:**
```
growth_score = earnings_growth_rate / 15% (capped at 1.0) * 5
surprise_score = beat_ratio * 5 (0-5 based on beat history)
guidance_score = guidance_signal + 3 (ranges -1 to +1, normalized to 1-5 scale)
quality_score = red_flags_count * (-1) + green_flags_count * (+1) + 3
forward_score = estimate_realism_assessment (1-5)

final_score = average([growth_score, surprise_score, guidance_score, quality_score, forward_score])
```

**Final Score Interpretation:**
- **5** → Excellent earnings (strong growth, beat history, raised guidance, high quality, realistic forecasts)
- **4** → Good earnings (solid growth, consistent execution)
- **3** → Fair earnings (moderate growth or mixed signals)
- **2** → Weak earnings (slowing growth, miss history, lowered guidance)
- **1** → Poor earnings (declining, missed guidance, quality concerns)

## Decision Logic

| Earnings Signal | Decision | Timeframe |
|-----------------|----------|-----------|
| Strong growth + beat history + raised guidance | BUY | Mid (3-12 months) |
| Consistent misses + lowered guidance | SELL | Mid |
| Flat growth + stable guidance | HOLD | Mid |
| Declining EPS + negative outlook | SELL | Mid |

## Timeframe
**Mid-term (3-12 months)** — Earnings shifts are reflected in stock valuations over quarters, not days.

## Confidence Scoring

- **High (0.75+)** → Multiple consistent signals (beats, growth, quality high), recent 10-Q data
- **Medium (0.5-0.75)** → Mixed signals or older data (10-K only)
- **Low (<0.5)** → Conflicting signals, extreme uncertainty, no recent filings

## Error Handling

### Missing Data Scenarios:

**No 10-Q/10-K available:**
- Return HOLD score=2 with confidence=0.1
- Flag: "No recent SEC filings found"

**Filings available but no earnings data extracted:**
- Return HOLD score=2 with confidence=0.2
- Flag: "Filing content retrieved but no earnings metrics extracted"

**Multiple signals present but unclear:**
- Return HOLD score=3 with confidence=0.5
- Flag: "Mixed earnings signals, unable to determine direction"

### LLM Failure:
- If OpenAI synthesis fails, return HOLD score=3 with confidence=0.2
- Flag: "LLM analysis failed, fallback to neutral"

## Integration Notes
- This analyst feeds into Orchestrator weighted average
- Weight: 10% (important for fundamental investors)
- Aligns strongly with Fundamentals Analyst (both long-term value)
- Contrarian with short-term traders (Technical Analyst may push BUY on momentum despite weak earnings)
- Red flag if diverges from Peers Analyst (peers growing faster = relative underperformance)

## Key Limitations
- SEC filings are backward-looking (history, not future)
- Management guidance can be overly conservative or optimistic
- Non-GAAP adjustments hide true earnings quality
- One quarter doesn't make a trend
- Earnings per share can grow even if total earnings flat (share buybacks)
