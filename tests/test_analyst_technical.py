"""
test_analyst_technical.py
--------------------------
Smoke-tests src/analysts/technical.py.
Requires OPENAI_API_KEY in .env.
Run from project root:
    uv run python -m tests.test_analyst_technical [TICKER]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from src.analysts.technical import analyze_technical  # noqa: E402

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== technical analyst - {TICKER} ==\n")

score = analyze_technical(TICKER)

print(f"  Decision:   {score.decision}")
print(f"  Score:      {score.score}/5")
print(f"  Confidence: {score.confidence:.0%}")
print(f"  Reasoning:  {score.reasoning}")
print(f"  Data gaps:  {score.data_gaps}")
print()

for error in score.validate():
    print(f"  [FAIL] {error}")
print(f"  [{'PASS' if not score.validate() else 'FAIL'}] AgentScore valid")
print(f"  [{'PASS' if not score.data_gaps else 'WARN'}] No data gaps")
print()
