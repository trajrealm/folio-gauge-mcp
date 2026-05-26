"""
test_analyst_technical.py
-------------------------
Tests src/analysts/technical.py.
Requires POLYGON_API_KEY in .env.
Run from project root:
    uv run python test_analyst_technical.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  technical analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.technical import analyze_technical

score = analyze_technical(TICKER)

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
    "Agent is 'technical'":             score.agent == "technical",
    "Decision is BUY/HOLD/SELL":        score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5":               1 <= score.score <= 5,
    "Confidence in range 0-1":          0.0 <= score.confidence <= 1.0,
    "Timeframe is short":               score.timeframe == "short",
    "Reasoning has technical signal":   any(
        kw in score.reasoning.lower()
        for kw in ["sma", "rsi", "macd", "cross", "trend", "momentum", "above", "below"]
    ),
    "Not all data gaps":                len(score.data_gaps) < 5,
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

if len(score.data_gaps) >= 5:
    print(f"\n  ⚠️   Many data gaps — check POLYGON_API_KEY in .env")
print()