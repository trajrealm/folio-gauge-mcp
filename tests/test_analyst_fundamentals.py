"""
test_analyst_fundamentals.py
----------------------------
Tests src/analysts/fundamentals.py.
Run from project root:
    uv run python test_analyst_fundamentals.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  fundamentals analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.fundamentals import analyze_fundamentals

score = analyze_fundamentals(TICKER)

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
    "Agent is 'fundamentals'":          score.agent == "fundamentals",
    "Decision is BUY/HOLD/SELL":        score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5":               1 <= score.score <= 5,
    "Confidence in range 0-1":          0.0 <= score.confidence <= 1.0,
    "Timeframe is long":                score.timeframe == "long",
    "Reasoning is not placeholder":     "pending" not in score.reasoning.lower(),
    "Not integrated msg gone":          "not yet integrated" not in str(score.data_gaps).lower(),
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

if score.data_gaps and len(score.data_gaps) > 3:
    print(f"\n  ⚠️   {len(score.data_gaps)} data gaps — yfinance returned sparse data")
print()