"""
test_analyst_price_volume.py
-----------------------------
Tests src/analysts/price_volume.py.
Run from project root:
    uv run python tests/test_analyst_price_volume.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  price_volume analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.price_volume import analyze_price_volume

score = analyze_price_volume(TICKER)

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
    "Agent is 'price_volume'":          score.agent == "price_volume",
    "Decision is BUY/HOLD/SELL":        score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5":               1 <= score.score <= 5,
    "Confidence in range 0-1":          0.0 <= score.confidence <= 1.0,
    "Timeframe is short":               score.timeframe == "short",
    "Reasoning has price/vol signal":   any(
        kw in score.reasoning.lower()
        for kw in ["52-week", "momentum", "volume", "dividend", "price", "range", "high", "low"]
    ),
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

print()
