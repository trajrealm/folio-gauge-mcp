"""
test_orchestrator.py
--------------------
Smoke-tests the full per-ticker pipeline (src/agent/graph.py): 8 analysts in
parallel -> aggregate -> evaluate. Requires OPENAI_API_KEY, FRED_API_KEY and
EDGAR_USER_AGENT in .env. Takes about a minute.
Run from project root:
    uv run python -m tests.test_orchestrator [TICKER]
"""

import sys
import time

from dotenv import load_dotenv

load_dotenv()

from src import config  # noqa: E402
from src.agent.graph import analyze_ticker, format_analysis  # noqa: E402

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== orchestrator - {TICKER} ==\n")

start = time.time()
analysis = analyze_ticker(TICKER)
elapsed = time.time() - start
print(format_analysis(analysis))
print(f"\n  Elapsed: {elapsed:.0f}s\n")

c, d = analysis.consensus, analysis.decision
checks = {
    "All 8 analysts scored": {s.agent for s in c.agent_scores} == set(config.AGENT_WEIGHTS),
    "No analyst failed": not any("Analyst failed" in g for g in c.data_gaps),
    "Gated means HOLD": not c.gated or c.decision == "HOLD",
    "Evaluator keeps the consensus decision": d.decision == c.decision,
    "BUY has stop below and target above price": d.decision != "BUY" or d.plan.stop_loss < d.price < d.plan.take_profit,
    "Thesis written": bool(d.thesis),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
