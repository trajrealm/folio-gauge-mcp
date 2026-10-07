"""
test_analyst_sector.py
-----------------------
Smoke-tests src/analysts/sector.py.
Requires OPENAI_API_KEY in .env.
Run from project root:
    uv run python -m tests.test_analyst_sector [TICKER]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from src.analysts.sector import analyze_sector  # noqa: E402

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== sector analyst - {TICKER} ==\n")

score = analyze_sector(TICKER)

print(f"  Decision:   {score.decision}")
print(f"  Score:      {score.score}/5")
print(f"  Confidence: {score.confidence:.0%}")
print(f"  Reasoning:  {score.reasoning}")
print(f"  Data gaps:  {score.data_gaps}")
print()

print("  [PASS] AgentScore valid (validated on construction)")
print(f"  [{'PASS' if not score.data_gaps else 'WARN'}] No data gaps")
print()
