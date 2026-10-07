"""
test_discovery.py
-----------------
Smoke-tests src/discovery.py. Requires OPENAI_API_KEY in .env for the review.
Without --analyze, candidates are reviewed without per-ticker analysis (fast).
With --analyze, the top 2 candidates run the full per-ticker analysis first (slow).
Run from project root:
    uv run python -m tests.test_discovery [--analyze]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from src.discovery import find_candidates, review_candidates  # noqa: E402
from src.agent.graph import analyze_ticker  # noqa: E402

print("\n== discovery ==\n")

discovery = find_candidates()
for c in discovery.candidates:
    print(
        f"  {c.symbol:<6} sources={','.join(c.sources):<17} rank={c.apewisdom_rank} "
        f"mentions={c.mentions} growth={c.mention_growth} watchlist={c.stocktwits_watchlist}"
    )
print(f"  Data gaps: {discovery.data_gaps or 'none'}\n")

results = {}
if "--analyze" in sys.argv:
    results = {c.symbol: analyze_ticker(c.symbol).consensus for c in discovery.candidates[:2]}

review = review_candidates(discovery, results)
print(f"  Summary: {review.summary}")
for v in review.candidates:
    print(f"    {v.symbol:<6} {v.action:<17} {v.reason}")
print()

checks = {
    "Candidates found": bool(discovery.candidates),
    "Review covers every candidate": {v.symbol for v in review.candidates} == {c.symbol for c in discovery.candidates},
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
