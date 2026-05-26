"""
test_analyst_earnings.py
------------------------
Tests src/analysts/earnings.py.
Requires OPENAI_API_KEY, ANTHROPIC_API_KEY in .env for SEC filing ingestion.
Run from project root:
    uv run python tests/test_analyst_earnings.py
"""

from dotenv import load_dotenv

load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  earnings analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.earnings import analyze_earnings

score = analyze_earnings(TICKER)

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
    "Agent is 'earnings'": score.agent == "earnings",
    "Decision is BUY/HOLD/SELL": score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5": 1 <= score.score <= 5,
    "Confidence in range 0-1": 0.0 <= score.confidence <= 1.0,
    "Timeframe is mid": score.timeframe == "mid",
    "Reasoning has earnings signal": any(
        kw in score.reasoning.lower()
        for kw in [
            "earnings",
            "eps",
            "growth",
            "surprise",
            "guidance",
            "quality",
            "beat",
            "miss",
        ]
    ),
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

if score.data_gaps and any(
    "filing" in gap.lower() or "ingestion" in gap.lower() for gap in score.data_gaps
):
    print(f"\n  ⚠️   Filing ingestion issue — check API keys or EDGAR availability")
print()
