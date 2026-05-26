"""
test_analyst_sentiment.py
--------------------------
Tests src/analysts/sentiment.py.
Requires OPENAI_API_KEY, POLYGON_API_KEY, STOCKTWITS_API_KEY in .env.
Run from project root:
    uv run python tests/test_analyst_sentiment.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  sentiment analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.sentiment import analyze_sentiment

score = analyze_sentiment(TICKER)

print(f"  Agent:      {score.agent}")
print(f"  Decision:   {score.decision}")
print(f"  Score:      {score.score}/5")
print(f"  Confidence: {score.confidence:.0%}")
print(f"  Reasoning:  {score.reasoning}")
print(f"  Timeframe:  {score.timeframe}")
if score.data_gaps:
    print(f"  Data gaps:  {score.data_gaps}")

print()

# Validations
checks = {
    "Agent is 'sentiment'":             score.agent == "sentiment",
    "Decision is BUY/HOLD/SELL":        score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5":               1 <= score.score <= 5,
    "Confidence in range 0-1":          0.0 <= score.confidence <= 1.0,
    "Timeframe is short":               score.timeframe == "short",
    "Reasoning has sentiment signal":   any(
        kw in score.reasoning.lower()
        for kw in ["bullish", "bearish", "sentiment", "polymarket", "stocktwits", "probability", "positive", "negative"]
    ),
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

if score.data_gaps and len(score.data_gaps) > 3:
    print(f"\n  ⚠️   {len(score.data_gaps)} data gaps — check API keys in .env")
print()
