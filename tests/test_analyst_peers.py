"""
test_analyst_peers.py
----------------------
Tests src/analysts/peers.py.
Requires POLYGON_API_KEY in .env.
Run from project root:
    uv run python tests/test_analyst_peers.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  peers analyst — {TICKER}")
print(f"{'='*60}\n")

from src.analysts.peers import analyze_peers

score = analyze_peers(TICKER)

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
    "Agent is 'peers'":                 score.agent == "peers",
    "Decision is BUY/HOLD/SELL":        score.decision in ("BUY", "HOLD", "SELL"),
    "Score in range 1-5":               1 <= score.score <= 5,
    "Confidence in range 0-1":          0.0 <= score.confidence <= 1.0,
    "Timeframe is long":                score.timeframe == "long",
    "Reasoning has peer signal":        any(
        kw in score.reasoning.lower()
        for kw in ["peer", "competitor", "relative", "outperform", "underperform", "valuation"]
    ),
}

for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'}  {label}")

if score.data_gaps and "No similar" in str(score.data_gaps):
    print(f"\n  ⚠️   No peer data found — check POLYGON_API_KEY in .env")
print()
